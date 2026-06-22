"""Conservative dedupe and canonicalization for banking deal candidates."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping
from urllib.parse import urlparse

from pdi.storage import (
    get_banking_deal,
    get_banking_deal_by_canonical_key,
    get_banking_deal_candidate,
    get_raw_snapshot,
    get_source_record,
    insert_banking_deal,
    insert_banking_deal_source_link,
    insert_deal_change_event,
    insert_status_event,
    list_banking_deal_source_links,
    list_banking_deals,
    list_pending_banking_deal_candidates,
    mark_banking_deal_candidate_canonicalized,
    update_banking_deal,
    upsert_banking_deal_terms,
)


DbPath = str
OFFICIAL_SOURCE_TYPES = {"official_promo_page", "api"}
SECONDARY_SOURCE_TYPES = {
    "rss_feed",
    "newsletter_email",
    "deal_blog",
    "affiliate_feed",
    "manual_url",
}
FUZZY_CONFIDENCE_THRESHOLD = 0.55
SIGNIFICANT_TITLE_WORDS = {
    "account",
    "bank",
    "banking",
    "bonus",
    "brokerage",
    "cash",
    "checking",
    "deposit",
    "earn",
    "market",
    "money",
    "new",
    "offer",
    "promotion",
    "promo",
    "savings",
    "transfer",
}
MATERIAL_DEAL_FIELDS = (
    "bonus_amount_cents",
    "expires_at",
    "application_deadline",
    "source_url",
    "confidence_score",
)
MATERIAL_TERM_FIELDS = (
    "direct_deposit_required",
    "direct_deposit_minimum_cents",
    "minimum_deposit_amount_cents",
    "minimum_balance_required_cents",
    "monthly_fee_cents",
    "state_restrictions",
    "new_customer_only",
)
REVIEW_FIELDS = {
    "bonus_amount_cents",
    "expires_at",
    "application_deadline",
    "direct_deposit_required",
    "direct_deposit_minimum_cents",
    "minimum_deposit_amount_cents",
    "minimum_balance_required_cents",
    "monthly_fee_cents",
    "state_restrictions",
    "new_customer_only",
}
FIELD_EVIDENCE_FIELDS = {
    "bonus_amount_cents",
    "issuer",
    "card_name",
    "customer_type",
    "headline_bonus_amount",
    "minimum_spend_cents",
    "spend_window_days",
    "annual_fee_cents",
    "first_year_annual_fee_waived",
    "statement_credit_amount_cents",
    "statement_credit_requirements",
    "targeted",
    "eligibility_restriction_notes",
    "direct_deposit_required",
    "direct_deposit_minimum_cents",
    "minimum_deposit_amount_cents",
    "minimum_balance_required_cents",
    "balance_hold_days",
    "expires_at",
    "application_deadline",
    "monthly_fee_cents",
    "state_restrictions",
    "new_customer_only",
}
EXTRACTION_METHOD = "rule_based_banking_extractor"
EXTRACTION_VERSION = "2"
CREDIT_CARD_SUBCATEGORY = "credit_card_signup_bonus"
CREDIT_CARD_MATERIAL_FIELDS = (
    "issuer_name",
    "card_name",
    "product_family",
    "customer_type",
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
    "targeted",
    "eligibility_restriction_notes",
)
REVIEW_FIELDS.update(CREDIT_CARD_MATERIAL_FIELDS)


@dataclass(frozen=True)
class CanonicalizationResult:
    """Result from processing one extracted candidate."""

    candidate_id: int
    deal_id: int | None
    action: str
    match_reason: str
    changed_fields: list[str] = field(default_factory=list)
    conflict_fields: list[str] = field(default_factory=list)


def generate_canonical_key(candidate: Mapping[str, Any]) -> str:
    """Generate a deterministic canonical key for an extracted candidate."""

    if _is_credit_card_candidate(candidate):
        return _credit_card_canonical_key(candidate)

    institution = _slug(_normalize_name(candidate.get("institution_name")))
    subcategory = _slug(str(candidate.get("subcategory") or "unknown"))
    bonus = candidate.get("bonus_amount_cents")
    bonus_part = "bonus-unknown" if bonus is None else f"bonus-{int(bonus)}"
    product_part = _slug(_product_key(candidate)) or "product-unknown"
    expiration = str(candidate.get("expires_at") or "expires-unknown")
    source_path = _slug(_source_path_key(candidate.get("source_url"))) or "source-unknown"
    return "-".join(
        part
        for part in (
            institution or "institution-unknown",
            subcategory,
            bonus_part,
            product_part,
            _slug(expiration),
            source_path,
        )
        if part
    )


def canonicalize_candidate(
    db_path: DbPath,
    candidate_id: int,
) -> CanonicalizationResult:
    """Create or update a canonical deal from one extracted candidate."""

    candidate = get_banking_deal_candidate(db_path, candidate_id)
    if candidate is None:
        raise ValueError(f"Candidate id {candidate_id} does not exist.")

    if candidate["rejected"]:
        mark_banking_deal_candidate_canonicalized(
            db_path,
            candidate_id,
            deal_id=None,
            status="skipped",
        )
        return CanonicalizationResult(candidate_id, None, "skipped", "rejected")

    if not candidate.get("institution_name") or not candidate.get("subcategory"):
        mark_banking_deal_candidate_canonicalized(
            db_path,
            candidate_id,
            deal_id=None,
            status="skipped",
        )
        return CanonicalizationResult(
            candidate_id,
            None,
            "skipped",
            "missing_required_identity",
        )

    match, match_reason = _find_match(db_path, candidate)
    if match is None:
        deal_id = _create_canonical_deal(db_path, candidate)
        _link_source(db_path, deal_id, candidate)
        mark_banking_deal_candidate_canonicalized(
            db_path,
            candidate_id,
            deal_id=deal_id,
            status="created",
        )
        return CanonicalizationResult(candidate_id, deal_id, "created", "no_match")

    changed_fields, conflict_fields = _merge_candidate(
        db_path,
        match,
        candidate,
        match_reason,
    )
    action = "updated" if changed_fields else "matched"
    mark_banking_deal_candidate_canonicalized(
        db_path,
        candidate_id,
        deal_id=int(match["id"]),
        status=action,
    )
    return CanonicalizationResult(
        candidate_id,
        int(match["id"]),
        action,
        match_reason,
        changed_fields,
        conflict_fields,
    )


def canonicalize_pending_candidates(
    db_path: DbPath,
    *,
    limit: int | None = None,
) -> list[CanonicalizationResult]:
    """Canonicalize all non-rejected candidates that have not been processed."""

    return [
        canonicalize_candidate(db_path, int(candidate["id"]))
        for candidate in list_pending_banking_deal_candidates(db_path, limit=limit)
    ]


def _find_match(
    db_path: DbPath,
    candidate: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    canonical_key = generate_canonical_key(candidate)
    exact = get_banking_deal_by_canonical_key(db_path, canonical_key)
    if exact is not None:
        return exact, "exact_canonical_key"

    if _is_credit_card_candidate(candidate):
        return _find_credit_card_match(db_path, candidate)

    candidate_institution = _normalize_name(candidate.get("institution_name"))
    candidate_subcategory = candidate.get("subcategory")
    candidate_source_path = _source_path_key(candidate.get("source_url"))
    candidate_product = _product_key(candidate)

    same_identity: list[dict[str, Any]] = []
    for deal in list_banking_deals(db_path):
        if _normalize_name(deal.get("institution_name")) != candidate_institution:
            continue
        if deal.get("subcategory") != candidate_subcategory:
            continue
        same_identity.append(deal)

    for deal in same_identity:
        same_source_path = (
            candidate_source_path
            and _source_path_key(deal.get("source_url")) == candidate_source_path
        )
        same_product = (
            candidate_product
            and _product_key(deal)
            and candidate_product == _product_key(deal)
        )
        if same_source_path or same_product:
            return get_banking_deal(db_path, int(deal["id"])), "same_source_or_product"

    if (candidate.get("confidence_score") or 0) < FUZZY_CONFIDENCE_THRESHOLD:
        return None, "low_confidence_no_match"

    for deal in same_identity:
        if deal.get("bonus_amount_cents") != candidate.get("bonus_amount_cents"):
            continue
        if not _expiration_compatible(deal, candidate):
            continue
        if not _product_compatible(deal, candidate):
            continue
        return get_banking_deal(db_path, int(deal["id"])), "strong_fuzzy"

    return None, "no_match"


def _create_canonical_deal(db_path: DbPath, candidate: Mapping[str, Any]) -> int:
    observed_at = candidate.get("retrieved_at") or _utc_now()
    title = candidate.get("title") or _fallback_title(candidate)
    status = "needs_review" if _candidate_needs_review(candidate) else "new"
    return insert_banking_deal(
        db_path,
        {
            "canonical_key": generate_canonical_key(candidate),
            "title": title,
            "institution_name": candidate["institution_name"],
            "subcategory": candidate["subcategory"],
            "bonus_amount_cents": candidate.get("bonus_amount_cents"),
            "currency": candidate.get("currency", "USD"),
            "source_url": candidate.get("source_url"),
            "source_name": candidate.get("source_name"),
            "discovered_at": observed_at,
            "last_seen_at": observed_at,
            "expires_at": candidate.get("expires_at"),
            "application_deadline": candidate.get("application_deadline"),
            "status": status,
            "confidence_score": candidate.get("confidence_score"),
            "raw_snapshot_id": candidate["raw_snapshot_id"],
            "terms": _candidate_terms(candidate),
        },
    )


def _merge_candidate(
    db_path: DbPath,
    deal: Mapping[str, Any],
    candidate: Mapping[str, Any],
    match_reason: str,
) -> tuple[list[str], list[str]]:
    deal_id = int(deal["id"])
    candidate_id = int(candidate["id"])
    observed_at = _latest_timestamp(deal.get("last_seen_at"), candidate.get("retrieved_at"))
    candidate_authority = _candidate_authority(db_path, candidate)
    existing_authority = _deal_authority(db_path, deal_id)

    deal_updates: dict[str, Any] = {"last_seen_at": observed_at}
    term_updates: dict[str, Any] = {}
    changed_fields: list[str] = []
    conflict_fields: list[str] = []

    for field_name in MATERIAL_DEAL_FIELDS:
        if field_name == "source_url":
            selected, reason, is_conflict = _select_source_url_value(
                deal.get(field_name),
                candidate.get(field_name),
            )
        else:
            selected, reason, is_conflict = _select_value(
                deal.get(field_name),
                candidate.get(field_name),
                existing_confidence=deal.get("confidence_score"),
                candidate_confidence=candidate.get("confidence_score"),
                existing_authority=existing_authority,
                candidate_authority=candidate_authority,
            )
        if reason == "unchanged":
            continue
        if selected != deal.get(field_name):
            deal_updates[field_name] = selected
        _record_field_change(
            db_path,
            deal_id,
            field_name,
            deal.get(field_name),
            candidate.get(field_name),
            selected,
            candidate,
            reason,
        )
        changed_fields.append(field_name)
        if is_conflict and field_name in REVIEW_FIELDS:
            conflict_fields.append(field_name)

    existing_terms = deal.get("terms") or {}
    for field_name in MATERIAL_TERM_FIELDS:
        existing_value = _term_value(existing_terms, field_name)
        candidate_value = _candidate_term_value(candidate, field_name)
        selected, reason, is_conflict = _select_value(
            existing_value,
            candidate_value,
            existing_confidence=deal.get("confidence_score"),
            candidate_confidence=candidate.get("confidence_score"),
            existing_authority=existing_authority,
            candidate_authority=candidate_authority,
        )
        if reason == "unchanged":
            continue
        if selected != existing_value:
            term_updates[field_name] = selected
        _record_field_change(
            db_path,
            deal_id,
            field_name,
            existing_value,
            candidate_value,
            selected,
            candidate,
            reason,
        )
        changed_fields.append(field_name)
        if is_conflict and field_name in REVIEW_FIELDS:
            conflict_fields.append(field_name)

    if _is_credit_card_candidate(candidate):
        card_updates, card_changed, card_conflicts = _merge_credit_card_terms(
            db_path,
            deal,
            candidate,
            existing_terms,
            existing_authority=existing_authority,
            candidate_authority=candidate_authority,
        )
        if card_updates:
            term_updates["terms_json"] = card_updates
        changed_fields.extend(card_changed)
        conflict_fields.extend(card_conflicts)

    update_banking_deal(db_path, deal_id, deal_updates)
    if term_updates:
        upsert_banking_deal_terms(db_path, deal_id, term_updates)
    _link_source(db_path, deal_id, candidate)

    if conflict_fields and deal.get("status") != "needs_review":
        insert_status_event(
            db_path,
            deal_id,
            "needs_review",
            note=(
                "Dedupe conflict requires review: "
                + ", ".join(sorted(set(conflict_fields)))
            ),
        )

    return sorted(set(changed_fields)), sorted(set(conflict_fields))


def _select_value(
    existing_value: Any,
    candidate_value: Any,
    *,
    existing_confidence: float | None,
    candidate_confidence: float | None,
    existing_authority: str,
    candidate_authority: str,
) -> tuple[Any, str, bool]:
    existing_value = _normalized_json_value(existing_value)
    candidate_value = _normalized_json_value(candidate_value)
    if candidate_value is None:
        return existing_value, "unchanged", False
    if existing_value is None:
        return candidate_value, "filled_unknown", False
    if existing_value == candidate_value:
        return existing_value, "unchanged", False

    if candidate_authority == "official" and existing_authority != "official":
        return candidate_value, "candidate_official_preferred", True
    if existing_authority == "official" and candidate_authority != "official":
        return existing_value, "existing_official_preserved", True

    if (candidate_confidence or 0) > (existing_confidence or 0):
        return candidate_value, "candidate_higher_confidence", True
    return existing_value, "existing_confidence_preserved", True


def _select_source_url_value(
    existing_value: Any,
    candidate_value: Any,
) -> tuple[Any, str, bool]:
    if candidate_value is None:
        return existing_value, "unchanged", False
    if existing_value is None:
        return candidate_value, "filled_unknown", False
    if existing_value == candidate_value:
        return existing_value, "unchanged", False
    return existing_value, "additional_source_preserved_as_link", False


def _record_field_change(
    db_path: DbPath,
    deal_id: int,
    field_name: str,
    old_value: Any,
    candidate_value: Any,
    selected_value: Any,
    candidate: Mapping[str, Any],
    reason: str,
) -> None:
    insert_deal_change_event(
        db_path,
        deal_id,
        "canonical_field_changed",
        {
            field_name: {
                "old_value": _normalized_json_value(old_value),
                "candidate_value": _normalized_json_value(candidate_value),
                "selected_value": _normalized_json_value(selected_value),
                "candidate_id": candidate["id"],
                "raw_snapshot_id": candidate["raw_snapshot_id"],
                "source_name": candidate.get("source_name"),
                "source_url": candidate.get("source_url"),
                "confidence_score": candidate.get("confidence_score"),
                "reason": reason,
            }
        },
        note=f"Dedupe observed material field difference for {field_name}.",
    )


def _link_source(
    db_path: DbPath,
    deal_id: int,
    candidate: Mapping[str, Any],
) -> None:
    insert_banking_deal_source_link(
        db_path,
        {
            "deal_id": deal_id,
            "candidate_id": candidate["id"],
            "raw_snapshot_id": candidate["raw_snapshot_id"],
            "source_name": candidate["source_name"],
            "source_url": candidate.get("source_url"),
            "source_authority": _candidate_authority(db_path, candidate),
            "retrieved_at": candidate.get("retrieved_at"),
            "confidence_score": candidate.get("confidence_score"),
            "evidence": _field_evidence_from_candidate(candidate),
        },
    )


def _field_evidence_from_candidate(candidate: Mapping[str, Any]) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for span in _json_list(candidate.get("evidence_spans_json")):
        if not isinstance(span, Mapping):
            continue
        field_name = span.get("field")
        if not field_name or str(field_name) not in FIELD_EVIDENCE_FIELDS:
            continue
        enriched = dict(span)
        enriched.setdefault("evidence_text", span.get("text"))
        enriched.setdefault("excerpt", span.get("text"))
        enriched.setdefault(
            "extracted_value",
            _normalized_json_value(_candidate_field_value(candidate, str(field_name))),
        )
        enriched.setdefault("raw_snapshot_id", candidate.get("raw_snapshot_id"))
        enriched.setdefault("candidate_id", candidate.get("id"))
        enriched.setdefault("confidence_score", candidate.get("confidence_score"))
        enriched.setdefault("extraction_method", EXTRACTION_METHOD)
        enriched.setdefault("extraction_version", EXTRACTION_VERSION)
        evidence.append(enriched)
    return evidence


def _find_credit_card_match(
    db_path: DbPath,
    candidate: Mapping[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    if (candidate.get("confidence_score") or 0) < FUZZY_CONFIDENCE_THRESHOLD:
        return None, "low_confidence_no_match"

    candidate_issuer = _normalize_name(candidate.get("issuer_name") or candidate.get("institution_name"))
    candidate_card = _normalize_card_name(candidate.get("card_name"))
    candidate_source_path = _source_path_key(candidate.get("source_url"))
    candidate_headline = _normalized_json_value(candidate.get("headline_bonus_amount_json"))
    candidate_currency = candidate.get("offer_currency")
    candidate_customer_type = candidate.get("customer_type")

    for deal in list_banking_deals(db_path, subcategory=CREDIT_CARD_SUBCATEGORY):
        full_deal = get_banking_deal(db_path, int(deal["id"]))
        if full_deal is None:
            continue
        deal_issuer = _normalize_name(
            _credit_card_record_value(full_deal, "issuer_name")
            or full_deal.get("institution_name")
        )
        deal_card = _normalize_card_name(_credit_card_record_value(full_deal, "card_name"))
        same_card_identity = bool(candidate_card and deal_card and candidate_card == deal_card)
        if candidate_issuer and deal_issuer and candidate_issuer != deal_issuer:
            continue
        if candidate_card and deal_card and not same_card_identity:
            continue

        deal_customer_type = _credit_card_record_value(full_deal, "customer_type")
        if _known_different(candidate_customer_type, deal_customer_type):
            continue

        same_source_path = (
            candidate_source_path
            and _source_path_key(full_deal.get("source_url")) == candidate_source_path
        )
        deal_headline = _credit_card_record_value(full_deal, "headline_bonus_amount")
        deal_currency = _credit_card_record_value(full_deal, "offer_currency")
        same_offer = (
            same_card_identity
            and _compatible_value(candidate_currency, deal_currency)
            and _compatible_value(candidate_headline, deal_headline)
            and _expiration_compatible(full_deal, candidate)
        )
        if same_source_path:
            return full_deal, "same_credit_card_source"
        if same_offer:
            return full_deal, "same_credit_card_offer"

    return None, "no_match"


def _merge_credit_card_terms(
    db_path: DbPath,
    deal: Mapping[str, Any],
    candidate: Mapping[str, Any],
    existing_terms: Mapping[str, Any],
    *,
    existing_authority: str,
    candidate_authority: str,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    existing_terms_json = _terms_json(existing_terms)
    existing_card_terms = dict(existing_terms_json.get("credit_card") or {})
    updated_card_terms = dict(existing_card_terms)
    changed_fields: list[str] = []
    conflict_fields: list[str] = []

    for field_name in CREDIT_CARD_MATERIAL_FIELDS:
        existing_value = existing_card_terms.get(field_name)
        candidate_value = _candidate_credit_card_value(candidate, field_name)
        selected, reason, is_conflict = _select_value(
            existing_value,
            candidate_value,
            existing_confidence=deal.get("confidence_score"),
            candidate_confidence=candidate.get("confidence_score"),
            existing_authority=existing_authority,
            candidate_authority=candidate_authority,
        )
        if reason == "unchanged":
            continue
        updated_card_terms[field_name] = selected
        _record_field_change(
            db_path,
            int(deal["id"]),
            field_name,
            existing_value,
            candidate_value,
            selected,
            candidate,
            reason,
        )
        changed_fields.append(field_name)
        if is_conflict:
            conflict_fields.append(field_name)

    if updated_card_terms == existing_card_terms:
        return None, changed_fields, conflict_fields

    existing_terms_json["credit_card"] = updated_card_terms
    existing_terms_json["last_credit_card_candidate_id"] = candidate["id"]
    return existing_terms_json, sorted(set(changed_fields)), sorted(set(conflict_fields))


def _is_credit_card_candidate(record: Mapping[str, Any]) -> bool:
    if record.get("subcategory") == CREDIT_CARD_SUBCATEGORY:
        return True
    terms = record.get("terms")
    if isinstance(terms, Mapping):
        return bool(_terms_json(terms).get("credit_card"))
    return False


def _credit_card_canonical_key(candidate: Mapping[str, Any]) -> str:
    issuer = _slug(_normalize_name(candidate.get("issuer_name") or candidate.get("institution_name")))
    card = _slug(str(candidate.get("card_name") or "card-unknown"))
    customer_type = _slug(str(candidate.get("customer_type") or "customer-unknown"))
    currency = _slug(str(candidate.get("offer_currency") or "currency-unknown"))
    headline = _slug(str(_normalized_json_value(candidate.get("headline_bonus_amount_json")) or "headline-unknown"))
    expiration = _slug(str(candidate.get("expires_at") or "expires-unknown"))
    return "-".join(
        part
        for part in (
            issuer or "issuer-unknown",
            CREDIT_CARD_SUBCATEGORY.replace("_", "-"),
            card,
            customer_type,
            currency,
            headline,
            expiration,
        )
        if part
    )


def _candidate_credit_card_terms(candidate: Mapping[str, Any]) -> dict[str, Any]:
    return {
        field_name: _candidate_credit_card_value(candidate, field_name)
        for field_name in CREDIT_CARD_MATERIAL_FIELDS
        if _candidate_credit_card_value(candidate, field_name) is not None
    }


def _candidate_credit_card_value(candidate: Mapping[str, Any], field_name: str) -> Any:
    if field_name == "headline_bonus_amount":
        return _json_candidate_scalar(candidate.get("headline_bonus_amount_json"))
    if field_name == "eligibility_restriction_notes":
        return _json_list(candidate.get("eligibility_restriction_notes_json"))
    if field_name in {"first_year_annual_fee_waived", "targeted"}:
        return _int_to_bool(candidate.get(field_name))
    return candidate.get(field_name)


def _credit_card_record_value(record: Mapping[str, Any], field_name: str) -> Any:
    if field_name in record and record.get(field_name) is not None:
        return record.get(field_name)
    terms = record.get("terms")
    if isinstance(terms, Mapping):
        return (_terms_json(terms).get("credit_card") or {}).get(field_name)
    return None


def _json_candidate_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _terms_json(terms: Mapping[str, Any]) -> dict[str, Any]:
    value = _normalized_json_value(terms.get("terms_json"))
    return value if isinstance(value, dict) else {}


def _normalize_card_name(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


def _known_different(left: Any, right: Any) -> bool:
    return (
        left not in (None, "", "unknown")
        and right not in (None, "", "unknown")
        and left != right
    )


def _compatible_value(left: Any, right: Any) -> bool:
    left = _normalized_json_value(left)
    right = _normalized_json_value(right)
    return left in (None, "", "unknown", []) or right in (None, "", "unknown", []) or left == right


def _candidate_field_value(candidate: Mapping[str, Any], field_name: str) -> Any:
    aliases = {
        "issuer": "issuer_name",
        "headline_bonus_amount": "headline_bonus_amount_json",
        "eligibility_restriction_notes": "eligibility_restriction_notes_json",
    }
    if field_name in aliases:
        value = candidate.get(aliases[field_name])
        if field_name == "headline_bonus_amount":
            return _json_candidate_scalar(value)
        return _normalized_json_value(value)
    if field_name in {
        "direct_deposit_required",
        "new_customer_only",
        "hard_pull_risk",
        "soft_pull_only",
        "first_year_annual_fee_waived",
        "targeted",
    }:
        return _int_to_bool(candidate.get(field_name))
    if field_name == "state_restrictions":
        return _json_list(candidate.get("state_restrictions_json"))
    return candidate.get(field_name)


def _candidate_authority(db_path: DbPath, candidate: Mapping[str, Any]) -> str:
    snapshot = get_raw_snapshot(db_path, int(candidate["raw_snapshot_id"]))
    if not snapshot or snapshot.get("source_record_id") is None:
        return "unknown"
    source = get_source_record(db_path, int(snapshot["source_record_id"]))
    if not source:
        return "unknown"
    source_type = source.get("source_type")
    if source_type in OFFICIAL_SOURCE_TYPES:
        return "official"
    if source_type in SECONDARY_SOURCE_TYPES:
        return "secondary"
    return "unknown"


def _deal_authority(db_path: DbPath, deal_id: int) -> str:
    links = list_banking_deal_source_links(db_path, deal_id=deal_id)
    authorities = {link["source_authority"] for link in links}
    if "official" in authorities:
        return "official"
    if "secondary" in authorities:
        return "secondary"
    return "unknown"


def _candidate_terms(candidate: Mapping[str, Any]) -> dict[str, Any]:
    terms_json: dict[str, Any] = {
        "candidate_id": candidate["id"],
        "missing_fields": _json_list(candidate.get("missing_fields_json")),
    }
    if _is_credit_card_candidate(candidate):
        terms_json["credit_card"] = _candidate_credit_card_terms(candidate)

    return {
        "minimum_deposit_amount_cents": candidate.get("minimum_deposit_amount_cents"),
        "direct_deposit_required": _int_to_bool(candidate.get("direct_deposit_required")),
        "direct_deposit_minimum_cents": candidate.get("direct_deposit_minimum_cents"),
        "minimum_balance_required_cents": candidate.get(
            "minimum_balance_required_cents"
        ),
        "balance_hold_days": candidate.get("balance_hold_days"),
        "monthly_fee_cents": candidate.get("monthly_fee_cents"),
        "monthly_fee_waiver_terms": candidate.get("monthly_fee_waiver_terms"),
        "early_closure_fee_cents": candidate.get("early_closure_fee_cents"),
        "hard_pull_risk": _int_to_bool(candidate.get("hard_pull_risk")),
        "soft_pull_only": _int_to_bool(candidate.get("soft_pull_only")),
        "state_restrictions": _json_list(candidate.get("state_restrictions_json")),
        "new_customer_only": _int_to_bool(candidate.get("new_customer_only")),
        "household_limit": candidate.get("household_limit"),
        "terms_json": terms_json,
    }


def _candidate_term_value(candidate: Mapping[str, Any], field_name: str) -> Any:
    if field_name == "state_restrictions":
        return _json_list(candidate.get("state_restrictions_json"))
    if field_name in {"direct_deposit_required", "new_customer_only"}:
        return _int_to_bool(candidate.get(field_name))
    return candidate.get(field_name)


def _term_value(terms: Mapping[str, Any], field_name: str) -> Any:
    if field_name == "state_restrictions":
        return _json_list(terms.get("state_restrictions"))
    if field_name in {"direct_deposit_required", "new_customer_only"}:
        return _int_to_bool(terms.get(field_name))
    return terms.get(field_name)


def _candidate_needs_review(candidate: Mapping[str, Any]) -> bool:
    missing = set(_json_list(candidate.get("missing_fields_json")))
    return bool(missing.intersection(REVIEW_FIELDS)) or _int_to_bool(
        candidate.get("targeted")
    ) is True


def _fallback_title(candidate: Mapping[str, Any]) -> str:
    parts = [str(candidate["institution_name"])]
    if candidate.get("bonus_amount_cents") is not None:
        parts.append(f"${int(candidate['bonus_amount_cents']) // 100:,}")
    parts.append(str(candidate["subcategory"]).replace("_", " ").title())
    return " ".join(parts)


def _expiration_compatible(
    deal: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> bool:
    return (
        not deal.get("expires_at")
        or not candidate.get("expires_at")
        or deal.get("expires_at") == candidate.get("expires_at")
    )


def _product_compatible(
    deal: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> bool:
    deal_product = _product_key(deal)
    candidate_product = _product_key(candidate)
    return (
        not deal_product
        or not candidate_product
        or deal_product == candidate_product
    )


def _product_key(record: Mapping[str, Any]) -> str:
    if _is_credit_card_candidate(record):
        card_name = _credit_card_record_value(record, "card_name")
        if card_name:
            return _slug(str(card_name))
    title = str(record.get("title") or "")
    institution = str(record.get("institution_name") or "")
    title = title.replace(institution, " ")
    title = re.sub(r"\$[0-9,]+(?:\.[0-9]{2})?", " ", title)
    words = [
        word
        for word in re.findall(r"[a-z0-9]+", title.lower())
        if word not in SIGNIFICANT_TITLE_WORDS
    ]
    return "-".join(words[:5])


def _source_path_key(source_url: Any) -> str:
    if not source_url:
        return ""
    parsed = urlparse(str(source_url))
    if not parsed.netloc and not parsed.path:
        return ""
    path = parsed.path.strip("/")
    if not path:
        return parsed.netloc.lower()
    path_parts = [part for part in path.split("/") if part]
    return "/".join([parsed.netloc.lower(), *path_parts[:3]])


def _normalize_name(value: Any) -> str:
    text = str(value or "").lower()
    text = re.sub(r"\b(?:the|bank|national|association|na|n\.a\.)\b", " ", text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def _slug(value: str) -> str:
    return "-".join(re.findall(r"[a-z0-9]+", value.lower()))


def _json_list(value: Any) -> list[Any]:
    decoded = _normalized_json_value(value)
    if decoded is None:
        return []
    if isinstance(decoded, list):
        return decoded
    return [decoded]


def _normalized_json_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("[", "{")):
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                return value
    return value


def _int_to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _latest_timestamp(existing_value: Any, candidate_value: Any) -> str:
    existing = str(existing_value or "")
    candidate = str(candidate_value or "")
    if not existing and not candidate:
        return _utc_now()
    if not existing:
        return candidate
    if not candidate:
        return existing
    return max(existing, candidate)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
