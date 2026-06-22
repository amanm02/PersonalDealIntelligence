import json
from datetime import date
from pathlib import Path


FIXTURE_ROOT = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "extractors"
    / "credit_cards"
)
MANIFEST_PATH = FIXTURE_ROOT / "manifest.json"

REQUIRED_SCENARIOS = {
    "cash_bonus_card",
    "points_bonus_card",
    "miles_bonus_card",
    "statement_credit_card",
    "mixed_bonus_card",
    "business_card",
    "targeted_offer",
    "duplicate_offer_across_sources",
    "conflicting_minimum_spend",
    "benefits_only_non_deal",
    "expired_card_offer",
}

REQUIRED_EXPECTED_FIELDS = {
    "issuer",
    "card_name",
    "product_family",
    "customer_type",
    "card_network",
    "offer_title",
    "source_identifier",
    "source_url",
    "offer_currency",
    "headline_bonus_amount",
    "headline_bonus_value_cents",
    "minimum_spend_cents",
    "spend_window_days",
    "annual_fee_cents",
    "first_year_annual_fee_waived",
    "statement_credit_amount_cents",
    "statement_credit_requirements",
    "bonus_payout_timing",
    "offer_expiration_date",
    "targeted",
    "eligibility_restriction_notes",
    "expected_missing_critical_fields",
    "expected_evidence_fields",
    "is_deal",
}

VALID_CURRENCIES = {
    "cash",
    "points",
    "miles",
    "statement_credit",
    "mixed",
    "unknown",
}


def load_manifest():
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def manifest_entries():
    manifest = load_manifest()
    assert manifest["version"] == 1
    return manifest["fixtures"]


def test_manifest_references_existing_non_empty_fixture_files():
    for entry in manifest_entries():
        fixture_path = FIXTURE_ROOT / entry["file"]

        assert fixture_path.exists(), entry["file"]
        assert fixture_path.suffix == ".txt"
        assert fixture_path.read_text(encoding="utf-8").strip()


def test_every_credit_card_fixture_file_has_one_manifest_entry():
    fixture_files = {
        path.name
        for path in FIXTURE_ROOT.glob("*.txt")
    }
    manifest_files = [entry["file"] for entry in manifest_entries()]

    assert set(manifest_files) == fixture_files
    assert len(manifest_files) == len(set(manifest_files))


def test_required_expected_fields_exist_for_every_fixture():
    for entry in manifest_entries():
        expected = entry["expected"]

        assert set(expected) == REQUIRED_EXPECTED_FIELDS
        assert entry["id"]
        assert isinstance(entry["scenario_tags"], list)
        assert entry["scenario_tags"]
        assert expected["offer_currency"] in VALID_CURRENCIES
        assert expected["customer_type"] in {"personal", "business", "unknown"}
        assert isinstance(expected["targeted"], bool)
        assert isinstance(expected["is_deal"], bool)
        assert isinstance(expected["eligibility_restriction_notes"], list)
        assert isinstance(expected["expected_missing_critical_fields"], list)
        assert isinstance(expected["expected_evidence_fields"], list)
        assert expected["expected_evidence_fields"]
        assert (
            expected["source_url"].startswith("https://example.test/")
            or expected["source_url"].startswith("manual://")
        )


def test_required_credit_card_scenarios_are_covered():
    scenario_tags = {
        scenario
        for entry in manifest_entries()
        for scenario in entry["scenario_tags"]
    }

    assert REQUIRED_SCENARIOS.issubset(scenario_tags)


def test_special_expectations_are_explicit():
    entries = manifest_entries()
    by_id = {entry["id"]: entry for entry in entries}

    assert by_id["benefits_only_non_deal"]["expected"]["is_deal"] is False
    assert by_id["benefits_only_non_deal"]["expected"]["offer_currency"] == "unknown"
    assert by_id["targeted_offer"]["expected"]["targeted"] is True
    assert by_id["conflicting_minimum_spend"]["expected"]["minimum_spend_cents"] == (
        200000
    )
    assert any(
        "conflict" in note.lower()
        for note in by_id["conflicting_minimum_spend"]["expected"][
            "eligibility_restriction_notes"
        ]
    )
    assert date.fromisoformat(
        by_id["expired_card_offer"]["expected"]["offer_expiration_date"]
    ) < date(2026, 1, 1)

    duplicate_groups = {}
    for entry in entries:
        duplicate_group = entry.get("duplicate_group")
        if duplicate_group is None:
            continue
        duplicate_groups.setdefault(duplicate_group, []).append(entry["id"])

    assert len(duplicate_groups["beacon-cash-forward-300"]) >= 2


def test_fixture_sources_and_text_stay_safe_and_fictional():
    forbidden_terms = {
        "social security",
        "ssn",
        "password",
        "account number",
        "routing number",
    }
    fixture_text = "\n".join(
        path.read_text(encoding="utf-8").lower()
        for path in FIXTURE_ROOT.glob("*.txt")
    )

    for forbidden in forbidden_terms:
        assert forbidden not in fixture_text

    for entry in manifest_entries():
        text = (FIXTURE_ROOT / entry["file"]).read_text(encoding="utf-8").lower()
        expected = entry["expected"]
        source_url = expected["source_url"]

        assert "fictional" in text or "mock" in text or "demo" in text or "sample" in text or "example" in text
        assert source_url.startswith("https://example.test/") or source_url.startswith(
            "manual://"
        )
