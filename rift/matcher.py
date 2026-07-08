"""Rift v0.2 — Declaration Matcher (Rift Ruling 3.1).

Matches a natural-language user declaration against Rift map blocks in two tiers:

    Tier 1 — exact:    map patterns with [captures] compiled to anchored,
                       case-insensitive regexes; captures extracted.
    Tier 2 — semantic: cosine similarity between the (normalized) declaration
                       and each map's comparison text, using an embedding model
                       owned by this module. Runs only when Tier 1 finds nothing.

Layer boundary (continuum_layer_boundaries.md): this module is Layer 3 and is
deliberately independent of the Layer 2 semantic matching shipped by Ruling 9.8.
It owns its own model instance and cache. Cross-layer integration is v0.4+.

Spec: docs/rift_v02_ruling_3_1_semantic_declaration_matching.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable

DEFAULT_SIMILARITY_THRESHOLD = 0.30
DEFAULT_AMBIGUITY_MARGIN = 0.05

_CAPTURE_RE = re.compile(r"\[(\w+)\]")

# ── Embedding model (Rift's own instance — Ruling 3.1 §3.1.3) ────────────────

_MODEL = None
_AVAILABLE: bool | None = None


def _get_model():
    global _MODEL, _AVAILABLE
    if _AVAILABLE is None:
        try:
            from sentence_transformers import SentenceTransformer  # noqa: PLC0415
            _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
            _AVAILABLE = True
        except Exception:  # noqa: BLE001
            _AVAILABLE = False
    return _MODEL if _AVAILABLE else None


def _encode(texts: list[str]):
    """Encode texts as normalized embeddings, or None when the model is
    unavailable (Ruling 3.1 §3.1.9 — degrade, never crash)."""
    model = _get_model()
    if model is None:
        return None
    try:
        return model.encode(texts, normalize_embeddings=True)
    except Exception:  # noqa: BLE001
        return None


# ── Result contract (Ruling 3.1 §3.1.4) ──────────────────────────────────────

@dataclass
class MatchResult:
    matched: bool
    tier: str                                   # "exact" | "semantic" | "none"
    map: dict[str, Any] | None = None
    map_index: int | None = None
    captures: dict[str, str] = field(default_factory=dict)
    score: float | None = None
    candidates: list[dict[str, Any]] = field(default_factory=list)
    degraded: bool = False
    explanation: str = ""


# ── Tier 1 — exact matching (Ruling 3.1 §3.1.5) ──────────────────────────────

def _ws_flexible(literal: str) -> str:
    """Escape a literal pattern segment, matching any internal run of
    whitespace flexibly and preserving boundary whitespace as a separator."""
    tokens = [re.escape(t) for t in literal.split()]
    if not tokens:
        return r"\s+" if literal else ""
    out = r"\s+".join(tokens)
    if literal[0].isspace():
        out = r"\s+" + out
    if literal[-1].isspace():
        out += r"\s+"
    return out


def _pattern_to_regex(pattern: str) -> re.Pattern:
    """Compile a map pattern like "I shelved [project]" to an anchored,
    case-insensitive regex with named capture groups."""
    parts = []
    pos = 0
    for m in _CAPTURE_RE.finditer(pattern):
        parts.append(_ws_flexible(pattern[pos:m.start()]))
        parts.append(f"(?P<{m.group(1)}>.+?)")
        pos = m.end()
    parts.append(_ws_flexible(pattern[pos:]))
    return re.compile(r"^\s*" + "".join(parts) + r"\s*$", re.IGNORECASE)


def _exact_match(declaration: str, maps: list[dict]) -> tuple[int, dict] | None:
    """First map (source order) whose pattern matches the declaration."""
    for i, m in enumerate(maps):
        pattern = m.get("pattern") or ""
        if not pattern:
            continue
        hit = _pattern_to_regex(pattern).match(declaration)
        if hit:
            captures = {k: v.strip() for k, v in hit.groupdict().items()}
            return i, captures
    return None


# ── Tier 2 — semantic matching (Ruling 3.1 §3.1.6) ───────────────────────────

def _comparison_text(pattern: str) -> str:
    """Map pattern rendered for embedding: each [name] becomes the name itself."""
    return _CAPTURE_RE.sub(lambda m: m.group(1), pattern)


def _capture_name(pattern: str) -> str | None:
    names = _CAPTURE_RE.findall(pattern)
    return names[0] if names else None


def _normalize_declaration(
    declaration: str, known_values: Iterable[str], capture_name: str | None
) -> str:
    """Mask known capture values with the map's capture name (§3.1.6)."""
    if not capture_name:
        return declaration
    text = declaration
    for value in known_values:
        if value:
            text = re.sub(re.escape(value), capture_name, text, flags=re.IGNORECASE)
    # collapse doubled capture words: "the project project" -> "the project"
    text = re.sub(rf"\b{capture_name}\s+{capture_name}\b", capture_name, text)
    return text


# ── Public API ────────────────────────────────────────────────────────────────

def match_declaration(
    declaration: str,
    maps: list[dict[str, Any]],
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    margin: float = DEFAULT_AMBIGUITY_MARGIN,
    known_values: Iterable[str] = (),
) -> MatchResult:
    """Match a user declaration against Rift map IR entries (Ruling 3.1).

    Tier 1 exact pattern match first; semantic similarity fallback only when
    no pattern matches. Ambiguous or low-confidence semantic comparisons
    return no match — never a silent arbitrary choice.
    """
    if not 0.0 < threshold <= 1.0:
        raise ValueError(
            f"threshold must be in (0.0, 1.0], got {threshold} "
            "(0.0 would accept everything — governance bypass)"
        )
    if not 0.0 <= margin < 1.0:
        raise ValueError(f"margin must be in [0.0, 1.0), got {margin}")

    if not declaration or not declaration.strip():
        return MatchResult(
            matched=False, tier="none",
            explanation="no match: empty declaration",
        )
    if not maps:
        return MatchResult(
            matched=False, tier="none",
            explanation="no match: no maps declared",
        )

    # ── Tier 1: exact ─────────────────────────────────────────────────────────
    exact = _exact_match(declaration, maps)
    if exact is not None:
        idx, captures = exact
        m = maps[idx]
        return MatchResult(
            matched=True, tier="exact", map=m, map_index=idx, captures=captures,
            explanation=(
                f"exact match: pattern \"{m.get('pattern')}\" matched; "
                f"captures: {captures}"
            ),
        )

    # ── Tier 2: semantic fallback ─────────────────────────────────────────────
    known_values = list(known_values)
    probes = [
        _normalize_declaration(declaration, known_values, _capture_name(m.get("pattern") or ""))
        for m in maps
    ]
    comparison_texts = [_comparison_text(m.get("pattern") or "") for m in maps]

    unique_texts = list(dict.fromkeys(probes + comparison_texts))
    embeddings = _encode(unique_texts)
    if embeddings is None:
        return MatchResult(
            matched=False, tier="none", degraded=True,
            explanation=(
                "no match: exact tier found nothing; semantic tier unavailable "
                "(embedding model not loadable) — DEGRADED"
            ),
        )

    emb_by_text = {t: embeddings[i] for i, t in enumerate(unique_texts)}
    scores = [
        round(float(emb_by_text[probes[i]] @ emb_by_text[comparison_texts[i]]), 4)
        for i in range(len(maps))
    ]

    candidates = sorted(
        (
            {
                "pattern": maps[i].get("pattern"),
                "comparison_text": comparison_texts[i],
                "score": scores[i],
                "map_index": i,
            }
            for i in range(len(maps))
        ),
        key=lambda c: c["score"],
        reverse=True,
    )
    best = candidates[0]
    second = candidates[1] if len(candidates) > 1 else None

    if best["score"] < threshold:
        return MatchResult(
            matched=False, tier="none", candidates=candidates,
            explanation=(
                f"no match: best semantic score {best['score']} "
                f"(\"{best['comparison_text']}\") below threshold {threshold}"
            ),
        )

    if second is not None and (best["score"] - second["score"]) < margin:
        return MatchResult(
            matched=False, tier="none", candidates=candidates,
            explanation=(
                f"no match: ambiguous — top candidates "
                f"\"{best['comparison_text']}\" ({best['score']}) and "
                f"\"{second['comparison_text']}\" ({second['score']}) "
                f"are within margin {margin}"
            ),
        )

    idx = best["map_index"]
    return MatchResult(
        matched=True, tier="semantic", map=maps[idx], map_index=idx,
        captures={},  # §3.1.8 — semantic matching identifies the map, not captures
        score=best["score"], candidates=candidates,
        explanation=(
            f"semantic match: \"{best['comparison_text']}\" "
            f"(score {best['score']} >= threshold {threshold}"
            + (
                f", margin {round(best['score'] - second['score'], 4)} >= {margin}"
                if second is not None else ""
            )
            + "); captures not extracted at this tier"
        ),
    )


def render_match(
    result: MatchResult,
    declaration: str = "",
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    margin: float = DEFAULT_AMBIGUITY_MARGIN,
) -> str:
    """Human-readable trace block for a match decision (Ruling 3.1 §3.1.10)."""
    lines = ["RIFT MATCH TRACE"]
    if declaration:
        lines.append(f"├── Declaration : \"{declaration}\"")
    lines.append(f"├── Tier        : {result.tier}")

    if result.tier == "exact":
        lines.append(f"├── Pattern     : \"{result.map.get('pattern')}\"")
        if result.captures:
            caps = ", ".join(f"[{k}] = \"{v}\"" for k, v in result.captures.items())
            lines.append(f"├── Captures    : {caps}")
    elif result.candidates:
        lines.append(f"├── Threshold   : {threshold}   Margin: {margin}")
        lines.append("├── Candidates  :")
        for j, c in enumerate(result.candidates):
            branch = "└──" if j == len(result.candidates) - 1 else "├──"
            selected = "   ← selected" if (
                result.matched and c["map_index"] == result.map_index
            ) else ""
            lines.append(
                f"│   {branch} \"{c['comparison_text']}\"   score: {c['score']}{selected}"
            )

    if result.degraded:
        lines.append("├── ⚠ DEGRADED  : embedding model unavailable")

    if result.matched:
        m = result.map
        target = f"{m.get('target_entity')}.{m.get('target_field')}: {m.get('state_value')}"
        lines.append(f"└── ✓ MATCHED → {target}")
    else:
        lines.append(f"└── ✗ NO MATCH — {result.explanation}")
    return "\n".join(lines)
