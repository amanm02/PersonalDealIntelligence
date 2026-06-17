"""Policy-enforced collectors for raw Banking MVP snapshots."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pdi.sources import SourcePolicy
from pdi.storage import insert_raw_snapshot


DbPath = str | Path
FetchResult = str | tuple[str, int | None] | tuple[str, int | None, Mapping[str, Any]]
HtmlFetcher = Callable[[str], FetchResult]


class CollectionBlockedError(ValueError):
    """Raised when source policy blocks a collection attempt."""


@dataclass(frozen=True)
class CollectedSnapshot:
    """Normalized raw content collected from an approved Banking MVP source."""

    source_name: str
    source_url: str | None
    retrieved_at: str
    content_hash: str
    raw_text: str
    raw_payload: Mapping[str, Any] = field(default_factory=dict)
    http_status: int | None = None
    collector_name: str = "unknown"

    @classmethod
    def from_text(
        cls,
        *,
        source_name: str,
        source_url: str | None,
        raw_text: str,
        collector_name: str,
        retrieved_at: str | None = None,
        raw_payload: Mapping[str, Any] | None = None,
        http_status: int | None = None,
    ) -> "CollectedSnapshot":
        """Build a snapshot and compute a stable content hash."""

        return cls(
            source_name=source_name,
            source_url=source_url,
            retrieved_at=retrieved_at or _utc_now(),
            content_hash=hash_content(raw_text),
            raw_text=raw_text,
            raw_payload=dict(raw_payload or {}),
            http_status=http_status,
            collector_name=collector_name,
        )

    def to_storage_record(self, source_record_id: int | None = None) -> dict[str, Any]:
        """Return fields accepted by pdi.storage.insert_raw_snapshot."""

        return {
            "source_record_id": source_record_id,
            "source_url": self.source_url,
            "source_name": self.source_name,
            "retrieved_at": self.retrieved_at,
            "content_hash": self.content_hash,
            "raw_text": self.raw_text,
            "raw_payload_json": dict(self.raw_payload),
            "http_status": self.http_status,
            "collector_name": self.collector_name,
        }


def hash_content(raw_text: str) -> str:
    """Return the SHA-256 hash used for snapshot dedupe/change detection."""

    return hashlib.sha256(raw_text.encode("utf-8")).hexdigest()


def persist_collected_snapshot(
    db_path: DbPath,
    snapshot: CollectedSnapshot,
    *,
    source_record_id: int | None = None,
) -> int:
    """Persist a collected snapshot with the existing storage schema."""

    return insert_raw_snapshot(
        db_path,
        snapshot.to_storage_record(source_record_id=source_record_id),
    )


class ManualTextCollector:
    """Collect pasted text or local fixture content without external requests."""

    collector_name = "manual_text"

    def collect(
        self,
        policy: SourcePolicy,
        *,
        raw_text: str | None = None,
        fixture_path: str | Path | None = None,
        retrieved_at: str | None = None,
        raw_payload: Mapping[str, Any] | None = None,
    ) -> CollectedSnapshot:
        _ensure_enabled_and_approved(policy, self.collector_name)
        _ensure_method(policy, "manual_only")
        _ensure_not_login_required(policy, self.collector_name)
        text = _load_text(raw_text=raw_text, fixture_path=fixture_path)
        return CollectedSnapshot.from_text(
            source_name=policy.name,
            source_url=policy.url,
            raw_text=text,
            retrieved_at=retrieved_at,
            raw_payload={
                "source_type": policy.source_type,
                "input_method": "fixture" if fixture_path else "manual_text",
                **dict(raw_payload or {}),
            },
            collector_name=self.collector_name,
        )


class ManualUrlCollector:
    """Record manual URLs and gate any future HTML fetching behind policy."""

    record_collector_name = "manual_url"
    fetch_collector_name = "manual_url_html"

    def record_url(
        self,
        policy: SourcePolicy,
        *,
        url: str | None = None,
        retrieved_at: str | None = None,
    ) -> CollectedSnapshot:
        _ensure_method(policy, "manual_only")
        target_url = url or policy.url
        raw_text = f"User-provided banking promotion URL: {target_url}"
        return CollectedSnapshot.from_text(
            source_name=policy.name,
            source_url=target_url,
            raw_text=raw_text,
            retrieved_at=retrieved_at,
            raw_payload={
                "source_type": policy.source_type,
                "input_method": "manual_url_record",
            },
            collector_name=self.record_collector_name,
        )

    def fetch_html(
        self,
        policy: SourcePolicy,
        *,
        fetcher: HtmlFetcher | None = None,
        last_collected_at: str | datetime | None = None,
        now: datetime | None = None,
    ) -> CollectedSnapshot:
        _ensure_scrape_allowed(policy, collector_name=self.fetch_collector_name)
        _ensure_frequency_allowed(policy, last_collected_at=last_collected_at, now=now)
        if fetcher is None:
            raise CollectionBlockedError(
                f"{policy.name}: HTML fetching requires an explicit fetcher; "
                "no live network client is provided by the collector framework."
            )

        raw_text, http_status, raw_payload = _normalize_fetch_result(fetcher(policy.url))
        return CollectedSnapshot.from_text(
            source_name=policy.name,
            source_url=policy.url,
            raw_text=raw_text,
            raw_payload={
                "source_type": policy.source_type,
                "input_method": "policy_approved_html_fetch",
                **dict(raw_payload),
            },
            http_status=http_status,
            collector_name=self.fetch_collector_name,
        )


class RssCollector:
    """Parse RSS or Atom content from local fixture text."""

    collector_name = "rss"

    def collect(
        self,
        policy: SourcePolicy,
        *,
        raw_text: str | None = None,
        fixture_path: str | Path | None = None,
        retrieved_at: str | None = None,
        last_collected_at: str | datetime | None = None,
        now: datetime | None = None,
    ) -> list[CollectedSnapshot]:
        _ensure_feed_allowed(policy)
        _ensure_frequency_allowed(policy, last_collected_at=last_collected_at, now=now)
        feed_text = _load_text(raw_text=raw_text, fixture_path=fixture_path)
        return [
            CollectedSnapshot.from_text(
                source_name=policy.name,
                source_url=item["source_url"],
                raw_text=item["raw_text"],
                retrieved_at=retrieved_at,
                raw_payload=item["raw_payload"],
                collector_name=self.collector_name,
            )
            for item in _parse_feed_items(feed_text, policy)
        ]


class NewsletterEmailCollector:
    """Collect user-authorized exported newsletter content only."""

    collector_name = "newsletter_email"

    def collect(
        self,
        policy: SourcePolicy,
        *,
        raw_text: str | None = None,
        fixture_path: str | Path | None = None,
        retrieved_at: str | None = None,
    ) -> CollectedSnapshot:
        _ensure_email_export_allowed(policy)
        text = _load_text(raw_text=raw_text, fixture_path=fixture_path)
        return CollectedSnapshot.from_text(
            source_name=policy.name,
            source_url=policy.url,
            raw_text=text,
            retrieved_at=retrieved_at,
            raw_payload={
                "source_type": policy.source_type,
                "input_method": (
                    "email_export_fixture" if fixture_path else "email_export_text"
                ),
            },
            collector_name=self.collector_name,
        )


class ApiCollector:
    """Fixture-backed API collector placeholder with no credential handling."""

    collector_name = "api_fixture"

    def collect_fixture(
        self,
        policy: SourcePolicy,
        *,
        payload: str | Mapping[str, Any],
        retrieved_at: str | None = None,
    ) -> CollectedSnapshot:
        _ensure_api_allowed(policy)
        raw_text = (
            json.dumps(payload, sort_keys=True)
            if isinstance(payload, Mapping)
            else payload
        )
        return CollectedSnapshot.from_text(
            source_name=policy.name,
            source_url=policy.url,
            raw_text=raw_text,
            retrieved_at=retrieved_at,
            raw_payload={
                "source_type": policy.source_type,
                "input_method": "api_fixture",
            },
            collector_name=self.collector_name,
        )


def _ensure_enabled_and_approved(policy: SourcePolicy, collector_name: str) -> None:
    if not policy.enabled:
        raise CollectionBlockedError(
            f"{policy.name}: {collector_name} requires an enabled source policy."
        )
    if policy.compliance_status != "approved":
        raise CollectionBlockedError(
            f"{policy.name}: {collector_name} requires compliance_status approved."
        )


def _ensure_method(policy: SourcePolicy, expected_method: str) -> None:
    if policy.collection_method != expected_method:
        raise CollectionBlockedError(
            f"{policy.name}: expected collection_method {expected_method}, "
            f"got {policy.collection_method}."
        )


def _ensure_not_login_required(policy: SourcePolicy, collector_name: str) -> None:
    if policy.requires_login:
        raise CollectionBlockedError(
            f"{policy.name}: {collector_name} cannot collect login-required sources."
        )


def _ensure_scrape_allowed(policy: SourcePolicy, *, collector_name: str) -> None:
    _ensure_enabled_and_approved(policy, collector_name)
    _ensure_method(policy, "scrape")
    if policy.requires_login:
        raise CollectionBlockedError(
            f"{policy.name}: logged-in HTML collection is not allowed."
        )
    if not policy.allow_scrape:
        raise CollectionBlockedError(
            f"{policy.name}: HTML collection requires allow_scrape true."
        )


def _ensure_feed_allowed(policy: SourcePolicy) -> None:
    _ensure_enabled_and_approved(policy, "rss")
    _ensure_method(policy, "rss_feed")
    _ensure_not_login_required(policy, "rss")
    if not policy.allow_rss:
        raise CollectionBlockedError(
            f"{policy.name}: RSS collection requires allow_rss true."
        )


def _ensure_email_export_allowed(policy: SourcePolicy) -> None:
    _ensure_enabled_and_approved(policy, "newsletter_email")
    _ensure_method(policy, "email_export")
    if not policy.allow_email_parse:
        raise CollectionBlockedError(
            f"{policy.name}: newsletter export collection requires "
            "allow_email_parse true."
        )


def _ensure_api_allowed(policy: SourcePolicy) -> None:
    _ensure_enabled_and_approved(policy, "api_fixture")
    _ensure_method(policy, "api")
    _ensure_not_login_required(policy, "api_fixture")
    if not policy.allow_api:
        raise CollectionBlockedError(
            f"{policy.name}: API fixture collection requires allow_api true."
        )


def _ensure_frequency_allowed(
    policy: SourcePolicy,
    *,
    last_collected_at: str | datetime | None,
    now: datetime | None,
) -> None:
    if last_collected_at is None or policy.max_frequency_hours <= 0:
        return

    last_collected = _parse_datetime(last_collected_at)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    elapsed_hours = (current_time - last_collected).total_seconds() / 3600
    if elapsed_hours < policy.max_frequency_hours:
        raise CollectionBlockedError(
            f"{policy.name}: collection blocked by max_frequency_hours "
            f"{policy.max_frequency_hours}; last collected {elapsed_hours:.2f} "
            "hours ago."
        )


def _load_text(
    *,
    raw_text: str | None,
    fixture_path: str | Path | None,
) -> str:
    if raw_text is not None and fixture_path is not None:
        raise ValueError("Provide raw_text or fixture_path, not both.")
    if fixture_path is not None:
        return Path(fixture_path).read_text(encoding="utf-8")
    if raw_text is None:
        raise ValueError("Provide raw_text or fixture_path.")
    return raw_text


def _normalize_fetch_result(
    result: FetchResult,
) -> tuple[str, int | None, Mapping[str, Any]]:
    if isinstance(result, str):
        return result, None, {}
    if len(result) == 2:
        raw_text, http_status = result
        return raw_text, http_status, {}
    raw_text, http_status, raw_payload = result
    return raw_text, http_status, raw_payload


def _parse_feed_items(feed_text: str, policy: SourcePolicy) -> list[dict[str, Any]]:
    root = ET.fromstring(feed_text)
    if _strip_namespace(root.tag) == "rss":
        return _parse_rss_items(root, policy)
    if _strip_namespace(root.tag) == "feed":
        return _parse_atom_entries(root, policy)
    raise ValueError("Unsupported feed fixture: expected RSS or Atom XML.")


def _parse_rss_items(root: ET.Element, policy: SourcePolicy) -> list[dict[str, Any]]:
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall("item")
    parsed_items = []
    for index, item in enumerate(items):
        title = _child_text(item, "title")
        link = _child_text(item, "link")
        description = _child_text(item, "description")
        published = _child_text(item, "pubDate")
        raw_text = _join_nonempty([title, link, description])
        parsed_items.append(
            {
                "source_url": link or policy.url,
                "raw_text": raw_text,
                "raw_payload": {
                    "source_type": policy.source_type,
                    "feed_format": "rss",
                    "feed_url": policy.url,
                    "item_index": index,
                    "title": title,
                    "link": link,
                    "published": published,
                },
            }
        )
    return parsed_items


def _parse_atom_entries(root: ET.Element, policy: SourcePolicy) -> list[dict[str, Any]]:
    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", namespace)
    if not entries:
        entries = [child for child in root if _strip_namespace(child.tag) == "entry"]

    parsed_items = []
    for index, entry in enumerate(entries):
        title = _child_text(entry, "title")
        link = _atom_link(entry)
        summary = _child_text(entry, "summary") or _child_text(entry, "content")
        updated = _child_text(entry, "updated") or _child_text(entry, "published")
        raw_text = _join_nonempty([title, link, summary])
        parsed_items.append(
            {
                "source_url": link or policy.url,
                "raw_text": raw_text,
                "raw_payload": {
                    "source_type": policy.source_type,
                    "feed_format": "atom",
                    "feed_url": policy.url,
                    "item_index": index,
                    "title": title,
                    "link": link,
                    "published": updated,
                },
            }
        )
    return parsed_items


def _child_text(element: ET.Element, child_name: str) -> str | None:
    for child in element:
        if _strip_namespace(child.tag) == child_name and child.text is not None:
            return child.text.strip()
    return None


def _atom_link(entry: ET.Element) -> str | None:
    for child in entry:
        if _strip_namespace(child.tag) == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text:
                return child.text.strip()
    return None


def _strip_namespace(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _join_nonempty(values: list[str | None]) -> str:
    return "\n".join(value for value in values if value)


def _parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
