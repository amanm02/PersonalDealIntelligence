"""SQLite storage primitives for the Banking MVP."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from typing import Any, Mapping


DbPath = str | Path


def initialize_database(db_path: DbPath) -> None:
    """Create or migrate a local SQLite database."""

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
              version TEXT PRIMARY KEY,
              applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        applied_versions = {
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations")
        }

        for migration_name, migration_sql in _migration_scripts():
            version = migration_name.split("_", 1)[0]
            if version in applied_versions:
                continue
            connection.executescript(migration_sql)
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (?)",
                (version,),
            )
        connection.commit()


def insert_source_record(
    db_path: DbPath,
    source_record: Mapping[str, Any] | None = None,
    **fields: Any,
) -> int:
    """Insert source metadata and return the new source id."""

    data = _merge_record(source_record, fields)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO source_records (
              source_name,
              source_url,
              source_type,
              collection_method,
              enabled,
              max_frequency,
              compliance_notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["source_name"],
                data.get("source_url"),
                data["source_type"],
                data["collection_method"],
                _bool_to_int(data.get("enabled", False)),
                data.get("max_frequency"),
                data.get("compliance_notes"),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def insert_raw_snapshot(
    db_path: DbPath,
    raw_snapshot: Mapping[str, Any] | None = None,
    **fields: Any,
) -> int:
    """Insert a raw source snapshot and return the new snapshot id."""

    data = _merge_record(raw_snapshot, fields)
    raw_text = data["raw_text"]
    content_hash = data.get("content_hash") or _hash_text(raw_text)

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO raw_deal_snapshots (
              source_record_id,
              source_url,
              source_name,
              retrieved_at,
              content_hash,
              raw_text,
              raw_html_path,
              raw_payload_json,
              http_status,
              collector_name
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("source_record_id"),
                data.get("source_url"),
                data["source_name"],
                data.get("retrieved_at", _utc_now()),
                content_hash,
                raw_text,
                data.get("raw_html_path"),
                _json_text(data.get("raw_payload_json")),
                data.get("http_status"),
                data["collector_name"],
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def get_raw_snapshot(db_path: DbPath, snapshot_id: int) -> dict[str, Any] | None:
    """Return one raw source snapshot, or None."""

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM raw_deal_snapshots WHERE id = ?",
            (snapshot_id,),
        ).fetchone()
        return _row_to_dict(row) if row is not None else None


def get_source_record(db_path: DbPath, source_record_id: int) -> dict[str, Any] | None:
    """Return one source record, or None."""

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM source_records WHERE id = ?",
            (source_record_id,),
        ).fetchone()
        return _row_to_dict(row) if row is not None else None


def insert_banking_deal(
    db_path: DbPath,
    banking_deal: Mapping[str, Any] | None = None,
    **fields: Any,
) -> int:
    """Insert a canonical banking deal, optional terms, and initial status event."""

    data = _merge_record(banking_deal, fields)
    terms = data.get("terms")

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO banking_deals (
              canonical_key,
              title,
              institution_name,
              category,
              subcategory,
              bonus_amount_cents,
              estimated_net_value_cents,
              currency,
              source_url,
              source_name,
              discovered_at,
              last_seen_at,
              expires_at,
              application_deadline,
              status,
              confidence_score,
              raw_snapshot_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["canonical_key"],
                data["title"],
                data["institution_name"],
                data.get("category", "banking"),
                data["subcategory"],
                data.get("bonus_amount_cents"),
                data.get("estimated_net_value_cents"),
                data.get("currency", "USD"),
                data.get("source_url"),
                data.get("source_name"),
                data.get("discovered_at", _utc_now()),
                data.get("last_seen_at", _utc_now()),
                data.get("expires_at"),
                data.get("application_deadline"),
                data.get("status", "new"),
                data.get("confidence_score"),
                data.get("raw_snapshot_id"),
            ),
        )
        deal_id = int(cursor.lastrowid)

        if terms is not None:
            _insert_terms(connection, deal_id, terms)

        connection.execute(
            """
            INSERT INTO deal_status_events (deal_id, old_status, new_status, note)
            VALUES (?, NULL, ?, ?)
            """,
            (
                deal_id,
                data.get("status", "new"),
                "Initial status recorded at deal insert.",
            ),
        )
        connection.commit()
        return deal_id


def insert_banking_deal_candidate(
    db_path: DbPath,
    candidate: Mapping[str, Any] | None = None,
    **fields: Any,
) -> int:
    """Insert an extracted pre-dedupe banking deal candidate."""

    data = _merge_record(candidate, fields)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO banking_deal_candidates (
              raw_snapshot_id,
              title,
              institution_name,
              category,
              subcategory,
              bonus_amount_cents,
              currency,
              source_url,
              source_name,
              retrieved_at,
              expires_at,
              application_deadline,
              minimum_deposit_amount_cents,
              direct_deposit_required,
              direct_deposit_minimum_cents,
              minimum_balance_required_cents,
              balance_hold_days,
              monthly_fee_cents,
              monthly_fee_waiver_terms,
              early_closure_fee_cents,
              state_restrictions_json,
              new_customer_only,
              household_limit,
              hard_pull_risk,
              soft_pull_only,
              evidence_spans_json,
              missing_fields_json,
              extraction_notes_json,
              tiered_bonus_json,
              raw_pattern_matches_json,
              confidence_score,
              rejected,
              rejection_reason
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["raw_snapshot_id"],
                data.get("title"),
                data.get("institution_name"),
                data.get("category", "banking"),
                data.get("subcategory"),
                data.get("bonus_amount_cents"),
                data.get("currency", "USD"),
                data.get("source_url"),
                data.get("source_name"),
                data.get("retrieved_at"),
                data.get("expires_at"),
                data.get("application_deadline"),
                data.get("minimum_deposit_amount_cents"),
                _bool_to_int(data.get("direct_deposit_required")),
                data.get("direct_deposit_minimum_cents"),
                data.get("minimum_balance_required_cents"),
                data.get("balance_hold_days"),
                data.get("monthly_fee_cents"),
                data.get("monthly_fee_waiver_terms"),
                data.get("early_closure_fee_cents"),
                _json_text(data.get("state_restrictions")),
                _bool_to_int(data.get("new_customer_only")),
                data.get("household_limit"),
                _bool_to_int(data.get("hard_pull_risk")),
                _bool_to_int(data.get("soft_pull_only")),
                _json_text(data.get("evidence_spans")),
                _json_text(data.get("missing_fields")),
                _json_text(data.get("extraction_notes")),
                _json_text(data.get("tiered_bonus")),
                _json_text(data.get("raw_pattern_matches")),
                data.get("confidence_score"),
                _bool_to_int(data.get("rejected", False)),
                data.get("rejection_reason"),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def mark_banking_deal_candidate_canonicalized(
    db_path: DbPath,
    candidate_id: int,
    *,
    deal_id: int | None,
    status: str,
) -> None:
    """Record canonicalization status for one extracted candidate."""

    with _connect(db_path) as connection:
        connection.execute(
            """
            UPDATE banking_deal_candidates
            SET canonical_deal_id = ?,
                canonicalized_at = ?,
                canonicalization_status = ?
            WHERE id = ?
            """,
            (deal_id, _utc_now(), status, candidate_id),
        )
        connection.commit()


def insert_banking_deal_source_link(
    db_path: DbPath,
    source_link: Mapping[str, Any] | None = None,
    **fields: Any,
) -> int:
    """Link a canonical deal to candidate/source evidence."""

    data = _merge_record(source_link, fields)
    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO banking_deal_source_links (
              deal_id,
              candidate_id,
              raw_snapshot_id,
              source_name,
              source_url,
              source_authority,
              retrieved_at,
              confidence_score,
              evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["deal_id"],
                data["candidate_id"],
                data["raw_snapshot_id"],
                data["source_name"],
                data.get("source_url"),
                data.get("source_authority", "unknown"),
                data.get("retrieved_at"),
                data.get("confidence_score"),
                _json_text(data.get("evidence")),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def insert_deal_change_event(
    db_path: DbPath,
    deal_id: int,
    event_type: str,
    changed_fields: Mapping[str, Any] | None = None,
    *,
    note: str | None = None,
) -> int:
    """Record a material canonical deal change or conflict."""

    with _connect(db_path) as connection:
        cursor = connection.execute(
            """
            INSERT INTO deal_change_events (
              deal_id,
              event_type,
              changed_fields_json,
              note
            )
            VALUES (?, ?, ?, ?)
            """,
            (deal_id, event_type, _json_text(changed_fields), note),
        )
        connection.commit()
        return int(cursor.lastrowid)


def insert_status_event(
    db_path: DbPath,
    deal_id: int,
    new_status: str,
    *,
    old_status: str | None = None,
    note: str | None = None,
) -> int:
    """Record a status transition and update the canonical deal status."""

    with _connect(db_path) as connection:
        if old_status is None:
            row = connection.execute(
                "SELECT status FROM banking_deals WHERE id = ?",
                (deal_id,),
            ).fetchone()
            if row is None:
                raise ValueError(f"Deal id {deal_id} does not exist.")
            old_status = row["status"]

        cursor = connection.execute(
            """
            INSERT INTO deal_status_events (deal_id, old_status, new_status, note)
            VALUES (?, ?, ?, ?)
            """,
            (deal_id, old_status, new_status, note),
        )
        connection.execute(
            """
            UPDATE banking_deals
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (new_status, deal_id),
        )
        connection.commit()
        return int(cursor.lastrowid)


def update_banking_deal(
    db_path: DbPath,
    deal_id: int,
    updates: Mapping[str, Any],
) -> None:
    """Update selected canonical deal columns."""

    allowed_columns = {
        "canonical_key",
        "title",
        "institution_name",
        "subcategory",
        "bonus_amount_cents",
        "estimated_net_value_cents",
        "currency",
        "source_url",
        "source_name",
        "discovered_at",
        "last_seen_at",
        "expires_at",
        "application_deadline",
        "status",
        "confidence_score",
        "raw_snapshot_id",
    }
    columns = [column for column in updates if column in allowed_columns]
    if not columns:
        return

    assignments = ", ".join(f"{column} = ?" for column in columns)
    values = [updates[column] for column in columns]
    values.append(deal_id)

    with _connect(db_path) as connection:
        connection.execute(
            f"""
            UPDATE banking_deals
            SET {assignments}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            tuple(values),
        )
        connection.commit()


def upsert_banking_deal_terms(
    db_path: DbPath,
    deal_id: int,
    terms: Mapping[str, Any],
) -> None:
    """Insert or update term fields for a canonical banking deal."""

    with _connect(db_path) as connection:
        existing = connection.execute(
            "SELECT id FROM banking_deal_terms WHERE deal_id = ?",
            (deal_id,),
        ).fetchone()
        if existing is None:
            _insert_terms(connection, deal_id, terms)
        else:
            _update_terms(connection, deal_id, terms)
        connection.commit()


def get_banking_deal_candidate(
    db_path: DbPath,
    candidate_id: int,
) -> dict[str, Any] | None:
    """Return one extracted banking deal candidate, or None."""

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM banking_deal_candidates WHERE id = ?",
            (candidate_id,),
        ).fetchone()
        return _row_to_dict(row) if row is not None else None


def get_banking_deal(db_path: DbPath, deal_id: int) -> dict[str, Any] | None:
    """Return one banking deal with nested terms, or None."""

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM banking_deals WHERE id = ?",
            (deal_id,),
        ).fetchone()
        if row is None:
            return None

        deal = _row_to_dict(row)
        terms = connection.execute(
            "SELECT * FROM banking_deal_terms WHERE deal_id = ?",
            (deal_id,),
        ).fetchone()
        deal["terms"] = _row_to_dict(terms) if terms is not None else None
        return deal


def get_banking_deal_by_canonical_key(
    db_path: DbPath,
    canonical_key: str,
) -> dict[str, Any] | None:
    """Return one canonical banking deal by canonical key, or None."""

    with _connect(db_path) as connection:
        row = connection.execute(
            "SELECT id FROM banking_deals WHERE canonical_key = ?",
            (canonical_key,),
        ).fetchone()
    if row is None:
        return None
    return get_banking_deal(db_path, int(row["id"]))


def list_banking_deal_candidates(
    db_path: DbPath,
    *,
    raw_snapshot_id: int | None = None,
    rejected: bool | None = None,
    subcategory: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List extracted pre-dedupe candidates with optional filters."""

    clauses: list[str] = []
    values: list[Any] = []
    if raw_snapshot_id is not None:
        clauses.append("raw_snapshot_id = ?")
        values.append(raw_snapshot_id)
    if rejected is not None:
        clauses.append("rejected = ?")
        values.append(_bool_to_int(rejected))
    if subcategory is not None:
        clauses.append("subcategory = ?")
        values.append(subcategory)

    query = "SELECT * FROM banking_deal_candidates"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at DESC, id DESC"
    if limit is not None:
        query += " LIMIT ?"
        values.append(limit)

    with _connect(db_path) as connection:
        return [
            _row_to_dict(row)
            for row in connection.execute(query, tuple(values)).fetchall()
        ]


def list_pending_banking_deal_candidates(
    db_path: DbPath,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List non-rejected candidates that have not been canonicalized."""

    query = """
        SELECT *
        FROM banking_deal_candidates
        WHERE rejected = 0
          AND canonicalization_status IS NULL
        ORDER BY created_at ASC, id ASC
    """
    values: list[Any] = []
    if limit is not None:
        query += " LIMIT ?"
        values.append(limit)

    with _connect(db_path) as connection:
        return [
            _row_to_dict(row)
            for row in connection.execute(query, tuple(values)).fetchall()
        ]


def list_banking_deals(
    db_path: DbPath,
    *,
    status: str | None = None,
    subcategory: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """List canonical banking deals with optional simple filters."""

    clauses: list[str] = []
    values: list[Any] = []
    if status is not None:
        clauses.append("status = ?")
        values.append(status)
    if subcategory is not None:
        clauses.append("subcategory = ?")
        values.append(subcategory)

    query = "SELECT * FROM banking_deals"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY discovered_at DESC, id DESC"
    if limit is not None:
        query += " LIMIT ?"
        values.append(limit)

    with _connect(db_path) as connection:
        return [
            _row_to_dict(row)
            for row in connection.execute(query, tuple(values)).fetchall()
        ]


def list_banking_deal_source_links(
    db_path: DbPath,
    *,
    deal_id: int | None = None,
) -> list[dict[str, Any]]:
    """List source evidence links for canonical banking deals."""

    clauses: list[str] = []
    values: list[Any] = []
    if deal_id is not None:
        clauses.append("deal_id = ?")
        values.append(deal_id)

    query = "SELECT * FROM banking_deal_source_links"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at ASC, id ASC"

    with _connect(db_path) as connection:
        return [
            _row_to_dict(row)
            for row in connection.execute(query, tuple(values)).fetchall()
        ]


def list_deal_change_events(
    db_path: DbPath,
    *,
    deal_id: int | None = None,
) -> list[dict[str, Any]]:
    """List material change events for canonical banking deals."""

    clauses: list[str] = []
    values: list[Any] = []
    if deal_id is not None:
        clauses.append("deal_id = ?")
        values.append(deal_id)

    query = "SELECT * FROM deal_change_events"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at ASC, id ASC"

    with _connect(db_path) as connection:
        return [
            _row_to_dict(row)
            for row in connection.execute(query, tuple(values)).fetchall()
        ]


def list_deal_status_events(
    db_path: DbPath,
    *,
    deal_id: int | None = None,
) -> list[dict[str, Any]]:
    """List status transitions for canonical banking deals."""

    clauses: list[str] = []
    values: list[Any] = []
    if deal_id is not None:
        clauses.append("deal_id = ?")
        values.append(deal_id)

    query = "SELECT * FROM deal_status_events"
    if clauses:
        query += " WHERE " + " AND ".join(clauses)
    query += " ORDER BY created_at ASC, id ASC"

    with _connect(db_path) as connection:
        return [
            _row_to_dict(row)
            for row in connection.execute(query, tuple(values)).fetchall()
        ]


def load_seed_fixture(db_path: DbPath, fixture_path: DbPath) -> int:
    """Load fictional banking deal examples from a JSON fixture."""

    fixture = json.loads(Path(fixture_path).read_text(encoding="utf-8"))
    loaded_count = 0
    for item in fixture["deals"]:
        source_id = insert_source_record(db_path, item["source_record"])

        snapshot = dict(item["raw_snapshot"])
        snapshot["source_record_id"] = source_id
        snapshot_id = insert_raw_snapshot(db_path, snapshot)

        deal = dict(item["banking_deal"])
        deal["raw_snapshot_id"] = snapshot_id
        insert_banking_deal(db_path, deal)
        loaded_count += 1
    return loaded_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m pdi.storage")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Initialize a local database.")
    init_parser.add_argument("--db", required=True, help="SQLite database path.")
    init_parser.add_argument(
        "--seed-fixture",
        help="Optional JSON fixture file containing mock banking deals.",
    )

    args = parser.parse_args(argv)
    if args.command == "init":
        initialize_database(args.db)
        message = f"Initialized database at {args.db}"
        if args.seed_fixture:
            loaded_count = load_seed_fixture(args.db, args.seed_fixture)
            message += f"; seeded {loaded_count} mock deals"
        print(message)
        return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


def _connect(db_path: DbPath) -> sqlite3.Connection:
    connection = sqlite3.connect(Path(db_path))
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def _migration_scripts() -> list[tuple[str, str]]:
    migration_root = resources.files("pdi.storage.migrations")
    scripts = []
    for migration in sorted(migration_root.iterdir(), key=lambda item: item.name):
        if migration.name.endswith(".sql"):
            scripts.append((migration.name, migration.read_text(encoding="utf-8")))
    return scripts


def _merge_record(
    record: Mapping[str, Any] | None,
    fields: Mapping[str, Any],
) -> dict[str, Any]:
    data = dict(record or {})
    data.update(fields)
    return data


def _insert_terms(
    connection: sqlite3.Connection,
    deal_id: int,
    terms: Mapping[str, Any],
) -> None:
    connection.execute(
        """
        INSERT INTO banking_deal_terms (
          deal_id,
          minimum_deposit_amount_cents,
          direct_deposit_required,
          direct_deposit_minimum_cents,
          minimum_balance_required_cents,
          balance_hold_days,
          monthly_fee_cents,
          monthly_fee_waiver_terms,
          early_closure_fee_cents,
          hard_pull_risk,
          soft_pull_only,
          state_restrictions,
          new_customer_only,
          household_limit,
          terms_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            deal_id,
            terms.get("minimum_deposit_amount_cents"),
            _bool_to_int(terms.get("direct_deposit_required")),
            terms.get("direct_deposit_minimum_cents"),
            terms.get("minimum_balance_required_cents"),
            terms.get("balance_hold_days"),
            terms.get("monthly_fee_cents"),
            terms.get("monthly_fee_waiver_terms"),
            terms.get("early_closure_fee_cents"),
            _bool_to_int(terms.get("hard_pull_risk")),
            _bool_to_int(terms.get("soft_pull_only")),
            _json_text(terms.get("state_restrictions")),
            _bool_to_int(terms.get("new_customer_only")),
            terms.get("household_limit"),
            _json_text(terms.get("terms_json")),
        ),
    )


def _update_terms(
    connection: sqlite3.Connection,
    deal_id: int,
    terms: Mapping[str, Any],
) -> None:
    allowed_columns = {
        "minimum_deposit_amount_cents",
        "direct_deposit_required",
        "direct_deposit_minimum_cents",
        "minimum_balance_required_cents",
        "balance_hold_days",
        "monthly_fee_cents",
        "monthly_fee_waiver_terms",
        "early_closure_fee_cents",
        "hard_pull_risk",
        "soft_pull_only",
        "state_restrictions",
        "new_customer_only",
        "household_limit",
        "terms_json",
    }
    columns = [column for column in terms if column in allowed_columns]
    if not columns:
        return

    assignments = ", ".join(f"{column} = ?" for column in columns)
    values = [
        _bool_to_int(terms[column])
        if column
        in {
            "direct_deposit_required",
            "hard_pull_risk",
            "soft_pull_only",
            "new_customer_only",
        }
        else _json_text(terms[column])
        if column in {"state_restrictions", "terms_json"}
        else terms[column]
        for column in columns
    ]
    values.append(deal_id)

    connection.execute(
        f"""
        UPDATE banking_deal_terms
        SET {assignments}, updated_at = CURRENT_TIMESTAMP
        WHERE deal_id = ?
        """,
        tuple(values),
    )


def _bool_to_int(value: Any) -> int | None:
    if value is None:
        return None
    return 1 if bool(value) else 0


def _json_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), row, strict=True))


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
