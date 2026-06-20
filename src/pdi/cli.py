"""Command line interface for Personal Deal Intelligence."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from pdi.alerts import (
    dispatch_notifications,
    generate_banking_digest,
    load_alert_config,
    write_digest_artifact,
)
from pdi.scoring import BankingScore, score_banking_deal
from pdi.smoke import run_offline_banking_smoke
from pdi.storage import (
    get_banking_deal,
    insert_status_event,
    list_banking_deal_source_links,
    list_banking_deals,
    list_deal_change_events,
    list_deal_status_events,
)


DEFAULT_DB_PATH = Path("data/pdi.sqlite")
DEFAULT_OUTPUT_FORMAT = "table"
STATUS_VALUES = (
    "new",
    "needs_review",
    "watching",
    "interested",
    "in_progress",
    "completed",
    "skipped",
    "expired",
    "rejected",
    "applied",
)
REVIEW_RECOMMENDATIONS = {"needs_more_info", "conflict_needs_review"}
CONFLICT_REASONS = {
    "candidate_official_preferred",
    "existing_official_preserved",
    "candidate_higher_confidence",
    "existing_confidence_preserved",
}


def main(argv: list[str] | None = None) -> int:
    """Run the PDI CLI."""

    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(args)
    except sqlite3.OperationalError as error:
        print(f"ERROR: {error}")
        return 1
    except ValueError as error:
        print(f"ERROR: {error}")
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pdi")
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB_PATH),
        help="SQLite database path.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    banking_parser = subparsers.add_parser(
        "banking",
        help="Review canonical banking deals.",
    )
    banking_subparsers = banking_parser.add_subparsers(
        dest="banking_command",
        required=True,
    )

    list_parser = banking_subparsers.add_parser(
        "list",
        help="List canonical banking deals.",
    )
    _add_list_filters(list_parser)
    _add_output_format(list_parser)
    list_parser.set_defaults(handler=_handle_list)

    show_parser = banking_subparsers.add_parser(
        "show",
        help="Show one canonical banking deal.",
    )
    show_parser.add_argument("deal_id", type=int)
    _add_output_format(show_parser)
    show_parser.set_defaults(handler=_handle_show)

    update_parser = banking_subparsers.add_parser(
        "update-status",
        help="Update review status and record a status event.",
    )
    update_parser.add_argument("deal_id", type=int)
    update_parser.add_argument("status", choices=STATUS_VALUES)
    update_parser.add_argument("--note", help="Optional review note.")
    update_parser.set_defaults(handler=_handle_update_status)

    review_parser = banking_subparsers.add_parser(
        "review-needed",
        help="List deals that need review.",
    )
    _add_output_format(review_parser)
    review_parser.set_defaults(handler=_handle_review_needed)

    expiring_parser = banking_subparsers.add_parser(
        "expiring",
        help="List deals expiring within a window.",
    )
    expiring_parser.add_argument("--days", type=int, default=14)
    _add_output_format(expiring_parser)
    expiring_parser.set_defaults(handler=_handle_expiring)

    search_parser = banking_subparsers.add_parser(
        "search",
        help="Search deals by institution.",
    )
    search_parser.add_argument("--institution", required=True)
    _add_output_format(search_parser)
    search_parser.set_defaults(handler=_handle_search)

    score_parser = banking_subparsers.add_parser(
        "score",
        help="Show score details for one deal.",
    )
    score_parser.add_argument("deal_id", type=int)
    _add_output_format(score_parser)
    score_parser.set_defaults(handler=_handle_score)

    digest_parser = banking_subparsers.add_parser(
        "digest",
        help="Generate a local banking deal alert digest.",
    )
    digest_parser.add_argument(
        "--config",
        default="config/banking_alerts.yaml",
        help="Path to banking alert config.",
    )
    digest_parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Digest output format.",
    )
    digest_parser.add_argument("--output", help="Digest output artifact path.")
    digest_parser.add_argument("--as-of", help="Digest date in YYYY-MM-DD format.")
    digest_parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate even inside the configured frequency window.",
    )
    digest_parser.add_argument(
        "--dry-run-notifications",
        action="store_true",
        help="Exercise notification hooks without external sends.",
    )
    digest_parser.set_defaults(handler=_handle_digest)

    smoke_parser = banking_subparsers.add_parser(
        "smoke-test",
        help="Run the offline Banking MVP fixture smoke flow.",
    )
    smoke_parser.add_argument(
        "--fixture-dir",
        default="examples/offline_smoke",
        help="Directory containing offline smoke fixtures.",
    )
    smoke_parser.add_argument(
        "--digest-output",
        default="data/digests/offline_smoke_digest.md",
        help="Markdown digest artifact path.",
    )
    smoke_parser.add_argument(
        "--alert-config",
        default="config/banking_alerts.yaml",
        help="Path to banking alert config.",
    )
    smoke_parser.add_argument("--as-of", default="2026-06-18")
    smoke_parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Replace the target smoke database if it already exists.",
    )
    smoke_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format.",
    )
    smoke_parser.set_defaults(handler=_handle_smoke_test)

    return parser


def _add_output_format(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format.",
    )


def _add_list_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--status", choices=STATUS_VALUES)
    parser.add_argument("--institution")
    parser.add_argument("--subcategory")
    parser.add_argument("--score-band")
    parser.add_argument("--recommended-action")
    parser.add_argument("--expires-within-days", type=int)
    parser.add_argument("--needs-review", action="store_true")


def _handle_list(args: argparse.Namespace) -> int:
    deals = _filtered_deals(
        args.db,
        status=args.status,
        institution=args.institution,
        subcategory=args.subcategory,
        score_band=args.score_band,
        recommended_action=args.recommended_action,
        expires_within_days=args.expires_within_days,
        needs_review=args.needs_review,
    )
    _print_deal_list(deals, args.format)
    return 0


def _handle_show(args: argparse.Namespace) -> int:
    detail = _deal_detail(args.db, args.deal_id)
    if args.format == "json":
        _print_json(detail)
    else:
        _print_detail(detail)
    return 0


def _handle_update_status(args: argparse.Namespace) -> int:
    event_id = insert_status_event(
        args.db,
        args.deal_id,
        args.status,
        note=args.note,
    )
    deal = get_banking_deal(args.db, args.deal_id)
    if deal is None:
        raise ValueError(f"Deal id {args.deal_id} does not exist.")
    print(
        "Updated deal "
        f"{args.deal_id} status to {deal['status']} "
        f"(status event {event_id})."
    )
    return 0


def _handle_review_needed(args: argparse.Namespace) -> int:
    deals = _filtered_deals(args.db, needs_review=True)
    _print_deal_list(deals, args.format)
    return 0


def _handle_expiring(args: argparse.Namespace) -> int:
    deals = _filtered_deals(args.db, expires_within_days=args.days)
    _print_deal_list(deals, args.format)
    return 0


def _handle_search(args: argparse.Namespace) -> int:
    deals = _filtered_deals(args.db, institution=args.institution)
    _print_deal_list(deals, args.format)
    return 0


def _handle_score(args: argparse.Namespace) -> int:
    score = score_banking_deal(args.db, args.deal_id)
    payload = score.to_dict()
    if args.format == "json":
        _print_json(payload)
    else:
        _print_score(payload)
    return 0


def _handle_digest(args: argparse.Namespace) -> int:
    config = load_alert_config(args.config)
    as_of = _parse_cli_date(args.as_of) if args.as_of else None
    digest = generate_banking_digest(args.db, config=config, as_of=as_of)
    notification_results = dispatch_notifications(
        digest,
        config,
        dry_run=args.dry_run_notifications,
    )
    digest = replace(digest, notification_results=notification_results)
    output_path = args.output or (
        config.default_json_output_path
        if args.format == "json"
        else config.default_markdown_output_path
    )
    written_path = write_digest_artifact(
        digest,
        output_path,
        output_format=args.format,
        minimum_hours_between_digests=config.minimum_hours_between_digests,
        force=args.force,
    )
    print(f"Generated banking digest at {written_path} ({args.format}).")
    return 0


def _handle_smoke_test(args: argparse.Namespace) -> int:
    summary = run_offline_banking_smoke(
        args.db,
        fixture_dir=args.fixture_dir,
        digest_output=args.digest_output,
        alert_config_path=args.alert_config,
        as_of=_parse_cli_date(args.as_of),
        reset_db=args.reset_db,
    )
    if args.format == "json":
        _print_json(summary.to_dict())
    else:
        print("Offline banking smoke test complete.")
        _print_table(
            [
                {"metric": key, "value": value}
                for key, value in summary.to_dict().items()
            ],
            empty_message="No smoke summary generated.",
        )
    return 0


def _filtered_deals(
    db_path: str,
    *,
    status: str | None = None,
    institution: str | None = None,
    subcategory: str | None = None,
    score_band: str | None = None,
    recommended_action: str | None = None,
    expires_within_days: int | None = None,
    needs_review: bool = False,
) -> list[dict[str, Any]]:
    rows = list_banking_deals(
        db_path,
        status=status,
        subcategory=subcategory,
    )
    deals = [_summary_record(db_path, row) for row in rows]

    filters: list[Callable[[Mapping[str, Any]], bool]] = []
    if institution:
        institution_filter = institution.lower()
        filters.append(
            lambda deal: institution_filter
            in str(deal.get("institution_name") or "").lower()
        )
    if score_band:
        filters.append(lambda deal: deal.get("score_band") == score_band)
    if recommended_action:
        filters.append(
            lambda deal: deal.get("recommended_action") == recommended_action
        )
    if expires_within_days is not None:
        filters.append(
            lambda deal: _expires_within(deal.get("expires_at"), expires_within_days)
        )
    if needs_review:
        filters.append(lambda deal: bool(deal.get("needs_review")))

    for item_filter in filters:
        deals = [deal for deal in deals if item_filter(deal)]
    return deals


def _summary_record(db_path: str, deal: Mapping[str, Any]) -> dict[str, Any]:
    score = score_banking_deal(db_path, int(deal["id"]))
    change_events = list_deal_change_events(db_path, deal_id=int(deal["id"]))
    needs_review = _needs_review(deal, score, change_events)
    return {
        "id": deal["id"],
        "title": deal["title"],
        "institution_name": deal["institution_name"],
        "subcategory": deal["subcategory"],
        "status": deal["status"],
        "bonus_amount_cents": deal.get("bonus_amount_cents"),
        "estimated_net_value_cents": score.estimated_net_value,
        "score_0_to_100": score.score_0_to_100,
        "score_band": score.score_band,
        "recommended_action": score.recommended_action,
        "expires_at": deal.get("expires_at"),
        "needs_review": needs_review,
    }


def _deal_detail(db_path: str, deal_id: int) -> dict[str, Any]:
    deal = get_banking_deal(db_path, deal_id)
    if deal is None:
        raise ValueError(f"Deal id {deal_id} does not exist.")

    score = score_banking_deal(db_path, deal_id)
    source_links = list_banking_deal_source_links(db_path, deal_id=deal_id)
    change_events = list_deal_change_events(db_path, deal_id=deal_id)
    status_events = list_deal_status_events(db_path, deal_id=deal_id)
    source_urls = _source_urls(deal, source_links)
    terms = _normalized_terms(deal.get("terms") or {})
    return {
        "id": deal["id"],
        "title": deal["title"],
        "institution_name": deal["institution_name"],
        "category": deal["category"],
        "subcategory": deal["subcategory"],
        "status": deal["status"],
        "source_urls": source_urls,
        "source_links": [_source_link_payload(link) for link in source_links],
        "bonus_amount_cents": deal.get("bonus_amount_cents"),
        "estimated_net_value_cents": score.estimated_net_value,
        "score": score.to_dict(),
        "requirements": _requirements(terms),
        "restrictions": _restrictions(terms),
        "expires_at": deal.get("expires_at"),
        "application_deadline": deal.get("application_deadline"),
        "confidence_score": deal.get("confidence_score"),
        "missing_data_warnings": score.missing_data_warnings,
        "evidence_references": [_source_link_payload(link) for link in source_links],
        "status_history": status_events,
        "change_events": change_events,
        "safety_note": (
            "For personal review only; verify final terms on the official "
            "institution page before acting."
        ),
    }


def _normalized_terms(terms: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "minimum_deposit_amount_cents": terms.get("minimum_deposit_amount_cents"),
        "direct_deposit_required": _to_bool(terms.get("direct_deposit_required")),
        "direct_deposit_minimum_cents": terms.get("direct_deposit_minimum_cents"),
        "minimum_balance_required_cents": terms.get(
            "minimum_balance_required_cents"
        ),
        "balance_hold_days": terms.get("balance_hold_days"),
        "monthly_fee_cents": terms.get("monthly_fee_cents"),
        "monthly_fee_waiver_terms": terms.get("monthly_fee_waiver_terms"),
        "early_closure_fee_cents": terms.get("early_closure_fee_cents"),
        "hard_pull_risk": _to_bool(terms.get("hard_pull_risk")),
        "soft_pull_only": _to_bool(terms.get("soft_pull_only")),
        "state_restrictions": _json_value(terms.get("state_restrictions")),
        "new_customer_only": _to_bool(terms.get("new_customer_only")),
        "household_limit": terms.get("household_limit"),
        "terms_json": _json_value(terms.get("terms_json")),
    }


def _requirements(terms: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "minimum_deposit_amount_cents": terms.get("minimum_deposit_amount_cents"),
        "direct_deposit_required": terms.get("direct_deposit_required"),
        "direct_deposit_minimum_cents": terms.get("direct_deposit_minimum_cents"),
        "minimum_balance_required_cents": terms.get(
            "minimum_balance_required_cents"
        ),
        "balance_hold_days": terms.get("balance_hold_days"),
        "monthly_fee_cents": terms.get("monthly_fee_cents"),
        "monthly_fee_waiver_terms": terms.get("monthly_fee_waiver_terms"),
    }


def _restrictions(terms: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "state_restrictions": terms.get("state_restrictions"),
        "new_customer_only": terms.get("new_customer_only"),
        "household_limit": terms.get("household_limit"),
        "early_closure_fee_cents": terms.get("early_closure_fee_cents"),
        "hard_pull_risk": terms.get("hard_pull_risk"),
        "soft_pull_only": terms.get("soft_pull_only"),
    }


def _source_urls(
    deal: Mapping[str, Any],
    source_links: Sequence[Mapping[str, Any]],
) -> list[str]:
    urls = []
    values = [
        deal.get("source_url"),
        *[link.get("source_url") for link in source_links],
    ]
    for value in values:
        if value and value not in urls:
            urls.append(str(value))
    return urls


def _source_link_payload(link: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": link.get("id"),
        "source_name": link.get("source_name"),
        "source_url": link.get("source_url"),
        "source_authority": link.get("source_authority"),
        "retrieved_at": link.get("retrieved_at"),
        "confidence_score": link.get("confidence_score"),
        "evidence": _json_value(link.get("evidence_json")),
    }


def _needs_review(
    deal: Mapping[str, Any],
    score: BankingScore,
    change_events: Sequence[Mapping[str, Any]],
) -> bool:
    return (
        deal.get("status") == "needs_review"
        or score.recommended_action in REVIEW_RECOMMENDATIONS
        or bool(score.missing_data_warnings)
        or _has_conflict(change_events)
    )


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


def _expires_within(value: Any, days: int) -> bool:
    expiration = _parse_date(value)
    if expiration is None:
        return False
    days_until = (expiration - date.today()).days
    return 0 <= days_until <= days


def _print_deal_list(deals: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        _print_json(deals)
        return

    rows = [
        {
            "id": deal["id"],
            "status": deal["status"],
            "institution": deal["institution_name"],
            "subcategory": deal["subcategory"],
            "bonus": _money(deal.get("bonus_amount_cents")),
            "net": _money(deal.get("estimated_net_value_cents")),
            "score": deal["score_0_to_100"],
            "band": deal["score_band"],
            "action": deal["recommended_action"],
            "expires": deal.get("expires_at") or "unknown",
            "review": "yes" if deal["needs_review"] else "no",
        }
        for deal in deals
    ]
    _print_table(rows, empty_message="No banking deals matched.")


def _print_detail(detail: Mapping[str, Any]) -> None:
    score = detail["score"]
    print(f"Deal {detail['id']}: {detail['title']}")
    print(f"Institution: {detail['institution_name']}")
    print(f"Category: {detail['category']} / {detail['subcategory']}")
    print(f"Status: {detail['status']}")
    print(f"Bonus: {_money(detail.get('bonus_amount_cents'))}")
    print(f"Estimated net value: {_money(detail.get('estimated_net_value_cents'))}")
    print(
        "Score: "
        f"{score['score_0_to_100']} ({score['score_band']}; "
        f"{score['recommended_action']})"
    )
    print(f"Score explanation: {score['score_explanation']}")
    print(f"Expiration: {detail.get('expires_at') or 'unknown'}")
    print(
        "Application deadline: "
        f"{detail.get('application_deadline') or 'unknown'}"
    )
    print(f"Confidence: {detail.get('confidence_score')}")
    print("Source URLs:")
    for url in detail["source_urls"] or ["unknown"]:
        print(f"  - {url}")
    print("Requirements:")
    for key, value in detail["requirements"].items():
        print(f"  - {key}: {_display_value(value)}")
    print("Restrictions:")
    for key, value in detail["restrictions"].items():
        print(f"  - {key}: {_display_value(value)}")
    print("Missing data warnings:")
    for warning in detail["missing_data_warnings"] or ["none"]:
        print(f"  - {warning}")
    print("Evidence references:")
    for item in detail["evidence_references"] or [{"source_name": "none"}]:
        print(
            "  - "
            f"{item.get('source_name')} "
            f"{item.get('source_url') or ''}".rstrip()
        )
    print("Status history:")
    for event in detail["status_history"]:
        old_status = event.get("old_status") or "none"
        note = f" ({event['note']})" if event.get("note") else ""
        print(
            "  - "
            f"{event['created_at']}: {old_status} -> {event['new_status']}{note}"
        )
    print(f"Safety: {detail['safety_note']}")


def _print_score(payload: Mapping[str, Any]) -> None:
    rows = [
        {"component": key, "value": _display_value(value)}
        for key, value in payload.items()
    ]
    _print_table(rows, empty_message="No score data.")


def _print_table(
    rows: list[Mapping[str, Any]],
    *,
    empty_message: str,
) -> None:
    if not rows:
        print(empty_message)
        return
    headers = list(rows[0].keys())
    widths = {
        header: max(
            len(header),
            *[len(str(row.get(header, ""))) for row in rows],
        )
        for header in headers
    }
    header_line = "  ".join(header.ljust(widths[header]) for header in headers)
    divider = "  ".join("-" * widths[header] for header in headers)
    print(header_line)
    print(divider)
    for row in rows:
        print(
            "  ".join(
                str(row.get(header, "")).ljust(widths[header])
                for header in headers
            )
        )


def _print_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _money(value: Any) -> str:
    if value is None:
        return "unknown"
    cents = int(value)
    sign = "-" if cents < 0 else ""
    return f"{sign}${abs(cents) / 100:,.2f}"


def _display_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "none"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _to_bool(value: Any) -> bool | None:
    if value is None:
        return None
    return bool(value)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _parse_cli_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid --as-of date: {value}") from error


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
