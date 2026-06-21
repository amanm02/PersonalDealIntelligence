import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from pdi.fetchers import SafeFetchResult
from pdi.public_pilot import PublicPilotCollectionError
from pdi.public_pilot import run_public_pilot_workflow
from pdi.storage import list_banking_deals


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_DIR = REPO_ROOT / "examples" / "public_pilot"


def run_cli(db_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(REPO_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "pdi", "--db", str(db_path), *args],
        cwd=REPO_ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )


def test_fixture_backed_public_pilot_flow_produces_searchable_deal(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    config_path = _public_pilot_config(tmp_path, enabled=True)
    digest_path = tmp_path / "public-pilot-digest.md"

    summary = run_public_pilot_workflow(
        db_path,
        source_config_path=config_path,
        dry_run=False,
        confirm_live=True,
        fixture_dir=FIXTURE_DIR,
        digest_output=digest_path,
    )

    assert summary["network_fetch_attempted"] is False
    assert summary["sources"] == 1
    assert summary["raw_snapshots"] == 1
    assert summary["candidates"] == 1
    assert summary["canonical_deals"] == 1
    assert summary["scored_deals"] == 1
    assert digest_path.exists()
    deals = list_banking_deals(db_path)
    assert deals[0]["institution_name"] == "Pilot Public Bank"

    result = run_cli(
        db_path,
        "banking",
        "find",
        "--query",
        "Pilot Public",
        "--format",
        "json",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload[0]["institution_name"] == "Pilot Public Bank"
    assert payload[0]["score_0_to_100"] is not None


def test_public_pilot_dry_run_does_not_call_fetcher(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    config_path = _public_pilot_config(tmp_path, enabled=True)

    def fetcher(policy):
        raise AssertionError("dry-run must not fetch network content")

    summary = run_public_pilot_workflow(
        db_path,
        source_config_path=config_path,
        dry_run=True,
        fetcher=fetcher,
    )

    assert summary["enabled_source_count"] == 1
    assert summary["network_fetch_attempted"] is False
    assert summary["raw_snapshots"] == 0
    assert summary["planned_sources"][0]["eligibility_status"] == "eligible"
    assert summary["planned_sources"][0]["collection_status"] == "skipped_due_to_dry_run"


def test_public_pilot_policy_blocked_source_does_not_call_fetcher(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    config_path = _public_pilot_config(
        tmp_path,
        enabled=False,
        compliance_status="pending_review",
    )
    fetcher_called = False

    def fetcher(policy):
        nonlocal fetcher_called
        fetcher_called = True
        raise AssertionError("blocked sources must not call the fetcher")

    summary = run_public_pilot_workflow(
        db_path,
        source_config_path=config_path,
        dry_run=False,
        confirm_live=True,
        fetcher=fetcher,
    )

    assert fetcher_called is False
    assert summary["enabled_source_count"] == 0
    assert summary["network_fetch_attempted"] is False
    assert summary["planned_sources"][0]["eligibility_status"] == "disabled"
    assert summary["planned_sources"][0]["collection_status"] == "disabled"


def test_public_pilot_confirm_live_uses_mocked_safe_fetch_result(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    config_path = _public_pilot_config(tmp_path, enabled=True, fixture_enabled=False)
    digest_path = tmp_path / "public-pilot-digest.md"

    def fetcher(policy):
        return SafeFetchResult.success(
            body_text=_rss_text(),
            status_code=200,
            content_type="application/rss+xml",
            final_url="https://pilot-public.example.test/rss.xml?token=secret",
            bytes_read=len(_rss_text().encode("utf-8")),
            max_size_bytes=1_000_000,
        )

    summary = run_public_pilot_workflow(
        db_path,
        source_config_path=config_path,
        dry_run=False,
        confirm_live=True,
        fetcher=fetcher,
        digest_output=digest_path,
    )

    assert summary["network_fetch_attempted"] is True
    assert summary["raw_snapshots"] == 1
    assert summary["canonical_deals"] == 1
    assert summary["planned_sources"][0]["collection_status"] == "fetch_succeeded"
    fetch_result = summary["planned_sources"][0]["fetch_result"]
    assert fetch_result["status_code"] == 200
    assert fetch_result["content_type"] == "application/rss+xml"
    assert fetch_result["final_url"] == "https://pilot-public.example.test/rss.xml"
    assert "secret" not in str(fetch_result)
    assert list_banking_deals(db_path)[0]["institution_name"] == "Pilot Public Bank"


def test_public_pilot_confirm_live_fetch_failure_fails_closed_with_metadata(tmp_path):
    db_path = tmp_path / "pdi.sqlite"
    config_path = _public_pilot_config(tmp_path, enabled=True, fixture_enabled=False)

    def fetcher(policy):
        return SafeFetchResult.failure(
            error_type="unsupported_content_type",
            error_message="unsupported public-pilot content type",
            status_code=200,
            content_type="text/html",
            final_url="https://pilot-public.example.test/rss.xml?token=secret",
        )

    with pytest.raises(PublicPilotCollectionError) as error:
        run_public_pilot_workflow(
            db_path,
            source_config_path=config_path,
            dry_run=False,
            confirm_live=True,
            fetcher=fetcher,
        )

    assert "unsupported_content_type" in str(error.value)
    assert "secret" not in str(error.value.planned_sources)
    source = error.value.planned_sources[0]
    assert source["collection_status"] == "fetch_failed"
    assert source["fetch_result"]["error_type"] == "unsupported_content_type"
    assert source["fetch_result"]["content_type"] == "text/html"


def _public_pilot_config(
    tmp_path,
    *,
    enabled,
    url="https://pilot-public.example.test/rss.xml",
    collection_method="rss_feed",
    allow_rss=True,
    fixture_enabled=True,
    compliance_status="approved",
):
    config_path = tmp_path / "banking_sources.yaml"
    config_path.write_text(
        f"""sources:
  - source_id: "public-pilot-fixture-rss"
    source_group: "public-pilot"
    publisher_name: "Public Pilot Fixture Publisher"
    name: "Public Pilot Fixture RSS"
    url: "{url}"
    source_type: "rss_feed"
    source_class: "third_party"
    category_scope:
      - "banking"
    subcategory_scope:
      - "checking_bonus"
    coverage_purpose: "Fixture-backed public-pilot discovery source for offline tests."
    trust_tier: "community"
    official_source: false
    deposit_account_source: true
    brokerage_source: false
    credit_card_source: false
    fixture_enabled: {str(fixture_enabled).lower()}
    source_priority: 50
    region_scope:
      - "US"
    enabled: {str(enabled).lower()}
    collection_method: "{collection_method}"
    max_frequency_hours: 48
    requires_login: false
    allow_scrape: false
    allow_api: false
    allow_rss: {str(allow_rss).lower()}
    allow_email_parse: false
    robots_policy_notes: "RSS fixture only; no scraping."
    terms_policy_notes: "Fixture-backed public-pilot source for offline tests."
    rate_limit_notes: "At most once every 48 hours if explicitly enabled."
    compliance_status: "{compliance_status}"
    last_reviewed_at: "2026-06-21"
    notes: "Offline public-pilot integration test source."
""",
        encoding="utf-8",
    )
    return config_path


def _rss_text():
    return """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Fictional Public Pilot Banking Promos</title>
    <item>
      <title>Pilot Public Bank $450 checking bonus</title>
      <link>https://pilot-public.example.test/promos/checking-450</link>
      <description>Pilot Public Bank offers a $450 checking bonus for new customers. Open a qualifying checking account by December 31, 2026. Receive qualifying direct deposits totaling $2,000 within 90 days. Monthly service fee is $10, waived with qualifying direct deposit. Available only to residents of CA, OR, WA. Final terms must be verified on the official institution page.</description>
      <pubDate>Sun, 21 Jun 2026 12:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""
