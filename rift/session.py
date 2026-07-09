"""Rift v0.2 — Declaration-Resolution Session (Rift Ruling 3.2).

The Intent Layer's runtime entry point: a user declares something in natural
language and Rift decides which map it corresponds to, via the two-tier
matcher shipped by Ruling 3.1. The session's job beyond delegation is
known-values accumulation: every confirmed Tier 1 (exact) match yields real
capture values, which are remembered (in-memory, per-instance) and used to
mask later declarations before Tier 2 semantic comparison — the single
highest-leverage normalization found during Ruling 3.1 calibration.

The accumulated set is a match-quality cache, not authoritative intent state:
losing it degrades Tier 2 scores to the documented unmasked baseline, never
produces incorrect behavior. Persistence across processes is explicitly
deferred (Ruling 3.2 §3.2.3).

Layer boundary (continuum_layer_boundaries.md): this module is Layer 3.
Known values are sourced ONLY from declarations this session itself resolved
(plus explicit caller-supplied per-call overrides) — never from any other
layer's runtime state. Cross-layer integration is v0.4+.

Spec: docs/rift_v02_ruling_3_2_known_values_accumulation.md
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from rift.matcher import (
    DEFAULT_AMBIGUITY_MARGIN,
    DEFAULT_SIMILARITY_THRESHOLD,
    MatchResult,
    match_declaration,
    render_match,
)


# ── Result contract (Ruling 3.2 §3.2.5) ──────────────────────────────────────

@dataclass(frozen=True)
class Resolution:
    result: MatchResult
    trace: str
    known_values_used: tuple[str, ...]      # what the matcher received, in masking order
    newly_accumulated: tuple[str, ...]      # capture values this call added to the session


# ── Session ───────────────────────────────────────────────────────────────────

class RiftSession:
    """Declaration-resolution entry point with known-values accumulation.

    One session = one in-memory accumulation scope (Ruling 3.2 §3.2.3).
    No module-level state: two sessions never share accumulated values.
    """

    def __init__(
        self,
        maps: list[dict[str, Any]],
        *,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        margin: float = DEFAULT_AMBIGUITY_MARGIN,
    ):
        self._maps = list(maps)
        self._threshold = threshold
        self._margin = margin
        self._known: list[str] = []          # first-seen forms, insertion order
        self._known_lower: set[str] = set()  # case-insensitive dedup index

    @classmethod
    def from_rift_file(
        cls,
        path: str,
        *,
        threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
        margin: float = DEFAULT_AMBIGUITY_MARGIN,
    ) -> "RiftSession":
        """Build a session from a .rift source file.

        Raises ValueError listing the validator's errors if the source does
        not validate — never returns a session over an invalid IR (§3.2.5).
        """
        from rift.validator import validate_file  # noqa: PLC0415

        ok, errors, ir = validate_file(str(path))
        if not ok:
            raise ValueError(
                f"cannot build RiftSession: {path} failed validation:\n"
                + "\n".join(errors)
            )
        return cls(ir["maps"], threshold=threshold, margin=margin)

    @property
    def known_values(self) -> tuple[str, ...]:
        """Accumulated capture values (inspectable state — §3.2.5)."""
        return tuple(self._known)

    def resolve(
        self,
        declaration: str,
        *,
        known_values: Iterable[str] = (),
    ) -> Resolution:
        """Resolve a natural-language declaration against this session's maps.

        `known_values` is the per-call caller-supplied override (Ruling 3.2
        option 1): used for this call only, never persisted (§3.2.6 rule 5).
        """
        merged = self._merge(known_values)
        result = match_declaration(
            declaration,
            self._maps,
            threshold=self._threshold,
            margin=self._margin,
            known_values=merged,
        )
        newly = self._accumulate(result)
        trace = (
            render_match(
                result, declaration,
                threshold=self._threshold, margin=self._margin,
            )
            + "\n"
            + self._render_session(merged, newly, result)
        )
        return Resolution(
            result=result,
            trace=trace,
            known_values_used=merged,
            newly_accumulated=newly,
        )

    # ── Known-values plumbing (Ruling 3.2 §3.2.6) ─────────────────────────────

    def _merge(self, caller_values: Iterable[str]) -> tuple[str, ...]:
        """Accumulated ∪ caller-supplied: case-insensitive dedup with the
        accumulated form winning (rule 6), longest-first masking order over
        the merged set (rule 4)."""
        merged = list(self._known)
        seen = set(self._known_lower)
        for value in caller_values:
            if value and value.lower() not in seen:
                merged.append(value)
                seen.add(value.lower())
        # stable sort: equal lengths keep insertion order
        merged.sort(key=len, reverse=True)
        return tuple(merged)

    def _accumulate(self, result: MatchResult) -> tuple[str, ...]:
        """Only Tier 1 exact matches contribute (rule 1); the semantic tier
        never extracts captures (Ruling 3.1 §3.1.8)."""
        if not (result.matched and result.tier == "exact"):
            return ()
        newly = []
        for value in result.captures.values():
            if value and value.lower() not in self._known_lower:
                self._known.append(value)
                self._known_lower.add(value.lower())
                newly.append(value)
        return tuple(newly)

    # ── Trace (Ruling 3.2 §3.2.8) ─────────────────────────────────────────────

    @staticmethod
    def _render_session(
        used: tuple[str, ...],
        newly: tuple[str, ...],
        result: MatchResult,
    ) -> str:
        known_str = ", ".join(f"\"{v}\"" for v in used) if used else "(none)"
        if newly:
            names_by_value = {v: k for k, v in result.captures.items()}
            acc_str = ", ".join(
                f"[{names_by_value[v]}] = \"{v}\"" for v in newly
            )
        elif result.matched and result.tier == "semantic":
            acc_str = "(none — semantic tier extracts no captures)"
        else:
            acc_str = "(none)"
        return (
            "RIFT SESSION\n"
            f"├── Known values : {known_str}\n"
            f"└── Accumulated  : {acc_str}"
        )
