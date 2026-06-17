"""Machine-readable source policy validation for Banking MVP inputs."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml


REQUIRED_FIELDS = {
    "name",
    "url",
    "source_type",
    "category_scope",
    "subcategory_scope",
    "enabled",
    "collection_method",
    "max_frequency_hours",
    "requires_login",
    "allow_scrape",
    "allow_api",
    "allow_rss",
    "allow_email_parse",
    "robots_policy_notes",
    "terms_policy_notes",
    "rate_limit_notes",
    "compliance_status",
    "last_reviewed_at",
    "notes",
}

ALLOWED_SOURCE_TYPES = {
    "official_promo_page",
    "rss_feed",
    "newsletter_email",
    "manual_url",
    "deal_blog",
    "affiliate_feed",
    "api",
    "disabled",
}

ALLOWED_COLLECTION_METHODS = {
    "manual_only",
    "rss_feed",
    "email_export",
    "api",
    "scrape",
    "disabled",
}

ALLOWED_COMPLIANCE_STATUSES = {
    "approved",
    "pending_review",
    "disabled",
    "rejected",
}

ALLOWED_CATEGORIES = {"banking"}

ALLOWED_SUBCATEGORIES = {
    "checking_bonus",
    "savings_bonus",
    "checking_savings_bundle",
    "brokerage_bonus",
    "money_market_bonus",
    "cd_bonus",
    "credit_card_signup_bonus",
}

FORBIDDEN_FIELD_FRAGMENTS = {
    "bot_protection_evasion",
    "bot-protection-evasion",
    "captcha_bypass",
    "captcha-bypass",
    "ip_rotation",
    "ip-rotation",
    "credential",
    "password",
    "token",
    "session_cookie",
}

LOW_FREQUENCY_HOURS = 24


@dataclass(frozen=True)
class SourcePolicy:
    """Validated source policy record."""

    name: str
    url: str
    source_type: str
    category_scope: tuple[str, ...]
    subcategory_scope: tuple[str, ...]
    enabled: bool
    collection_method: str
    max_frequency_hours: int
    requires_login: bool
    allow_scrape: bool
    allow_api: bool
    allow_rss: bool
    allow_email_parse: bool
    robots_policy_notes: str
    terms_policy_notes: str
    rate_limit_notes: str
    compliance_status: str
    last_reviewed_at: date
    notes: str


class SourcePolicyError(ValueError):
    """Raised when a source policy config fails validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


def load_source_policies(config_path: str | Path) -> list[SourcePolicy]:
    """Load and validate source policies from a YAML config file."""

    path = Path(config_path)
    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_source_config(raw_config)


def validate_source_config(raw_config: Any) -> list[SourcePolicy]:
    """Validate a parsed source policy config and return typed policies."""

    errors: list[str] = []
    if not isinstance(raw_config, Mapping):
        raise SourcePolicyError(["source config must be a mapping with a sources list"])

    unknown_top_level = set(raw_config) - {"sources"}
    for field in sorted(unknown_top_level):
        errors.append(f"unknown top-level field: {field}")

    raw_sources = raw_config.get("sources")
    if not isinstance(raw_sources, list):
        errors.append("sources must be a list")
        raise SourcePolicyError(errors)

    policies: list[SourcePolicy] = []
    for index, raw_source in enumerate(raw_sources):
        source_label = _source_label(index, raw_source)
        if not isinstance(raw_source, Mapping):
            errors.append(f"{source_label}: source record must be a mapping")
            continue

        source_errors = _validate_source_mapping(raw_source, source_label)
        errors.extend(source_errors)
        if source_errors:
            continue

        policies.append(_to_policy(raw_source))

    if errors:
        raise SourcePolicyError(errors)
    return policies


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pdi.sources")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate banking source policy config.",
    )
    validate_parser.add_argument(
        "--config",
        default="config/banking_sources.yaml",
        help="Path to source policy YAML.",
    )

    args = parser.parse_args(argv)
    if args.command == "validate":
        try:
            policies = load_source_policies(args.config)
        except SourcePolicyError as error:
            for message in error.errors:
                print(f"ERROR: {message}")
            return 1

        print(f"Validated {len(policies)} source policies from {args.config}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _validate_source_mapping(source: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []

    missing_fields = REQUIRED_FIELDS - set(source)
    for field in sorted(missing_fields):
        errors.append(f"{label}: missing required field: {field}")

    unknown_fields = set(source) - REQUIRED_FIELDS
    for field in sorted(unknown_fields):
        if _is_forbidden_field(field):
            errors.append(f"{label}: unsafe field is not allowed: {field}")
        else:
            errors.append(f"{label}: unknown field: {field}")

    if missing_fields or unknown_fields:
        return errors

    errors.extend(_validate_text(source, label, "name"))
    errors.extend(_validate_text(source, label, "url"))
    errors.extend(_validate_text(source, label, "robots_policy_notes"))
    errors.extend(_validate_text(source, label, "terms_policy_notes"))
    errors.extend(_validate_text(source, label, "rate_limit_notes"))
    errors.extend(_validate_text(source, label, "notes"))

    source_type = source["source_type"]
    if source_type not in ALLOWED_SOURCE_TYPES:
        errors.append(f"{label}: unsupported source_type: {source_type}")

    collection_method = source["collection_method"]
    if collection_method not in ALLOWED_COLLECTION_METHODS:
        errors.append(f"{label}: unsupported collection_method: {collection_method}")

    compliance_status = source["compliance_status"]
    if compliance_status not in ALLOWED_COMPLIANCE_STATUSES:
        errors.append(f"{label}: unsupported compliance_status: {compliance_status}")

    for field in [
        "enabled",
        "requires_login",
        "allow_scrape",
        "allow_api",
        "allow_rss",
        "allow_email_parse",
    ]:
        if not isinstance(source[field], bool):
            errors.append(f"{label}: {field} must be true or false")

    max_frequency_hours = source["max_frequency_hours"]
    if not isinstance(max_frequency_hours, int) or max_frequency_hours < 0:
        errors.append(f"{label}: max_frequency_hours must be a non-negative integer")

    errors.extend(
        _validate_scope_list(
            source,
            label,
            "category_scope",
            ALLOWED_CATEGORIES,
        )
    )
    errors.extend(
        _validate_scope_list(
            source,
            label,
            "subcategory_scope",
            ALLOWED_SUBCATEGORIES,
        )
    )

    try:
        _parse_review_date(source["last_reviewed_at"])
    except ValueError:
        errors.append(f"{label}: last_reviewed_at must be an ISO date")

    if errors:
        return errors

    errors.extend(_validate_compliance_rules(source, label))
    return errors


def _validate_compliance_rules(source: Mapping[str, Any], label: str) -> list[str]:
    errors: list[str] = []
    enabled = source["enabled"]
    method = source["collection_method"]
    max_frequency_hours = source["max_frequency_hours"]

    if enabled and source["compliance_status"] != "approved":
        errors.append(f"{label}: enabled sources must have compliance_status approved")

    if source["requires_login"] and source["allow_scrape"]:
        errors.append(f"{label}: logged-in source scraping is not allowed")

    if method == "scrape":
        if not source["allow_scrape"]:
            errors.append(f"{label}: scrape method requires allow_scrape true")
        if source["requires_login"]:
            errors.append(f"{label}: scrape method cannot require login")
        if max_frequency_hours < LOW_FREQUENCY_HOURS:
            errors.append(
                f"{label}: scrape method requires max_frequency_hours >= "
                f"{LOW_FREQUENCY_HOURS}"
            )
    elif source["allow_scrape"]:
        errors.append(f"{label}: allow_scrape can be true only for scrape method")

    if enabled and method == "rss_feed" and not source["allow_rss"]:
        errors.append(f"{label}: enabled RSS sources require allow_rss true")
    if enabled and method == "api" and not source["allow_api"]:
        errors.append(f"{label}: enabled API sources require allow_api true")
    if enabled and method == "email_export" and not source["allow_email_parse"]:
        errors.append(
            f"{label}: enabled email export sources require allow_email_parse true"
        )

    if method != "rss_feed" and source["allow_rss"]:
        errors.append(f"{label}: allow_rss can be true only for rss_feed method")
    if method != "api" and source["allow_api"]:
        errors.append(f"{label}: allow_api can be true only for api method")
    if method != "email_export" and source["allow_email_parse"]:
        errors.append(
            f"{label}: allow_email_parse can be true only for email_export method"
        )

    if enabled and method in {"rss_feed", "api", "email_export"}:
        if max_frequency_hours < LOW_FREQUENCY_HOURS:
            errors.append(
                f"{label}: enabled {method} sources require max_frequency_hours >= "
                f"{LOW_FREQUENCY_HOURS}"
            )

    if max_frequency_hours == 0 and not (
        method in {"manual_only", "disabled"} and not enabled
    ):
        errors.append(
            f"{label}: max_frequency_hours 0 is only allowed for disabled "
            "manual-only or disabled sources"
        )

    if source["source_type"] == "disabled" and (enabled or method != "disabled"):
        errors.append(f"{label}: disabled source_type must be disabled and not enabled")

    return errors


def _validate_text(source: Mapping[str, Any], label: str, field: str) -> list[str]:
    value = source[field]
    if not isinstance(value, str) or not value.strip():
        return [f"{label}: {field} must be a non-empty string"]
    return []


def _validate_scope_list(
    source: Mapping[str, Any],
    label: str,
    field: str,
    allowed_values: set[str],
) -> list[str]:
    value = source[field]
    if not isinstance(value, list) or not value:
        return [f"{label}: {field} must be a non-empty list"]

    errors = []
    for item in value:
        if not isinstance(item, str):
            errors.append(f"{label}: {field} entries must be strings")
        elif item not in allowed_values:
            errors.append(f"{label}: unsupported {field} entry: {item}")
    return errors


def _to_policy(source: Mapping[str, Any]) -> SourcePolicy:
    return SourcePolicy(
        name=source["name"],
        url=source["url"],
        source_type=source["source_type"],
        category_scope=tuple(source["category_scope"]),
        subcategory_scope=tuple(source["subcategory_scope"]),
        enabled=source["enabled"],
        collection_method=source["collection_method"],
        max_frequency_hours=source["max_frequency_hours"],
        requires_login=source["requires_login"],
        allow_scrape=source["allow_scrape"],
        allow_api=source["allow_api"],
        allow_rss=source["allow_rss"],
        allow_email_parse=source["allow_email_parse"],
        robots_policy_notes=source["robots_policy_notes"],
        terms_policy_notes=source["terms_policy_notes"],
        rate_limit_notes=source["rate_limit_notes"],
        compliance_status=source["compliance_status"],
        last_reviewed_at=_parse_review_date(source["last_reviewed_at"]),
        notes=source["notes"],
    )


def _source_label(index: int, source: Any) -> str:
    if isinstance(source, Mapping) and isinstance(source.get("name"), str):
        return f"sources[{index}] {source['name']!r}"
    return f"sources[{index}]"


def _parse_review_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("expected ISO date string")
    return date.fromisoformat(value)


def _is_forbidden_field(field: str) -> bool:
    normalized = field.lower()
    return any(fragment in normalized for fragment in FORBIDDEN_FIELD_FRAGMENTS)
