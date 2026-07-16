"""
moltbook/detector.py — credential-leak detector for the M7 pre-send gate.

Implements §4 of docs/m7_credential_integrity_ruling.md. Scans outbound content for
secrets in priority order:

    1. exact own-key match  (primary — zero false positives; the client knows its key)
    2. key-prefix pattern   (secondary — moltbook_sk_ / moltdev_; catches relayed keys)

Generic high-entropy secret regexes (step 3 in the ruling) are deliberately NOT
implemented in this first pass: false-positive minefield (ruling §4, decision #2).

Redaction (ruling §6): a scan result NEVER contains the secret itself, only which
rule fired and a redacted marker — otherwise the audit trail becomes a second copy
of the leak. Do not add the matched string to CredentialScan.

Known limitation (ruling §4, pinned by xfail tests in the suite): exact-match +
prefix is defeated by any content transformation (base64, reversal, splitting a key
across two actions). Tolerable for the OWN key because it never enters model context
(ruling §5.1); a real, documented gap for relayed foreign keys.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# moltbook_sk_<key> (agent keys) and moltdev_<key> (app-verification keys).
_KEY_PREFIX_RE = re.compile(r"molt(?:book_sk|dev)_[A-Za-z0-9]+")

# An own-key shorter than this is treated as unset/degenerate and skipped for the
# exact-match tier — guards against an empty or truncated key matching everything.
_MIN_OWN_KEY_LEN = 8


@dataclass(frozen=True)
class CredentialScan:
    """Result of scanning one piece of outbound content. Carries no secret material."""

    is_leak: bool
    rule: str          # "own_key" | "key_prefix" | "none"
    detail: str        # redacted, human-readable — never the secret itself


def scan_content(content: str, own_key: str | None = None) -> CredentialScan:
    """
    Scan outbound content for a credential leak.

    Args:
        content:  the exact post/comment/DM/profile text about to be sent.
        own_key:  the agent's own API key, supplied from the same runtime secret
                  source as the client's auth (ruling §6). Used only for the
                  exact-match tier; never logged, never returned.

    Returns a CredentialScan. On a leak, `detail` is redacted.
    """
    text = content or ""

    # Tier 1 — exact own-key match (primary).
    if own_key and len(own_key) >= _MIN_OWN_KEY_LEN and own_key in text:
        return CredentialScan(
            is_leak=True,
            rule="own_key",
            detail="own API key present in outbound content",
        )

    # Tier 2 — key-prefix pattern (secondary; catches any agent's key, incl. relayed).
    if _KEY_PREFIX_RE.search(text):
        return CredentialScan(
            is_leak=True,
            rule="key_prefix",
            detail="key-prefixed secret (molt…_…) present in outbound content",
        )

    return CredentialScan(is_leak=False, rule="none", detail="no credential detected")
