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
from pdi.extractors import reextract_all_snapshots, reextract_snapshot
from pdi.public_pilot import (
    NO_ENABLED_PUBLIC_PILOT_MESSAGE,
    validate_public_pilot_sources,
)
from pdi.qa_benchmark import BENCHMARK_CATEGORIES, run_banking_qa_benchmark
from pdi.runs import run_banking_workflow_once
from pdi.scoring import BankingScore, score_banking_deal
from pdi.smoke import run_offline_banking_smoke
from pdi.sources import (
    ALLOWED_COMPLIANCE_STATUSES,
    ALLOWED_SOURCE_CLASSES,
    ALLOWED_SOURCE_GROUPS,
    ALLOWED_SOURCE_TYPES,
    ALLOWED_SUBCATEGORIES,
    ALLOWED_TRUST_TIERS,
    SourcePolicyError,
    build_source_scaffold,
    filter_source_policies,
    load_source_onboarding_reviews,
    load_source_policies,
    render_source_scaffold_yaml,
    source_policy_to_dict,
)
from pdi.storage import (
    get_banking_deal,
    get_banking_run,
    get_raw_snapshot,
    initialize_database,
    insert_status_event,
    list_banking_deal_source_links,
    list_banking_deals,
    list_banking_runs,
    list_deal_change_events,
    list_deal_status_events,
    list_field_evidence_links,
)


DEFAULT_DB_PATH = Path("data/pdi.sqlite")
DEFAULT_OUTPUT_FORMAT = "table"
DEFAULT_DEMO_FIXTURE_DIR = "examples/offline_smoke"
DEFAULT_DEMO_DIGEST_OUTPUT = "data/digests/banking_demo_digest.md"
DEFAULT_DEMO_JSON_DIGEST_OUTPUT = "data/digests/banking_demo_digest.json"
DEFAULT_DEMO_AS_OF = "2026-06-18"
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
CREDIT_CARD_SUBCATEGORY = "credit_card_signup_bonus"
CARD_OFFER_CURRENCIES = ("cash", "statement_credit", "points", "miles", "mixed")
CARD_CUSTOMER_TYPES = ("personal", "business")
CRITICAL_EVIDENCE_FIELDS = (
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
    "expires_at",
    "application_deadline",
    "direct_deposit_required",
    "direct_deposit_minimum_cents",
    "minimum_deposit_amount_cents",
    "minimum_balance_required_cents",
    "balance_hold_days",
    "monthly_fee_cents",
    "state_restrictions",
    "new_customer_only",
)
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
        help="Search ranked local banking deals.",
    )
    _add_search_filters(search_parser)
    _add_output_format(search_parser)
    search_parser.set_defaults(handler=_handle_search)

    find_parser = banking_subparsers.add_parser(
        "find",
        help="Alias for ranked local banking deal search.",
    )
    _add_search_filters(find_parser)
    _add_output_format(find_parser)
    find_parser.set_defaults(handler=_handle_search)

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
    digest_parser.add_argument(
        "--demo",
        action="store_true",
        help="Use deterministic local-only demo digest defaults.",
    )
    digest_parser.set_defaults(handler=_handle_digest)

    sources_parser = banking_subparsers.add_parser(
        "sources",
        help="Inspect and validate banking source policy entries.",
    )
    sources_subparsers = sources_parser.add_subparsers(
        dest="sources_command",
        required=True,
    )
    sources_list_parser = sources_subparsers.add_parser(
        "list",
        help="List configured banking source policy entries.",
    )
    sources_list_parser.add_argument(
        "--config",
        default="config/banking_sources.yaml",
        help="Path to source policy YAML.",
    )
    sources_list_parser.add_argument(
        "--group",
        choices=sorted(ALLOWED_SOURCE_GROUPS),
        help="Limit output to one source group.",
    )
    _add_source_filters(sources_list_parser)
    _add_output_format(sources_list_parser)
    sources_list_parser.set_defaults(handler=_handle_sources_list)

    sources_validate_parser = sources_subparsers.add_parser(
        "validate",
        help="Validate configured banking source policy entries.",
    )
    sources_validate_parser.add_argument(
        "--config",
        default="config/banking_sources.yaml",
        help="Path to source policy YAML.",
    )
    _add_output_format(sources_validate_parser)
    sources_validate_parser.set_defaults(handler=_handle_sources_validate)

    sources_show_parser = sources_subparsers.add_parser(
        "show",
        help="Show one banking source policy entry.",
    )
    sources_show_parser.add_argument("source_id")
    sources_show_parser.add_argument(
        "--config",
        default="config/banking_sources.yaml",
        help="Path to source policy YAML.",
    )
    _add_output_format(sources_show_parser)
    sources_show_parser.set_defaults(handler=_handle_sources_show)

    sources_onboarding_parser = sources_subparsers.add_parser(
        "onboarding-check",
        help="Report missing source onboarding fields and review blockers.",
    )
    sources_onboarding_parser.add_argument(
        "--config",
        default="config/banking_sources.yaml",
        help="Path to source policy YAML.",
    )
    sources_onboarding_parser.add_argument(
        "--review-required",
        action="store_true",
        help="Show only sources that still need policy review.",
    )
    sources_onboarding_parser.add_argument(
        "--group",
        choices=sorted(ALLOWED_SOURCE_GROUPS),
        help="Limit output to one source group.",
    )
    _add_source_filters(sources_onboarding_parser)
    _add_output_format(sources_onboarding_parser)
    sources_onboarding_parser.set_defaults(handler=_handle_sources_onboarding_check)

    sources_scaffold_parser = sources_subparsers.add_parser(
        "scaffold",
        help="Print a disabled source policy YAML scaffold.",
    )
    sources_scaffold_parser.add_argument("--id", dest="source_id", required=True)
    sources_scaffold_parser.add_argument("--name", required=True)
    sources_scaffold_parser.add_argument("--publisher", dest="publisher_name", required=True)
    sources_scaffold_parser.add_argument("--url", required=True)
    sources_scaffold_parser.add_argument(
        "--source-type",
        choices=sorted(ALLOWED_SOURCE_TYPES),
        required=True,
    )
    sources_scaffold_parser.add_argument(
        "--source-class",
        choices=sorted(ALLOWED_SOURCE_CLASSES),
        required=True,
    )
    sources_scaffold_parser.add_argument(
        "--subcategory",
        action="append",
        choices=sorted(ALLOWED_SUBCATEGORIES),
        required=True,
        help="Banking subcategory covered by the source. Repeat for multiple.",
    )
    sources_scaffold_parser.add_argument(
        "--trust-tier",
        choices=sorted(ALLOWED_TRUST_TIERS),
        help="Trust tier. Defaults from source class.",
    )
    sources_scaffold_parser.add_argument(
        "--group",
        choices=sorted(ALLOWED_SOURCE_GROUPS),
        default="core",
        help="Source group for the scaffold.",
    )
    sources_scaffold_parser.add_argument(
        "--fixture-only",
        action="store_true",
        help="Mark the source as fixture-enabled while keeping it disabled.",
    )
    sources_scaffold_parser.add_argument(
        "--disabled",
        action="store_true",
        default=True,
        help="Keep enabled false in the scaffold. This is the default.",
    )
    sources_scaffold_parser.add_argument(
        "--coverage-purpose",
        help="Optional reviewed coverage purpose text.",
    )
    sources_scaffold_parser.add_argument(
        "--last-reviewed-at",
        help="Review date in YYYY-MM-DD format. Defaults to today.",
    )
    sources_scaffold_parser.set_defaults(handler=_handle_sources_scaffold)

    run_parser = banking_subparsers.add_parser(
        "run",
        help="Run the local Banking MVP workflow once.",
    )
    run_mode = run_parser.add_mutually_exclusive_group()
    run_mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=None,
        help="Preview the workflow without durable deal or digest changes.",
    )
    run_mode.add_argument(
        "--execute",
        dest="dry_run",
        action="store_false",
        help="Persist workflow changes and write the digest artifact.",
    )
    run_parser.add_argument(
        "--sources",
        choices=("demo", "public-pilot"),
        default="demo",
        help="Source group to run.",
    )
    run_parser.add_argument(
        "--source-config",
        default="config/banking_sources.yaml",
        help="Path to source policy YAML for source-group runs.",
    )
    run_parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Explicitly allow guarded live public-pilot collection.",
    )
    run_parser.add_argument(
        "--fixture-dir",
        default="examples/offline_smoke",
        help="Directory containing offline workflow fixtures.",
    )
    run_parser.add_argument(
        "--digest-output",
        default="data/digests/banking_run_digest.md",
        help="Markdown digest artifact path for executed runs.",
    )
    run_parser.add_argument(
        "--alert-config",
        default="config/banking_alerts.yaml",
        help="Path to banking alert config.",
    )
    run_parser.add_argument("--as-of", default="2026-06-18")
    run_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format.",
    )
    run_parser.set_defaults(handler=_handle_run)

    runs_parser = banking_subparsers.add_parser(
        "runs",
        help="List recent Banking MVP workflow runs.",
    )
    runs_parser.add_argument("--limit", type=int, default=10)
    _add_output_format(runs_parser)
    runs_parser.set_defaults(handler=_handle_runs)

    run_status_parser = banking_subparsers.add_parser(
        "run-status",
        help="Inspect one Banking MVP workflow run.",
    )
    run_status_parser.add_argument("run_id", type=int)
    _add_output_format(run_status_parser)
    run_status_parser.set_defaults(handler=_handle_run_status)

    demo_parser = banking_subparsers.add_parser(
        "demo",
        help="Seed the local Banking MVP demo from offline fixtures.",
    )
    demo_parser.add_argument(
        "--seed",
        choices=("fixtures",),
        default="fixtures",
        help="Demo seed source.",
    )
    demo_parser.add_argument(
        "--fixture-dir",
        default=DEFAULT_DEMO_FIXTURE_DIR,
        help="Directory containing demo fixture text.",
    )
    demo_parser.add_argument(
        "--digest-output",
        default=DEFAULT_DEMO_DIGEST_OUTPUT,
        help="Markdown digest artifact path.",
    )
    demo_parser.add_argument(
        "--alert-config",
        default="config/banking_alerts.yaml",
        help="Path to banking alert config.",
    )
    demo_parser.add_argument("--as-of", default=DEFAULT_DEMO_AS_OF)
    demo_parser.add_argument(
        "--reset",
        "--reset-db",
        dest="reset",
        action="store_true",
        help="Replace the target demo database if it already exists.",
    )
    demo_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format.",
    )
    demo_parser.set_defaults(handler=_handle_demo)

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

    qa_parser = banking_subparsers.add_parser(
        "qa-benchmark",
        help="Run the offline Banking MVP demo QA benchmark.",
    )
    qa_parser.add_argument(
        "--category",
        choices=BENCHMARK_CATEGORIES,
        default="all",
        help="Benchmark scope.",
    )
    qa_parser.add_argument(
        "--demo-dir",
        default="examples/demo_banking",
        help="Directory containing demo banking fixtures.",
    )
    qa_parser.add_argument(
        "--source-config",
        default="config/banking_sources.demo.yaml",
        help="Path to demo banking source config.",
    )
    qa_parser.add_argument("--as-of", default=DEFAULT_DEMO_AS_OF)
    qa_parser.add_argument(
        "--reset-db",
        action="store_true",
        help="Replace the target QA benchmark database if it already exists.",
    )
    qa_parser.add_argument(
        "--format",
        choices=("table", "json"),
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format.",
    )
    qa_parser.add_argument(
        "--json",
        action="store_true",
        help="Shortcut for --format json.",
    )
    qa_parser.set_defaults(handler=_handle_qa_benchmark)

    reextract_parser = banking_subparsers.add_parser(
        "reextract",
        help="Reprocess stored raw snapshots without live collection.",
    )
    reextract_target = reextract_parser.add_mutually_exclusive_group(required=True)
    reextract_target.add_argument("--snapshot", type=int, help="Raw snapshot id.")
    reextract_target.add_argument(
        "--all",
        action="store_true",
        help="Reprocess all stored raw snapshots.",
    )
    reextract_mode = reextract_parser.add_mutually_exclusive_group()
    reextract_mode.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=True,
        help="Report changes without writing new candidates. This is the default.",
    )
    reextract_mode.add_argument(
        "--write",
        dest="dry_run",
        action="store_false",
        help="Persist new candidate rows while preserving canonical deals.",
    )
    _add_output_format(reextract_parser)
    reextract_parser.set_defaults(handler=_handle_reextract)

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
    parser.add_argument("--issuer")
    parser.add_argument("--card")
    parser.add_argument("--customer-type", choices=CARD_CUSTOMER_TYPES)
    parser.add_argument("--offer-currency", choices=CARD_OFFER_CURRENCIES)
    parser.add_argument("--score-band")
    parser.add_argument("--recommended-action")
    parser.add_argument("--expires-within-days", type=int)
    parser.add_argument("--needs-review", action="store_true")


def _add_search_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--query", help="Free-text query.")
    parser.add_argument("--institution")
    parser.add_argument("--subcategory")
    parser.add_argument("--issuer")
    parser.add_argument("--card")
    parser.add_argument("--customer-type", choices=CARD_CUSTOMER_TYPES)
    parser.add_argument("--offer-currency", choices=CARD_OFFER_CURRENCIES)
    parser.add_argument("--min-bonus", type=_money_arg)
    parser.add_argument("--min-net-value", type=_money_arg)
    parser.add_argument("--score-band")
    parser.add_argument("--recommended-action")
    parser.add_argument("--status", choices=STATUS_VALUES)
    parser.add_argument("--expiring-days", type=int)
    parser.add_argument("--needs-review", action="store_true")


def _add_source_filters(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--category", choices=("banking",))
    parser.add_argument("--subcategory", choices=sorted(ALLOWED_SUBCATEGORIES))
    parser.add_argument("--source-type", choices=sorted(ALLOWED_SOURCE_TYPES))
    parser.add_argument("--source-class", choices=sorted(ALLOWED_SOURCE_CLASSES))
    parser.add_argument("--trust-tier", choices=sorted(ALLOWED_TRUST_TIERS))
    parser.add_argument("--enabled", choices=("true", "false"))
    parser.add_argument("--official", choices=("true", "false"))
    parser.add_argument("--deposit", choices=("true", "false"))
    parser.add_argument("--brokerage", choices=("true", "false"))
    parser.add_argument("--credit-card", choices=("true", "false"))
    parser.add_argument("--compliance-status", choices=sorted(ALLOWED_COMPLIANCE_STATUSES))


def _handle_list(args: argparse.Namespace) -> int:
    deals = _filtered_deals(
        args.db,
        status=args.status,
        institution=args.institution,
        subcategory=args.subcategory,
        issuer=args.issuer,
        card=args.card,
        customer_type=args.customer_type,
        offer_currency=args.offer_currency,
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
    deals = _search_deals(
        args.db,
        query=args.query,
        institution=args.institution,
        subcategory=args.subcategory,
        issuer=args.issuer,
        card=args.card,
        customer_type=args.customer_type,
        offer_currency=args.offer_currency,
        min_bonus=args.min_bonus,
        min_net_value=args.min_net_value,
        score_band=args.score_band,
        recommended_action=args.recommended_action,
        status=args.status,
        expiring_days=args.expiring_days,
        needs_review=args.needs_review,
    )
    _print_search_results(deals, args.format)
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
    as_of_value = args.as_of or (DEFAULT_DEMO_AS_OF if args.demo else None)
    as_of = _parse_cli_date(as_of_value) if as_of_value else None
    digest = generate_banking_digest(args.db, config=config, as_of=as_of)
    notification_results = dispatch_notifications(
        digest,
        config,
        dry_run=args.dry_run_notifications or args.demo,
    )
    digest = replace(digest, notification_results=notification_results)
    output_path = args.output or (
        (
            DEFAULT_DEMO_JSON_DIGEST_OUTPUT
            if args.format == "json"
            else DEFAULT_DEMO_DIGEST_OUTPUT
        )
        if args.demo
        else (
            config.default_json_output_path
            if args.format == "json"
            else config.default_markdown_output_path
        )
    )
    written_path = write_digest_artifact(
        digest,
        output_path,
        output_format=args.format,
        minimum_hours_between_digests=(
            0 if args.demo else config.minimum_hours_between_digests
        ),
        force=args.force or args.demo,
    )
    print(f"Generated banking digest at {written_path} ({args.format}).")
    return 0


def _handle_sources_list(args: argparse.Namespace) -> int:
    policies = load_source_policies(args.config)
    policies = filter_source_policies(
        policies,
        source_group=args.group,
        category=args.category,
        subcategory=args.subcategory,
        source_type=args.source_type,
        source_class=args.source_class,
        trust_tier=args.trust_tier,
        enabled=_optional_cli_bool(args.enabled),
        official=_optional_cli_bool(args.official),
        deposit=_optional_cli_bool(args.deposit),
        brokerage=_optional_cli_bool(args.brokerage),
        credit_card=_optional_cli_bool(args.credit_card),
        compliance_status=args.compliance_status,
    )
    sources = [source_policy_to_dict(policy) for policy in policies]
    if args.format == "json":
        _print_json(sources)
    else:
        columns = [
            "source_id",
            "source_group",
            "source_class",
            "trust_tier",
            "source_type",
            "collection_method",
            "enabled",
            "official_source",
            "deposit_account_source",
            "brokerage_source",
            "credit_card_source",
            "source_priority",
            "compliance_status",
            "last_reviewed_at",
            "safety_state",
            "blocked_reason",
        ]
        _print_table(
            [
                {column: source.get(column) for column in columns}
                for source in sources
            ],
            empty_message="No banking sources configured.",
        )
    return 0


def _handle_sources_validate(args: argparse.Namespace) -> int:
    result = validate_public_pilot_sources(args.config)
    if args.format == "json":
        _print_json(result)
    else:
        print(
            f"Validated {result['source_count']} source policies from "
            f"{result['config_path']}."
        )
        print(
            "Public-pilot sources: "
            f"{result['public_pilot_source_count']} configured, "
            f"{result['enabled_public_pilot_source_count']} enabled."
        )
    return 0


def _handle_sources_show(args: argparse.Namespace) -> int:
    policies = load_source_policies(args.config)
    policy = next(
        (candidate for candidate in policies if candidate.source_id == args.source_id),
        None,
    )
    if policy is None:
        raise ValueError(f"Source id {args.source_id} does not exist.")

    payload = source_policy_to_dict(policy)
    reviews = {
        review.source_id: review.to_dict()
        for review in load_source_onboarding_reviews(args.config)
    }
    payload["onboarding_review"] = reviews.get(args.source_id)
    if args.format == "json":
        _print_json(payload)
    else:
        _print_table(
            [{"field": key, "value": value} for key, value in payload.items()],
            empty_message="No source detail.",
        )
    return 0


def _handle_sources_onboarding_check(args: argparse.Namespace) -> int:
    reviews = [
        review.to_dict() for review in load_source_onboarding_reviews(args.config)
    ]
    reviews = _filter_source_review_payloads(reviews, args)
    if args.review_required:
        reviews = [review for review in reviews if review["review_required"]]

    if args.format == "json":
        _print_json(
            {
                "config_path": args.config,
                "source_count": len(reviews),
                "review_required_count": sum(
                    1 for review in reviews if review["review_required"]
                ),
                "invalid_count": sum(
                    1
                    for review in reviews
                    if review["onboarding_status"] == "invalid"
                ),
                "sources": reviews,
            }
        )
    else:
        columns = [
            "source_id",
            "source_group",
            "source_class",
            "trust_tier",
            "subcategory_scope",
            "official_source",
            "deposit_account_source",
            "brokerage_source",
            "credit_card_source",
            "enabled",
            "fixture_enabled",
            "compliance_status",
            "safe_default",
            "live_collection_enabled",
            "onboarding_status",
            "missing_policy_fields",
            "review_blockers",
        ]
        _print_table(
            [{column: review.get(column) for column in columns} for review in reviews],
            empty_message="No source onboarding records.",
        )
    return 0


def _handle_sources_scaffold(args: argparse.Namespace) -> int:
    try:
        scaffold = build_source_scaffold(
            source_id=args.source_id,
            name=args.name,
            publisher_name=args.publisher_name,
            url=args.url,
            source_type=args.source_type,
            source_class=args.source_class,
            subcategories=args.subcategory,
            trust_tier=args.trust_tier,
            source_group=args.group,
            fixture_only=args.fixture_only,
            disabled=args.disabled,
            coverage_purpose=args.coverage_purpose,
            last_reviewed_at=args.last_reviewed_at,
        )
    except SourcePolicyError as error:
        for message in error.errors:
            print(f"ERROR: {message}")
        return 1

    print(render_source_scaffold_yaml(scaffold), end="")
    return 0


def _optional_cli_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "true"


def _filter_source_review_payloads(
    reviews: list[dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    filters: list[Callable[[Mapping[str, Any]], bool]] = []
    if getattr(args, "group", None):
        filters.append(lambda review: review.get("source_group") == args.group)
    if getattr(args, "source_type", None):
        filters.append(lambda review: review.get("source_type") == args.source_type)
    if getattr(args, "source_class", None):
        filters.append(lambda review: review.get("source_class") == args.source_class)
    if getattr(args, "trust_tier", None):
        filters.append(lambda review: review.get("trust_tier") == args.trust_tier)
    if getattr(args, "category", None):
        filters.append(lambda review: args.category in review.get("category_scope", []))
    if getattr(args, "subcategory", None):
        filters.append(
            lambda review: args.subcategory in review.get("subcategory_scope", [])
        )
    if getattr(args, "enabled", None):
        enabled = _optional_cli_bool(args.enabled)
        filters.append(lambda review: review.get("enabled") is enabled)
    if getattr(args, "official", None):
        official = _optional_cli_bool(args.official)
        filters.append(lambda review: review.get("official_source") is official)
    if getattr(args, "deposit", None):
        deposit = _optional_cli_bool(args.deposit)
        filters.append(lambda review: review.get("deposit_account_source") is deposit)
    if getattr(args, "brokerage", None):
        brokerage = _optional_cli_bool(args.brokerage)
        filters.append(lambda review: review.get("brokerage_source") is brokerage)
    if getattr(args, "credit_card", None):
        credit_card = _optional_cli_bool(args.credit_card)
        filters.append(
            lambda review: review.get("credit_card_source") is credit_card
        )
    if getattr(args, "compliance_status", None):
        filters.append(
            lambda review: review.get("compliance_status") == args.compliance_status
        )

    for item_filter in filters:
        reviews = [review for review in reviews if item_filter(review)]
    return reviews


def _handle_run(args: argparse.Namespace) -> int:
    dry_run = _resolve_run_mode(args)
    run = run_banking_workflow_once(
        args.db,
        dry_run=dry_run,
        sources=args.sources,
        source_config_path=args.source_config,
        confirm_live=args.confirm_live,
        fixture_dir=args.fixture_dir,
        digest_output=args.digest_output,
        alert_config_path=args.alert_config,
        as_of=_parse_cli_date(args.as_of),
    )
    payload = _run_record_payload(run)
    if args.format == "json":
        _print_json(payload)
    else:
        print(
            "Banking run "
            f"{payload['id']} {payload['status']} "
            f"({'dry-run' if payload['dry_run'] else 'execute'})."
        )
        _print_run_detail(payload)
        message = _run_metadata_message(payload)
        if message:
            print(message)
    return 0 if payload["status"] == "succeeded" else 1


def _resolve_run_mode(args: argparse.Namespace) -> bool:
    if args.sources == "demo":
        if args.confirm_live:
            raise ValueError("--confirm-live is only supported with --sources public-pilot")
        return True if args.dry_run is None else bool(args.dry_run)

    if args.sources != "public-pilot":
        raise ValueError(f"Unsupported source group: {args.sources}")
    if args.confirm_live and args.dry_run is True:
        raise ValueError("--dry-run and --confirm-live cannot be used together")
    if args.confirm_live:
        return False
    if args.dry_run is True:
        return True
    raise ValueError("Public pilot live collection requires --confirm-live or use --dry-run.")


def _run_metadata_message(payload: Mapping[str, Any]) -> str | None:
    metadata = payload.get("metadata")
    if not isinstance(metadata, Mapping):
        return None
    public_pilot = metadata.get("public_pilot")
    if not isinstance(public_pilot, Mapping):
        return None
    message = public_pilot.get("message")
    if message == NO_ENABLED_PUBLIC_PILOT_MESSAGE:
        return NO_ENABLED_PUBLIC_PILOT_MESSAGE
    return str(message) if message else None


def _handle_runs(args: argparse.Namespace) -> int:
    initialize_database(args.db)
    runs = [_run_record_payload(run) for run in list_banking_runs(args.db, limit=args.limit)]
    if args.format == "json":
        _print_json(runs)
    else:
        _print_run_list(runs)
    return 0


def _handle_run_status(args: argparse.Namespace) -> int:
    initialize_database(args.db)
    run = get_banking_run(args.db, args.run_id)
    if run is None:
        raise ValueError(f"Run id {args.run_id} does not exist.")
    payload = _run_record_payload(run)
    if args.format == "json":
        _print_json(payload)
    else:
        _print_run_detail(payload)
    return 0


def _handle_demo(args: argparse.Namespace) -> int:
    _ = args.seed
    summary = run_offline_banking_smoke(
        args.db,
        fixture_dir=args.fixture_dir,
        digest_output=args.digest_output,
        alert_config_path=args.alert_config,
        as_of=_parse_cli_date(args.as_of),
        reset_db=args.reset,
    )
    if args.format == "json":
        _print_json(summary.to_dict())
    else:
        print("Banking MVP demo data ready.")
        _print_table(
            [
                {"metric": key, "value": value}
                for key, value in summary.to_dict().items()
            ],
            empty_message="No demo summary generated.",
        )
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


def _handle_qa_benchmark(args: argparse.Namespace) -> int:
    summary = run_banking_qa_benchmark(
        args.db,
        category=args.category,
        demo_dir=args.demo_dir,
        source_config=args.source_config,
        as_of=_parse_cli_date(args.as_of),
        reset_db=args.reset_db,
    )
    if args.format == "json" or args.json:
        _print_json(summary)
    else:
        print("Offline banking QA benchmark complete.")
        _print_qa_benchmark_summary(summary)
    return 1 if summary["verification_status"] == "fail" else 0


def _handle_reextract(args: argparse.Namespace) -> int:
    initialize_database(args.db)
    if args.all:
        results = reextract_all_snapshots(args.db, dry_run=args.dry_run)
    else:
        results = [reextract_snapshot(args.db, args.snapshot, dry_run=args.dry_run)]
    payload = {
        "dry_run": args.dry_run,
        "snapshot_count": len(results),
        "candidate_write_count": sum(
            1 for result in results if result.new_candidate_id is not None
        ),
        "changed_snapshot_count": sum(1 for result in results if result.changed_fields),
        "results": [result.to_dict() for result in results],
        "canonical_values_preserved": True,
    }
    if args.format == "json":
        _print_json(payload)
    else:
        _print_reextract_summary(payload)
    return 0


def _filtered_deals(
    db_path: str,
    *,
    status: str | None = None,
    institution: str | None = None,
    subcategory: str | None = None,
    issuer: str | None = None,
    card: str | None = None,
    customer_type: str | None = None,
    offer_currency: str | None = None,
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
    if issuer:
        issuer_filter = issuer.lower()
        filters.append(
            lambda deal: issuer_filter
            in str(_card_details(deal).get("issuer_name") or "").lower()
        )
    if card:
        card_filter = card.lower()
        filters.append(
            lambda deal: card_filter
            in str(_card_details(deal).get("card_name") or "").lower()
        )
    if customer_type:
        filters.append(
            lambda deal: _card_details(deal).get("customer_type") == customer_type
        )
    if offer_currency:
        filters.append(
            lambda deal: _card_details(deal).get("offer_currency") == offer_currency
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
    detail = get_banking_deal(db_path, int(deal["id"])) or deal
    terms = _normalized_terms(detail.get("terms") or {})
    card_details = _credit_card_details(terms, score.to_dict(), score.missing_data_warnings)
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
        "credit_card": card_details,
    }


def _search_deals(
    db_path: str,
    *,
    query: str | None = None,
    institution: str | None = None,
    subcategory: str | None = None,
    issuer: str | None = None,
    card: str | None = None,
    customer_type: str | None = None,
    offer_currency: str | None = None,
    min_bonus: int | None = None,
    min_net_value: int | None = None,
    score_band: str | None = None,
    recommended_action: str | None = None,
    status: str | None = None,
    expiring_days: int | None = None,
    needs_review: bool = False,
) -> list[dict[str, Any]]:
    rows = list_banking_deals(
        db_path,
        status=status,
        subcategory=subcategory,
    )
    records = [_search_record(db_path, row) for row in rows]
    query_tokens = _query_tokens(query)

    filters: list[Callable[[Mapping[str, Any]], bool]] = []
    if query_tokens:
        filters.append(lambda deal: _matches_query(deal, query_tokens))
    if institution:
        institution_filter = institution.lower()
        filters.append(
            lambda deal: institution_filter
            in str(deal.get("institution_name") or "").lower()
        )
    if issuer:
        issuer_filter = issuer.lower()
        filters.append(
            lambda deal: issuer_filter
            in str(_card_details(deal).get("issuer_name") or "").lower()
        )
    if card:
        card_filter = card.lower()
        filters.append(
            lambda deal: card_filter
            in str(_card_details(deal).get("card_name") or "").lower()
        )
    if customer_type:
        filters.append(
            lambda deal: _card_details(deal).get("customer_type") == customer_type
        )
    if offer_currency:
        filters.append(
            lambda deal: _card_details(deal).get("offer_currency") == offer_currency
        )
    if min_bonus is not None:
        filters.append(lambda deal: int(deal.get("bonus_amount_cents") or 0) >= min_bonus)
    if min_net_value is not None:
        filters.append(
            lambda deal: int(deal.get("estimated_net_value_cents") or 0)
            >= min_net_value
        )
    if score_band:
        filters.append(lambda deal: deal.get("score_band") == score_band)
    if recommended_action:
        filters.append(
            lambda deal: deal.get("recommended_action") == recommended_action
        )
    if expiring_days is not None:
        filters.append(
            lambda deal: _expires_within(deal.get("expires_at"), expiring_days)
        )
    if needs_review:
        filters.append(lambda deal: bool(deal.get("needs_review")))

    for item_filter in filters:
        records = [record for record in records if item_filter(record)]

    for record in records:
        record["match_reason"] = _match_reason(
            query_tokens=query_tokens,
            institution=institution,
            subcategory=subcategory,
            issuer=issuer,
            card=card,
            customer_type=customer_type,
            offer_currency=offer_currency,
            min_bonus=min_bonus,
            min_net_value=min_net_value,
            score_band=score_band,
            recommended_action=recommended_action,
            status=status,
            expiring_days=expiring_days,
            needs_review=needs_review,
        )

    ranked = sorted(
        records,
        key=lambda deal: (
            -int(deal.get("score_0_to_100") or 0),
            -int(deal.get("estimated_net_value_cents") or 0),
            -int(deal.get("bonus_amount_cents") or 0),
            int(deal["id"]),
        ),
    )
    return [_public_search_record(record) for record in ranked]


def _search_record(db_path: str, deal: Mapping[str, Any]) -> dict[str, Any]:
    deal_id = int(deal["id"])
    detail = _deal_detail(db_path, deal_id)
    score = detail["score"]
    source_context = _source_context(deal, detail["source_links"])
    return {
        "id": deal_id,
        "title": detail["title"],
        "institution_name": detail["institution_name"],
        "subcategory": detail["subcategory"],
        "status": detail["status"],
        "bonus_amount_cents": detail.get("bonus_amount_cents"),
        "estimated_net_value_cents": detail.get("estimated_net_value_cents"),
        "score_0_to_100": score["score_0_to_100"],
        "score_band": score["score_band"],
        "recommended_action": score["recommended_action"],
        "expires_at": detail.get("expires_at"),
        "application_deadline": detail.get("application_deadline"),
        "needs_review": _needs_review(
            deal,
            score_banking_deal(db_path, deal_id),
            detail["change_events"],
        ),
        "match_reason": "ranked by score and estimated net value",
        "source_name": source_context["source_name"],
        "source_url": source_context["source_url"],
        "source_context": source_context,
        "requirements": detail["requirements"],
        "restrictions": detail["restrictions"],
        "credit_card": detail["credit_card"],
        "missing_data_warnings": detail["missing_data_warnings"],
    }


def _public_search_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "title": record["title"],
        "institution_name": record["institution_name"],
        "subcategory": record["subcategory"],
        "status": record["status"],
        "bonus_amount_cents": record.get("bonus_amount_cents"),
        "estimated_net_value_cents": record.get("estimated_net_value_cents"),
        "score_0_to_100": record["score_0_to_100"],
        "score_band": record["score_band"],
        "recommended_action": record["recommended_action"],
        "expires_at": record.get("expires_at"),
        "application_deadline": record.get("application_deadline"),
        "needs_review": record["needs_review"],
        "match_reason": record["match_reason"],
        "source_name": record.get("source_name"),
        "source_url": record.get("source_url"),
        "credit_card": record.get("credit_card"),
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
    field_evidence = _review_field_evidence(db_path, deal_id)
    return {
        "id": deal["id"],
        "title": deal["title"],
        "institution_name": deal["institution_name"],
        "category": deal["category"],
        "subcategory": deal["subcategory"],
        "status": deal["status"],
        "source_urls": source_urls,
        "source_links": [_source_link_payload(link) for link in source_links],
        "source_snapshots": _source_snapshots(db_path, source_links),
        "bonus_amount_cents": deal.get("bonus_amount_cents"),
        "estimated_net_value_cents": score.estimated_net_value,
        "score": score.to_dict(),
        "requirements": _requirements(terms),
        "restrictions": _restrictions(terms),
        "credit_card": _credit_card_details(
            terms,
            score.to_dict(),
            score.missing_data_warnings,
        ),
        "expires_at": deal.get("expires_at"),
        "application_deadline": deal.get("application_deadline"),
        "confidence_score": deal.get("confidence_score"),
        "missing_data_warnings": score.missing_data_warnings,
        "missing_evidence_warnings": _missing_evidence_warnings(
            _evidence_field_values(deal, terms),
            field_evidence,
        ),
        "evidence_authority_warnings": _evidence_authority_warnings(field_evidence),
        "evidence_references": [_source_link_payload(link) for link in source_links],
        "field_evidence": field_evidence,
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


def _credit_card_terms(terms: Mapping[str, Any]) -> dict[str, Any]:
    terms_json = _json_value(terms.get("terms_json"))
    if not isinstance(terms_json, Mapping):
        return {}
    credit_card = terms_json.get("credit_card")
    return dict(credit_card) if isinstance(credit_card, Mapping) else {}


def _credit_card_details(
    terms: Mapping[str, Any],
    score: Mapping[str, Any],
    missing_data_warnings: Sequence[str],
) -> dict[str, Any] | None:
    card_terms = _credit_card_terms(terms)
    if not card_terms:
        return None
    return {
        "issuer_name": card_terms.get("issuer_name"),
        "card_name": card_terms.get("card_name"),
        "customer_type": card_terms.get("customer_type"),
        "offer_currency": card_terms.get("offer_currency"),
        "headline_bonus_amount": card_terms.get("headline_bonus_amount"),
        "estimated_cash_equivalent_value_cents": score.get(
            "estimated_cash_equivalent_value"
        ),
        "reward_valuation_assumption_ids": score.get(
            "reward_valuation_assumption_ids",
            [],
        ),
        "minimum_spend_cents": card_terms.get("minimum_spend_cents"),
        "spend_window_days": card_terms.get("spend_window_days"),
        "annual_fee_cents": card_terms.get("annual_fee_cents"),
        "first_year_annual_fee_waived": card_terms.get(
            "first_year_annual_fee_waived"
        ),
        "statement_credit_amount_cents": card_terms.get(
            "statement_credit_amount_cents"
        ),
        "statement_credit_requirements": card_terms.get(
            "statement_credit_requirements"
        ),
        "targeted": card_terms.get("targeted"),
        "eligibility_restriction_notes": _json_value(
            card_terms.get("eligibility_restriction_notes")
        )
        or [],
        "missing_critical_fields": _card_missing_fields(missing_data_warnings),
    }


def _card_details(deal: Mapping[str, Any]) -> Mapping[str, Any]:
    value = deal.get("credit_card")
    return value if isinstance(value, Mapping) else {}


def _card_missing_fields(warnings: Sequence[str]) -> list[str]:
    return [
        warning.split(" missing", 1)[0]
        for warning in warnings
        if warning.endswith(" missing")
    ]


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
        "raw_snapshot_id": link.get("raw_snapshot_id"),
        "candidate_id": link.get("candidate_id"),
        "source_name": link.get("source_name"),
        "source_url": link.get("source_url"),
        "source_authority": link.get("source_authority"),
        "retrieved_at": link.get("retrieved_at"),
        "confidence_score": link.get("confidence_score"),
        "evidence": _json_value(link.get("evidence_json")),
    }


def _source_snapshots(
    db_path: str,
    source_links: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    seen: set[int] = set()
    for link in source_links:
        raw_snapshot_id = link.get("raw_snapshot_id")
        if raw_snapshot_id is None:
            continue
        snapshot_id = int(raw_snapshot_id)
        if snapshot_id in seen:
            continue
        seen.add(snapshot_id)
        snapshot = get_raw_snapshot(db_path, snapshot_id)
        if snapshot is None:
            continue
        raw_payload = _json_value(snapshot.get("raw_payload_json"))
        snapshots.append(
            {
                "id": snapshot["id"],
                "source_record_id": snapshot.get("source_record_id"),
                "source_name": snapshot.get("source_name"),
                "source_url": snapshot.get("source_url"),
                "retrieved_at": snapshot.get("retrieved_at"),
                "content_hash": snapshot.get("content_hash"),
                "http_status": snapshot.get("http_status"),
                "collector_name": snapshot.get("collector_name"),
                "raw_payload_metadata": _raw_payload_metadata(raw_payload),
                "raw_text_length": len(snapshot.get("raw_text") or ""),
            }
        )
    return sorted(snapshots, key=lambda item: int(item["id"]))


def _review_field_evidence(db_path: str, deal_id: int) -> list[dict[str, Any]]:
    evidence_items = [
        item
        for item in list_field_evidence_links(db_path, deal_id=deal_id)
        if item.get("field") in CRITICAL_EVIDENCE_FIELDS
    ]
    expanded: list[dict[str, Any]] = []
    for item in evidence_items:
        expanded.append(item)
        if item.get("field") == "expires_at":
            deadline_item = dict(item)
            deadline_item["field"] = "application_deadline"
            expanded.append(deadline_item)
    return sorted(
        expanded,
        key=lambda item: (
            str(item.get("field") or ""),
            int(item.get("raw_snapshot_id") or 0),
            int(item.get("start") or 0),
        ),
    )


def _field_evidence(
    db_path: str,
    source_links: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    evidence_items: list[dict[str, Any]] = []
    for link in source_links:
        snapshot = None
        raw_snapshot_id = link.get("raw_snapshot_id")
        if raw_snapshot_id is not None:
            snapshot = get_raw_snapshot(db_path, int(raw_snapshot_id))

        evidence = _json_value(link.get("evidence_json")) or []
        if not isinstance(evidence, list):
            continue
        for span in evidence:
            if not isinstance(span, Mapping):
                continue
            field_name = span.get("field")
            if field_name not in CRITICAL_EVIDENCE_FIELDS:
                continue
            evidence_items.append(
                _field_evidence_item(
                    field_name,
                    span,
                    link,
                    snapshot=snapshot,
                    raw_snapshot_id=raw_snapshot_id,
                )
            )
            if field_name == "expires_at":
                evidence_items.append(
                    _field_evidence_item(
                        "application_deadline",
                        span,
                        link,
                        snapshot=snapshot,
                        raw_snapshot_id=raw_snapshot_id,
                    )
                )
    return sorted(
        evidence_items,
        key=lambda item: (
            str(item.get("field") or ""),
            int(item.get("raw_snapshot_id") or 0),
            int(item.get("start") or 0),
        ),
    )


def _field_evidence_item(
    field_name: str,
    span: Mapping[str, Any],
    link: Mapping[str, Any],
    *,
    snapshot: Mapping[str, Any] | None,
    raw_snapshot_id: Any,
) -> dict[str, Any]:
    return {
        "field": field_name,
        "excerpt": span.get("text"),
        "start": span.get("start"),
        "end": span.get("end"),
        "source_name": link.get("source_name"),
        "source_url": link.get("source_url"),
        "source_authority": link.get("source_authority"),
        "raw_snapshot_id": raw_snapshot_id,
        "candidate_id": link.get("candidate_id"),
        "content_hash": snapshot.get("content_hash") if snapshot else None,
        "collector_name": snapshot.get("collector_name") if snapshot else None,
        "retrieved_at": link.get("retrieved_at"),
        "confidence_score": link.get("confidence_score"),
    }


def _evidence_field_values(
    deal: Mapping[str, Any],
    terms: Mapping[str, Any],
) -> dict[str, Any]:
    card_terms = _credit_card_terms(terms)
    return {
        "bonus_amount_cents": deal.get("bonus_amount_cents"),
        "expires_at": deal.get("expires_at"),
        "application_deadline": deal.get("application_deadline"),
        **{
            field_name: terms.get(field_name)
            for field_name in CRITICAL_EVIDENCE_FIELDS
            if field_name not in {"bonus_amount_cents", "expires_at", "application_deadline"}
        },
        **{
            field_name: card_terms.get(field_name)
            for field_name in CRITICAL_EVIDENCE_FIELDS
            if field_name in card_terms
        },
    }


def _missing_evidence_warnings(
    field_values: Mapping[str, Any],
    field_evidence: Sequence[Mapping[str, Any]],
) -> list[str]:
    evidence_fields = {item.get("field") for item in field_evidence}
    warnings = []
    for field_name in CRITICAL_EVIDENCE_FIELDS:
        value = field_values.get(field_name)
        if value is not None and field_name not in evidence_fields:
            warnings.append(f"{field_name} has value but no field-level evidence")
    return warnings


def _evidence_authority_warnings(
    field_evidence: Sequence[Mapping[str, Any]],
) -> list[str]:
    by_field: dict[str, set[str]] = {}
    for item in field_evidence:
        field_name = item.get("field")
        if field_name is None:
            continue
        by_field.setdefault(str(field_name), set()).add(
            str(item.get("source_authority") or "unknown")
        )
    warnings = []
    for field_name in sorted(by_field):
        authorities = by_field[field_name]
        if "official" not in authorities and authorities <= {"secondary"}:
            warnings.append(f"{field_name} has only secondary-source evidence")
    return warnings


def _source_context(
    deal: Mapping[str, Any],
    source_links: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if source_links:
        first = source_links[0]
        return {
            "source_name": first.get("source_name"),
            "source_url": first.get("source_url"),
            "source_authority": first.get("source_authority"),
        }
    return {
        "source_name": deal.get("source_name"),
        "source_url": deal.get("source_url"),
        "source_authority": "unknown",
    }


def _raw_payload_metadata(raw_payload: Any) -> dict[str, Any] | None:
    if raw_payload is None:
        return None
    if isinstance(raw_payload, Mapping):
        return {
            "keys": sorted(str(key) for key in raw_payload),
            "field_count": len(raw_payload),
        }
    if isinstance(raw_payload, list):
        return {"type": "list", "item_count": len(raw_payload)}
    return {"type": type(raw_payload).__name__}


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


def _query_tokens(query: str | None) -> list[str]:
    if not query:
        return []
    return [token.lower() for token in query.split() if token.strip()]


def _matches_query(deal: Mapping[str, Any], tokens: Sequence[str]) -> bool:
    haystack = _search_text(deal)
    return all(token in haystack for token in tokens)


def _search_text(deal: Mapping[str, Any]) -> str:
    values = [
        deal.get("title"),
        deal.get("institution_name"),
        deal.get("subcategory"),
        deal.get("source_name"),
        deal.get("source_url"),
        deal.get("requirements"),
        deal.get("restrictions"),
        deal.get("credit_card"),
        deal.get("missing_data_warnings"),
    ]
    return " ".join(_flatten_search_values(values)).lower()


def _flatten_search_values(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, Mapping):
        flattened: list[str] = []
        for key, value in values.items():
            flattened.append(str(key))
            flattened.extend(_flatten_search_values(value))
        return flattened
    if isinstance(values, (list, tuple, set)):
        flattened = []
        for value in values:
            flattened.extend(_flatten_search_values(value))
        return flattened
    return [str(values)]


def _match_reason(
    *,
    query_tokens: Sequence[str],
    institution: str | None,
    subcategory: str | None,
    issuer: str | None,
    card: str | None,
    customer_type: str | None,
    offer_currency: str | None,
    min_bonus: int | None,
    min_net_value: int | None,
    score_band: str | None,
    recommended_action: str | None,
    status: str | None,
    expiring_days: int | None,
    needs_review: bool,
) -> str:
    reasons: list[str] = []
    if query_tokens:
        reasons.append(f"matched query '{' '.join(query_tokens)}'")
    if institution:
        reasons.append(f"institution contains '{institution}'")
    if subcategory:
        reasons.append(f"subcategory {subcategory}")
    if issuer:
        reasons.append(f"issuer matches {issuer}")
    if card:
        reasons.append(f"card matches {card}")
    if customer_type:
        reasons.append(f"customer type {customer_type}")
    if offer_currency:
        reasons.append(f"offer currency {offer_currency}")
    if min_bonus is not None:
        reasons.append(f"bonus at least {_money(min_bonus)}")
    if min_net_value is not None:
        reasons.append(f"net value at least {_money(min_net_value)}")
    if score_band:
        reasons.append(f"score band {score_band}")
    if recommended_action:
        reasons.append(f"recommended action {recommended_action}")
    if status:
        reasons.append(f"status {status}")
    if expiring_days is not None:
        reasons.append(f"expires within {expiring_days} days")
    if needs_review:
        reasons.append("needs review")
    if not reasons:
        reasons.append("ranked by score and estimated net value")
    return "; ".join(reasons) + "."


def _print_deal_list(deals: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        _print_json(deals)
        return

    rows = [
        {
            "card": (_card_details(deal).get("card_name") or ""),
            "id": deal["id"],
            "status": deal["status"],
            "institution": deal["institution_name"],
            "subcategory": deal["subcategory"],
            "currency": (_card_details(deal).get("offer_currency") or ""),
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


def _print_search_results(deals: list[dict[str, Any]], output_format: str) -> None:
    if output_format == "json":
        _print_json(deals)
        return

    rows = [
        {
            "card": (_card_details(deal).get("card_name") or ""),
            "id": deal["id"],
            "institution": deal["institution_name"],
            "subcategory": deal["subcategory"],
            "currency": (_card_details(deal).get("offer_currency") or ""),
            "bonus": _money(deal.get("bonus_amount_cents")),
            "net": _money(deal.get("estimated_net_value_cents")),
            "score": deal["score_0_to_100"],
            "band": deal["score_band"],
            "action": deal["recommended_action"],
            "review": "yes" if deal["needs_review"] else "no",
            "source": deal.get("source_name") or deal.get("source_url") or "unknown",
            "reason": deal["match_reason"],
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
    if detail.get("credit_card"):
        print("Credit card:")
        for key, value in detail["credit_card"].items():
            print(f"  - {key}: {_display_value(value)}")
    print("Missing data warnings:")
    for warning in detail["missing_data_warnings"] or ["none"]:
        print(f"  - {warning}")
    print("Missing evidence warnings:")
    for warning in detail["missing_evidence_warnings"] or ["none"]:
        print(f"  - {warning}")
    print("Evidence authority warnings:")
    for warning in detail["evidence_authority_warnings"] or ["none"]:
        print(f"  - {warning}")
    print("Evidence references:")
    for item in detail["evidence_references"] or [{"source_name": "none"}]:
        print(
            "  - "
            f"{item.get('source_name')} "
            f"{item.get('source_url') or ''}".rstrip()
        )
    print("Source snapshots:")
    for item in detail["source_snapshots"] or [{"id": "none"}]:
        if item.get("id") == "none":
            print("  - none")
            continue
        content_hash = item.get("content_hash") or "unknown"
        print(
            "  - "
            f"snapshot {item.get('id')}: {item.get('source_name')} "
            f"(hash {content_hash[:12]}, collector {item.get('collector_name')}, "
            f"retrieved {item.get('retrieved_at') or 'unknown'})"
        )
    print("Field evidence:")
    for item in detail["field_evidence"] or [{"field": "none"}]:
        if item.get("field") == "none":
            print("  - none")
            continue
        content_hash = item.get("content_hash") or "unknown"
        excerpt = item.get("excerpt") or ""
        print(
            "  - "
            f"{item.get('field')}: {excerpt!r} "
            f"(snapshot {item.get('raw_snapshot_id')}, hash {content_hash[:12]})"
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


def _print_run_list(runs: list[dict[str, Any]]) -> None:
    rows = [
        {
            "id": run["id"],
            "status": run["status"],
            "mode": "dry-run" if run["dry_run"] else "execute",
            "started": run["started_at"],
            "ended": run.get("ended_at") or "running",
            "candidates": run["candidate_count"],
            "deals": run["canonical_deal_count"],
            "conflicts": run["conflict_count"],
            "errors": run["error_count"],
        }
        for run in runs
    ]
    _print_table(rows, empty_message="No banking runs recorded.")


def _print_run_detail(run: Mapping[str, Any]) -> None:
    rows = [
        {"field": key, "value": _display_value(value)}
        for key, value in run.items()
        if key not in {"metadata", "errors"}
    ]
    _print_table(rows, empty_message="No run data.")
    print("Errors:")
    for error in run.get("errors") or ["none"]:
        print(f"  - {error}")
    print("Metadata:")
    metadata = run.get("metadata") or {}
    if isinstance(metadata, Mapping):
        for key, value in metadata.items():
            print(f"  - {key}: {_display_value(value)}")
    else:
        print(f"  - {_display_value(metadata)}")


def _print_qa_benchmark_summary(summary: Mapping[str, Any]) -> None:
    rows = [
        {"metric": "verification_status", "value": summary["verification_status"]},
        {"metric": "category", "value": summary["category"]},
        {"metric": "offline_only", "value": summary["offline_only"]},
    ]
    rows.extend(
        {"metric": key, "value": value}
        for key, value in summary["summary"].items()
    )
    _print_table(rows, empty_message="No QA benchmark summary generated.")

    print("Sections:")
    section_rows = []
    for name, section in summary["sections"].items():
        section_rows.append(
            {
                "section": name,
                "status": section["status"],
                "found": section.get("expected_deals_found", "n/a"),
                "missed": ", ".join(section.get("expected_deals_missed") or [])
                or "none",
                "failures": ", ".join(section.get("failures") or []) or "none",
            }
        )
    _print_table(section_rows, empty_message="No QA benchmark sections generated.")

    if summary["failures"]:
        print("Failures:")
        for failure in summary["failures"]:
            print(f"  - {failure}")


def _print_reextract_summary(payload: Mapping[str, Any]) -> None:
    print(
        "Offline banking re-extraction complete "
        f"({'dry-run' if payload['dry_run'] else 'write'})."
    )
    rows = []
    for item in payload["results"]:
        changed = item.get("changed_fields") or []
        rows.append(
            {
                "snapshot": item["raw_snapshot_id"],
                "previous_candidate": item.get("previous_candidate_id") or "none",
                "new_candidate": item.get("new_candidate_id") or "dry-run",
                "changed_fields": ",".join(change["field"] for change in changed)
                or "none",
                "source": item.get("source_name") or "unknown",
            }
        )
    _print_table(rows, empty_message="No raw snapshots found.")
    print("Canonical values preserved: yes")


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


def _money_arg(value: str) -> int:
    raw = value.strip().replace("$", "").replace(",", "")
    try:
        amount = float(raw)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            f"expected dollar amount, got {value!r}"
        ) from error
    if amount < 0:
        raise argparse.ArgumentTypeError("amount must be non-negative")
    return int(round(amount * 100))


def _run_record_payload(run: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "id": run["id"],
        "started_at": run["started_at"],
        "ended_at": run.get("ended_at"),
        "status": run["status"],
        "dry_run": _to_bool(run["dry_run"]),
        "source_count": run["source_count"],
        "raw_snapshot_count": run["raw_snapshot_count"],
        "candidate_count": run["candidate_count"],
        "rejected_candidate_count": run["rejected_candidate_count"],
        "canonical_deal_count": run["canonical_deal_count"],
        "duplicate_merge_count": run["duplicate_merge_count"],
        "conflict_count": run["conflict_count"],
        "review_needed_deal_count": run["review_needed_deal_count"],
        "scored_deal_count": run["scored_deal_count"],
        "expired_scored_deal_count": run["expired_scored_deal_count"],
        "error_count": run["error_count"],
        "errors": _json_value(run.get("errors_json")) or [],
        "digest_path": run.get("digest_path"),
        "metadata": _json_value(run.get("metadata_json")) or {},
    }
