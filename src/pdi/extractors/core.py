"""Deterministic banking deal extraction from raw snapshots."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Mapping

from pdi.storage import (
    get_raw_snapshot,
    insert_banking_deal_candidate,
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
        candidate.evidence_spans.append(_span("tiered_bonus", match, text))

    if tier_matches:
        candidate.tiered_bonus = tier_matches
        candidate.bonus_amount_cents = max(
            tier["bonus_amount_cents"] for tier in tier_matches
        )
        candidate.minimum_deposit_amount_cents = min(
            tier["minimum_deposit_amount_cents"] for tier in tier_matches
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
