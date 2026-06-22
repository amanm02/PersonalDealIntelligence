"""Transparent expected-value scoring for canonical banking deals."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

import yaml

from pdi.storage import (
    get_banking_deal,
    insert_banking_score_record,
    list_deal_change_events,
    update_banking_deal,
)


DbPath = str | Path
CONFIG_DEFAULT_PATH = Path("config/banking_scoring.yaml")
CHECKING_SUBCATEGORIES = {"checking_bonus", "checking_savings_bundle"}
SCORING_VERSION = "banking-scoring-v1"


@dataclass(frozen=True)
class ScoringConfig:
    """Validated scoring assumptions."""

    annual_opportunity_cost_rate: float
    default_hold_period_days: int
    default_fee_exposure_months: int
    minimum_net_value_review_cents: int
    unclear_terms_penalty_cents: int
    score_thresholds: dict[str, int]
    expiration_urgency: dict[str, int]
    hassle_penalties_cents: dict[str, int]
    risk_penalties_cents: dict[str, int]
    missing_data_penalties_cents: dict[str, int]


@dataclass(frozen=True)
class BankingScore:
    """Component-level expected-value score for one canonical banking deal."""

    deal_id: int
    gross_bonus_value: int
    estimated_fee_cost: int
    estimated_cash_lockup_cost: int
    estimated_hassle_penalty: int
    estimated_risk_penalty: int
    estimated_net_value: int
    score_0_to_100: int
    score_band: str
    recommended_action: str
    score_explanation: str
    missing_data_warnings: list[str]
    expiration_urgency: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "deal_id": self.deal_id,
            "gross_bonus_value": self.gross_bonus_value,
            "estimated_fee_cost": self.estimated_fee_cost,
            "estimated_cash_lockup_cost": self.estimated_cash_lockup_cost,
            "estimated_hassle_penalty": self.estimated_hassle_penalty,
            "estimated_risk_penalty": self.estimated_risk_penalty,
            "estimated_net_value": self.estimated_net_value,
            "score_0_to_100": self.score_0_to_100,
            "score_band": self.score_band,
            "recommended_action": self.recommended_action,
            "score_explanation": self.score_explanation,
            "missing_data_warnings": list(self.missing_data_warnings),
            "expiration_urgency": self.expiration_urgency,
        }


class ScoringConfigError(ValueError):
    """Raised when scoring config is invalid."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def load_scoring_config(config_path: str | Path = CONFIG_DEFAULT_PATH) -> ScoringConfig:
    """Load and validate scoring assumptions from YAML."""

    path = Path(config_path)
    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_scoring_config(raw_config)


def validate_scoring_config(raw_config: Any) -> ScoringConfig:
    """Validate a parsed scoring config and return typed assumptions."""

    errors: list[str] = []
    if not isinstance(raw_config, Mapping):
        raise ScoringConfigError(["scoring config must be a mapping"])

    required_fields = {
        "annual_opportunity_cost_rate",
        "default_hold_period_days",
        "default_fee_exposure_months",
        "minimum_net_value_review_cents",
        "unclear_terms_penalty_cents",
        "score_thresholds",
        "expiration_urgency",
        "hassle_penalties_cents",
        "risk_penalties_cents",
        "missing_data_penalties_cents",
    }
    unknown_fields = set(raw_config) - required_fields
    for field in sorted(unknown_fields):
        errors.append(f"unknown top-level field: {field}")
    for field in sorted(required_fields - set(raw_config)):
        errors.append(f"missing required field: {field}")
    if errors:
        raise ScoringConfigError(errors)

    errors.extend(_validate_rate(raw_config, "annual_opportunity_cost_rate"))
    for field in (
        "default_hold_period_days",
        "default_fee_exposure_months",
        "minimum_net_value_review_cents",
        "unclear_terms_penalty_cents",
    ):
        errors.extend(_validate_non_negative_int(raw_config, field))

    errors.extend(_validate_thresholds(raw_config["score_thresholds"]))
    errors.extend(_validate_named_ints(raw_config, "expiration_urgency"))
    errors.extend(_validate_named_ints(raw_config, "hassle_penalties_cents"))
    errors.extend(_validate_named_ints(raw_config, "risk_penalties_cents"))
    errors.extend(_validate_named_ints(raw_config, "missing_data_penalties_cents"))
    if errors:
        raise ScoringConfigError(errors)

    return ScoringConfig(
        annual_opportunity_cost_rate=float(raw_config["annual_opportunity_cost_rate"]),
        default_hold_period_days=int(raw_config["default_hold_period_days"]),
        default_fee_exposure_months=int(raw_config["default_fee_exposure_months"]),
        minimum_net_value_review_cents=int(
            raw_config["minimum_net_value_review_cents"]
        ),
        unclear_terms_penalty_cents=int(raw_config["unclear_terms_penalty_cents"]),
        score_thresholds=dict(raw_config["score_thresholds"]),
        expiration_urgency=dict(raw_config["expiration_urgency"]),
        hassle_penalties_cents=dict(raw_config["hassle_penalties_cents"]),
        risk_penalties_cents=dict(raw_config["risk_penalties_cents"]),
        missing_data_penalties_cents=dict(
            raw_config["missing_data_penalties_cents"]
        ),
    )


def scoring_config_hash(config: ScoringConfig) -> str:
    """Return a stable content hash for validated scoring assumptions."""

    payload = json.dumps(asdict(config), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def score_banking_deal(
    db_path: DbPath,
    deal_id: int,
    *,
    config: ScoringConfig | None = None,
    config_path: str | Path = CONFIG_DEFAULT_PATH,
    as_of: date | None = None,
) -> BankingScore:
    """Score one stored canonical banking deal."""

    deal = get_banking_deal(db_path, deal_id)
    if deal is None:
        raise ValueError(f"Deal id {deal_id} does not exist.")
    change_events = list_deal_change_events(db_path, deal_id=deal_id)
    return score_banking_deal_record(
        deal,
        config=config or load_scoring_config(config_path),
        as_of=as_of,
        change_events=change_events,
    )


def persist_banking_deal_score(
    db_path: DbPath,
    deal_id: int,
    *,
    config: ScoringConfig | None = None,
    config_path: str | Path = CONFIG_DEFAULT_PATH,
    as_of: date | None = None,
    banking_run_id: int | None = None,
) -> BankingScore:
    """Score a deal and persist latest summary plus durable score history."""

    resolved_config = config or load_scoring_config(config_path)
    resolved_as_of = as_of or date.today()
    score = score_banking_deal(
        db_path,
        deal_id,
        config=resolved_config,
        config_path=config_path,
        as_of=resolved_as_of,
    )
    insert_banking_score_record(
        db_path,
        {
            "deal_id": deal_id,
            "banking_run_id": banking_run_id,
            "scoring_version": SCORING_VERSION,
            "scoring_config_hash": scoring_config_hash(resolved_config),
            "scored_as_of": resolved_as_of.isoformat(),
            "estimated_net_value_cents": score.estimated_net_value,
            "score_0_to_100": score.score_0_to_100,
            "score_band": score.score_band,
            "recommended_action": score.recommended_action,
            "score_components": _score_components(score),
            "missing_data_warnings": score.missing_data_warnings,
            "score_explanation": score.score_explanation,
            "expiration_urgency": score.expiration_urgency,
        },
    )
    update_banking_deal(
        db_path,
        deal_id,
        {"estimated_net_value_cents": score.estimated_net_value},
    )
    return score


def _score_components(score: BankingScore) -> dict[str, int]:
    return {
        "gross_bonus_value": score.gross_bonus_value,
        "estimated_fee_cost": score.estimated_fee_cost,
        "estimated_cash_lockup_cost": score.estimated_cash_lockup_cost,
        "estimated_hassle_penalty": score.estimated_hassle_penalty,
        "estimated_risk_penalty": score.estimated_risk_penalty,
    }


def score_banking_deal_record(
    deal: Mapping[str, Any],
    *,
    config: ScoringConfig,
    as_of: date | None = None,
    change_events: list[Mapping[str, Any]] | None = None,
) -> BankingScore:
    """Score one canonical banking deal mapping with nested terms."""

    as_of = as_of or date.today()
    terms = deal.get("terms") or {}
    warnings = _missing_data_warnings(deal, terms)
    expiration_state, expiration_boost = _expiration_state(
        deal.get("expires_at"),
        as_of,
        config,
    )

    gross_bonus = int(deal.get("bonus_amount_cents") or 0)
    fee_cost = _fee_cost(terms, config)
    cash_lockup_cost = _cash_lockup_cost(terms, config, warnings)
    hassle_penalty = _hassle_penalty(deal, terms, config)
    risk_penalty = _risk_penalty(deal, terms, config, warnings)
    net_value = gross_bonus - fee_cost - cash_lockup_cost - hassle_penalty - risk_penalty

    has_conflict = _has_conflict(change_events or [])
    if expiration_state == "expired":
        score_value = 0
    else:
        score_value = _score_value(gross_bonus, net_value, expiration_boost, config)

    score_band = _score_band(score_value, expiration_state, config)
    recommended_action = _recommended_action(
        score_value,
        net_value,
        expiration_state,
        has_conflict,
        warnings,
        config,
    )
    explanation = _explanation(
        deal,
        gross_bonus,
        fee_cost,
        cash_lockup_cost,
        hassle_penalty,
        risk_penalty,
        net_value,
        expiration_state,
    )

    return BankingScore(
        deal_id=int(deal["id"]),
        gross_bonus_value=gross_bonus,
        estimated_fee_cost=fee_cost,
        estimated_cash_lockup_cost=cash_lockup_cost,
        estimated_hassle_penalty=hassle_penalty,
        estimated_risk_penalty=risk_penalty,
        estimated_net_value=net_value,
        score_0_to_100=score_value,
        score_band=score_band,
        recommended_action=recommended_action,
        score_explanation=explanation,
        missing_data_warnings=warnings,
        expiration_urgency=expiration_state,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pdi.scoring")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate banking scoring config.",
    )
    validate_parser.add_argument(
        "--config",
        default=str(CONFIG_DEFAULT_PATH),
        help="Path to banking scoring YAML.",
    )

    args = parser.parse_args(argv)
    if args.command == "validate":
        try:
            load_scoring_config(args.config)
        except ScoringConfigError as error:
            for message in error.errors:
                print(f"ERROR: {message}")
            return 1

        print(f"Validated scoring config from {args.config}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _fee_cost(terms: Mapping[str, Any], config: ScoringConfig) -> int:
    monthly_fee = terms.get("monthly_fee_cents")
    if monthly_fee is None:
        return 0
    return int(monthly_fee) * config.default_fee_exposure_months


def _cash_lockup_cost(
    terms: Mapping[str, Any],
    config: ScoringConfig,
    warnings: list[str],
) -> int:
    principal = max(
        int(terms.get("minimum_balance_required_cents") or 0),
        int(terms.get("minimum_deposit_amount_cents") or 0),
    )
    if principal <= 0:
        return 0

    hold_days = terms.get("balance_hold_days")
    if hold_days is None:
        hold_days = config.default_hold_period_days
        warning = (
            "balance_hold_days missing; used default "
            f"{config.default_hold_period_days} days"
        )
        if warning not in warnings:
            warnings.append(warning)

    return int(
        round(
            principal
            * config.annual_opportunity_cost_rate
            * (int(hold_days) / 365)
        )
    )


def _hassle_penalty(
    deal: Mapping[str, Any],
    terms: Mapping[str, Any],
    config: ScoringConfig,
) -> int:
    subcategory = str(deal.get("subcategory") or "")
    penalty = int(config.hassle_penalties_cents.get(subcategory, 0))
    direct_deposit_required = _to_bool(terms.get("direct_deposit_required"))
    if direct_deposit_required is True:
        penalty += int(config.hassle_penalties_cents["direct_deposit_required"])
    elif direct_deposit_required is None and subcategory in CHECKING_SUBCATEGORIES:
        penalty += int(config.hassle_penalties_cents["direct_deposit_unknown"])
    return penalty


def _risk_penalty(
    deal: Mapping[str, Any],
    terms: Mapping[str, Any],
    config: ScoringConfig,
    warnings: list[str],
) -> int:
    penalty = 0
    if _to_bool(terms.get("hard_pull_risk")):
        penalty += int(config.risk_penalties_cents["hard_pull_risk"])
    if _json_list(terms.get("state_restrictions")):
        penalty += int(config.risk_penalties_cents["state_restrictions"])
    if _to_bool(terms.get("new_customer_only")):
        penalty += int(config.risk_penalties_cents["new_customer_only"])
    if terms.get("early_closure_fee_cents") is not None:
        penalty += int(config.risk_penalties_cents["early_closure_terms"])
    if (deal.get("confidence_score") or 1) < 0.5:
        penalty += int(config.risk_penalties_cents["low_confidence"])

    missing_penalties = config.missing_data_penalties_cents
    for warning in warnings:
        field_name = warning.split(" missing", 1)[0]
        penalty += int(missing_penalties.get(field_name, 0))
    if warnings:
        penalty += int(config.unclear_terms_penalty_cents)
    return penalty


def _missing_data_warnings(
    deal: Mapping[str, Any],
    terms: Mapping[str, Any],
) -> list[str]:
    warnings: list[str] = []
    if deal.get("bonus_amount_cents") is None:
        warnings.append("bonus_amount_cents missing")
    if deal.get("expires_at") is None:
        warnings.append("expires_at missing")
    if terms.get("monthly_fee_cents") is None:
        warnings.append("monthly_fee_cents missing")

    subcategory = deal.get("subcategory")
    if subcategory in CHECKING_SUBCATEGORIES and terms.get("direct_deposit_required") is None:
        warnings.append("direct_deposit_required missing")

    terms_missing = _json_list(_json_value(terms.get("terms_json")).get("missing_fields"))
    for field_name in terms_missing:
        warning = f"{field_name} missing"
        if warning not in warnings:
            warnings.append(warning)
    return warnings


def _expiration_state(
    expires_at: Any,
    as_of: date,
    config: ScoringConfig,
) -> tuple[str, int]:
    expiration = _parse_date(expires_at)
    if expiration is None:
        return "unknown", 0
    days_until = (expiration - as_of).days
    if days_until < 0:
        return "expired", 0
    if days_until <= int(config.expiration_urgency["urgent_days"]):
        return "urgent", int(config.expiration_urgency["urgent_score_boost"])
    if days_until <= int(config.expiration_urgency["soon_days"]):
        return "soon", int(config.expiration_urgency["soon_score_boost"])
    return "none", 0


def _score_value(
    gross_bonus: int,
    net_value: int,
    expiration_boost: int,
    config: ScoringConfig,
) -> int:
    if gross_bonus <= 0 or net_value <= 0:
        return 0
    value_score = round((net_value / gross_bonus) * 100)
    if net_value < config.minimum_net_value_review_cents:
        expiration_boost = 0
    return max(0, min(100, value_score + expiration_boost))


def _score_band(score_value: int, expiration_state: str, config: ScoringConfig) -> str:
    if expiration_state == "expired":
        return "expired"
    thresholds = config.score_thresholds
    if score_value >= int(thresholds["high"]):
        return "high"
    if score_value >= int(thresholds["medium"]):
        return "medium"
    if score_value >= int(thresholds["low"]):
        return "low"
    return "very_low"


def _recommended_action(
    score_value: int,
    net_value: int,
    expiration_state: str,
    has_conflict: bool,
    warnings: list[str],
    config: ScoringConfig,
) -> str:
    if expiration_state == "expired":
        return "expired"
    if has_conflict:
        return "conflict_needs_review"
    if _has_critical_missing_data(warnings):
        return "needs_more_info"
    if net_value < config.minimum_net_value_review_cents:
        return "skip_low_value"
    if score_value >= int(config.score_thresholds["high"]):
        return "review_now"
    if score_value >= int(config.score_thresholds["medium"]):
        return "watch"
    return "skip_low_value"


def _has_critical_missing_data(warnings: list[str]) -> bool:
    critical_prefixes = {
        "bonus_amount_cents",
        "direct_deposit_required",
    }
    return any(
        warning.split(" missing", 1)[0] in critical_prefixes
        for warning in warnings
    )


def _has_conflict(change_events: list[Mapping[str, Any]]) -> bool:
    conflict_reasons = {
        "candidate_official_preferred",
        "existing_official_preserved",
        "candidate_higher_confidence",
        "existing_confidence_preserved",
    }
    for event in change_events:
        changed = _json_value(event.get("changed_fields_json"))
        for field_change in changed.values():
            if isinstance(field_change, Mapping):
                if field_change.get("reason") in conflict_reasons:
                    return True
    return False


def _explanation(
    deal: Mapping[str, Any],
    gross_bonus: int,
    fee_cost: int,
    cash_lockup_cost: int,
    hassle_penalty: int,
    risk_penalty: int,
    net_value: int,
    expiration_state: str,
) -> str:
    title = deal.get("title") or f"deal {deal['id']}"
    return (
        f"{title}: gross bonus {_money(gross_bonus)} minus estimated fees "
        f"{_money(fee_cost)}, cash lockup cost {_money(cash_lockup_cost)}, "
        f"hassle penalty {_money(hassle_penalty)}, and risk/unclear-terms "
        f"penalty {_money(risk_penalty)} gives estimated net value "
        f"{_money(net_value)}. Expiration urgency is {expiration_state}. "
        "For personal review only; verify official terms before acting."
    )


def _validate_rate(config: Mapping[str, Any], field: str) -> list[str]:
    value = config.get(field)
    if not isinstance(value, int | float) or isinstance(value, bool):
        return [f"{field} must be a number"]
    if value < 0 or value > 1:
        return [f"{field} must be between 0 and 1"]
    return []


def _validate_non_negative_int(config: Mapping[str, Any], field: str) -> list[str]:
    value = config.get(field)
    if not isinstance(value, int) or isinstance(value, bool):
        return [f"{field} must be an integer"]
    if value < 0:
        return [f"{field} must be non-negative"]
    return []


def _validate_thresholds(value: Any) -> list[str]:
    errors = _validate_named_mapping(value, "score_thresholds", {"high", "medium", "low"})
    if errors:
        return errors
    thresholds = {key: int(value[key]) for key in ("high", "medium", "low")}
    if not all(0 <= threshold <= 100 for threshold in thresholds.values()):
        errors.append("score_thresholds values must be between 0 and 100")
    if not thresholds["high"] > thresholds["medium"] > thresholds["low"]:
        errors.append("score_thresholds must satisfy high > medium > low")
    return errors


def _validate_named_ints(config: Mapping[str, Any], field: str) -> list[str]:
    value = config.get(field)
    if not isinstance(value, Mapping):
        return [f"{field} must be a mapping"]
    errors = []
    if not value:
        errors.append(f"{field} must not be empty")
    for key, item in value.items():
        if not isinstance(key, str):
            errors.append(f"{field} keys must be strings")
        if not isinstance(item, int) or isinstance(item, bool):
            errors.append(f"{field}.{key} must be an integer")
        elif item < 0:
            errors.append(f"{field}.{key} must be non-negative")
    return errors


def _validate_named_mapping(
    value: Any,
    field: str,
    required_keys: set[str],
) -> list[str]:
    if not isinstance(value, Mapping):
        return [f"{field} must be a mapping"]
    errors = []
    for key in sorted(required_keys - set(value)):
        errors.append(f"{field} missing required key: {key}")
    for key, item in value.items():
        if not isinstance(item, int) or isinstance(item, bool):
            errors.append(f"{field}.{key} must be an integer")
    return errors


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    text = str(value)
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text).date()
        except ValueError:
            return None


def _json_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if isinstance(value, str) and value.strip().startswith("{"):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return decoded if isinstance(decoded, dict) else {}
    return {}


def _json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip().startswith("["):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return []
        return decoded if isinstance(decoded, list) else []
    return [value]


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"
