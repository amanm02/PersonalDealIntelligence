from pathlib import Path

import pytest

from pdi.sources import (
    SourcePolicyError,
    load_source_policies,
    validate_source_config,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config" / "banking_sources.yaml"
DEMO_CONFIG_PATH = REPO_ROOT / "config" / "banking_sources.demo.yaml"


def base_source(**overrides):
    source = {
        "source_id": "test-rss-source",
        "source_group": "core",
        "publisher_name": "Test Publisher",
        "name": "Test RSS Source",
        "url": "https://example.test/rss.xml",
        "source_type": "rss_feed",
        "source_class": "third_party",
        "category_scope": ["banking"],
        "subcategory_scope": ["checking_bonus", "savings_bonus"],
        "coverage_purpose": "Source policy validation test.",
        "trust_tier": "community",
        "official_source": False,
        "deposit_account_source": True,
        "brokerage_source": False,
        "credit_card_source": False,
        "fixture_enabled": False,
        "source_priority": 50,
        "region_scope": ["US"],
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

    assert len(policies) == 13
    assert {policy.source_type for policy in policies} == {
        "manual_url",
        "official_promo_page",
        "rss_feed",
        "newsletter_email",
        "disabled",
    }
    assert any(policy.credit_card_source for policy in policies)
    assert any(policy.brokerage_source for policy in policies)
    assert any(policy.deposit_account_source for policy in policies)
    assert any(policy.official_source for policy in policies)
    public_pilot = [
        policy for policy in policies if policy.source_group == "public-pilot"
    ]
    assert len(public_pilot) == 1
    assert public_pilot[0].enabled is False
    assert public_pilot[0].allow_rss is True


def test_demo_source_config_validates():
    policies = load_source_policies(DEMO_CONFIG_PATH)

    assert len(policies) == 9
    assert {policy.source_type for policy in policies} == {
        "official_promo_page",
        "deal_blog",
        "newsletter_email",
        "manual_url",
        "disabled",
    }
    assert all(policy.requires_login is False for policy in policies)
    assert all(policy.allow_scrape is False for policy in policies)
    assert all(policy.source_group == "demo" for policy in policies)


def test_unsafe_demo_source_variant_fails_validation():
    source = base_source(
        name="Unsafe Demo Scrape",
        url="https://unsafe-demo.example.test/private",
        source_type="official_promo_page",
        collection_method="scrape",
        max_frequency_hours=12,
        requires_login=True,
        allow_scrape=True,
        allow_rss=False,
    )

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    message = str(error.value)
    assert "logged-in source scraping is not allowed" in message
    assert "scrape method requires max_frequency_hours >= 24" in message


def test_valid_source_config_returns_typed_policy():
    policies = validate_source_config(config_for(base_source()))

    assert len(policies) == 1
    assert policies[0].name == "Test RSS Source"
    assert policies[0].publisher_name == "Test Publisher"
    assert policies[0].source_class == "third_party"
    assert policies[0].trust_tier == "community"
    assert policies[0].subcategory_scope == ("checking_bonus", "savings_bonus")
    assert policies[0].region_scope == ("US",)


def test_missing_required_field_fails_validation():
    source = base_source()
    del source["source_id"]

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "missing required field: source_id" in str(error.value)


def test_missing_collection_method_fails_validation():
    source = base_source()
    del source["collection_method"]

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "missing required field: collection_method" in str(error.value)


def test_invalid_source_group_fails_validation():
    source = base_source(source_group="managed-source-universe")

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "unsupported source_group: managed-source-universe" in str(error.value)


def test_invalid_trust_tier_fails_validation():
    source = base_source(trust_tier="unreviewed")

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "unsupported trust_tier: unreviewed" in str(error.value)


def test_official_source_flag_requires_official_source_class():
    source = base_source(official_source=True)

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "official_source true requires source_class official" in str(error.value)


def test_subcategory_requires_matching_product_source_flag():
    source = base_source(deposit_account_source=False)

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "deposit subcategories require deposit_account_source true" in str(
        error.value
    )


def test_credit_card_source_metadata_validates():
    policies = validate_source_config(
        config_for(
            base_source(
                source_id="test-credit-card-source",
                source_type="official_promo_page",
                source_class="official",
                subcategory_scope=["credit_card_signup_bonus"],
                trust_tier="official",
                official_source=True,
                deposit_account_source=False,
                credit_card_source=True,
            )
        )
    )

    assert policies[0].credit_card_source is True
    assert policies[0].official_source is True


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


def test_public_pilot_requires_login_fails_closed():
    source = base_source(
        source_group="public-pilot",
        requires_login=True,
    )

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "public-pilot sources cannot require login" in str(error.value)


def test_public_pilot_enabled_non_rss_method_fails_validation():
    source = base_source(
        source_group="public-pilot",
        source_type="manual_url",
        collection_method="manual_only",
        allow_rss=False,
    )

    with pytest.raises(SourcePolicyError) as error:
        validate_source_config(config_for(source))

    assert "public-pilot live collection is limited to rss_feed" in str(error.value)


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
