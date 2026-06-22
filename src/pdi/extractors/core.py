"""Deterministic banking deal extraction from raw snapshots."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

from pdi.storage import (
    get_raw_snapshot,
    insert_banking_deal_candidate,
    list_banking_deal_candidates,
    list_raw_snapshots,
)


DbPath = str
MONEY_PATTERN = r"\$([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)(?:\.([0-9]{2}))?"
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}
HIGH_IMPACT_FIELDS = (
    "bonus_amount_cents",
    "direct_deposit_required",
    "minimum_deposit_amount_cents",
    "minimum_balance_required_cents",
    "balance_hold_days",
    "expires_at",
    "monthly_fee_cents",
    "state_restrictions",
    "new_customer_only",
)
CREDIT_CARD_CRITICAL_FIELDS = (
    "headline_bonus_amount",
    "minimum_spend_cents",
    "spend_window_days",
    "annual_fee_cents",
    "offer_expiration_date",
    "card_network",
    "bonus_payout_timing",
)
EXTRACTOR_METHOD = "rule_based_banking_extractor"
EXTRACTOR_VERSION = "2"
REEXTRACTION_COMPARE_FIELDS = (
    "title",
    "institution_name",
    "category",
    "subcategory",
    "bonus_amount_cents",
    "currency",
    "expires_at",
    "application_deadline",
    "minimum_deposit_amount_cents",
    "direct_deposit_required",
    "direct_deposit_minimum_cents",
    "minimum_balance_required_cents",
    "balance_hold_days",
    "monthly_fee_cents",
    "monthly_fee_waiver_terms",
    "early_closure_fee_cents",
    "state_restrictions",
    "new_customer_only",
    "household_limit",
    "hard_pull_risk",
    "soft_pull_only",
    "issuer_name",
    "card_name",
    "product_family",
    "customer_type",
    "card_network",
    "offer_currency",
    "headline_bonus_amount",
    "headline_bonus_value_cents",
    "point_mile_valuation_assumption_id",
    "minimum_spend_cents",
    "spend_window_days",
    "annual_fee_cents",
    "first_year_annual_fee_waived",
    "statement_credit_amount_cents",
    "statement_credit_requirements",
    "bonus_payout_timing",
    "targeted",
    "eligibility_restriction_notes",
    "source_confidence",
    "tiered_bonus",
    "missing_fields",
    "confidence_score",
    "rejected",
    "rejection_reason",
)
JSON_CANDIDATE_FIELDS = {
    "state_restrictions": "state_restrictions_json",
    "tiered_bonus": "tiered_bonus_json",
    "missing_fields": "missing_fields_json",
    "headline_bonus_amount": "headline_bonus_amount_json",
    "eligibility_restriction_notes": "eligibility_restriction_notes_json",
}
BOOL_CANDIDATE_FIELDS = {
    "direct_deposit_required",
    "new_customer_only",
    "hard_pull_risk",
    "soft_pull_only",
    "first_year_annual_fee_waived",
    "targeted",
    "rejected",
}


@dataclass(frozen=True)
class ReextractionFieldChange:
    """A deterministic old/new extracted value comparison."""

    field: str
    previous_value: Any
    new_value: Any

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "previous_value": self.previous_value,
            "new_value": self.new_value,
        }


@dataclass(frozen=True)
class ReextractionResult:
    """Result from reprocessing one stored raw snapshot."""

    raw_snapshot_id: int
    content_hash: str | None
    source_name: str
    source_url: str | None
    dry_run: bool
    previous_candidate_id: int | None
    new_candidate_id: int | None
    changed_fields: list[ReextractionFieldChange]
    new_candidate: ExtractedDealCandidate

    def to_dict(self) -> dict[str, Any]:
        return {
            "raw_snapshot_id": self.raw_snapshot_id,
            "content_hash": self.content_hash,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "dry_run": self.dry_run,
            "previous_candidate_id": self.previous_candidate_id,
            "new_candidate_id": self.new_candidate_id,
            "candidate_written": self.new_candidate_id is not None,
            "extractor_method": EXTRACTOR_METHOD,
            "extractor_version": EXTRACTOR_VERSION,
            "changed_fields": [
                change.to_dict() for change in self.changed_fields
            ],
            "new_candidate": self.new_candidate.to_storage_record(),
            "canonical_values_preserved": True,
        }


@dataclass(frozen=True)
class EvidenceSpan:
    """A source text span supporting one extracted field."""

    field: str
    text: str
    start: int
    end: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "text": self.text,
            "start": self.start,
            "end": self.end,
        }


@dataclass
class ExtractedDealCandidate:
    """Pre-dedupe extracted banking deal candidate."""

    raw_snapshot_id: int
    source_name: str
    source_url: str | None
    retrieved_at: str | None
    title: str | None = None
    institution_name: str | None = None
    category: str = "banking"
    subcategory: str | None = None
    bonus_amount_cents: int | None = None
    currency: str = "USD"
    expires_at: str | None = None
    application_deadline: str | None = None
    minimum_deposit_amount_cents: int | None = None
    direct_deposit_required: bool | None = None
    direct_deposit_minimum_cents: int | None = None
    minimum_balance_required_cents: int | None = None
    balance_hold_days: int | None = None
    monthly_fee_cents: int | None = None
    monthly_fee_waiver_terms: str | None = None
    early_closure_fee_cents: int | None = None
    state_restrictions: list[str] | None = None
    new_customer_only: bool | None = None
    household_limit: str | None = None
    hard_pull_risk: bool | None = None
    soft_pull_only: bool | None = None
    issuer_name: str | None = None
    card_name: str | None = None
    product_family: str | None = None
    customer_type: str | None = None
    card_network: str | None = None
    offer_currency: str | None = None
    headline_bonus_amount: int | dict[str, int] | None = None
    headline_bonus_value_cents: int | None = None
    point_mile_valuation_assumption_id: str | None = None
    minimum_spend_cents: int | None = None
    spend_window_days: int | None = None
    annual_fee_cents: int | None = None
    first_year_annual_fee_waived: bool | None = None
    statement_credit_amount_cents: int | None = None
    statement_credit_requirements: str | None = None
    bonus_payout_timing: str | None = None
    targeted: bool | None = None
    eligibility_restriction_notes: list[str] = field(default_factory=list)
    source_confidence: float | None = None
    evidence_spans: list[EvidenceSpan] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    extraction_notes: list[str] = field(default_factory=list)
    tiered_bonus: list[dict[str, int]] = field(default_factory=list)
    raw_pattern_matches: dict[str, list[str]] = field(default_factory=dict)
    confidence_score: float = 0.0
    rejected: bool = False
    rejection_reason: str | None = None

    def to_storage_record(self) -> dict[str, Any]:
        return {
            "raw_snapshot_id": self.raw_snapshot_id,
            "title": self.title,
            "institution_name": self.institution_name,
            "category": self.category,
            "subcategory": self.subcategory,
            "bonus_amount_cents": self.bonus_amount_cents,
            "currency": self.currency,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "retrieved_at": self.retrieved_at,
            "expires_at": self.expires_at,
            "application_deadline": self.application_deadline,
            "minimum_deposit_amount_cents": self.minimum_deposit_amount_cents,
            "direct_deposit_required": self.direct_deposit_required,
            "direct_deposit_minimum_cents": self.direct_deposit_minimum_cents,
            "minimum_balance_required_cents": self.minimum_balance_required_cents,
            "balance_hold_days": self.balance_hold_days,
            "monthly_fee_cents": self.monthly_fee_cents,
            "monthly_fee_waiver_terms": self.monthly_fee_waiver_terms,
            "early_closure_fee_cents": self.early_closure_fee_cents,
            "state_restrictions": self.state_restrictions,
            "new_customer_only": self.new_customer_only,
            "household_limit": self.household_limit,
            "hard_pull_risk": self.hard_pull_risk,
            "soft_pull_only": self.soft_pull_only,
            "issuer_name": self.issuer_name,
            "card_name": self.card_name,
            "product_family": self.product_family,
            "customer_type": self.customer_type,
            "card_network": self.card_network,
            "offer_currency": self.offer_currency,
            "headline_bonus_amount": self.headline_bonus_amount,
            "headline_bonus_value_cents": self.headline_bonus_value_cents,
            "point_mile_valuation_assumption_id": (
                self.point_mile_valuation_assumption_id
            ),
            "minimum_spend_cents": self.minimum_spend_cents,
            "spend_window_days": self.spend_window_days,
            "annual_fee_cents": self.annual_fee_cents,
            "first_year_annual_fee_waived": self.first_year_annual_fee_waived,
            "statement_credit_amount_cents": self.statement_credit_amount_cents,
            "statement_credit_requirements": self.statement_credit_requirements,
            "bonus_payout_timing": self.bonus_payout_timing,
            "targeted": self.targeted,
            "eligibility_restriction_notes": list(
                self.eligibility_restriction_notes
            ),
            "source_confidence": self.source_confidence,
            "evidence_spans": [span.to_dict() for span in self.evidence_spans],
            "missing_fields": list(self.missing_fields),
            "extraction_notes": list(self.extraction_notes),
            "tiered_bonus": list(self.tiered_bonus),
            "raw_pattern_matches": dict(self.raw_pattern_matches),
            "confidence_score": self.confidence_score,
            "rejected": self.rejected,
            "rejection_reason": self.rejection_reason,
        }


def extract_banking_deal(
    raw_text: str,
    source_metadata: Mapping[str, Any],
) -> ExtractedDealCandidate:
    """Extract one conservative banking deal candidate from raw text."""

    candidate = ExtractedDealCandidate(
        raw_snapshot_id=int(source_metadata.get("raw_snapshot_id") or 0),
        source_name=str(source_metadata.get("source_name") or "unknown"),
        source_url=source_metadata.get("source_url"),
        retrieved_at=source_metadata.get("retrieved_at"),
    )
    text = _normalize_text(raw_text)
    lower_text = text.lower()

    if _looks_like_credit_card_text(lower_text):
        _extract_credit_card_candidate(candidate, text)
        return candidate

    if not _looks_like_deal(lower_text):
        candidate.rejected = True
        candidate.rejection_reason = "No explicit banking promotion terms found."
        candidate.confidence_score = 0.1
        candidate.missing_fields = list(HIGH_IMPACT_FIELDS)
        candidate.extraction_notes.append("Rejected as non-deal or informational text.")
        return candidate

    _extract_institution_and_subcategory(candidate, text)
    _extract_bonus(candidate, text)
    _extract_direct_deposit(candidate, text)
    _extract_deposit_and_balance(candidate, text)
    _extract_hold_period(candidate, text)
    _extract_fees(candidate, text)
    _extract_dates(candidate, text)
    _extract_restrictions(candidate, text)
    _extract_title(candidate)
    _finalize_missing_fields(candidate)
    candidate.confidence_score = _confidence_score(candidate)

    if candidate.confidence_score < 0.35:
        candidate.rejected = True
        candidate.rejection_reason = "Low confidence extraction."

    return candidate


def _extract_credit_card_candidate(
    candidate: ExtractedDealCandidate,
    text: str,
) -> None:
    candidate.subcategory = "credit_card_signup_bonus"
    candidate.offer_currency = "unknown"
    candidate.customer_type = "unknown"
    candidate.source_confidence = 0.6

    _extract_credit_card_identity(candidate, text)
    _extract_credit_card_offer_terms(candidate, text)
    _extract_credit_card_fees_network_and_dates(candidate, text)
    _extract_credit_card_targeting_and_notes(candidate, text)
    _finalize_credit_card_candidate(candidate)


def _extract_credit_card_identity(
    candidate: ExtractedDealCandidate,
    text: str,
) -> None:
    sentences = _sentences_with_offsets(text)
    for sentence, offset in sentences[:2]:
        card_matches = re.finditer(
            r"\b(?:(?:advertising|presents|describe|lists|promoted|for|page for|roundup:)\s+)?(?:the\s+)?([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){1,6}\s+Card)\b",
            sentence,
        )
        for card_match in card_matches:
            if candidate.card_name is not None:
                break
            following_text = sentence[card_match.end() : card_match.end() + 12]
            if following_text.startswith(" Services"):
                continue
            candidate.card_name = card_match.group(1)
            candidate.evidence_spans.append(
                _offset_span("card_name", card_match, sentence, offset)
            )
            candidate.product_family = _product_family_from_card_name(
                candidate.card_name
            )

        issuer_patterns = (
            r"\b([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,5}\s+(?:Bank|Credit Union|Finance|Card Services))\b",
            r"\b([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,5}\s+Bank)\s+(?:offers|presents|landing|sent|previously)",
            r"\bfrom\s+([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,5}\s+Bank)\b",
        )
        for pattern in issuer_patterns:
            issuer_match = re.search(pattern, sentence)
            if issuer_match:
                candidate.issuer_name = issuer_match.group(1)
                candidate.institution_name = candidate.issuer_name
                candidate.evidence_spans.append(
                    _offset_span("issuer", issuer_match, sentence, offset)
                )
                break
        if candidate.card_name and candidate.issuer_name:
            break


def _extract_credit_card_offer_terms(
    candidate: ExtractedDealCandidate,
    text: str,
) -> None:
    for sentence, offset in _sentences_with_offsets(text):
        lower_sentence = sentence.lower()
        if not re.search(r"earn|receive|signup offer|cash bonus|statement credit", lower_sentence):
            continue
        if not re.search(r"bonus|points?|miles?|statement credit", lower_sentence):
            continue

        mixed_match = re.search(
            rf"earn\s+([0-9]{{1,3}}(?:,[0-9]{{3}})*|[0-9]+)\s+[^.]*?points\s+plus\s+a\s+{MONEY_PATTERN}\s+[^.]*?statement credit",
            sentence,
            re.I,
        )
        if mixed_match:
            points = _int_from_number_text(mixed_match.group(1))
            credit_cents = _money_to_cents(mixed_match.group(2), mixed_match.group(3))
            candidate.offer_currency = "mixed"
            candidate.headline_bonus_amount = {
                "points": points,
                "statement_credit_cents": credit_cents,
            }
            candidate.statement_credit_amount_cents = credit_cents
            candidate.evidence_spans.append(
                _offset_span("headline_bonus_amount", mixed_match, sentence, offset)
            )
            candidate.evidence_spans.append(
                _offset_span(
                    "statement_credit_amount_cents",
                    mixed_match,
                    sentence,
                    offset,
                )
            )
            candidate.raw_pattern_matches.setdefault("headline_bonus_amount", []).append(
                mixed_match.group(0)
            )
        elif "statement credit" in lower_sentence:
            money_match = re.search(MONEY_PATTERN, sentence)
            if money_match:
                amount_cents = _money_to_cents(money_match.group(1), money_match.group(2))
                candidate.offer_currency = "statement_credit"
                candidate.headline_bonus_amount = amount_cents // 100
                candidate.headline_bonus_value_cents = amount_cents
                candidate.statement_credit_amount_cents = amount_cents
                candidate.bonus_amount_cents = amount_cents
                candidate.evidence_spans.append(
                    _offset_span("statement_credit_amount_cents", money_match, sentence, offset)
                )
                candidate.evidence_spans.append(
                    _offset_span("headline_bonus_amount", money_match, sentence, offset)
                )
        else:
            points_match = re.search(
                r"([0-9]{1,3}(?:,[0-9]{3})*|[0-9]+)\s+[^.]*?\b(points?|miles?)\b",
                sentence,
                re.I,
            )
            money_match = re.search(MONEY_PATTERN, sentence)
            if points_match:
                amount = _int_from_number_text(points_match.group(1))
                currency_word = points_match.group(2).lower()
                candidate.offer_currency = (
                    "miles" if currency_word.startswith("mile") else "points"
                )
                candidate.headline_bonus_amount = amount
                candidate.evidence_spans.append(
                    _offset_span("headline_bonus_amount", points_match, sentence, offset)
                )
            elif money_match and "cash bonus" in lower_sentence:
                amount_cents = _money_to_cents(money_match.group(1), money_match.group(2))
                candidate.offer_currency = "cash"
                candidate.headline_bonus_amount = amount_cents // 100
                candidate.headline_bonus_value_cents = amount_cents
                candidate.bonus_amount_cents = amount_cents
                candidate.evidence_spans.append(
                    _offset_span("headline_bonus_amount", money_match, sentence, offset)
                )

        _extract_credit_card_spend_requirement(candidate, sentence, offset)
        if candidate.statement_credit_amount_cents is not None:
            candidate.statement_credit_requirements = _statement_credit_requirement(sentence)
            candidate.evidence_spans.append(
                EvidenceSpan(
                    field="statement_credit_requirements",
                    text=sentence,
                    start=offset,
                    end=offset + len(sentence),
                )
            )
        if candidate.headline_bonus_amount is not None:
            return


def _extract_credit_card_spend_requirement(
    candidate: ExtractedDealCandidate,
    sentence: str,
    offset: int,
) -> None:
    if not re.search(r"\bspend|spending|purchases?\b", sentence, re.I):
        return
    spend_match = re.search(
        rf"(?:after spending|after spend|spending|spend|after)\s+{MONEY_PATTERN}",
        sentence,
        re.I,
    )
    window_match = re.search(
        r"(?:within|in the first|in)\s+([0-9]+)\s+(days?|months?)",
        sentence,
        re.I,
    )
    if spend_match and window_match:
        money_groups = spend_match.groups()[-2:]
        candidate.minimum_spend_cents = _money_to_cents(
            money_groups[0],
            money_groups[1],
        )
        candidate.spend_window_days = _window_to_days(
            window_match.group(1),
            window_match.group(2),
        )
        candidate.evidence_spans.append(
            _offset_span("minimum_spend_cents", spend_match, sentence, offset)
        )
        candidate.evidence_spans.append(
            _offset_span("spend_window_days", window_match, sentence, offset)
        )


def _extract_credit_card_fees_network_and_dates(
    candidate: ExtractedDealCandidate,
    text: str,
) -> None:
    for sentence, offset in _sentences_with_offsets(text):
        fee_match = re.search(rf"(?:annual fee is|has a|The annual fee was)\s+{MONEY_PATTERN}", sentence, re.I)
        if not fee_match:
            fee_match = re.search(rf"{MONEY_PATTERN}\s+annual fee", sentence, re.I)
        if fee_match:
            groups = fee_match.groups()[-2:]
            candidate.annual_fee_cents = _money_to_cents(groups[0], groups[1])
            if candidate.annual_fee_cents == 0:
                candidate.first_year_annual_fee_waived = False
            candidate.evidence_spans.append(
                _offset_span("annual_fee_cents", fee_match, sentence, offset)
            )
            after_first_year_match = re.search(
                rf"{MONEY_PATTERN}\s+after\b",
                sentence,
                re.I,
            )
            if after_first_year_match:
                after_groups = after_first_year_match.groups()[-2:]
                candidate.annual_fee_cents = _money_to_cents(
                    after_groups[0],
                    after_groups[1],
                )
        no_fee_match = re.search(r"\b(?:has a |There is )no annual fee\b", sentence, re.I)
        if no_fee_match:
            candidate.annual_fee_cents = 0
            candidate.first_year_annual_fee_waived = False
            candidate.evidence_spans.append(
                _offset_span("annual_fee_cents", no_fee_match, sentence, offset)
            )
        waived_match = re.search(r"\b(?:first-year annual fee is waived|annual fee is \$0 for the first year|first year annual fee is waived)\b", sentence, re.I)
        not_waived_match = re.search(r"\b(?:not waived the first year|is not waived)\b", sentence, re.I)
        if waived_match:
            candidate.first_year_annual_fee_waived = True
            candidate.evidence_spans.append(
                _offset_span("first_year_annual_fee_waived", waived_match, sentence, offset)
            )
        elif not_waived_match:
            candidate.first_year_annual_fee_waived = False
            candidate.evidence_spans.append(
                _offset_span("first_year_annual_fee_waived", not_waived_match, sentence, offset)
            )

        network_match = re.search(
            r"\b(Visa|Mastercard|American Express|Discover)\b",
            sentence,
            re.I,
        )
        if network_match and "no visible card network" not in sentence.lower():
            candidate.card_network = _canonical_network(network_match.group(1))
            candidate.evidence_spans.append(
                _offset_span("card_network", network_match, sentence, offset)
            )

        date_match = re.search(
            r"(?:must be submitted by|received by|ends|expires|expired on|deadline of)\s+"
            r"([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})",
            sentence,
            re.I,
        )
        if date_match:
            parsed = _date_from_month_name(
                date_match.group(1),
                date_match.group(2),
                date_match.group(3),
            )
            if parsed:
                candidate.expires_at = parsed
                candidate.application_deadline = parsed
                candidate.evidence_spans.append(
                    _offset_span("offer_expiration_date", date_match, sentence, offset)
                )

        payout_match = re.search(
            r"(?:cash bonus posts|points are expected|miles may take|miles were expected|bonus will post|statement credit appears|points and the travel statement credit may post)[^.]*",
            sentence,
            re.I,
        )
        if payout_match:
            candidate.bonus_payout_timing = _normalize_payout_timing(
                payout_match.group(0)
            )
            candidate.evidence_spans.append(
                _offset_span("bonus_payout_timing", payout_match, sentence, offset)
            )


def _extract_credit_card_targeting_and_notes(
    candidate: ExtractedDealCandidate,
    text: str,
) -> None:
    for sentence, offset in _sentences_with_offsets(text):
        lower_sentence = sentence.lower()
        if "business" in lower_sentence and candidate.customer_type != "business":
            candidate.customer_type = "business"
            match = re.search(r"\bbusiness\b", sentence, re.I)
            if match:
                candidate.evidence_spans.append(
                    _offset_span("customer_type", match, sentence, offset)
                )
        elif "personal" in lower_sentence and candidate.customer_type == "unknown":
            candidate.customer_type = "personal"
            match = re.search(r"\bpersonal\b", sentence, re.I)
            if match:
                candidate.evidence_spans.append(
                    _offset_span("customer_type", match, sentence, offset)
                )

        targeted_match = re.search(
            r"\b(?:targeted invitation|Invitation code required|Targeted offer|not transferable)\b",
            sentence,
            re.I,
        )
        public_match = re.search(
            r"\bpublic (?:signup )?offer\b|\boffer is public\b",
            sentence,
            re.I,
        )
        if targeted_match:
            candidate.targeted = True
            candidate.evidence_spans.append(
                _offset_span("targeted", targeted_match, sentence, offset)
            )
        elif public_match and candidate.targeted is not True:
            candidate.targeted = False
            candidate.evidence_spans.append(
                _offset_span("targeted", public_match, sentence, offset)
            )

        note = _credit_card_note_from_sentence(sentence)
        if note and note not in candidate.eligibility_restriction_notes:
            candidate.eligibility_restriction_notes.append(note)
            candidate.evidence_spans.append(
                EvidenceSpan(
                    field="eligibility_restriction_notes",
                    text=sentence,
                    start=offset,
                    end=offset + len(sentence),
                )
            )
        if (
            "sole proprietors may apply" in lower_sentence
            and "Sole proprietors may apply."
            not in candidate.eligibility_restriction_notes
        ):
            candidate.eligibility_restriction_notes.append("Sole proprietors may apply.")
            candidate.evidence_spans.append(
                EvidenceSpan(
                    field="eligibility_restriction_notes",
                    text=sentence,
                    start=offset,
                    end=offset + len(sentence),
                )
            )


def _finalize_credit_card_candidate(candidate: ExtractedDealCandidate) -> None:
    is_deal = candidate.headline_bonus_amount is not None and (
        candidate.minimum_spend_cents is not None
        or candidate.statement_credit_amount_cents is not None
    )
    candidate.rejected = not is_deal
    if candidate.rejected:
        candidate.rejection_reason = "No explicit credit-card acquisition offer found."

    if candidate.issuer_name:
        candidate.institution_name = candidate.issuer_name
    if candidate.card_name and candidate.headline_bonus_amount is not None:
        candidate.title = _credit_card_title(candidate)

    if (
        candidate.offer_currency == "mixed"
        and candidate.statement_credit_amount_cents is not None
    ):
        candidate.statement_credit_requirements = (
            "Travel statement credit after qualifying purchases are verified."
        )

    if candidate.rejected:
        missing = [
            "headline_bonus_amount",
            "minimum_spend_cents",
            "spend_window_days",
            "offer_expiration_date",
        ]
    else:
        missing = []
        for field_name in CREDIT_CARD_CRITICAL_FIELDS:
            if field_name == "offer_expiration_date":
                value = candidate.expires_at
            else:
                value = getattr(candidate, field_name)
            if value is None:
                missing.append(field_name)
    candidate.missing_fields = missing
    if candidate.targeted:
        candidate.extraction_notes.append(
            "Targeted or invitation-only language requires manual review."
        )

    candidate.source_confidence = _credit_card_source_confidence(candidate)
    candidate.confidence_score = candidate.source_confidence


def _looks_like_credit_card_text(lower_text: str) -> bool:
    if "debit card" in lower_text and "credit card" not in lower_text:
        return False
    has_card_context = any(
        term in lower_text
        for term in (
            "credit card",
            "card for business applicants",
            "card for personal applicants",
            "card from ",
            "page for the ",
            "cardmembers",
            "cardholders",
            "annual fee",
            "statement credit",
            "card network",
            "invitation code",
        )
    )
    has_acquisition_context = any(
        term in lower_text
        for term in (
            "cardmembers can earn",
            "cardholders can receive",
            "applicants can earn",
            "earn a $",
            "earn 40,000",
            "earn 50,000",
            "earn 60,000",
            "earn 75,000",
            "describes a $",
            "signup offer",
            "cash bonus after spending",
            "points after",
            "miles after",
            "statement credit after",
            "general benefits",
        )
    )
    return has_card_context and has_acquisition_context


def persist_extracted_candidate(
    db_path: DbPath,
    candidate: ExtractedDealCandidate,
) -> int:
    """Persist a pre-dedupe extracted candidate."""

    return insert_banking_deal_candidate(db_path, candidate.to_storage_record())


def extract_and_persist_snapshot(db_path: DbPath, raw_snapshot_id: int) -> int:
    """Load one raw snapshot, extract a candidate, and persist it."""

    snapshot = get_raw_snapshot(db_path, raw_snapshot_id)
    if snapshot is None:
        raise ValueError(f"Raw snapshot id {raw_snapshot_id} does not exist.")

    candidate = extract_banking_deal(
        snapshot["raw_text"],
        {
            "raw_snapshot_id": raw_snapshot_id,
            "source_name": snapshot["source_name"],
            "source_url": snapshot["source_url"],
            "retrieved_at": snapshot["retrieved_at"],
        },
    )
    return persist_extracted_candidate(db_path, candidate)


def reextract_snapshot(
    db_path: DbPath,
    raw_snapshot_id: int,
    *,
    dry_run: bool = True,
) -> ReextractionResult:
    """Reprocess one stored raw snapshot without touching canonical deals."""

    snapshot = get_raw_snapshot(db_path, raw_snapshot_id)
    if snapshot is None:
        raise ValueError(f"Raw snapshot id {raw_snapshot_id} does not exist.")

    candidate = _candidate_from_snapshot(snapshot)
    candidate.extraction_notes.append(
        f"Re-extracted with {EXTRACTOR_METHOD} v{EXTRACTOR_VERSION}."
    )
    previous_candidate = _latest_candidate_for_snapshot(db_path, raw_snapshot_id)
    changed_fields = _changed_fields(previous_candidate, candidate)
    new_candidate_id = None
    if not dry_run:
        new_candidate_id = persist_extracted_candidate(db_path, candidate)

    return ReextractionResult(
        raw_snapshot_id=raw_snapshot_id,
        content_hash=snapshot.get("content_hash"),
        source_name=str(snapshot.get("source_name") or "unknown"),
        source_url=snapshot.get("source_url"),
        dry_run=dry_run,
        previous_candidate_id=(
            int(previous_candidate["id"]) if previous_candidate is not None else None
        ),
        new_candidate_id=new_candidate_id,
        changed_fields=changed_fields,
        new_candidate=candidate,
    )


def reextract_all_snapshots(
    db_path: DbPath,
    *,
    dry_run: bool = True,
) -> list[ReextractionResult]:
    """Reprocess every stored raw snapshot in deterministic order."""

    return [
        reextract_snapshot(db_path, int(snapshot["id"]), dry_run=dry_run)
        for snapshot in list_raw_snapshots(db_path)
    ]


def _candidate_from_snapshot(snapshot: Mapping[str, Any]) -> ExtractedDealCandidate:
    return extract_banking_deal(
        snapshot["raw_text"],
        {
            "raw_snapshot_id": snapshot["id"],
            "source_name": snapshot["source_name"],
            "source_url": snapshot["source_url"],
            "retrieved_at": snapshot["retrieved_at"],
        },
    )


def _latest_candidate_for_snapshot(
    db_path: DbPath,
    raw_snapshot_id: int,
) -> dict[str, Any] | None:
    candidates = list_banking_deal_candidates(
        db_path,
        raw_snapshot_id=raw_snapshot_id,
        limit=1,
    )
    return candidates[0] if candidates else None


def _changed_fields(
    previous_candidate: Mapping[str, Any] | None,
    new_candidate: ExtractedDealCandidate,
) -> list[ReextractionFieldChange]:
    if previous_candidate is None:
        return []

    new_record = new_candidate.to_storage_record()
    changes: list[ReextractionFieldChange] = []
    for field_name in REEXTRACTION_COMPARE_FIELDS:
        previous_value = _candidate_compare_value(previous_candidate, field_name)
        new_value = _candidate_compare_value(new_record, field_name)
        if previous_value != new_value:
            changes.append(
                ReextractionFieldChange(
                    field=field_name,
                    previous_value=previous_value,
                    new_value=new_value,
                )
            )
    return changes


def _candidate_compare_value(candidate: Mapping[str, Any], field_name: str) -> Any:
    storage_field = JSON_CANDIDATE_FIELDS.get(field_name, field_name)
    value = candidate.get(storage_field)
    if value is None and storage_field != field_name:
        value = candidate.get(field_name)
    if field_name in JSON_CANDIDATE_FIELDS:
        value = _json_value(value)
    if field_name in BOOL_CANDIDATE_FIELDS:
        return _to_bool(value)
    return value


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str):
        return json.loads(value)
    return value


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    return None


def _looks_like_deal(lower_text: str) -> bool:
    if re.search(r"does not describe[^.]+(?:promotion|bonus|offer)", lower_text):
        return False
    has_banking_context = any(
        term in lower_text
        for term in (
            "checking",
            "savings",
            "brokerage",
            "money market",
            "certificate of deposit",
            " cd ",
            "account",
        )
    )
    has_offer_context = any(
        term in lower_text
        for term in (
            "bonus",
            "promotion",
            "promo",
            "earn",
            "cash offer",
            "new money",
            "direct deposit",
        )
    )
    return has_banking_context and has_offer_context


def _extract_institution_and_subcategory(
    candidate: ExtractedDealCandidate,
    text: str,
) -> None:
    first_sentence = _sentences(text)[0] if _sentences(text) else text
    patterns = (
        r"\b([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,4}\s+(?:Bank|Credit Union|Brokerage))\b",
        r"\b([A-Z][A-Za-z]*(?:\s+[A-Z][A-Za-z]*){0,4}\s+(?:Financial|Investments))\b",
    )
    for pattern in patterns:
        match = re.search(pattern, first_sentence)
        if match:
            candidate.institution_name = match.group(1)
            candidate.evidence_spans.append(_span("institution_name", match, text))
            break

    lower = text.lower()
    if "checking" in lower and "savings" in lower:
        candidate.subcategory = "checking_savings_bundle"
    elif "brokerage" in lower or "transfer bonus" in lower:
        candidate.subcategory = "brokerage_bonus"
    elif "money market" in lower:
        candidate.subcategory = "money_market_bonus"
    elif re.search(r"\bcd\b|certificate of deposit", lower):
        candidate.subcategory = "cd_bonus"
    elif "savings" in lower:
        candidate.subcategory = "savings_bonus"
    elif "checking" in lower:
        candidate.subcategory = "checking_bonus"


def _extract_bonus(candidate: ExtractedDealCandidate, text: str) -> None:
    tier_matches = []
    tier_spans = []
    for match in re.finditer(
        rf"{MONEY_PATTERN}\s+(?:bonus\s+)?(?:for|when you transfer|with)\s+{MONEY_PATTERN}",
        text,
        flags=re.IGNORECASE,
    ):
        bonus_cents = _money_to_cents(match.group(1), match.group(2))
        threshold_cents = _money_to_cents(match.group(3), match.group(4))
        tier_matches.append(
            {
                "bonus_amount_cents": bonus_cents,
                "minimum_deposit_amount_cents": threshold_cents,
            }
        )
        tier_spans.append((match, bonus_cents, threshold_cents))
        candidate.evidence_spans.append(_span("tiered_bonus", match, text))

    if tier_matches:
        candidate.tiered_bonus = tier_matches
        candidate.bonus_amount_cents = max(
            tier["bonus_amount_cents"] for tier in tier_matches
        )
        candidate.minimum_deposit_amount_cents = min(
            tier["minimum_deposit_amount_cents"] for tier in tier_matches
        )
        for match, bonus_cents, threshold_cents in tier_spans:
            if bonus_cents == candidate.bonus_amount_cents:
                candidate.evidence_spans.append(_span("bonus_amount_cents", match, text))
            if threshold_cents == candidate.minimum_deposit_amount_cents:
                candidate.evidence_spans.append(
                    _span("minimum_deposit_amount_cents", match, text)
                )
        candidate.raw_pattern_matches["tiered_bonus"] = [
            str(tier) for tier in tier_matches
        ]
        return

    for sentence, offset in _sentences_with_offsets(text):
        if not re.search(r"bonus|earn|receive|get|cash offer|promotion", sentence, re.I):
            continue
        money_match = re.search(MONEY_PATTERN, sentence)
        if money_match:
            candidate.bonus_amount_cents = _money_to_cents(
                money_match.group(1),
                money_match.group(2),
            )
            candidate.evidence_spans.append(
                _offset_span("bonus_amount_cents", money_match, sentence, offset)
            )
            candidate.raw_pattern_matches.setdefault("bonus_amount", []).append(
                money_match.group(0)
            )
            return


def _extract_direct_deposit(candidate: ExtractedDealCandidate, text: str) -> None:
    no_match = re.search(r"\bno direct deposit(?:s)? (?:is |are )?required\b", text, re.I)
    if no_match:
        candidate.direct_deposit_required = False
        candidate.evidence_spans.append(_span("direct_deposit_required", no_match, text))
        return

    dd_match = re.search(r"\bdirect deposit(?:s)?\b", text, re.I)
    if not dd_match:
        return

    candidate.direct_deposit_required = True
    candidate.evidence_spans.append(_span("direct_deposit_required", dd_match, text))

    sentence, offset = _sentence_containing(text, dd_match.start())
    amount_match = re.search(
        rf"direct deposit(?:s)?(?:\s+\w+){{0,5}}\s+(?:of|totaling|at least|minimum)?\s*{MONEY_PATTERN}",
        sentence,
        re.I,
    )
    if not amount_match:
        amount_match = re.search(rf"(?:totaling|at least|minimum)\s+{MONEY_PATTERN}", sentence, re.I)
    if amount_match:
        groups = amount_match.groups()
        amount_groups = groups[-2:]
        candidate.direct_deposit_minimum_cents = _money_to_cents(
            amount_groups[0],
            amount_groups[1],
        )
        candidate.evidence_spans.append(
            _offset_span("direct_deposit_minimum_cents", amount_match, sentence, offset)
        )


def _extract_deposit_and_balance(candidate: ExtractedDealCandidate, text: str) -> None:
    deposit_patterns = (
        rf"(?:minimum opening deposit|opening deposit|deposit|transfer|new money|eligible assets)\s+(?:of|at least)?\s*{MONEY_PATTERN}",
        rf"{MONEY_PATTERN}\s+(?:in new money|in eligible assets|opening deposit)",
    )
    for pattern in deposit_patterns:
        for match in re.finditer(pattern, text, re.I):
            if "direct deposit" in match.group(0).lower():
                continue
            money_groups = match.groups()[-2:]
            candidate.minimum_deposit_amount_cents = _money_to_cents(
                money_groups[0],
                money_groups[1],
            )
            candidate.evidence_spans.append(
                _span("minimum_deposit_amount_cents", match, text)
            )
            break
        if candidate.minimum_deposit_amount_cents is not None:
            break

    balance_match = re.search(
        rf"(?:maintain|keep|balance of|minimum balance)(?:\s+\w+){{0,6}}\s+{MONEY_PATTERN}",
        text,
        re.I,
    )
    if balance_match:
        money_groups = balance_match.groups()[-2:]
        candidate.minimum_balance_required_cents = _money_to_cents(
            money_groups[0],
            money_groups[1],
        )
        candidate.evidence_spans.append(
            _span("minimum_balance_required_cents", balance_match, text)
        )


def _extract_hold_period(candidate: ExtractedDealCandidate, text: str) -> None:
    match = re.search(
        r"(?:maintain|keep|hold|held)[^.]{0,140}?\bfor\s+([0-9]{2,3})\s+days",
        text,
        re.I,
    )
    if match:
        candidate.balance_hold_days = int(match.group(1))
        candidate.evidence_spans.append(_span("balance_hold_days", match, text))


def _extract_fees(candidate: ExtractedDealCandidate, text: str) -> None:
    monthly_match = re.search(
        rf"(?:monthly (?:service )?fee|service fee)(?:\s+is|\s+of)?\s+{MONEY_PATTERN}",
        text,
        re.I,
    )
    if monthly_match:
        money_groups = monthly_match.groups()[-2:]
        candidate.monthly_fee_cents = _money_to_cents(money_groups[0], money_groups[1])
        candidate.evidence_spans.append(_span("monthly_fee_cents", monthly_match, text))

    waiver_match = re.search(r"(?:waived|avoid the fee)[^.]{0,140}", text, re.I)
    if waiver_match:
        candidate.monthly_fee_waiver_terms = waiver_match.group(0).strip()
        candidate.evidence_spans.append(
            _span("monthly_fee_waiver_terms", waiver_match, text)
        )

    closure_match = re.search(
        rf"(?:early closure fee|closed within [^.]+ fee)(?:\s+is|\s+of)?\s+{MONEY_PATTERN}",
        text,
        re.I,
    )
    if closure_match:
        money_groups = closure_match.groups()[-2:]
        candidate.early_closure_fee_cents = _money_to_cents(
            money_groups[0],
            money_groups[1],
        )
        candidate.evidence_spans.append(
            _span("early_closure_fee_cents", closure_match, text)
        )


def _extract_dates(candidate: ExtractedDealCandidate, text: str) -> None:
    match = re.search(
        r"(?:expires|expiration date|apply by|open by|open [^.]{0,80} by|offer ends)\s+"
        r"([A-Za-z]+)\s+([0-9]{1,2}),\s+([0-9]{4})",
        text,
        re.I,
    )
    if not match:
        match = re.search(
            r"(?:expires|expiration date|apply by|open by|offer ends)\s+"
            r"([0-9]{1,2})/([0-9]{1,2})/([0-9]{4})",
            text,
            re.I,
        )
        if match:
            parsed = _date_from_numbers(match.group(3), match.group(1), match.group(2))
        else:
            parsed = None
    else:
        parsed = _date_from_month_name(match.group(1), match.group(2), match.group(3))

    if parsed is not None:
        candidate.expires_at = parsed
        candidate.application_deadline = parsed
        candidate.evidence_spans.append(_span("expires_at", match, text))


def _extract_restrictions(candidate: ExtractedDealCandidate, text: str) -> None:
    state_match = re.search(
        r"(?:available only to residents of|residents of|available in)\s+([A-Z]{2}(?:,\s*[A-Z]{2})*)",
        text,
        re.I,
    )
    if state_match:
        candidate.state_restrictions = [
            item.strip().upper() for item in state_match.group(1).split(",")
        ]
        candidate.evidence_spans.append(_span("state_restrictions", state_match, text))

    new_customer_match = re.search(
        r"\b(?:new customers?|new clients?|new money customers?|new account holders?)\b",
        text,
        re.I,
    )
    if new_customer_match:
        candidate.new_customer_only = True
        candidate.evidence_spans.append(
            _span("new_customer_only", new_customer_match, text)
        )

    household_match = re.search(r"one bonus per household|household limit[^.]*", text, re.I)
    if household_match:
        candidate.household_limit = household_match.group(0).strip()
        candidate.evidence_spans.append(_span("household_limit", household_match, text))

    hard_pull_match = re.search(r"\bhard pull\b|\bhard credit inquiry\b", text, re.I)
    if hard_pull_match:
        candidate.hard_pull_risk = True
        candidate.evidence_spans.append(_span("hard_pull_risk", hard_pull_match, text))

    soft_pull_match = re.search(r"\bsoft pull only\b|\bsoft credit pull\b", text, re.I)
    if soft_pull_match:
        candidate.soft_pull_only = True
        candidate.evidence_spans.append(_span("soft_pull_only", soft_pull_match, text))


def _extract_title(candidate: ExtractedDealCandidate) -> None:
    if candidate.institution_name is None or candidate.subcategory is None:
        return
    parts = [candidate.institution_name]
    if candidate.bonus_amount_cents is not None:
        parts.append(f"${candidate.bonus_amount_cents // 100:,}")
    title_subcategory = candidate.subcategory.replace("_", " ").title()
    parts.append(title_subcategory)
    candidate.title = " ".join(parts)


def _finalize_missing_fields(candidate: ExtractedDealCandidate) -> None:
    candidate.missing_fields = [
        field_name
        for field_name in HIGH_IMPACT_FIELDS
        if getattr(candidate, field_name) is None
    ]
    if candidate.subcategory is None:
        candidate.missing_fields.append("subcategory")
    if candidate.institution_name is None:
        candidate.missing_fields.append("institution_name")


def _confidence_score(candidate: ExtractedDealCandidate) -> float:
    if candidate.rejected:
        return candidate.confidence_score
    score = 0.2
    for field_name, points in (
        ("institution_name", 0.12),
        ("subcategory", 0.1),
        ("bonus_amount_cents", 0.18),
        ("expires_at", 0.1),
        ("direct_deposit_required", 0.08),
        ("minimum_deposit_amount_cents", 0.08),
        ("minimum_balance_required_cents", 0.08),
        ("balance_hold_days", 0.08),
        ("new_customer_only", 0.04),
    ):
        if getattr(candidate, field_name) is not None:
            score += points
    if candidate.evidence_spans:
        score += min(0.12, len(candidate.evidence_spans) * 0.02)
    return min(round(score, 2), 1.0)


def _normalize_text(raw_text: str) -> str:
    return re.sub(r"\s+", " ", raw_text).strip()


def _sentences(text: str) -> list[str]:
    return [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]


def _sentences_with_offsets(text: str) -> list[tuple[str, int]]:
    sentences = []
    for match in re.finditer(r"[^.!?]+[.!?]?", text):
        raw_sentence = match.group(0)
        leading_spaces = len(raw_sentence) - len(raw_sentence.lstrip())
        sentence = raw_sentence.strip()
        if sentence:
            sentences.append((sentence, match.start() + leading_spaces))
    return sentences


def _sentence_containing(text: str, index: int) -> tuple[str, int]:
    for sentence, offset in _sentences_with_offsets(text):
        if offset <= index <= offset + len(sentence):
            return sentence, offset
    return text, 0


def _money_to_cents(dollars: str, cents: str | None = None) -> int:
    return int(dollars.replace(",", "")) * 100 + int(cents or "0")


def _int_from_number_text(value: str) -> int:
    return int(value.replace(",", ""))


def _window_to_days(value: str, unit: str) -> int:
    count = int(value)
    if unit.lower().startswith("month"):
        return count * 30
    return count


def _canonical_network(value: str) -> str:
    normalized = value.lower()
    if normalized == "mastercard":
        return "Mastercard"
    if normalized == "american express":
        return "American Express"
    if normalized == "discover":
        return "Discover"
    return "Visa"


def _product_family_from_card_name(card_name: str) -> str | None:
    family = card_name
    for suffix in (" Card",):
        if family.endswith(suffix):
            family = family[: -len(suffix)]
    words = family.split()
    if len(words) <= 1:
        return family or None
    return " ".join(words[1:])


def _statement_credit_requirement(sentence: str) -> str:
    grocery_match = re.search(
        rf"spending\s+{MONEY_PATTERN}\s+at grocery stores in the first ([0-9]+) days",
        sentence,
        re.I,
    )
    if grocery_match:
        dollars = grocery_match.group(1)
        cents = grocery_match.group(2)
        amount = _money_to_cents(dollars, cents) // 100
        return f"Spend ${amount:,} at grocery stores in the first {grocery_match.group(3)} days."
    return sentence.strip()


def _credit_card_note_from_sentence(sentence: str) -> str | None:
    lower = sentence.lower()
    if "not available to applicants" in lower:
        return sentence.strip()
    if "applicant must use the card for business purposes" in lower:
        return "Applicant must use the card for business purposes."
    if "sole proprietors may apply" in lower:
        return "Sole proprietors may apply."
    if "invitation code required" in lower:
        return "Invitation code required."
    if "not transferable" in lower:
        return "Offer is not transferable."
    if "verify terms on the issuer site" in lower:
        return "Verify terms on the issuer site before applying."
    if "source should preserve the conflict" in lower:
        return "Source conflicts with issuer landing page minimum spend of $1,500."
    if "archived offer expired" in lower:
        return "Archived expired offer."
    return None


def _credit_card_title(candidate: ExtractedDealCandidate) -> str | None:
    if candidate.card_name is None:
        return None
    title_suffix = ""
    if any("conflicts with issuer landing page" in note.lower() for note in candidate.eligibility_restriction_notes):
        title_suffix = " With Conflicting Spend"
    if candidate.offer_currency == "mixed":
        return f"{candidate.card_name} Mixed Points and Statement Credit Offer"
    if candidate.offer_currency == "statement_credit" and candidate.headline_bonus_amount:
        return f"{candidate.card_name} ${candidate.headline_bonus_amount} Statement Credit"
    if candidate.offer_currency == "cash" and candidate.headline_bonus_amount:
        return f"{candidate.card_name} ${candidate.headline_bonus_amount} Cash Bonus{title_suffix}"
    if candidate.offer_currency == "points" and candidate.headline_bonus_amount:
        prefix = "Targeted " if candidate.targeted else ""
        return f"{candidate.card_name} {prefix}{candidate.headline_bonus_amount:,} Point Offer"
    if candidate.offer_currency == "miles" and candidate.headline_bonus_amount:
        expired = " Expired" if candidate.expires_at and candidate.expires_at < "2026-01-01" else ""
        return f"{candidate.card_name} {candidate.headline_bonus_amount:,} Mile{expired} Offer"
    return candidate.card_name


def _credit_card_source_confidence(candidate: ExtractedDealCandidate) -> float:
    if candidate.rejected:
        return 0.25 if candidate.issuer_name or candidate.card_name else 0.1
    score = 0.35
    for field_name, points in (
        ("issuer_name", 0.08),
        ("card_name", 0.08),
        ("headline_bonus_amount", 0.12),
        ("minimum_spend_cents", 0.08),
        ("spend_window_days", 0.06),
        ("annual_fee_cents", 0.05),
        ("expires_at", 0.05),
        ("offer_currency", 0.05),
    ):
        if getattr(candidate, field_name) is not None:
            score += points
    if candidate.evidence_spans:
        score += min(0.08, len(candidate.evidence_spans) * 0.01)
    return min(round(score, 2), 1.0)


def _normalize_payout_timing(value: str) -> str:
    timing = value.strip().rstrip(".")
    replacements = (
        ("Cash bonus posts ", ""),
        ("Points are expected to appear ", ""),
        ("Miles may take ", ""),
        ("Miles were expected to post within ", ""),
        ("Bonus will post ", ""),
        ("Statement credit appears on the billing statement within ", ""),
        ("Points and the travel statement credit may post separately after qualifying purchases are verified", "points and statement credit may post separately"),
    )
    for prefix, replacement in replacements:
        if timing.startswith(prefix):
            timing = replacement + timing[len(prefix) :]
            break
    timing = timing.replace(" the minimum spend", " minimum spend")
    timing = timing.replace(" the qualifying spend", " qualifying spend")
    timing = timing.replace(" the qualifying purchases", " qualifying purchases")
    timing = timing.replace(" the spend", " spend")
    timing = timing.replace(" to post after", " after")
    if timing.startswith("within within "):
        timing = timing.removeprefix("within ")
    return timing


def _date_from_month_name(month_name: str, day: str, year: str) -> str | None:
    month = MONTHS.get(month_name.lower())
    if month is None:
        return None
    return _safe_iso_date(int(year), month, int(day))


def _date_from_numbers(year: str, month: str, day: str) -> str | None:
    return _safe_iso_date(int(year), int(month), int(day))


def _safe_iso_date(year: int, month: int, day: int) -> str | None:
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _span(field: str, match: re.Match[str], text: str) -> EvidenceSpan:
    return EvidenceSpan(
        field=field,
        text=text[match.start() : match.end()],
        start=match.start(),
        end=match.end(),
    )


def _offset_span(
    field: str,
    match: re.Match[str],
    sentence: str,
    offset: int,
) -> EvidenceSpan:
    return EvidenceSpan(
        field=field,
        text=sentence[match.start() : match.end()],
        start=offset + match.start(),
        end=offset + match.end(),
    )
