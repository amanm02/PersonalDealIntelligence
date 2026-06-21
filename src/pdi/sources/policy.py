"""Machine-readable source policy validation for Banking MVP inputs."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Mapping

import yaml


REQUIRED_FIELDS = {
    "source_id",
    "source_group",
    "publisher_name",
    "name",
    "url",
    "source_type",
    "source_class",
    "category_scope",
    "subcategory_scope",
    "coverage_purpose",
    "trust_tier",
    "official_source",
    "deposit_account_source",
    "brokerage_source",
    "credit_card_source",
    "fixture_enabled",
    "source_priority",
    "region_scope",
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

ALLOWED_SOURCE_GROUPS = {
    "core",
    "demo",
    "public-pilot",
}

ALLOWED_SOURCE_CLASSES = {
    "official",
    "third_party",
    "manual_import",
    "disabled",
}

ALLOWED_TRUST_TIERS = {
    "official",
    "trusted_third_party",
    "community",
    "user_provided",
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

DEPOSIT_SUBCATEGORIES = {
    "checking_bonus",
    "savings_bonus",
    "checking_savings_bundle",
    "money_market_bonus",
    "cd_bonus",
}

POLICY_NOTE_FIELDS = (
    "coverage_purpose",
    "robots_policy_notes",
    "terms_policy_notes",
    "rate_limit_notes",
    "notes",
)

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
SOURCE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class SourcePolicy:
    """Validated source policy record."""

    source_id: str
    source_group: str
    publisher_name: str
    name: str
    url: str
    source_type: str
    source_class: str
    category_scope: tuple[str, ...]
    subcategory_scope: tuple[str, ...]
    coverage_purpose: str
    trust_tier: str
    official_source: bool
    deposit_account_source: bool
    brokerage_source: bool
    credit_card_source: bool
    fixture_enabled: bool
    source_priority: int
    region_scope: tuple[str, ...]
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


@dataclass(frozen=True)
class SourceOnboardingReview:
    """Review status for one source policy record."""

    source_id: str
    source_group: str | None
    name: str | None
    source_type: str | None
    source_class: str | None
    category_scope: tuple[str, ...]
    subcategory_scope: tuple[str, ...]
    trust_tier: str | None
    official_source: bool | None
    deposit_account_source: bool | None
    brokerage_source: bool | None
    credit_card_source: bool | None
    enabled: bool | None
    fixture_enabled: bool | None
    compliance_status: str | None
    missing_policy_fields: tuple[str, ...]
    validation_errors: tuple[str, ...]
    review_blockers: tuple[str, ...]

    @property
    def live_collection_enabled(self) -> bool:
        return self.enabled is True

    @property
    def safe_default(self) -> bool:
        return self.enabled is not True or self.fixture_enabled is True

    @property
    def review_required(self) -> bool:
        return bool(self.missing_policy_fields or self.validation_errors or self.review_blockers)

    @property
    def onboarding_status(self) -> str:
        if self.missing_policy_fields or self.validation_errors:
            return "invalid"
        if self.review_blockers:
            return "review_required"
        return "ready"

    def to_dict(self) -> dict[str, Any]:
        """Return a stable JSON/table-friendly review payload."""

        return {
            "source_id": self.source_id,
            "source_group": self.source_group,
            "name": self.name,
            "source_type": self.source_type,
            "source_class": self.source_class,
            "category_scope": list(self.category_scope),
            "subcategory_scope": list(self.subcategory_scope),
            "trust_tier": self.trust_tier,
            "official_source": self.official_source,
            "deposit_account_source": self.deposit_account_source,
            "brokerage_source": self.brokerage_source,
            "credit_card_source": self.credit_card_source,
            "enabled": self.enabled,
            "fixture_enabled": self.fixture_enabled,
            "compliance_status": self.compliance_status,
            "missing_policy_fields": list(self.missing_policy_fields),
            "validation_errors": list(self.validation_errors),
            "review_blockers": list(self.review_blockers),
            "safe_default": self.safe_default,
            "live_collection_enabled": self.live_collection_enabled,
            "review_required": self.review_required,
            "onboarding_status": self.onboarding_status,
        }


def load_source_policies(config_path: str | Path) -> list[SourcePolicy]:
    """Load and validate source policies from a YAML config file."""

    path = Path(config_path)
    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_source_config(raw_config)


def load_raw_source_config(config_path: str | Path) -> Mapping[str, Any]:
    """Load source policy YAML without validating it."""

    path = Path(config_path)
    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw_config, Mapping):
        raise SourcePolicyError(["source config must be a mapping with a sources list"])
    return raw_config


def review_source_config(raw_config: Any) -> list[SourceOnboardingReview]:
    """Return onboarding review rows even when some source records are invalid."""

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

    reviews: list[SourceOnboardingReview] = []
    for index, raw_source in enumerate(raw_sources):
        label = _source_label(index, raw_source)
        if not isinstance(raw_source, Mapping):
            reviews.append(
                SourceOnboardingReview(
                    source_id=f"sources[{index}]",
                    source_group=None,
                    name=None,
                    source_type=None,
                    source_class=None,
                    category_scope=(),
                    subcategory_scope=(),
                    trust_tier=None,
                    official_source=None,
                    deposit_account_source=None,
                    brokerage_source=None,
                    credit_card_source=None,
                    enabled=None,
                    fixture_enabled=None,
                    compliance_status=None,
                    missing_policy_fields=tuple(sorted(REQUIRED_FIELDS)),
                    validation_errors=("source record must be a mapping",),
                    review_blockers=(),
                )
            )
            continue

        missing = tuple(sorted(REQUIRED_FIELDS - set(raw_source)))
        source_errors = tuple(_validate_source_mapping(raw_source, label))
        reviews.append(
            SourceOnboardingReview(
                source_id=str(raw_source.get("source_id") or f"sources[{index}]"),
                source_group=_optional_text(raw_source.get("source_group")),
                name=_optional_text(raw_source.get("name")),
                source_type=_optional_text(raw_source.get("source_type")),
                source_class=_optional_text(raw_source.get("source_class")),
                category_scope=_optional_string_tuple(raw_source.get("category_scope")),
                subcategory_scope=_optional_string_tuple(
                    raw_source.get("subcategory_scope")
                ),
                trust_tier=_optional_text(raw_source.get("trust_tier")),
                official_source=_optional_bool(raw_source.get("official_source")),
                deposit_account_source=_optional_bool(
                    raw_source.get("deposit_account_source")
                ),
                brokerage_source=_optional_bool(raw_source.get("brokerage_source")),
                credit_card_source=_optional_bool(raw_source.get("credit_card_source")),
                enabled=_optional_bool(raw_source.get("enabled")),
                fixture_enabled=_optional_bool(raw_source.get("fixture_enabled")),
                compliance_status=_optional_text(raw_source.get("compliance_status")),
                missing_policy_fields=missing,
                validation_errors=source_errors,
                review_blockers=tuple(_review_blockers(raw_source)),
            )
        )
    return reviews


def load_source_onboarding_reviews(
    config_path: str | Path,
) -> list[SourceOnboardingReview]:
    """Load source config and return onboarding review rows."""

    return review_source_config(load_raw_source_config(config_path))


def filter_source_policies(
    policies: list[SourcePolicy],
    *,
    source_group: str | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    source_type: str | None = None,
    source_class: str | None = None,
    trust_tier: str | None = None,
    enabled: bool | None = None,
    official: bool | None = None,
    deposit: bool | None = None,
    brokerage: bool | None = None,
    credit_card: bool | None = None,
    compliance_status: str | None = None,
) -> list[SourcePolicy]:
    """Filter source policies for source review CLI commands."""

    filtered = policies
    if source_group is not None:
        filtered = [policy for policy in filtered if policy.source_group == source_group]
    if category is not None:
        filtered = [policy for policy in filtered if category in policy.category_scope]
    if subcategory is not None:
        filtered = [
            policy for policy in filtered if subcategory in policy.subcategory_scope
        ]
    if source_type is not None:
        filtered = [policy for policy in filtered if policy.source_type == source_type]
    if source_class is not None:
        filtered = [policy for policy in filtered if policy.source_class == source_class]
    if trust_tier is not None:
        filtered = [policy for policy in filtered if policy.trust_tier == trust_tier]
    if enabled is not None:
        filtered = [policy for policy in filtered if policy.enabled is enabled]
    if official is not None:
        filtered = [
            policy for policy in filtered if policy.official_source is official
        ]
    if deposit is not None:
        filtered = [
            policy for policy in filtered if policy.deposit_account_source is deposit
        ]
    if brokerage is not None:
        filtered = [policy for policy in filtered if policy.brokerage_source is brokerage]
    if credit_card is not None:
        filtered = [
            policy for policy in filtered if policy.credit_card_source is credit_card
        ]
    if compliance_status is not None:
        filtered = [
            policy
            for policy in filtered
            if policy.compliance_status == compliance_status
        ]
    return filtered


def source_policy_to_dict(policy: SourcePolicy) -> dict[str, Any]:
    """Return a stable JSON/table-friendly source policy payload."""

    blocked_reason = source_blocked_reason(policy)
    return {
        "source_id": policy.source_id,
        "source_group": policy.source_group,
        "publisher_name": policy.publisher_name,
        "name": policy.name,
        "url": policy.url,
        "source_type": policy.source_type,
        "source_class": policy.source_class,
        "category_scope": list(policy.category_scope),
        "subcategory_scope": list(policy.subcategory_scope),
        "coverage_purpose": policy.coverage_purpose,
        "trust_tier": policy.trust_tier,
        "official_source": policy.official_source,
        "deposit_account_source": policy.deposit_account_source,
        "brokerage_source": policy.brokerage_source,
        "credit_card_source": policy.credit_card_source,
        "fixture_enabled": policy.fixture_enabled,
        "source_priority": policy.source_priority,
        "region_scope": list(policy.region_scope),
        "enabled": policy.enabled,
        "collection_method": policy.collection_method,
        "max_frequency_hours": policy.max_frequency_hours,
        "requires_login": policy.requires_login,
        "allow_scrape": policy.allow_scrape,
        "allow_api": policy.allow_api,
        "allow_rss": policy.allow_rss,
        "allow_email_parse": policy.allow_email_parse,
        "robots_policy_notes": policy.robots_policy_notes,
        "terms_policy_notes": policy.terms_policy_notes,
        "rate_limit_notes": policy.rate_limit_notes,
        "compliance_status": policy.compliance_status,
        "last_reviewed_at": policy.last_reviewed_at.isoformat(),
        "notes": policy.notes,
        "safety_state": "ready" if blocked_reason is None else "blocked",
        "blocked_reason": blocked_reason,
    }


def source_blocked_reason(policy: SourcePolicy) -> str | None:
    """Return the highest-priority reason a source is not collection-ready."""

    if not policy.enabled:
        return "disabled"
    if policy.requires_login:
        return "requires_login"
    if policy.compliance_status != "approved":
        return "compliance_status_not_approved"
    if policy.source_class == "disabled" or policy.source_type == "disabled":
        return "disabled"
    return None


def build_source_scaffold(
    *,
    source_id: str,
    name: str,
    publisher_name: str,
    url: str,
    source_type: str,
    source_class: str,
    subcategories: list[str],
    trust_tier: str | None = None,
    source_group: str = "core",
    fixture_only: bool = False,
    disabled: bool = True,
    coverage_purpose: str | None = None,
    region_scope: list[str] | None = None,
    last_reviewed_at: str | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Build a safe source YAML scaffold without writing it to config."""

    if not SOURCE_ID_PATTERN.fullmatch(source_id):
        raise SourcePolicyError(
            ["source_id must use lowercase letters, numbers, and hyphens"]
        )
    if source_group not in ALLOWED_SOURCE_GROUPS:
        raise SourcePolicyError([f"unsupported source_group: {source_group}"])
    if source_type not in ALLOWED_SOURCE_TYPES:
        raise SourcePolicyError([f"unsupported source_type: {source_type}"])
    if source_class not in ALLOWED_SOURCE_CLASSES:
        raise SourcePolicyError([f"unsupported source_class: {source_class}"])
    if not subcategories:
        raise SourcePolicyError(["at least one --subcategory is required"])
    unsupported_subcategories = sorted(set(subcategories) - ALLOWED_SUBCATEGORIES)
    if unsupported_subcategories:
        raise SourcePolicyError(
            [
                "unsupported subcategory: " + ", ".join(unsupported_subcategories)
            ]
        )

    resolved_trust_tier = trust_tier or _default_trust_tier(source_class)
    if resolved_trust_tier not in ALLOWED_TRUST_TIERS:
        raise SourcePolicyError([f"unsupported trust_tier: {resolved_trust_tier}"])
    if source_class == "official" and resolved_trust_tier != "official":
        raise SourcePolicyError(
            ["official source_class requires trust_tier official"]
        )

    collection_method = _default_collection_method(source_type, fixture_only)
    output_collection_method = (
        "disabled" if source_class == "disabled" else collection_method
    )
    source_is_disabled = disabled or source_class == "disabled" or source_type == "disabled"
    allow_rss = collection_method == "rss_feed"
    allow_email_parse = collection_method == "email_export"
    allow_api = collection_method == "api"
    product_flags = _product_flags(subcategories)
    review_date = last_reviewed_at or date.today().isoformat()
    try:
        _parse_review_date(review_date)
    except ValueError as error:
        raise SourcePolicyError(["last_reviewed_at must be an ISO date"]) from error
    record = {
        "source_id": source_id,
        "source_group": source_group,
        "publisher_name": publisher_name,
        "name": name,
        "url": url,
        "source_type": "disabled" if source_class == "disabled" else source_type,
        "source_class": source_class,
        "category_scope": ["banking"],
        "subcategory_scope": subcategories,
        "coverage_purpose": coverage_purpose
        or "New source scaffold for policy review before collection.",
        "trust_tier": resolved_trust_tier,
        "official_source": source_class == "official",
        "deposit_account_source": product_flags["deposit_account_source"],
        "brokerage_source": product_flags["brokerage_source"],
        "credit_card_source": product_flags["credit_card_source"],
        "fixture_enabled": fixture_only,
        "source_priority": 0,
        "region_scope": region_scope or ["US"],
        "enabled": False,
        "collection_method": output_collection_method,
        "max_frequency_hours": (
            0
            if source_is_disabled
            and output_collection_method in {"manual_only", "disabled"}
            else 24
        ),
        "requires_login": False,
        "allow_scrape": False,
        "allow_api": allow_api,
        "allow_rss": allow_rss,
        "allow_email_parse": allow_email_parse,
        "robots_policy_notes": "Review robots policy before any automated collection.",
        "terms_policy_notes": (
            "Pending source policy review; keep disabled until terms are reviewed."
        ),
        "rate_limit_notes": "No scheduled requests while disabled.",
        "compliance_status": "disabled" if source_class == "disabled" else "pending_review",
        "last_reviewed_at": review_date,
        "notes": "Scaffold only; verify policy notes before enabling any collection.",
    }
    return {"sources": [record]}


def render_source_scaffold_yaml(scaffold: Mapping[str, Any]) -> str:
    """Render source scaffold YAML in the same style as checked-in config."""

    return yaml.safe_dump(scaffold, sort_keys=False)


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

    errors.extend(_validate_text(source, label, "source_id"))
    errors.extend(_validate_text(source, label, "source_group"))
    errors.extend(_validate_text(source, label, "publisher_name"))
    errors.extend(_validate_text(source, label, "name"))
    errors.extend(_validate_text(source, label, "url"))
    errors.extend(_validate_text(source, label, "coverage_purpose"))
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

    source_group = source["source_group"]
    if source_group not in ALLOWED_SOURCE_GROUPS:
        errors.append(f"{label}: unsupported source_group: {source_group}")

    source_class = source["source_class"]
    if source_class not in ALLOWED_SOURCE_CLASSES:
        errors.append(f"{label}: unsupported source_class: {source_class}")

    trust_tier = source["trust_tier"]
    if trust_tier not in ALLOWED_TRUST_TIERS:
        errors.append(f"{label}: unsupported trust_tier: {trust_tier}")

    source_id = source["source_id"]
    if isinstance(source_id, str) and not SOURCE_ID_PATTERN.fullmatch(source_id):
        errors.append(
            f"{label}: source_id must use lowercase letters, numbers, and hyphens"
        )

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
        "official_source",
        "deposit_account_source",
        "brokerage_source",
        "credit_card_source",
        "fixture_enabled",
    ]:
        if not isinstance(source[field], bool):
            errors.append(f"{label}: {field} must be true or false")

    source_priority = source["source_priority"]
    if not isinstance(source_priority, int) or not 0 <= source_priority <= 100:
        errors.append(f"{label}: source_priority must be an integer from 0 to 100")

    max_frequency_hours = source["max_frequency_hours"]
    if not isinstance(max_frequency_hours, int) or max_frequency_hours < 0:
        errors.append(f"{label}: max_frequency_hours must be a non-negative integer")

    errors.extend(_validate_string_list(source, label, "region_scope"))
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

    errors.extend(_validate_source_universe_rules(source, label))
    errors.extend(_validate_compliance_rules(source, label))
    return errors


def _validate_source_universe_rules(
    source: Mapping[str, Any], label: str
) -> list[str]:
    errors: list[str] = []
    source_class = source["source_class"]
    trust_tier = source["trust_tier"]

    category_flags = [
        source["deposit_account_source"],
        source["brokerage_source"],
        source["credit_card_source"],
    ]
    if not any(category_flags):
        errors.append(
            f"{label}: at least one product source flag must be true "
            "(deposit_account_source, brokerage_source, credit_card_source)"
        )

    if source["official_source"] and source_class != "official":
        errors.append(f"{label}: official_source true requires source_class official")
    if source_class == "official" and not source["official_source"]:
        errors.append(f"{label}: official source_class requires official_source true")
    if source_class == "official" and trust_tier != "official":
        errors.append(f"{label}: official source_class requires trust_tier official")
    if source_class == "third_party" and trust_tier == "official":
        errors.append(f"{label}: third_party source_class cannot use official trust_tier")
    if source_class == "disabled" and trust_tier != "disabled":
        errors.append(f"{label}: disabled source_class requires trust_tier disabled")
    if source_class == "disabled" and source["enabled"]:
        errors.append(f"{label}: disabled source_class cannot be enabled")

    subcategories = set(source["subcategory_scope"])
    if subcategories & DEPOSIT_SUBCATEGORIES and not source["deposit_account_source"]:
        errors.append(
            f"{label}: deposit subcategories require deposit_account_source true"
        )
    if "brokerage_bonus" in subcategories and not source["brokerage_source"]:
        errors.append(f"{label}: brokerage_bonus requires brokerage_source true")
    if (
        "credit_card_signup_bonus" in subcategories
        and not source["credit_card_source"]
    ):
        errors.append(
            f"{label}: credit_card_signup_bonus requires credit_card_source true"
        )

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

    if source["source_group"] == "public-pilot":
        if source["requires_login"]:
            errors.append(
                f"{label}: public-pilot sources cannot require login unless a "
                "future local export method is explicitly approved"
            )
        if enabled and method != "rss_feed":
            errors.append(
                f"{label}: public-pilot live collection is limited to rss_feed"
            )
        if enabled and source["allow_scrape"]:
            errors.append(f"{label}: public-pilot sources cannot enable scraping")

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


def _validate_string_list(
    source: Mapping[str, Any],
    label: str,
    field: str,
) -> list[str]:
    value = source[field]
    if not isinstance(value, list) or not value:
        return [f"{label}: {field} must be a non-empty list"]

    errors = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            errors.append(f"{label}: {field} entries must be non-empty strings")
    return errors


def _to_policy(source: Mapping[str, Any]) -> SourcePolicy:
    return SourcePolicy(
        source_id=source["source_id"],
        source_group=source["source_group"],
        publisher_name=source["publisher_name"],
        name=source["name"],
        url=source["url"],
        source_type=source["source_type"],
        source_class=source["source_class"],
        category_scope=tuple(source["category_scope"]),
        subcategory_scope=tuple(source["subcategory_scope"]),
        coverage_purpose=source["coverage_purpose"],
        trust_tier=source["trust_tier"],
        official_source=source["official_source"],
        deposit_account_source=source["deposit_account_source"],
        brokerage_source=source["brokerage_source"],
        credit_card_source=source["credit_card_source"],
        fixture_enabled=source["fixture_enabled"],
        source_priority=source["source_priority"],
        region_scope=tuple(source["region_scope"]),
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
    if isinstance(source, Mapping) and isinstance(source.get("source_id"), str):
        return f"sources[{index}] {source['source_id']!r}"
    if isinstance(source, Mapping) and isinstance(source.get("name"), str):
        return f"sources[{index}] {source['name']!r}"
    return f"sources[{index}]"


def _parse_review_date(value: Any) -> date:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError("expected ISO date string")
    return date.fromisoformat(value)


def _optional_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    return None


def _optional_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _optional_string_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _review_blockers(source: Mapping[str, Any]) -> list[str]:
    blockers: list[str] = []
    for field in POLICY_NOTE_FIELDS:
        value = source.get(field)
        if not isinstance(value, str) or not value.strip():
            blockers.append(f"{field} needs review notes")

    if source.get("enabled") is True:
        if source.get("compliance_status") != "approved":
            blockers.append("enabled source must be compliance approved")
        if source.get("requires_login") is True:
            blockers.append("enabled source cannot require login")
        if source.get("allow_scrape") is True:
            blockers.append("scrape permission requires separate live-fetch review")
    elif source.get("compliance_status") == "pending_review":
        blockers.append("source policy pending review before collection")

    if source.get("enabled") is False and source.get("fixture_enabled") is not True:
        compliance_status = source.get("compliance_status")
        if compliance_status == "approved":
            blockers.append("disabled non-fixture source marked approved; confirm review")

    return blockers


def _default_trust_tier(source_class: str) -> str:
    if source_class == "official":
        return "official"
    if source_class == "third_party":
        return "community"
    if source_class == "manual_import":
        return "user_provided"
    return "disabled"


def _default_collection_method(source_type: str, fixture_only: bool) -> str:
    if source_type == "rss_feed":
        return "rss_feed"
    if source_type == "newsletter_email":
        return "email_export"
    if source_type == "api":
        return "api"
    if source_type == "disabled":
        return "disabled"
    if fixture_only:
        return "manual_only"
    return "manual_only"


def _product_flags(subcategories: list[str]) -> dict[str, bool]:
    subcategory_set = set(subcategories)
    return {
        "deposit_account_source": bool(subcategory_set & DEPOSIT_SUBCATEGORIES),
        "brokerage_source": "brokerage_bonus" in subcategory_set,
        "credit_card_source": "credit_card_signup_bonus" in subcategory_set,
    }


def _is_forbidden_field(field: str) -> bool:
    normalized = field.lower()
    return any(fragment in normalized for fragment in FORBIDDEN_FIELD_FRAGMENTS)
