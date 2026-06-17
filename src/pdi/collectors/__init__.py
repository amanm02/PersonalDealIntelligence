"""Compliant collector framework for Banking MVP source content."""

from pdi.collectors.core import (
    ApiCollector,
    CollectedSnapshot,
    CollectionBlockedError,
    ManualTextCollector,
    ManualUrlCollector,
    NewsletterEmailCollector,
    RssCollector,
    persist_collected_snapshot,
)

__all__ = [
    "ApiCollector",
    "CollectedSnapshot",
    "CollectionBlockedError",
    "ManualTextCollector",
    "ManualUrlCollector",
    "NewsletterEmailCollector",
    "RssCollector",
    "persist_collected_snapshot",
]
