"""Banking deal dedupe and canonicalization helpers."""

from pdi.dedupe.core import (
    CanonicalizationResult,
    canonicalize_candidate,
    canonicalize_pending_candidates,
    generate_canonical_key,
)

__all__ = [
    "CanonicalizationResult",
    "canonicalize_candidate",
    "canonicalize_pending_candidates",
    "generate_canonical_key",
]
