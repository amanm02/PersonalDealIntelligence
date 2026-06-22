"""Reusable offline demo corpus loading for Banking MVP fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import yaml

from pdi.collectors import (
    CollectedSnapshot,
    ManualTextCollector,
    NewsletterEmailCollector,
    RssCollector,
    persist_collected_snapshot,
)
from pdi.sources import SourcePolicy, load_source_policies
from pdi.storage import insert_source_record


DbPath = str | Path
DEFAULT_DEMO_DIR = Path("examples/demo_banking")
DEFAULT_DEMO_SOURCE_CONFIG = Path("config/banking_sources.demo.yaml")
DEMO_RETRIEVED_AT = "2026-06-18T12:00:00+00:00"


@dataclass(frozen=True)
class DemoFixture:
    """One manifest record in the reusable Banking MVP demo corpus."""

    fixture_id: str
    policy_name: str
    collector: str
    fixture_path: Path | None
    source_shape: str
    expected_subcategory: str | None = None
    expected_subcategories: tuple[str, ...] = ()
    deal_type: str | None = None
    deal_types: tuple[str, ...] = ()
    edge_cases: tuple[str, ...] = ()
    scenario_ids: tuple[str, ...] = ()
    collect: bool = True
    expected_snapshot_count: int = 1
    raw_metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectedDemoSnapshot:
    """A collected local snapshot plus the fixture metadata that produced it."""

    fixture: DemoFixture
    policy: SourcePolicy
    snapshot: CollectedSnapshot


class DemoCorpusError(ValueError):
    """Raised when the demo corpus manifest or source policies are invalid."""


def load_demo_fixtures(demo_dir: str | Path = DEFAULT_DEMO_DIR) -> list[DemoFixture]:
    """Load and validate the demo corpus manifest."""

    root = Path(demo_dir)
    manifest_path = root / "manifest.yaml"
    raw_manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(raw_manifest, Mapping):
        raise DemoCorpusError("demo corpus manifest must be a mapping")

    raw_fixtures = raw_manifest.get("fixtures")
    if not isinstance(raw_fixtures, list) or not raw_fixtures:
        raise DemoCorpusError("demo corpus manifest requires a non-empty fixtures list")

    fixtures: list[DemoFixture] = []
    for index, raw_fixture in enumerate(raw_fixtures):
        if not isinstance(raw_fixture, Mapping):
            raise DemoCorpusError(f"fixture {index} must be a mapping")
        fixtures.append(_fixture_from_mapping(root, index, raw_fixture))
    return fixtures


def collect_demo_snapshots(
    *,
    demo_dir: str | Path = DEFAULT_DEMO_DIR,
    source_config: str | Path = DEFAULT_DEMO_SOURCE_CONFIG,
    retrieved_at: str = DEMO_RETRIEVED_AT,
) -> list[CollectedDemoSnapshot]:
    """Collect every enabled demo fixture through existing offline collectors."""

    fixtures = load_demo_fixtures(demo_dir)
    policies = {policy.name: policy for policy in load_source_policies(source_config)}
    collected: list[CollectedDemoSnapshot] = []

    for fixture in fixtures:
        policy = policies.get(fixture.policy_name)
        if policy is None:
            raise DemoCorpusError(
                f"{fixture.fixture_id}: unknown source policy {fixture.policy_name}"
            )
        if not fixture.collect:
            continue
        if fixture.fixture_path is None:
            raise DemoCorpusError(f"{fixture.fixture_id}: collectable fixture has no path")
        collected.extend(
            _collect_fixture(
                fixture,
                policy,
                retrieved_at=retrieved_at,
            )
        )
    return collected


def persist_demo_snapshots(
    db_path: DbPath,
    *,
    demo_dir: str | Path = DEFAULT_DEMO_DIR,
    source_config: str | Path = DEFAULT_DEMO_SOURCE_CONFIG,
    retrieved_at: str = DEMO_RETRIEVED_AT,
) -> list[int]:
    """Persist collected demo snapshots and return raw snapshot ids."""

    snapshot_ids: list[int] = []
    for item in collect_demo_snapshots(
        demo_dir=demo_dir,
        source_config=source_config,
        retrieved_at=retrieved_at,
    ):
        source_record_id = insert_source_record(
            db_path,
            {
                "source_name": item.policy.name,
                "source_url": item.policy.url,
                "source_type": item.policy.source_type,
                "collection_method": item.policy.collection_method,
                "enabled": item.policy.enabled,
                "max_frequency": f"{item.policy.max_frequency_hours}h",
                "compliance_notes": (
                    "Offline demo fixture; no network access, credentials, or "
                    "browser automation."
                ),
            },
        )
        snapshot_ids.append(
            persist_collected_snapshot(
                db_path,
                item.snapshot,
                source_record_id=source_record_id,
            )
        )
    return snapshot_ids


def _fixture_from_mapping(
    root: Path,
    index: int,
    raw_fixture: Mapping[str, Any],
) -> DemoFixture:
    required = {"id", "policy_name", "collector", "source_shape", "edge_cases"}
    missing = required - set(raw_fixture)
    if missing:
        raise DemoCorpusError(
            f"fixture {index} missing required fields: {', '.join(sorted(missing))}"
        )

    fixture_path = raw_fixture.get("fixture_path")
    collect = bool(raw_fixture.get("collect", True))
    resolved_path = None if fixture_path is None else root / str(fixture_path)
    if collect and resolved_path is None:
        raise DemoCorpusError(f"fixture {index} requires fixture_path when collect=true")
    if resolved_path is not None and not resolved_path.exists():
        raise DemoCorpusError(f"fixture file does not exist: {resolved_path}")

    expected_snapshot_count = int(raw_fixture.get("expected_snapshot_count", 1))
    if expected_snapshot_count < 0:
        raise DemoCorpusError(f"fixture {index} expected_snapshot_count cannot be negative")

    return DemoFixture(
        fixture_id=str(raw_fixture["id"]),
        policy_name=str(raw_fixture["policy_name"]),
        collector=str(raw_fixture["collector"]),
        fixture_path=resolved_path,
        source_shape=str(raw_fixture["source_shape"]),
        expected_subcategory=_optional_str(raw_fixture.get("expected_subcategory")),
        expected_subcategories=tuple(raw_fixture.get("expected_subcategories") or ()),
        deal_type=_optional_str(raw_fixture.get("deal_type")),
        deal_types=tuple(raw_fixture.get("deal_types") or ()),
        edge_cases=tuple(str(item) for item in raw_fixture["edge_cases"]),
        scenario_ids=tuple(str(item) for item in raw_fixture.get("scenario_ids") or ()),
        collect=collect,
        expected_snapshot_count=expected_snapshot_count,
        raw_metadata=dict(raw_fixture),
    )


def _collect_fixture(
    fixture: DemoFixture,
    policy: SourcePolicy,
    *,
    retrieved_at: str,
) -> list[CollectedDemoSnapshot]:
    if fixture.collector == "manual_text":
        snapshot = ManualTextCollector().collect(
            policy,
            fixture_path=fixture.fixture_path,
            retrieved_at=retrieved_at,
            raw_payload=_raw_payload(fixture),
        )
        return [CollectedDemoSnapshot(fixture, policy, snapshot)]

    if fixture.collector == "newsletter_email":
        snapshot = NewsletterEmailCollector().collect(
            policy,
            fixture_path=fixture.fixture_path,
            retrieved_at=retrieved_at,
        )
        return [CollectedDemoSnapshot(fixture, policy, snapshot)]

    if fixture.collector == "rss":
        snapshots = RssCollector().collect(
            policy,
            fixture_path=fixture.fixture_path,
            retrieved_at=retrieved_at,
        )
        return [
            CollectedDemoSnapshot(fixture, policy, snapshot)
            for snapshot in snapshots
        ]

    raise DemoCorpusError(f"{fixture.fixture_id}: unsupported collector {fixture.collector}")


def _raw_payload(fixture: DemoFixture) -> dict[str, Any]:
    return {
        "fixture_id": fixture.fixture_id,
        "source_shape": fixture.source_shape,
        "edge_cases": list(fixture.edge_cases),
        "scenario_ids": list(fixture.scenario_ids),
        "deal_type": fixture.deal_type,
    }


def _optional_str(value: Any) -> str | None:
    return None if value is None else str(value)
