import json
from datetime import date
from pathlib import Path

import pytest

from pdi.scoring import (
    ScoringConfigError,
    load_scoring_config,
    persist_banking_deal_score,
    score_banking_deal,
    scoring_config_hash,
    validate_scoring_config,
)
from pdi.storage import (
    get_banking_deal,
    get_latest_banking_score_record,
    initialize_database,
    insert_banking_deal,
    insert_deal_change_event,
    list_banking_score_records,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "banking_scoring.yaml"
AS_OF = date(2026, 6, 18)


def deal(db_path, **overrides):
    values = {
        "canonical_key": "fixture-checking",
        "title": "Fixture Bank $300 Checking Bonus",
        "institution_name": "Fixture Bank",
        "subcategory": "checking_bonus",
        "bonus_amount_cents": 30000,
        "source_url": "manual://fixture",
        "source_name": "Fixture Source",
        "discovered_at": "2026-06-17T12:00:00+00:00",
        "last_seen_at": "2026-06-17T12:00:00+00:00",
        "expires_at": "2026-12-31",
        "status": "new",
        "confidence_score": 0.9,
        "terms": {
            "direct_deposit_required": True,
            "direct_deposit_minimum_cents": 100000,
            "minimum_deposit_amount_cents": None,
            "minimum_balance_required_cents": None,
            "balance_hold_days": None,
            "monthly_fee_cents": 0,
            "new_customer_only": True,
            "state_restrictions": [],
        },
    }
    values.update(overrides)
    return insert_banking_deal(db_path, values)


def test_repository_scoring_config_validates():
    config = load_scoring_config(CONFIG_PATH)

    assert config.annual_opportunity_cost_rate == 0.045
    assert config.score_thresholds["high"] == 75


def test_invalid_config_fails_validation():
    with pytest.raises(ScoringConfigError) as error:
        validate_scoring_config(
            {
                "annual_opportunity_cost_rate": 1.2,
                "default_hold_period_days": 90,
            }
        )

    assert "missing required field" in str(error.value)


def test_high_value_checking_bonus_scores_high(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(db_path)

    score = score_banking_deal(db_path, deal_id, config_path=CONFIG_PATH, as_of=AS_OF)

    assert score.gross_bonus_value == 30000
    assert score.estimated_net_value == 25500
    assert score.score_band == "high"
    assert score.recommended_action == "review_now"
    assert score.score_0_to_100 >= 75


def test_savings_bonus_with_large_cash_lockup_scores_lower(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    checking_id = deal(db_path, canonical_key="fixture-checking-high")
    savings_id = deal(
        db_path,
        canonical_key="fixture-savings",
        title="Fixture Bank $500 Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=50000,
        terms={
            "direct_deposit_required": False,
            "minimum_balance_required_cents": 1500000,
            "balance_hold_days": 180,
            "monthly_fee_cents": 0,
            "new_customer_only": True,
            "state_restrictions": [],
        },
    )

    checking_score = score_banking_deal(
        db_path,
        checking_id,
        config_path=CONFIG_PATH,
        as_of=AS_OF,
    )
    savings_score = score_banking_deal(
        db_path,
        savings_id,
        config_path=CONFIG_PATH,
        as_of=AS_OF,
    )

    assert savings_score.estimated_cash_lockup_cost > 30000
    assert savings_score.estimated_net_value > 0
    assert savings_score.score_0_to_100 < checking_score.score_0_to_100
    assert savings_score.recommended_action == "skip_low_value"


def test_missing_direct_deposit_terms_receive_warning(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(
        db_path,
        terms={
            "direct_deposit_required": None,
            "monthly_fee_cents": 0,
            "terms_json": {"missing_fields": ["direct_deposit_required"]},
        },
    )

    score = score_banking_deal(db_path, deal_id, config_path=CONFIG_PATH, as_of=AS_OF)

    assert "direct_deposit_required missing" in score.missing_data_warnings
    assert score.recommended_action == "needs_more_info"


def test_monthly_fees_reduce_net_value(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    no_fee_id = deal(db_path, canonical_key="fixture-no-fee")
    fee_id = deal(
        db_path,
        canonical_key="fixture-with-fee",
        terms={
            "direct_deposit_required": True,
            "monthly_fee_cents": 1200,
            "new_customer_only": True,
            "state_restrictions": [],
        },
    )

    no_fee_score = score_banking_deal(
        db_path,
        no_fee_id,
        config_path=CONFIG_PATH,
        as_of=AS_OF,
    )
    fee_score = score_banking_deal(db_path, fee_id, config_path=CONFIG_PATH, as_of=AS_OF)

    assert fee_score.estimated_fee_cost == 3600
    assert fee_score.estimated_net_value == no_fee_score.estimated_net_value - 3600


def test_expired_deal_returns_expired(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(db_path, expires_at="2026-06-01")

    score = score_banking_deal(db_path, deal_id, config_path=CONFIG_PATH, as_of=AS_OF)

    assert score.recommended_action == "expired"
    assert score.score_0_to_100 == 0
    assert score.score_band == "expired"


def test_conflicting_canonical_deal_returns_conflict_needs_review(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(db_path, status="needs_review")
    insert_deal_change_event(
        db_path,
        deal_id,
        "canonical_field_changed",
        {
            "direct_deposit_required": {
                "old_value": True,
                "candidate_value": False,
                "selected_value": False,
                "reason": "candidate_higher_confidence",
            }
        },
    )

    score = score_banking_deal(db_path, deal_id, config_path=CONFIG_PATH, as_of=AS_OF)

    assert score.recommended_action == "conflict_needs_review"


def test_scoring_config_changes_affect_score_predictably(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(db_path)
    config = load_scoring_config(CONFIG_PATH)
    higher_friction = validate_scoring_config(
        {
            **config.__dict__,
            "hassle_penalties_cents": {
                **config.hassle_penalties_cents,
                "direct_deposit_required": 10000,
            },
        }
    )

    base = score_banking_deal(db_path, deal_id, config=config, as_of=AS_OF)
    adjusted = score_banking_deal(db_path, deal_id, config=higher_friction, as_of=AS_OF)

    assert adjusted.estimated_hassle_penalty > base.estimated_hassle_penalty
    assert adjusted.score_0_to_100 < base.score_0_to_100


def test_scoring_config_hash_is_stable_and_changes_with_config():
    config = load_scoring_config(CONFIG_PATH)
    equivalent = validate_scoring_config(config.__dict__)
    adjusted = validate_scoring_config(
        {
            **config.__dict__,
            "hassle_penalties_cents": {
                **config.hassle_penalties_cents,
                "direct_deposit_required": 10000,
            },
        }
    )

    assert scoring_config_hash(config) == scoring_config_hash(equivalent)
    assert len(scoring_config_hash(config)) == 64
    assert scoring_config_hash(config) != scoring_config_hash(adjusted)


def test_persist_score_updates_existing_net_value_and_creates_record(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(db_path)
    config = load_scoring_config(CONFIG_PATH)

    score = persist_banking_deal_score(
        db_path,
        deal_id,
        config=config,
        as_of=AS_OF,
    )
    record = get_latest_banking_score_record(db_path, deal_id)

    assert get_banking_deal(db_path, deal_id)["estimated_net_value_cents"] == (
        score.estimated_net_value
    )
    assert record["deal_id"] == deal_id
    assert record["scoring_version"] == "banking-scoring-v1"
    assert record["scoring_config_hash"] == scoring_config_hash(config)
    assert record["scored_as_of"] == AS_OF.isoformat()
    assert record["estimated_net_value_cents"] == score.estimated_net_value
    assert record["score_0_to_100"] == score.score_0_to_100
    assert record["score_band"] == score.score_band
    assert record["recommended_action"] == score.recommended_action
    assert record["score_explanation"] == score.score_explanation
    assert record["expiration_urgency"] == score.expiration_urgency
    assert json.loads(record["score_components_json"]) == {
        "gross_bonus_value": score.gross_bonus_value,
        "estimated_fee_cost": score.estimated_fee_cost,
        "estimated_cash_lockup_cost": score.estimated_cash_lockup_cost,
        "estimated_hassle_penalty": score.estimated_hassle_penalty,
        "estimated_risk_penalty": score.estimated_risk_penalty,
    }
    assert json.loads(record["missing_data_warnings_json"]) == (
        score.missing_data_warnings
    )


def test_repeated_persist_score_creates_history(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = deal(db_path)
    config = load_scoring_config(CONFIG_PATH)
    higher_friction = validate_scoring_config(
        {
            **config.__dict__,
            "hassle_penalties_cents": {
                **config.hassle_penalties_cents,
                "direct_deposit_required": 10000,
            },
        }
    )

    first = persist_banking_deal_score(
        db_path,
        deal_id,
        config=config,
        as_of=AS_OF,
    )
    second = persist_banking_deal_score(
        db_path,
        deal_id,
        config=higher_friction,
        as_of=AS_OF,
    )

    records = list_banking_score_records(db_path, deal_id=deal_id)
    latest = get_latest_banking_score_record(db_path, deal_id)

    assert len(records) == 2
    assert records[0]["id"] == latest["id"]
    assert records[0]["estimated_net_value_cents"] == second.estimated_net_value
    assert records[1]["estimated_net_value_cents"] == first.estimated_net_value
    assert records[0]["scored_as_of"] == AS_OF.isoformat()
    assert records[1]["scored_as_of"] == AS_OF.isoformat()
    assert records[0]["scoring_config_hash"] == scoring_config_hash(higher_friction)
    assert records[1]["scoring_config_hash"] == scoring_config_hash(config)
    assert get_banking_deal(db_path, deal_id)["estimated_net_value_cents"] == (
        second.estimated_net_value
    )
