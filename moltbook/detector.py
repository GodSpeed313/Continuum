"""
moltbook/detector.py — outbound-content detectors for the M7 pre-send gate.

These detectors share this module because they run on the same candidate content in the
same client gate:
  - scan_content   — credential leak (docs/m7_credential_integrity_ruling.md §4)
  - scan_links     — link provenance (docs/m7_link_restriction_ruling.md §4)
  - scan_identity  — within-session identity contradiction (docs/m7_identity_integrity_ruling.md §6)

────────────────────────────────────────────────────────────────────────────────────
Credential-leak detector (CredentialIntegrity §4). Scans outbound content for secrets
in priority order:

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
from urllib.parse import urlparse

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


# ─────────────────────────────────────────────────────────────────────────────
# Link-provenance detector (LinkRestriction §4).
#
# A PROVENANCE check, not payload inspection: the gate never fetches a link or
# judges whether its destination is malicious — only whether the agent had
# legitimate grounds to surface it:
#   source    — the exact URL appears in the content being responded to/cited (a)
#   allowlist — the URL's host is on the static human-owned allowlist (b)
#   novel     — neither; a URL the agent was not given (constructed, assembled from
#               fragments, shortened/redirect, or suggested by another agent's post/
#               DM without meeting (a)/(b)). A novel link is a violation.
# ─────────────────────────────────────────────────────────────────────────────

_URL_RE = re.compile(r"""https?://[^\s<>"')\]]+""", re.IGNORECASE)


@dataclass(frozen=True)
class LinkFinding:
    """One URL found in outbound content, with its provenance. Logged per ruling §5."""

    url: str
    host: str
    provenance: str    # "source" | "allowlist" | "novel"
    allowed: bool


@dataclass(frozen=True)
class LinkScan:
    is_violation: bool                    # at least one novel link present
    findings: tuple[LinkFinding, ...]

    @property
    def novel(self) -> tuple[LinkFinding, ...]:
        return tuple(f for f in self.findings if f.provenance == "novel")


def _host(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def _host_allowed(host: str, allowed_hosts) -> bool:
    """Exact host or subdomain match against the allowlist."""
    if not host:
        return False
    for h in allowed_hosts:
        h = h.lower()
        if host == h or host.endswith("." + h):
            return True
    return False


def scan_links(content: str, source_content: str = "", allowed_hosts=()) -> LinkScan:
    """
    Classify every URL in outbound `content` by provenance.

    Args:
        content:        the post/comment/DM about to be sent.
        source_content: the content the agent is directly responding to/citing —
                        a URL present here has provenance (a).
        allowed_hosts:  the static, human-owned allowlist (ruling §4, Q1). Passed in
                        by the client as an immutable value; the agent cannot expand it.

    Returns a LinkScan. `is_violation` is True iff any URL is `novel`.
    """
    src = source_content or ""
    findings: list[LinkFinding] = []
    violation = False

    for match in _URL_RE.finditer(content or ""):
        url = match.group().rstrip(".,;")     # drop trailing sentence punctuation
        host = _host(url)
        if url in src:
            prov, allowed = "source", True
        elif _host_allowed(host, allowed_hosts):
            prov, allowed = "allowlist", True
        else:
            prov, allowed = "novel", False
            violation = True
        findings.append(LinkFinding(url=url, host=host, provenance=prov, allowed=allowed))

    return LinkScan(is_violation=violation, findings=tuple(findings))


# ─────────────────────────────────────────────────────────────────────────────
# Within-session identity contradiction detector (IdentityIntegrity §6).
#
# MECHANICAL ONLY, on purpose. The baseline pass found first-person "I am / I do X"
# is the dominant normal register on Moltbook, so this NEVER fires on a bare
# first-person claim. It fires only on:
#   handle_name   — an EXPLICIT self-naming construct ("my name/handle is X",
#                   "call me X", "I go by X", "posting/signing as X", "I am @X",
#                   "this is u/X") naming something other than the declared identity.
#   role_negation — a DIRECT negation of a captured declared role ("I am not <role>").
#
# Semantic persona-drift (a voice/persona shift with no explicit construct) is a
# DEFERRED gap (ruling §6), pinned by an xfail test — not detected here.
# ─────────────────────────────────────────────────────────────────────────────

# Explicit self-naming via a naming verb — a real name/handle follows these.
# Deliberately excludes bare "I am/I'm <phrase>" (the dominant-register guard).
_SELF_NAME_RE = re.compile(
    r"(?:my (?:name|handle|username) is|call me|i go by|posting as|signing as)\s+@?(\w[\w-]{1,})",
    re.IGNORECASE,
)
# Handle-prefixed self-claim: the @/u/ prefix makes "I am @X" unambiguously an
# identity claim (an adjective can't carry an @), so this is safe where bare
# "I am X" is not. Must be a SELF construct, so a reference like "@bytes said" —
# which has no "I am / this is / posting as" lead-in — does not match.
_SELF_HANDLE_RE = re.compile(
    r"(?:i am|i'm|this is|posting as)\s+(?:u/|@)(\w[\w-]{1,})",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IdentityScan:
    is_contradiction: bool
    kind: str          # "handle_name" | "role_negation" | "none"
    detail: str        # human-readable, names claimed vs declared (identity isn't secret)


def _norm(s: str) -> str:
    return (s or "").lstrip("@").strip().lower()


def scan_identity(
    content: str,
    declared_handle: str,
    declared_name: str | None = None,
    declared_roles=(),
) -> IdentityScan:
    """
    Detect a within-session identity contradiction against the session-start declaration.

    Args:
        content:         outbound post/comment/DM text.
        declared_handle: the agent's handle captured at session start (immutable for session).
        declared_name:   optional declared display name.
        declared_roles:  optional captured role strings, for direct-negation checks.

    Returns an IdentityScan. Mechanical only (ruling §6) — never fires on a bare
    first-person claim.
    """
    text = content or ""
    known = {_norm(declared_handle)}
    if declared_name:
        known.add(_norm(declared_name))

    # handle_name: an explicit self-naming construct claiming a DIFFERENT identity.
    for rx in (_SELF_NAME_RE, _SELF_HANDLE_RE):
        for m in rx.finditer(text):
            claimed = _norm(m.group(1))
            if claimed and claimed not in known:
                return IdentityScan(
                    is_contradiction=True,
                    kind="handle_name",
                    detail=f"asserts identity '{m.group(1)}' != declared '{declared_handle}'",
                )

    # role_negation: direct negation of a captured declared role.
    for role in declared_roles:
        role = (role or "").strip()
        if not role:
            continue
        if re.search(r"i(?:'m| am) not (?:a |an |the )?" + re.escape(role), text, re.IGNORECASE):
            return IdentityScan(
                is_contradiction=True,
                kind="role_negation",
                detail=f"directly negates declared role '{role}'",
            )

    return IdentityScan(is_contradiction=False, kind="none", detail="identity consistent")
