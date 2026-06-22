from datetime import date
from pathlib import Path

import pytest

from pdi.scoring import (
    ScoringConfigError,
    load_scoring_config,
    score_banking_deal,
    validate_scoring_config,
)
from pdi.storage import initialize_database, insert_banking_deal


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "banking_scoring.yaml"
AS_OF = date(2026, 6, 21)


def card_deal(db_path, **overrides):
    credit_card = {
        "issuer_name": "Beacon Mock Bank",
        "card_name": "Beacon Cash Forward Card",
        "customer_type": "personal",
        "offer_currency": "cash",
        "headline_bonus_amount": 300,
        "headline_bonus_value_cents": 30000,
        "minimum_spend_cents": 150000,
        "spend_window_days": 90,
        "annual_fee_cents": 0,
        "first_year_annual_fee_waived": False,
        "statement_credit_amount_cents": None,
        "targeted": False,
        "eligibility_restriction_notes": [],
    }
    credit_card.update(overrides.pop("credit_card", {}))
    values = {
        "canonical_key": "credit-card:beacon:cash-forward:300:2026-12-15",
        "title": "Beacon Cash Forward Card $300 Cash Bonus",
        "institution_name": "Beacon Mock Bank",
        "subcategory": "credit_card_signup_bonus",
        "bonus_amount_cents": 30000,
        "source_url": "https://example.test/beacon/cash-forward",
        "source_name": "Fixture Card Source",
        "discovered_at": "2026-06-21T12:00:00+00:00",
        "last_seen_at": "2026-06-21T12:00:00+00:00",
        "expires_at": "2026-12-15",
        "status": "new",
        "confidence_score": 0.9,
        "terms": {"terms_json": {"credit_card": credit_card}},
    }
    values.update(overrides)
    return insert_banking_deal(db_path, values)


def score_card(tmp_path, **overrides):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = card_deal(db_path, **overrides)
    return score_banking_deal(db_path, deal_id, config_path=CONFIG_PATH, as_of=AS_OF)


def test_cash_credit_card_scores_component_value(tmp_path):
    score = score_card(tmp_path)

    assert score.gross_headline_value == 300
    assert score.estimated_cash_equivalent_value == 30000
    assert score.estimated_annual_fee_cost == 0
    assert score.estimated_minimum_spend_friction_penalty == 2500
    assert score.estimated_spend_window_pressure_penalty == 1500
    assert score.estimated_net_value == 23000
    assert score.score_band == "high"
    assert "card_cash_face_value_v1" in score.reward_valuation_assumption_ids


def test_points_credit_card_uses_configured_assumption_id(tmp_path):
    score = score_card(
        tmp_path,
        title="Harbor Rewards Plus Card 60,000 Point Offer",
        bonus_amount_cents=None,
        credit_card={
            "card_name": "Harbor Rewards Plus Card",
            "offer_currency": "points",
            "headline_bonus_amount": 60000,
            "headline_bonus_value_cents": None,
            "minimum_spend_cents": 400000,
            "annual_fee_cents": 9500,
        },
    )

    assert score.estimated_cash_equivalent_value == 60000
    assert score.estimated_annual_fee_cost == 9500
    assert "card_points_one_cent_v1" in score.reward_valuation_assumption_ids
    assert "card_points_one_cent_v1" in score.score_explanation


def test_miles_credit_card_uses_configured_assumption_id(tmp_path):
    score = score_card(
        tmp_path,
        title="Prairie Voyager Card 50,000 Mile Offer",
        bonus_amount_cents=None,
        credit_card={
            "card_name": "Prairie Voyager Card",
            "offer_currency": "miles",
            "headline_bonus_amount": 50000,
            "headline_bonus_value_cents": None,
            "minimum_spend_cents": 300000,
            "annual_fee_cents": 9900,
        },
    )

    assert score.estimated_cash_equivalent_value == 50000
    assert score.estimated_annual_fee_cost == 9900
    assert score.reward_valuation_assumption_ids == ["card_miles_one_cent_v1"]


def test_statement_credit_offer_scores_as_cash_equivalent(tmp_path):
    score = score_card(
        tmp_path,
        title="Riverbend Grocery Statement Credit Card $150 Statement Credit",
        bonus_amount_cents=15000,
        credit_card={
            "card_name": "Riverbend Grocery Statement Credit Card",
            "offer_currency": "statement_credit",
            "headline_bonus_amount": 150,
            "headline_bonus_value_cents": 15000,
            "statement_credit_amount_cents": 15000,
            "minimum_spend_cents": 75000,
            "spend_window_days": 60,
        },
    )

    assert score.estimated_cash_equivalent_value == 15000
    assert "card_statement_credit_face_value_v1" in (
        score.reward_valuation_assumption_ids
    )


def test_mixed_offer_scores_points_and_statement_credit(tmp_path):
    score = score_card(
        tmp_path,
        title="Cypress Travel Blend Card Mixed Points and Statement Credit Offer",
        bonus_amount_cents=None,
        credit_card={
            "card_name": "Cypress Travel Blend Card",
            "offer_currency": "mixed",
            "headline_bonus_amount": {
                "points": 20000,
                "statement_credit_cents": 10000,
            },
            "headline_bonus_value_cents": None,
            "statement_credit_amount_cents": 10000,
            "minimum_spend_cents": 250000,
            "spend_window_days": 120,
            "annual_fee_cents": 8900,
            "first_year_annual_fee_waived": True,
        },
    )

    assert score.estimated_cash_equivalent_value == 30000
    assert score.estimated_annual_fee_cost == 0
    assert score.estimated_spend_window_pressure_penalty == 750
    assert score.reward_valuation_assumption_ids == [
        "card_statement_credit_face_value_v1",
        "card_points_one_cent_v1",
    ]


def test_first_year_annual_fee_waiver_reduces_cost(tmp_path):
    no_waiver = score_card(
        tmp_path,
        canonical_key="credit-card:no-waiver",
        credit_card={"annual_fee_cents": 9500, "first_year_annual_fee_waived": False},
    )
    waived = score_card(
        tmp_path,
        canonical_key="credit-card:waived",
        credit_card={"annual_fee_cents": 9500, "first_year_annual_fee_waived": True},
    )

    assert no_waiver.estimated_annual_fee_cost == 9500
    assert waived.estimated_annual_fee_cost == 0
    assert waived.estimated_net_value == no_waiver.estimated_net_value + 9500


def test_missing_credit_card_spend_terms_warn_and_penalize(tmp_path):
    score = score_card(
        tmp_path,
        credit_card={
            "minimum_spend_cents": None,
            "spend_window_days": None,
        },
    )

    assert "minimum_spend_cents missing" in score.missing_data_warnings
    assert "spend_window_days missing" in score.missing_data_warnings
    assert score.estimated_missing_data_penalty == 5000
    assert score.estimated_spend_window_pressure_penalty == 2500
    assert score.estimated_risk_penalty == 6500
    assert "unclear-terms penalty $15.00" in score.score_explanation
    assert score.recommended_action == "needs_more_info"


def test_targeted_credit_card_offer_receives_restriction_penalty(tmp_path):
    public = score_card(tmp_path, canonical_key="credit-card:public")
    targeted = score_card(
        tmp_path,
        canonical_key="credit-card:targeted",
        credit_card={
            "targeted": True,
            "eligibility_restriction_notes": ["Invitation code required."],
        },
    )

    assert targeted.estimated_targeting_restriction_penalty == 6500
    assert targeted.estimated_net_value == public.estimated_net_value - 6500


def test_low_confidence_credit_card_receives_source_adjustment(tmp_path):
    score = score_card(tmp_path, confidence_score=0.0)

    assert score.estimated_source_confidence_adjustment == 2000
    assert score.estimated_risk_penalty == 2000
    assert "source-confidence adjustment $20.00" in score.score_explanation


def test_expired_credit_card_offer_returns_expired(tmp_path):
    score = score_card(tmp_path, expires_at="2026-06-01")

    assert score.recommended_action == "expired"
    assert score.score_0_to_100 == 0
    assert score.score_band == "expired"


def test_invalid_credit_card_scoring_config_fails_validation():
    config = load_scoring_config(CONFIG_PATH)

    with pytest.raises(ScoringConfigError) as error:
        validate_scoring_config(
            {
                **config.__dict__,
                "credit_card_reward_assumption_ids": {
                    "cash": "card_cash_face_value_v1",
                    "statement_credit": "card_statement_credit_face_value_v1",
                    "points": "card_points_one_cent_v1",
                },
            }
        )

    assert "credit_card_reward_assumption_ids missing required key: miles" in str(
        error.value
    )
