import sqlite3
from datetime import date, datetime, timezone

import pytest

from pdi.collectors import (
    ApiCollector,
    CollectionBlockedError,
    ManualTextCollector,
    ManualUrlCollector,
    NewsletterEmailCollector,
    RssCollector,
    persist_collected_snapshot,
)
from pdi.sources import SourcePolicy
from pdi.storage import initialize_database
from pdi.storage import get_raw_snapshot


def policy(**overrides):
    values = {
        "source_id": "test-manual-source",
        "source_group": "demo",
        "publisher_name": "Test Publisher",
        "name": "Test Manual Source",
        "url": "manual://test-source",
        "source_type": "manual_url",
        "source_class": "manual_import",
        "category_scope": ("banking",),
        "subcategory_scope": ("checking_bonus",),
        "coverage_purpose": "Offline collector test source.",
        "trust_tier": "user_provided",
        "official_source": False,
        "deposit_account_source": True,
        "brokerage_source": False,
        "credit_card_source": False,
        "fixture_enabled": True,
        "source_priority": 30,
        "region_scope": ("US",),
        "enabled": True,
        "collection_method": "manual_only",
        "max_frequency_hours": 24,
        "requires_login": False,
        "allow_scrape": False,
        "allow_api": False,
        "allow_rss": False,
        "allow_email_parse": False,
        "robots_policy_notes": "No network access.",
        "terms_policy_notes": "Offline fixture only.",
        "rate_limit_notes": "Manual only.",
        "compliance_status": "approved",
        "last_reviewed_at": date(2026, 6, 17),
        "notes": "Test policy.",
    }
    values.update(overrides)
    return SourcePolicy(**values)


def test_manual_text_collection_succeeds_and_hash_is_stable():
    source_policy = policy()
    collector = ManualTextCollector()

    first = collector.collect(
        source_policy,
        raw_text="Mock Bank offers a fictional $300 checking bonus.",
        retrieved_at="2026-06-17T12:00:00+00:00",
    )
    second = collector.collect(
        source_policy,
        raw_text="Mock Bank offers a fictional $300 checking bonus.",
        retrieved_at="2026-06-17T12:05:00+00:00",
    )

    assert first.source_name == "Test Manual Source"
    assert first.collector_name == "manual_text"
    assert first.content_hash == second.content_hash
    assert len(first.content_hash) == 64


def test_rss_fixture_parsing_succeeds():
    source_policy = policy(
        name="Test RSS Source",
        url="https://example.test/banking.xml",
        source_type="rss_feed",
        collection_method="rss_feed",
        allow_rss=True,
    )
    rss_text = """<?xml version="1.0"?>
    <rss version="2.0">
      <channel>
        <title>Banking Deals</title>
        <item>
          <title>Mock Bank $300 Checking Bonus</title>
          <link>https://example.test/mock-checking</link>
          <description>Open a fictional checking account for a bonus.</description>
          <pubDate>Wed, 17 Jun 2026 12:00:00 GMT</pubDate>
        </item>
        <item>
          <title>Mock Savings Bonus</title>
          <link>https://example.test/mock-savings</link>
          <description>Deposit fictional funds for a bonus.</description>
        </item>
      </channel>
    </rss>
    """

    snapshots = RssCollector().collect(
        source_policy,
        raw_text=rss_text,
        retrieved_at="2026-06-17T12:00:00+00:00",
    )

    assert len(snapshots) == 2
    assert snapshots[0].source_url == "https://example.test/mock-checking"
    assert "Mock Bank $300 Checking Bonus" in snapshots[0].raw_text
    assert snapshots[0].raw_payload["feed_format"] == "rss"
    assert snapshots[1].collector_name == "rss"


def test_policy_blocks_disallowed_html_fetching():
    source_policy = policy(
        name="Disabled Scrape Source",
        url="https://example.test/disabled",
        source_type="official_promo_page",
        collection_method="manual_only",
        allow_scrape=False,
    )

    with pytest.raises(CollectionBlockedError) as error:
        ManualUrlCollector().fetch_html(source_policy, fetcher=lambda url: "blocked")

    assert "expected collection_method scrape" in str(error.value)


def test_policy_blocks_login_required_scraping_before_fetcher_runs():
    source_policy = policy(
        name="Login Required Source",
        url="https://example.test/private",
        source_type="official_promo_page",
        collection_method="scrape",
        allow_scrape=True,
        requires_login=True,
    )
    fetcher_called = False

    def fetcher(url):
        nonlocal fetcher_called
        fetcher_called = True
        return "should not run"

    with pytest.raises(CollectionBlockedError) as error:
        ManualUrlCollector().fetch_html(source_policy, fetcher=fetcher)

    assert "logged-in HTML collection is not allowed" in str(error.value)
    assert fetcher_called is False


def test_policy_blocks_high_frequency_collection_before_fetcher_runs():
    source_policy = policy(
        name="Approved Scrape Source",
        url="https://example.test/public",
        source_type="official_promo_page",
        collection_method="scrape",
        allow_scrape=True,
        max_frequency_hours=24,
    )
    fetcher_called = False

    def fetcher(url):
        nonlocal fetcher_called
        fetcher_called = True
        return "should not run"

    with pytest.raises(CollectionBlockedError) as error:
        ManualUrlCollector().fetch_html(
            source_policy,
            fetcher=fetcher,
            last_collected_at="2026-06-17T10:00:00+00:00",
            now=datetime(2026, 6, 17, 12, 0, tzinfo=timezone.utc),
        )

    assert "blocked by max_frequency_hours" in str(error.value)
    assert fetcher_called is False


def test_newsletter_email_collector_accepts_export_text_only():
    source_policy = policy(
        name="Newsletter Export",
        url="email-export://banking-newsletter",
        source_type="newsletter_email",
        collection_method="email_export",
        allow_email_parse=True,
    )

    snapshot = NewsletterEmailCollector().collect(
        source_policy,
        raw_text="Subject: Fictional banking bonus\n\nMock Bank bonus terms.",
    )

    assert snapshot.collector_name == "newsletter_email"
    assert snapshot.raw_payload["input_method"] == "email_export_text"


def test_api_collector_is_fixture_backed():
    source_policy = policy(
        name="Fixture API",
        url="https://example.test/api",
        source_type="api",
        collection_method="api",
        allow_api=True,
    )

    snapshot = ApiCollector().collect_fixture(
        source_policy,
        payload={"title": "Mock API banking bonus", "bonus": 300},
    )

    assert snapshot.collector_name == "api_fixture"
    assert snapshot.raw_text == '{"bonus": 300, "title": "Mock API banking bonus"}'


def test_snapshot_persistence_uses_existing_raw_snapshot_schema(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    initialize_database(db_path)
    snapshot = ManualTextCollector().collect(
        policy(),
        raw_text="Mock Bank offers a fictional $300 checking bonus.",
        retrieved_at="2026-06-17T12:00:00+00:00",
        raw_payload={"fixture_id": "collector-persistence"},
    )

    snapshot_id = persist_collected_snapshot(db_path, snapshot)

    assert snapshot_id > 0
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT source_name, content_hash, raw_payload_json, collector_name "
            "FROM raw_deal_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
    assert row[0] == "Test Manual Source"
    assert row[1] == snapshot.content_hash
    assert '"input_method": "manual_text"' in row[2]
    assert '"fixture_id": "collector-persistence"' in row[2]
    assert row[3] == "manual_text"
    stored = get_raw_snapshot(db_path, snapshot_id)
    assert stored["source_url"] == "manual://test-source"
    assert stored["retrieved_at"] == "2026-06-17T12:00:00+00:00"
    assert stored["raw_text"] == "Mock Bank offers a fictional $300 checking bonus."
