"""Local banking alert digest generation."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from pdi.scoring import BankingScore, score_banking_deal
from pdi.storage import (
    list_banking_deal_source_links,
    list_banking_deals,
    list_deal_change_events,
    list_deal_status_events,
)


DbPath = str | Path
CONFIG_DEFAULT_PATH = Path("config/banking_alerts.yaml")
DIGEST_SECTIONS = (
    "Review Now",
    "Expiring Soon",
    "Changed Deals",
    "Needs More Information",
    "Watchlist Updates",
)
STATUS_VALUES = {
    "new",
    "needs_review",
    "watching",
    "interested",
    "in_progress",
    "applied",
    "completed",
    "skipped",
    "expired",
    "rejected",
}
SUBCATEGORY_VALUES = {
    "checking_bonus",
    "savings_bonus",
    "checking_savings_bundle",
    "brokerage_bonus",
    "money_market_bonus",
    "cd_bonus",
    "credit_card_signup_bonus",
}
WATCHLIST_STATUSES = {"watching", "interested"}
REVIEW_RECOMMENDATIONS = {"needs_more_info", "conflict_needs_review"}
CRITICAL_MISSING_FIELDS = {"bonus_amount_cents", "direct_deposit_required"}
CONFLICT_REASONS = {
    "candidate_official_preferred",
    "existing_official_preserved",
    "candidate_higher_confidence",
    "existing_confidence_preserved",
}


@dataclass(frozen=True)
class AlertConfig:
    """Validated alert digest rules."""

    minimum_score: int
    minimum_estimated_net_value_cents: int
    expiration_warning_days: list[int]
    eligible_statuses: list[str]
    enabled_subcategories: list[str]
    minimum_hours_between_digests: int
    default_markdown_output_path: str
    default_json_output_path: str
    notification_channels: dict[str, dict[str, Any]]


@dataclass(frozen=True)
class AlertItem:
    """One deal surfaced in a digest section."""

    deal_id: int
    title: str
    institution_name: str
    subcategory: str
    status: str
    score_0_to_100: int
    score_band: str
    recommended_action: str
    estimated_net_value_cents: int
    expires_at: str | None
    source_url: str | None
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "deal_id": self.deal_id,
            "title": self.title,
            "institution_name": self.institution_name,
            "subcategory": self.subcategory,
            "status": self.status,
            "score_0_to_100": self.score_0_to_100,
            "score_band": self.score_band,
            "recommended_action": self.recommended_action,
            "estimated_net_value_cents": self.estimated_net_value_cents,
            "expires_at": self.expires_at,
            "source_url": self.source_url,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class NotificationResult:
    """Result of a notification channel attempt."""

    channel: str
    enabled: bool
    sent: bool
    dry_run: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "channel": self.channel,
            "enabled": self.enabled,
            "sent": self.sent,
            "dry_run": self.dry_run,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BankingDigest:
    """Rendered-ready banking alert digest."""

    generated_at: str
    as_of: str
    summary_counts: dict[str, int]
    expired_count: int
    skipped_count: int
    sections: dict[str, list[AlertItem]]
    notification_results: list[NotificationResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "as_of": self.as_of,
            "summary_counts": dict(self.summary_counts),
            "expired_count": self.expired_count,
            "skipped_count": self.skipped_count,
            "sections": {
                section: [item.to_dict() for item in items]
                for section, items in self.sections.items()
            },
            "notification_results": [
                result.to_dict() for result in self.notification_results
            ],
        }


class AlertConfigError(ValueError):
    """Raised when alert config is invalid."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("\n".join(errors))


class DigestFrequencyError(ValueError):
    """Raised when digest frequency controls suppress a write."""


def load_alert_config(config_path: str | Path = CONFIG_DEFAULT_PATH) -> AlertConfig:
    """Load and validate alert rules from YAML."""

    path = Path(config_path)
    raw_config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return validate_alert_config(raw_config)


def validate_alert_config(raw_config: Any) -> AlertConfig:
    """Validate parsed alert config and return typed rules."""

    if not isinstance(raw_config, Mapping):
        raise AlertConfigError(["alert config must be a mapping"])

    errors: list[str] = []
    required_fields = {
        "minimum_score",
        "minimum_estimated_net_value_cents",
        "expiration_warning_days",
        "eligible_statuses",
        "enabled_subcategories",
        "minimum_hours_between_digests",
        "default_outputs",
        "notification_channels",
    }
    unknown_fields = set(raw_config) - required_fields
    for field_name in sorted(unknown_fields):
        errors.append(f"unknown top-level field: {field_name}")
    for field_name in sorted(required_fields - set(raw_config)):
        errors.append(f"missing required field: {field_name}")
    if errors:
        raise AlertConfigError(errors)

    errors.extend(_validate_int(raw_config, "minimum_score", minimum=0, maximum=100))
    errors.extend(_validate_int(raw_config, "minimum_estimated_net_value_cents"))
    errors.extend(_validate_int(raw_config, "minimum_hours_between_digests"))
    errors.extend(
        _validate_int_list(raw_config, "expiration_warning_days", minimum=0)
    )
    errors.extend(_validate_string_list(raw_config, "eligible_statuses", STATUS_VALUES))
    errors.extend(
        _validate_string_list(
            raw_config,
            "enabled_subcategories",
            SUBCATEGORY_VALUES,
        )
    )
    errors.extend(_validate_outputs(raw_config["default_outputs"]))
    errors.extend(_validate_notification_channels(raw_config["notification_channels"]))
    if errors:
        raise AlertConfigError(errors)

    default_outputs = raw_config["default_outputs"]
    return AlertConfig(
        minimum_score=int(raw_config["minimum_score"]),
        minimum_estimated_net_value_cents=int(
            raw_config["minimum_estimated_net_value_cents"]
        ),
        expiration_warning_days=sorted(
            {int(value) for value in raw_config["expiration_warning_days"]}
        ),
        eligible_statuses=list(raw_config["eligible_statuses"]),
        enabled_subcategories=list(raw_config["enabled_subcategories"]),
        minimum_hours_between_digests=int(
            raw_config["minimum_hours_between_digests"]
        ),
        default_markdown_output_path=str(default_outputs["markdown_path"]),
        default_json_output_path=str(default_outputs["json_path"]),
        notification_channels={
            str(name): dict(value)
            for name, value in raw_config["notification_channels"].items()
        },
    )


def generate_banking_digest(
    db_path: DbPath,
    *,
    config: AlertConfig | None = None,
    config_path: str | Path = CONFIG_DEFAULT_PATH,
    as_of: date | None = None,
    generated_at: datetime | None = None,
    notification_results: Sequence[NotificationResult] | None = None,
) -> BankingDigest:
    """Build a local alert digest from canonical banking deals."""

    config = config or load_alert_config(config_path)
    as_of = as_of or date.today()
    generated_at = generated_at or datetime.combine(
        as_of,
        time.min,
        tzinfo=timezone.utc,
    )
    sections: dict[str, list[AlertItem]] = {
        section: [] for section in DIGEST_SECTIONS
    }
    expired_count = 0
    skipped_count = 0

    for deal in list_banking_deals(db_path):
        status = str(deal.get("status") or "")
        if status == "expired":
            expired_count += 1
        if status == "skipped":
            skipped_count += 1
        if not _is_alert_eligible(deal, config):
            continue

        deal_id = int(deal["id"])
        score = score_banking_deal(db_path, deal_id, as_of=as_of)
        change_events = list_deal_change_events(db_path, deal_id=deal_id)
        status_events = list_deal_status_events(db_path, deal_id=deal_id)
        source_url = _primary_source_url(
            deal,
            list_banking_deal_source_links(db_path, deal_id=deal_id),
        )

        if _is_review_now(score, config):
            sections["Review Now"].append(
                _alert_item(
                    deal,
                    score,
                    source_url,
                    _review_now_reason(score, config),
                )
            )

        days_until_expiration = _days_until(deal.get("expires_at"), as_of)
        if (
            days_until_expiration is not None
            and 0 <= days_until_expiration <= max(config.expiration_warning_days)
        ):
            sections["Expiring Soon"].append(
                _alert_item(
                    deal,
                    score,
                    source_url,
                    f"Expires in {days_until_expiration} days.",
                )
            )

        if status in WATCHLIST_STATUSES and _has_material_change(change_events):
            sections["Changed Deals"].append(
                _alert_item(
                    deal,
                    score,
                    source_url,
                    "Watched/interested deal has material term changes.",
                )
            )

        if _needs_more_information(deal, score, change_events):
            sections["Needs More Information"].append(
                _alert_item(
                    deal,
                    score,
                    source_url,
                    _needs_more_information_reason(deal, score, change_events),
                )
            )

        if status in WATCHLIST_STATUSES and (
            _has_material_change(change_events)
            or _has_relevant_status_event(status_events)
        ):
            sections["Watchlist Updates"].append(
                _alert_item(
                    deal,
                    score,
                    source_url,
                    "Watchlist deal has a status or change update.",
                )
            )

    sections = {
        section: _sort_section(items)
        for section, items in sections.items()
    }
    summary_counts = {
        section: len(items) for section, items in sections.items()
    }
    summary_counts["expired"] = expired_count
    summary_counts["skipped"] = skipped_count
    return BankingDigest(
        generated_at=generated_at.replace(microsecond=0).isoformat(),
        as_of=as_of.isoformat(),
        summary_counts=summary_counts,
        expired_count=expired_count,
        skipped_count=skipped_count,
        sections=sections,
        notification_results=list(notification_results or []),
    )


def render_digest_markdown(digest: BankingDigest) -> str:
    """Render a banking digest as local markdown."""

    lines = [
        "# Banking Deal Digest",
        "",
        f"Generated: {digest.generated_at}",
        f"As of: {digest.as_of}",
        "",
        "## Summary",
        "",
    ]
    for section in DIGEST_SECTIONS:
        lines.append(f"- {section}: {digest.summary_counts.get(section, 0)}")
    lines.append(f"- Expired deals: {digest.expired_count}")
    lines.append(f"- Skipped deals: {digest.skipped_count}")
    lines.append("")

    for section in DIGEST_SECTIONS:
        lines.append(f"## {section}")
        lines.append("")
        items = digest.sections.get(section, [])
        if not items:
            lines.append("No deals.")
            lines.append("")
            continue
        for item in items:
            lines.append(
                "- "
                f"Deal {item.deal_id}: {item.institution_name} - {item.title} "
                f"({item.score_0_to_100}/{item.score_band}, "
                f"net {_money(item.estimated_net_value_cents)})"
            )
            lines.append(f"  Reason: {item.reason}")
            lines.append(f"  Status: {item.status}; expires: {item.expires_at or 'unknown'}")
            lines.append(f"  CLI: pdi banking show {item.deal_id}")
            lines.append(f"  Source: {item.source_url or 'unknown'}")
        lines.append("")

    if digest.notification_results:
        lines.append("## Notification Dry Run")
        lines.append("")
        for result in digest.notification_results:
            lines.append(
                "- "
                f"{result.channel}: sent={str(result.sent).lower()}, "
                f"enabled={str(result.enabled).lower()}, "
                f"dry_run={str(result.dry_run).lower()} - {result.reason}"
            )
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_digest_json(digest: BankingDigest) -> str:
    """Render a banking digest as deterministic JSON."""

    return json.dumps(digest.to_dict(), indent=2, sort_keys=True) + "\n"


def write_digest_artifact(
    digest: BankingDigest,
    output_path: str | Path,
    *,
    output_format: str,
    minimum_hours_between_digests: int = 0,
    force: bool = False,
) -> Path:
    """Write a digest artifact, respecting simple file-mtime frequency control."""

    path = Path(output_path)
    if (
        path.exists()
        and not force
        and minimum_hours_between_digests > 0
        and _hours_since_modified(path) < minimum_hours_between_digests
    ):
        raise DigestFrequencyError(
            "Digest output already exists inside configured frequency window; "
            "use --force to regenerate."
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    if output_format == "markdown":
        rendered = render_digest_markdown(digest)
    elif output_format == "json":
        rendered = render_digest_json(digest)
    else:
        raise ValueError(f"Unsupported digest output format: {output_format}")
    path.write_text(rendered, encoding="utf-8")
    return path


def dispatch_notifications(
    digest: BankingDigest,
    config: AlertConfig,
    *,
    dry_run: bool = False,
) -> list[NotificationResult]:
    """Return no-op notification results without external network sends."""

    _ = digest
    results: list[NotificationResult] = []
    for channel, settings in sorted(config.notification_channels.items()):
        enabled = bool(settings.get("enabled", False))
        if not enabled:
            reason = "channel disabled by config"
        elif dry_run:
            reason = "dry run; no external message sent"
        else:
            reason = "no notification adapter configured; no external message sent"
        results.append(
            NotificationResult(
                channel=channel,
                enabled=enabled,
                sent=False,
                dry_run=dry_run,
                reason=reason,
            )
        )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pdi.alerts")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate banking alert config.",
    )
    validate_parser.add_argument(
        "--config",
        default=str(CONFIG_DEFAULT_PATH),
        help="Path to banking alerts YAML.",
    )

    args = parser.parse_args(argv)
    if args.command == "validate":
        try:
            load_alert_config(args.config)
        except AlertConfigError as error:
            for message in error.errors:
                print(f"ERROR: {message}")
            return 1
        print(f"Validated alert config from {args.config}")
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _is_alert_eligible(
    deal: Mapping[str, Any],
    config: AlertConfig,
) -> bool:
    return (
        deal.get("status") in config.eligible_statuses
        and deal.get("subcategory") in config.enabled_subcategories
    )


def _is_review_now(score: BankingScore, config: AlertConfig) -> bool:
    return (
        score.score_0_to_100 >= config.minimum_score
        or score.estimated_net_value >= config.minimum_estimated_net_value_cents
    )


def _review_now_reason(score: BankingScore, config: AlertConfig) -> str:
    if score.score_0_to_100 >= config.minimum_score:
        return f"Score {score.score_0_to_100} meets high-priority threshold."
    return (
        "Estimated net value "
        f"{_money(score.estimated_net_value)} meets configured threshold."
    )


def _needs_more_information(
    deal: Mapping[str, Any],
    score: BankingScore,
    change_events: Sequence[Mapping[str, Any]],
) -> bool:
    return (
        deal.get("status") == "needs_review"
        or score.recommended_action in REVIEW_RECOMMENDATIONS
        or _has_critical_missing_data(score.missing_data_warnings)
        or _has_conflict(change_events)
    )


def _needs_more_information_reason(
    deal: Mapping[str, Any],
    score: BankingScore,
    change_events: Sequence[Mapping[str, Any]],
) -> str:
    if _has_conflict(change_events) or score.recommended_action == "conflict_needs_review":
        return "Conflicting extracted terms need review."
    if _has_critical_missing_data(score.missing_data_warnings):
        return "Critical fields are missing."
    if deal.get("status") == "needs_review":
        return "Deal status is needs_review."
    return "Scoring recommends more information before action."


def _has_critical_missing_data(warnings: Sequence[str]) -> bool:
    return any(
        warning.split(" missing", 1)[0] in CRITICAL_MISSING_FIELDS
        for warning in warnings
    )


def _has_material_change(change_events: Sequence[Mapping[str, Any]]) -> bool:
    return any(event.get("event_type") == "canonical_field_changed" for event in change_events)


def _has_conflict(change_events: Sequence[Mapping[str, Any]]) -> bool:
    for event in change_events:
        changed = _json_value(event.get("changed_fields_json"))
        if not isinstance(changed, Mapping):
            continue
        for field_change in changed.values():
            if (
                isinstance(field_change, Mapping)
                and field_change.get("reason") in CONFLICT_REASONS
            ):
                return True
    return False


def _has_relevant_status_event(status_events: Sequence[Mapping[str, Any]]) -> bool:
    return any(event.get("old_status") for event in status_events)


def _alert_item(
    deal: Mapping[str, Any],
    score: BankingScore,
    source_url: str | None,
    reason: str,
) -> AlertItem:
    return AlertItem(
        deal_id=int(deal["id"]),
        title=str(deal["title"]),
        institution_name=str(deal["institution_name"]),
        subcategory=str(deal["subcategory"]),
        status=str(deal["status"]),
        score_0_to_100=score.score_0_to_100,
        score_band=score.score_band,
        recommended_action=score.recommended_action,
        estimated_net_value_cents=score.estimated_net_value,
        expires_at=deal.get("expires_at"),
        source_url=source_url,
        reason=reason,
    )


def _sort_section(items: list[AlertItem]) -> list[AlertItem]:
    return sorted(
        items,
        key=lambda item: (
            -(item.score_0_to_100),
            -(item.estimated_net_value_cents),
            item.expires_at or "9999-12-31",
            item.deal_id,
        ),
    )


def _primary_source_url(
    deal: Mapping[str, Any],
    source_links: Sequence[Mapping[str, Any]],
) -> str | None:
    if deal.get("source_url"):
        return str(deal["source_url"])
    for link in source_links:
        if link.get("source_url"):
            return str(link["source_url"])
    return None


def _days_until(value: Any, as_of: date) -> int | None:
    expiration = _parse_date(value)
    if expiration is None:
        return None
    return (expiration - as_of).days


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _json_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str) and value.strip().startswith(("{", "[")):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _hours_since_modified(path: Path) -> float:
    modified_at = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return (datetime.now(timezone.utc) - modified_at).total_seconds() / 3600


def _validate_int(
    config: Mapping[str, Any],
    field_name: str,
    *,
    minimum: int = 0,
    maximum: int | None = None,
) -> list[str]:
    value = config.get(field_name)
    if not isinstance(value, int) or isinstance(value, bool):
        return [f"{field_name} must be an integer"]
    if value < minimum:
        return [f"{field_name} must be at least {minimum}"]
    if maximum is not None and value > maximum:
        return [f"{field_name} must be at most {maximum}"]
    return []


def _validate_int_list(
    config: Mapping[str, Any],
    field_name: str,
    *,
    minimum: int,
) -> list[str]:
    value = config.get(field_name)
    if not isinstance(value, list) or not value:
        return [f"{field_name} must be a non-empty list"]
    errors: list[str] = []
    for item in value:
        if not isinstance(item, int) or isinstance(item, bool):
            errors.append(f"{field_name} values must be integers")
        elif item < minimum:
            errors.append(f"{field_name} values must be at least {minimum}")
    return errors


def _validate_string_list(
    config: Mapping[str, Any],
    field_name: str,
    allowed_values: set[str],
) -> list[str]:
    value = config.get(field_name)
    if not isinstance(value, list) or not value:
        return [f"{field_name} must be a non-empty list"]
    errors: list[str] = []
    for item in value:
        if not isinstance(item, str):
            errors.append(f"{field_name} values must be strings")
        elif item not in allowed_values:
            errors.append(f"{field_name} contains unsupported value: {item}")
    return errors


def _validate_outputs(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["default_outputs must be a mapping"]
    errors: list[str] = []
    required = {"markdown_path", "json_path"}
    for field_name in sorted(required - set(value)):
        errors.append(f"default_outputs missing required field: {field_name}")
    for field_name in sorted(set(value) - required):
        errors.append(f"default_outputs contains unknown field: {field_name}")
    for field_name in required.intersection(value):
        if not isinstance(value[field_name], str) or not value[field_name]:
            errors.append(f"default_outputs.{field_name} must be a non-empty string")
    return errors


def _validate_notification_channels(value: Any) -> list[str]:
    if not isinstance(value, Mapping):
        return ["notification_channels must be a mapping"]
    errors: list[str] = []
    for channel, settings in value.items():
        if not isinstance(channel, str):
            errors.append("notification channel names must be strings")
        if not isinstance(settings, Mapping):
            errors.append(f"notification_channels.{channel} must be a mapping")
            continue
        unknown_fields = set(settings) - {"enabled"}
        for field_name in sorted(unknown_fields):
            errors.append(
                f"notification_channels.{channel} contains unknown field: {field_name}"
            )
        if "enabled" not in settings:
            errors.append(f"notification_channels.{channel}.enabled is required")
        elif not isinstance(settings["enabled"], bool):
            errors.append(f"notification_channels.{channel}.enabled must be boolean")
    return errors


def _money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"
