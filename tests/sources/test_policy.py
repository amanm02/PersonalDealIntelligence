from pathlib import Path

import pytest

from pdi.sources import (
    SourcePolicyError,
    load_source_policies,
    validate_source_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "banking_sources.yaml"


def base_source(**overrides):
    source = {
        "name": "Test RSS Source",
        "url": "https://example.test/rss.xml",
        "source_type": "rss_feed",
        "category_scope": ["banking"],
        "subcategory_scope": ["checking_bonus", "savings_bonus"],
        "enabled": True,
        "collection_method": "rss_feed",
        "max_frequency_hours": 24,
        "requires_login": False,
        "allow_scrape": False,
        "allow_api": False,
        "allow_rss": True,
        "allow_email_parse": False,
        "robots_policy_notes": "RSS only; no scraping.",
        "terms_policy_notes": "Approved test policy.",
        "rate_limit_notes": "No more than daily.",
        "compliance_status": "approved",
        "last_reviewed_at": "2026-06-17",
        "notes": "Offline test source.",
    }
    source.update(overrides)
    return source


def config_for(source):
    return {"sources": [source]}


def test_repository_source_config_validates():
    policies = load_source_policies(CONFIG_PATH)

    assert len(policies) == 4
    assert {policy.source_type for policy in policies} == {
        "manual_url",
        "rss_feed",
        "newsletter_email",
        "disabled",
    }


def test_valid_source_config_returns_typed_policy():
    policies = validate_source_config(config_for(base_source()))

    assert len(policies) == 1
    assert policies[0].name == "Test RSS Source"
    assert policies[0].subcategory_scope == ("checking_bonus", "savings_bonus")


def test_missing_required_field_fails_validation():
    source = base_source()
    del source["collection_method"]

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "missing required field: collection_method" in str(error.value)


def test_unknown_field_fails_validation():
    source = base_source(extra_policy="not allowed")

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "unknown field: extra_policy" in str(error.value)


def test_unsafe_field_fails_validation():
    source = base_source(captcha_bypass=True)

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "unsafe field is not allowed: captcha_bypass" in str(error.value)


def test_enabled_source_requires_approved_compliance_status():
    source = base_source(compliance_status="pending_review")

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "enabled sources must have compliance_status approved" in str(error.value)


def test_logged_in_scraping_fails_closed():
    source = base_source(
        source_type="official_promo_page",
        collection_method="scrape",
        max_frequency_hours=24,
        requires_login=True,
        allow_scrape=True,
        allow_rss=False,
    )

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "logged-in source scraping is not allowed" in str(error.value)


def test_high_frequency_scraping_fails_validation():
    source = base_source(
        source_type="official_promo_page",
        collection_method="scrape",
        max_frequency_hours=12,
        allow_scrape=True,
        allow_rss=False,
    )

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "scrape method requires max_frequency_hours >= 24" in str(error.value)


def test_scraping_without_explicit_allowance_fails_validation():
    source = base_source(
        source_type="official_promo_page",
        collection_method="scrape",
        max_frequency_hours=24,
        allow_scrape=False,
        allow_rss=False,
    )

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "scrape method requires allow_scrape true" in str(error.value)


def test_enabled_rss_requires_matching_allow_flag():
    source = base_source(allow_rss=False)

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "enabled RSS sources require allow_rss true" in str(error.value)


def test_zero_frequency_only_allowed_for_disabled_unscheduled_sources():
    source = base_source(max_frequency_hours=0)

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "max_frequency_hours 0 is only allowed" in str(error.value)


def test_non_banking_scope_fails_validation():
    source = base_source(category_scope=["travel"])

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "unsupported category_scope entry: travel" in str(error.value)
