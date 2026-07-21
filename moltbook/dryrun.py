"""
moltbook/dryrun.py — the reserved dry-run identifier namespace (transport spec §11).

Single source of truth for the prefix so every store that ingests by ID can reject
dry-run identifiers structurally, rather than relying on callers remembering not to
pass them through. Deliberately dependency-free (no imports of other moltbook modules)
so cadence.py, citation.py, and transport.py can all import this without any risk of a
circular import.
"""

from __future__ import annotations

DRY_RUN_ID_PREFIX = "dryrun-"


def is_dry_run_id(identifier: str) -> bool:
    """True if `identifier` belongs to the reserved dry-run namespace."""
    return identifier.startswith(DRY_RUN_ID_PREFIX)
