import json
import os
import subprocess
import sys
from pathlib import Path

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


def _public_pilot_config(tmp_path, *, enabled):
    config_path = tmp_path / "banking_sources.yaml"
    config_path.write_text(
        f"""sources:
  - source_id: "public-pilot-fixture-rss"
    source_group: "public-pilot"
    publisher_name: "Public Pilot Fixture Publisher"
    name: "Public Pilot Fixture RSS"
    url: "https://pilot-public.example.test/rss.xml"
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
    fixture_enabled: true
    source_priority: 50
    region_scope:
      - "US"
    enabled: {str(enabled).lower()}
    collection_method: "rss_feed"
    max_frequency_hours: 48
    requires_login: false
    allow_scrape: false
    allow_api: false
    allow_rss: true
    allow_email_parse: false
    robots_policy_notes: "RSS fixture only; no scraping."
    terms_policy_notes: "Fixture-backed public-pilot source for offline tests."
    rate_limit_notes: "At most once every 48 hours if explicitly enabled."
    compliance_status: "approved"
    last_reviewed_at: "2026-06-21"
    notes: "Offline public-pilot integration test source."
""",
        encoding="utf-8",
    )
    return config_path
