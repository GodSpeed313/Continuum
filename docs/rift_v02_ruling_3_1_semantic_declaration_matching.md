# Rift Ruling 3.1 — Semantic Declaration Matching

**Status:** Binding for implementation. No code may be written against this ruling until this section is complete. This is the canonical Rift v0.2 spec ruling for NLP-based map matching in the Intent Layer.

**Numbering note:** Pi Script rulings use the 9.x series (Section IX of the Pi Script spec). Rift rulings use the 3.x series — 3 for Layer 3, numbered in order of adoption. This is the first Rift ruling.

---

## 3.1.1 Problem

Rift v0.1 maps user declarations to machine states through explicit string patterns with named captures (design note Draft 2, Q2): `map "I shelved [project]" → project.state: dormant`. Matching is purely lexical — a declaration matches a map only when it fits the pattern exactly. "I shelved Veritas" matches; "I put Veritas on ice" does not, even though both express the same intent.

This is the same governance gap Ruling 9.8 identified at Layer 2: semantically equivalent inputs escape detection, and the author is forced to enumerate every surface form of an intent — an unbounded, brittle list. At Layer 3 the consequence is worse: a declaration that matches no map produces no machine state at all, so the user's intent silently fails to become policy.

## 3.1.2 Solution

Rift v0.2 adds a **two-tier declaration matcher** to the `rift/` package:

| Tier | Name | Algorithm |
| --- | --- | --- |
| 1 | Exact | Pattern with named captures compiled to an anchored, case-insensitive regex. Captures extracted on match. |
| 2 | Semantic (fallback) | Cosine similarity of vector embeddings between the (normalized) declaration and each map's comparison text. Runs **only when Tier 1 finds nothing**. |

Tier 2 never overrides Tier 1. An exact match short-circuits: the semantic machinery is not invoked, and the embedding model is not loaded.

The matcher is a new, additive API. Nothing in the existing parse → validate → compile pipeline changes behavior. There is **no grammar change** in this ruling: threshold and margin are API parameters with spec'd defaults. Per-map opt-in syntax (the Layer 3 analogue of Ruling 9.8's `match_mode:` field) is deferred until a use case demands it.

## 3.1.3 Independence Boundary (Hard Requirement)

Ruling 9.8 already implements semantic similarity matching — inside `pi_script/resolver.py`, at Layer 2, where it serves constraint evaluation. Per `continuum_layer_boundaries.md`, cross-layer integration is a v0.4+ feature. Therefore:

- `rift/matcher.py` **must not** import from, call into, or share a model instance or cache with `pi_script.resolver` or any other `pi_script` module.
- The sentence-transformers setup is a **deliberate second instantiation**: Rift owns its own lazy loader and its own module-level model cache. sentence-transformers is already a project dependency (`requirements.txt`), so this duplicates setup code, not dependencies.
- The duplication is the cost of the layer boundary and is accepted. Consolidation, if ever, is a v0.4+ decision.

Enforcement is testable: the test suite asserts that the string `pi_script` does not appear in `rift/matcher.py` and that importing `rift.matcher` does not import any `pi_script` module.

## 3.1.4 API

```python
from rift.matcher import match_declaration, render_match

result = match_declaration(
    declaration,                 # str — the user's natural-language declaration
    maps,                        # list[dict] — validator IR map entries
    threshold=0.30,              # float in (0.0, 1.0] — semantic acceptance floor
    margin=0.05,                 # float in [0.0, 1.0) — ambiguity margin
    known_values=(),             # Iterable[str] — known capture values to mask
)
```

`maps` is the `ir["maps"]` list produced by `RiftValidator` — entries of shape `{"pattern", "target_entity", "target_field", "state_value"}`.

**Result contract (`MatchResult` dataclass):**

| Field | Type | Meaning |
| --- | --- | --- |
| `matched` | bool | A map was selected |
| `tier` | str | `"exact"`, `"semantic"`, or `"none"` |
| `map` | dict \| None | The winning map IR entry |
| `map_index` | int \| None | Index of the winning map in `maps` |
| `captures` | dict | Capture name → value. **Exact tier only**; always `{}` for semantic (see 3.1.8) |
| `score` | float \| None | Winning similarity score (semantic tier only), rounded to 4 places |
| `candidates` | list[dict] | All semantic candidates with `pattern`, `comparison_text`, `score`, sorted descending. Empty if Tier 2 never ran |
| `degraded` | bool | Embedding model unavailable when Tier 2 was needed |
| `explanation` | str | One-line human-readable account of the decision |

**Parameter validation (mirrors Ruling 9.8's validator contract):** `threshold` must satisfy `0.0 < threshold ≤ 1.0` — `0.0` is rejected as a governance bypass, values above `1.0` are unreachable. `margin` must satisfy `0.0 ≤ margin < 1.0`. Violations raise `ValueError` — never a silent clamp.

## 3.1.5 Tier 1 — Exact Matching Algorithm

1. For each map, in **source order**, compile `pattern` to a regex: literal segments escaped, each `[name]` replaced with a named group matching one or more characters, inter-token whitespace matched flexibly (`\s+`), anchored at both ends, case-insensitive.
2. The first map whose regex matches the whitespace-trimmed declaration wins. Captures come from the named groups.
3. **Precedence rule:** source order. If two patterns both match, the earlier map in the `.rift` file wins. This is deterministic and auditable; authors control it by ordering their maps.

## 3.1.6 Tier 2 — Semantic Matching Algorithm

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` — the same model family as Ruling 9.8, chosen for the same reasons (lightweight, no API key, deterministic within a version), instantiated independently per 3.1.3.

**Comparison text:** each map's pattern with every `[name]` capture replaced by the capture name itself (`"I shelved [project]"` → `"I shelved project"`). Calibration (3.1.7) showed this outperforms dropping the capture, substituting pronouns, or enriching with the target state value.

**Declaration normalization:** every occurrence of a `known_values` entry in the declaration is replaced (case-insensitively) with the map's capture name before encoding, and doubled capture words are collapsed (`"the project project"` → `"the project"`). Rift owns user-declared state, so callers typically know the entity names in play (e.g., every project name previously declared). Calibration showed this is the single highest-leverage normalization: it aligns `"I've completed the Veritas project"` with `"I'm done with project"` at 0.751 where the raw text scores 0.470. When `known_values` is empty, the raw declaration is used.

**Selection:**

1. Encode the normalized declaration and all comparison texts as normalized embeddings; cosine similarity = dot product.
2. Rank maps by score, descending. The maximum score wins **iff both hold**:
   - `best_score ≥ threshold`
   - `best_score − second_score ≥ margin` (when more than one map exists)
3. Otherwise the result is **no match** — with the failing condition named in `explanation`. Two maps scoring within the margin means the model cannot distinguish them; selecting one would be a silent arbitrary choice, which this project's conventions prohibit. The defined safe state is no match, reported as `ambiguous`.

The margin applies to the top two raw scores regardless of whether the runner-up clears the threshold: near-identical scores mean indistinguishable candidates either way.

## 3.1.7 Threshold and Margin — Calibration Data

Defaults were set from measurement, not intuition, against the canonical `shelved_projects.rift` maps (2026-07-08, sentence-transformers 5.6.0, all-MiniLM-L6-v2). Declarations masked per 3.1.6 with known value "Veritas":

| Declaration (normalized) | Expected | Best map | Score | 2nd | Gap |
| --- | --- | --- | --- | --- | --- |
| "let's pick project back up" | active | active ✓ | 0.683 | 0.517 | 0.166 |
| "I've completed the project" | closed | closed ✓ | 0.751 | 0.524 | 0.227 |
| "I'm shelving project" | dormant | dormant ✓ | 0.468 | 0.432 | 0.036 |
| "putting project on the back burner" | dormant | dormant ✓ | 0.342 | 0.325 | 0.018 |
| "project is finished, wrapping it up" | closed | dormant ✗ | 0.551 | 0.542 | 0.009 |
| "I put project on ice" | dormant | closed ✗ | 0.548 | 0.451 | 0.097 |
| "what's the weather like today" | none | — | 0.121 | | |
| "remind me to buy groceries" | none | — | 0.186 | | |
| "the build is failing on CI" | none | — | 0.247 | | |
| "schedule a dentist appointment" | none | — | 0.049 | | |

**`DEFAULT_SIMILARITY_THRESHOLD = 0.30`** — the empirical midpoint of the separation band: unrelated declarations top out at 0.247; true intent matches bottom out at 0.342.

**`DEFAULT_AMBIGUITY_MARGIN = 0.05`** — rejects the observed wrong-ranking case at gap 0.009 ("finished, wrapping it up") while admitting true matches at gaps ≥ 0.018 is not possible simultaneously; 0.05 was chosen to reject sub-0.05 coin flips while keeping the clear cases. Two dormant-phrasing cases with gaps 0.018/0.036 fall to ambiguous under the default — the safe direction.

**Known limitation, stated plainly:** all-MiniLM-L6-v2 does not reliably separate subtle lifecycle distinctions (dormant vs closed — "on ice" scored closed at gap 0.097 and would be accepted wrongly). The margin narrows but does not eliminate this. Semantic matching is a *fallback for intent discovery*, not a governance-grade decision: anything it matches is inspectable via `candidates` and `render_match`, and governance-critical callers should raise `threshold`/`margin` or require exact matches. This mirrors Ruling 9.8's stance that semantic matching is never the default.

## 3.1.8 Captures Under Semantic Matching

Tier 2 identifies **which map** the declaration means. It does not extract capture values: there is no pattern alignment in an embedding comparison, and guessing a capture span would be undefined behavior. `captures` is always `{}` for semantic matches, and the `explanation` says so. Callers that need the entity value must obtain it separately (e.g., from `known_values` occurrence in the raw declaration — the caller has the context to do this safely). Best-effort capture extraction is deliberately out of scope for this ruling.

## 3.1.9 Graceful Degradation

If the embedding model is unavailable (package missing, import error, encode failure) when Tier 2 is needed, the matcher **must not crash**:

1. Tier 1 has already run and found nothing — that result stands.
2. The result is no match with `degraded: True` and an `explanation` naming the degradation.
3. Degradation is per-call and always visible — silent degradation violates the audit-first principle (same contract as Ruling 9.8 §9.8.8).

## 3.1.10 Explanation / Trace Contract

Every result carries a one-line `explanation`. `render_match(result)` produces a human-readable trace block in the house style:

```text
RIFT MATCH TRACE
├── Declaration : "let's pick Veritas back up"
├── Tier        : semantic
├── Threshold   : 0.30   Margin: 0.05
├── Candidates  :
│   ├── "let's revisit project"   score: 0.6832   ← selected
│   ├── "I'm done with project"   score: 0.5170
│   └── "I shelved project"       score: 0.4321
└── ✓ MATCHED → project.state: active
```

No-match and degraded traces render the same block with `✗ NO MATCH` and the reason (`below threshold`, `ambiguous`, or `⚠ DEGRADED: embedding model unavailable`). A similarity decision that cannot be inspected is a black box; this trace is the non-negotiable window into it.

## 3.1.11 Test Contract

```text
TestRiftMatcherExact:
  test_exact_match_extracts_capture      (pattern with [capture] → tier exact, captures dict)
  test_exact_match_case_insensitive      (case differences still match)
  test_exact_whitespace_normalized       (extra internal/leading whitespace tolerated)
  test_exact_source_order_precedence     (two matching patterns → earlier map wins)
  test_literal_pattern_no_captures       (capture-free pattern matches exactly)
  test_no_match_returns_tier_none        (unrelated declaration, semantic mocked off → none)

TestRiftMatcherSemantic:  (embedding calls mocked; no model download in the suite)
  test_semantic_match_above_threshold    (best ≥ threshold, clear margin → matched, correct map)
  test_semantic_below_threshold_no_match (best < threshold → no match, explanation names threshold)
  test_semantic_ambiguous_no_match       (gap < margin → no match, explanation names ambiguity)
  test_semantic_captures_empty           (semantic match carries captures == {})
  test_semantic_result_has_candidates    (scores present, sorted descending)
  test_exact_short_circuits_semantic     (exact match → embedding function never called)
  test_degraded_flag_when_model_unavailable (encode unavailable → matched False, degraded True)
  test_threshold_zero_rejected           (threshold 0.0 → ValueError)
  test_threshold_one_accepted            (threshold 1.0 → valid)
  test_threshold_above_one_rejected      (threshold 1.1 → ValueError)
  test_known_values_masked_in_probe      (declaration normalization applied before encoding)
  test_render_match_shows_scores         (trace contains tier, scores, decision line)

TestRiftMatcherIndependence:
  test_no_pi_script_reference_in_source  (string "pi_script" absent from rift/matcher.py)
  test_import_does_not_load_pi_script    (fresh interpreter: importing rift.matcher leaves no pi_script module in sys.modules)
```

No implementation step begins until this spec section is locked.

---

| Field | Value |
| --- | --- |
| Ruling | Rift 3.1 — Semantic Declaration Matching |
| Layer | Rift (Layer 3) |
| Status | Spec locked. Implementation gate open. |
| Grammar change | None |
| Compiler change | None |
| New module | `rift/matcher.py` |
| Supersedes | Design note Draft 2 "NLP-based map matching — v0.2+" deferral |
| Boundary authority | `docs/continuum_layer_boundaries.md` — no `pi_script` imports, v0.4+ integration only |
