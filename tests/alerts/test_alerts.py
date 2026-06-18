import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from pdi.alerts import (
    AlertConfigError,
    dispatch_notifications,
    generate_banking_digest,
    load_alert_config,
    render_digest_json,
    render_digest_markdown,
    validate_alert_config,
)
from pdi.storage import (
    initialize_database,
    insert_banking_deal,
    insert_deal_change_event,
    insert_status_event,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "banking_alerts.yaml"
AS_OF = date(2026, 6, 18)
GENERATED_AT = datetime(2026, 6, 18, 9, 30, tzinfo=timezone.utc)


def seed_deal(db_path, **overrides):
    values = {
        "canonical_key": overrides.pop("canonical_key", "fixture-checking"),
        "title": overrides.pop("title", "Fixture Bank $300 Checking Bonus"),
        "institution_name": overrides.pop("institution_name", "Fixture Bank"),
        "subcategory": overrides.pop("subcategory", "checking_bonus"),
        "bonus_amount_cents": overrides.pop("bonus_amount_cents", 30000),
        "source_url": overrides.pop("source_url", "https://example.test/fixture"),
        "source_name": overrides.pop("source_name", "Fixture Source"),
        "discovered_at": overrides.pop(
            "discovered_at",
            "2026-06-17T12:00:00+00:00",
        ),
        "last_seen_at": overrides.pop(
            "last_seen_at",
            "2026-06-17T12:00:00+00:00",
        ),
        "expires_at": overrides.pop("expires_at", "2026-12-31"),
        "application_deadline": overrides.pop("application_deadline", None),
        "status": overrides.pop("status", "new"),
        "confidence_score": overrides.pop("confidence_score", 0.9),
        "terms": overrides.pop(
            "terms",
            {
                "direct_deposit_required": True,
                "direct_deposit_minimum_cents": 100000,
                "minimum_deposit_amount_cents": None,
                "minimum_balance_required_cents": None,
                "balance_hold_days": 90,
                "monthly_fee_cents": 0,
                "new_customer_only": True,
                "state_restrictions": [],
            },
        ),
    }
    values.update(overrides)
    return insert_banking_deal(db_path, values)


def test_repository_alert_config_validates():
    config = load_alert_config(CONFIG_PATH)

    assert config.minimum_score == 75
    assert config.notification_channels["email"]["enabled"] is False


def test_invalid_alert_config_fails_closed():
    with pytest.raises(AlertConfigError) as error:
        validate_alert_config(
            {
                "minimum_score": 101,
                "minimum_estimated_net_value_cents": 10000,
            }
        )

    assert "missing required field" in str(error.value)


def test_high_score_deal_appears_in_review_now(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path)

    digest = generate_banking_digest(
        db_path,
        config_path=CONFIG_PATH,
        as_of=AS_OF,
        generated_at=GENERATED_AT,
    )

    assert [item.deal_id for item in digest.sections["Review Now"]] == [deal_id]
    assert "Score" in digest.sections["Review Now"][0].reason


def test_low_score_deal_is_suppressed_from_high_priority_sections(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(
        db_path,
        canonical_key="low-value",
        title="Low Value Savings Bonus",
        subcategory="savings_bonus",
        bonus_amount_cents=1000,
        expires_at="2026-12-31",
        terms={
            "direct_deposit_required": False,
            "minimum_balance_required_cents": 1000000,
            "balance_hold_days": 365,
            "monthly_fee_cents": 0,
            "new_customer_only": False,
            "state_restrictions": [],
        },
    )

    digest = generate_banking_digest(db_path, config_path=CONFIG_PATH, as_of=AS_OF)

    assert deal_id not in [item.deal_id for item in digest.sections["Review Now"]]
    assert deal_id not in [
        item.deal_id for item in digest.sections["Needs More Information"]
    ]


def test_expiring_deal_appears_in_digest(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(
        db_path,
        canonical_key="expiring",
        expires_at="2026-06-25",
    )

    digest = generate_banking_digest(db_path, config_path=CONFIG_PATH, as_of=AS_OF)

    assert [item.deal_id for item in digest.sections["Expiring Soon"]] == [deal_id]
    assert digest.sections["Expiring Soon"][0].reason == "Expires in 7 days."


def test_watched_deal_with_material_change_appears(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    deal_id = seed_deal(db_path, canonical_key="watched", status="watching")
    insert_deal_change_event(
        db_path,
        deal_id,
        "canonical_field_changed",
        {"expires_at": {"old_value": "2026-12-31", "selected_value": "2027-01-31"}},
    )

    digest = generate_banking_digest(db_path, config_path=CONFIG_PATH, as_of=AS_OF)

    assert [item.deal_id for item in digest.sections["Changed Deals"]] == [deal_id]
    assert [item.deal_id for item in digest.sections["Watchlist Updates"]] == [deal_id]


def test_conflict_and_missing_data_deals_appear_in_review_needed(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    conflict_id = seed_deal(db_path, canonical_key="conflict", status="needs_review")
    missing_id = seed_deal(
        db_path,
        canonical_key="missing",
        title="Missing Direct Deposit Checking Bonus",
        terms={
            "direct_deposit_required": None,
            "monthly_fee_cents": 0,
            "terms_json": {"missing_fields": ["direct_deposit_required"]},
        },
    )
    insert_deal_change_event(
        db_path,
        conflict_id,
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

    digest = generate_banking_digest(db_path, config_path=CONFIG_PATH, as_of=AS_OF)

    assert {item.deal_id for item in digest.sections["Needs More Information"]} == {
        conflict_id,
        missing_id,
    }


def test_digest_rendering_is_deterministic_for_fixed_data(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path)

    first = generate_banking_digest(
        db_path,
        config_path=CONFIG_PATH,
        as_of=AS_OF,
        generated_at=GENERATED_AT,
    )
    second = generate_banking_digest(
        db_path,
        config_path=CONFIG_PATH,
        as_of=AS_OF,
        generated_at=GENERATED_AT,
    )

    assert render_digest_markdown(first) == render_digest_markdown(second)
    assert json.loads(render_digest_json(first)) == json.loads(render_digest_json(second))


def test_dry_run_notification_does_not_send_external_messages(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    seed_deal(db_path)
    config = validate_alert_config(
        {
            "minimum_score": 75,
            "minimum_estimated_net_value_cents": 25000,
            "expiration_warning_days": [3, 7, 14],
            "eligible_statuses": [
                "new",
                "needs_review",
                "watching",
                "interested",
                "in_progress",
            ],
            "enabled_subcategories": [
                "checking_bonus",
                "savings_bonus",
                "checking_savings_bundle",
                "brokerage_bonus",
                "money_market_bonus",
                "cd_bonus",
            ],
            "minimum_hours_between_digests": 12,
            "default_outputs": {
                "markdown_path": "data/digests/banking_digest.md",
                "json_path": "data/digests/banking_digest.json",
            },
            "notification_channels": {"email": {"enabled": True}},
        }
    )
    digest = generate_banking_digest(db_path, config=config, as_of=AS_OF)

    results = dispatch_notifications(digest, config, dry_run=True)

    assert results[0].channel == "email"
    assert results[0].sent is False
    assert results[0].dry_run is True


def test_expired_and_skipped_deals_are_summary_only_by_default(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    expired_id = seed_deal(
        db_path,
        canonical_key="expired",
        status="expired",
        expires_at="2026-06-01",
    )
    skipped_id = seed_deal(db_path, canonical_key="skipped", status="skipped")
    insert_status_event(db_path, expired_id, "expired")

    digest = generate_banking_digest(db_path, config_path=CONFIG_PATH, as_of=AS_OF)
    section_ids = {
        item.deal_id
        for items in digest.sections.values()
        for item in items
    }

    assert digest.expired_count == 1
    assert digest.skipped_count == 1
    assert expired_id not in section_ids
    assert skipped_id not in section_ids
