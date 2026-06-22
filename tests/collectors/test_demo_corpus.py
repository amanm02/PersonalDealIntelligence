from pathlib import Path

from pdi.demo_corpus import collect_demo_snapshots, load_demo_fixtures


REPO_ROOT = Path(__file__).resolve().parents[2]
DEMO_DIR = REPO_ROOT / "examples" / "demo_banking"
DEMO_CONFIG = REPO_ROOT / "config" / "banking_sources.demo.yaml"


def test_demo_manifest_covers_required_source_shapes_and_edge_cases():
    fixtures = load_demo_fixtures(DEMO_DIR)

    source_shapes = {fixture.source_shape for fixture in fixtures}
    deal_types = {
        deal_type
        for fixture in fixtures
        for deal_type in ([fixture.deal_type] if fixture.deal_type else fixture.deal_types)
    }
    edge_cases = {edge for fixture in fixtures for edge in fixture.edge_cases}
    scenario_ids = {scenario for fixture in fixtures for scenario in fixture.scenario_ids}

    assert {
        "official_bank_promo_page",
        "deal_blog_rss_item",
        "newsletter_email_export",
        "manual_user_text",
        "disabled_source_record",
    }.issubset(source_shapes)
    assert {
        "checking_bonus",
        "savings_bonus",
        "checking_savings_bundle",
        "brokerage_bonus",
        "cd_bonus",
        "low_value_offer",
        "expired_offer",
        "ambiguous_offer",
        "non_deal",
        "disabled_source",
    }.issubset(deal_types)
    assert {
        "duplicate_offer",
        "conflicting_terms",
        "missing_high_impact_terms",
        "disabled_or_disallowed_source",
        "non_deal_content",
    }.issubset(edge_cases)
    assert {
        "active_checking",
        "active_savings",
        "checking_savings_bundle",
        "brokerage_bonus",
        "cd_or_money_market",
        "expired_offer",
        "duplicate_offer",
        "conflicting_terms",
        "low_value_offer",
        "ambiguous_terms",
        "disabled_or_disallowed_source",
        "non_deal_content",
    }.issubset(scenario_ids)
    assert all(fixture.scenario_ids for fixture in fixtures)


def test_demo_fixtures_collect_offline_with_synthetic_source_urls():
    snapshots = collect_demo_snapshots(
        demo_dir=DEMO_DIR,
        source_config=DEMO_CONFIG,
        retrieved_at="2026-06-18T12:00:00+00:00",
    )

    assert len(snapshots) == 11
    assert {item.snapshot.collector_name for item in snapshots} == {
        "manual_text",
        "newsletter_email",
        "rss",
    }
    for item in snapshots:
        source_url = item.snapshot.source_url or ""
        policy_url = item.policy.url
        assert (
            source_url.startswith("manual://")
            or source_url.startswith("email-export://")
            or ".example.test" in source_url
        )
        assert (
            policy_url.startswith("manual://")
            or policy_url.startswith("email-export://")
            or ".example.test" in policy_url
        )
        if item.snapshot.collector_name == "rss":
            assert item.snapshot.raw_payload["feed_format"] == "rss"
        else:
            assert "fixture" in item.snapshot.raw_payload.get("input_method", "")
        assert item.fixture.scenario_ids


def test_demo_disabled_fixture_is_present_but_not_collected():
    fixtures = load_demo_fixtures(DEMO_DIR)
    disabled = [fixture for fixture in fixtures if not fixture.collect]
    snapshots = collect_demo_snapshots(demo_dir=DEMO_DIR, source_config=DEMO_CONFIG)

    assert [fixture.fixture_id for fixture in disabled] == ["disabled_private_placeholder"]
    assert all(item.policy.source_type != "disabled" for item in snapshots)
