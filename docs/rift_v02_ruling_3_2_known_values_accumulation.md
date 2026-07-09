# Rift Ruling 3.2 — Known-Values Accumulation and the Declaration-Resolution Entry Point

**Status:** Binding for implementation. Confirmed at Checkpoint 1 (2026-07-09) with three clarifications folded in: `from_rift_file` validation-failure behavior (§3.2.5), union dedup semantics (§3.2.6 rule 6), byte-accurate trace example (§3.2.8).

**Numbering note:** Rift rulings use the 3.x series (3 for Layer 3), numbered in order of adoption. This is the second Rift ruling, building directly on Ruling 3.1 (semantic declaration matching).

---

## 3.2.1 Problem

Ruling 3.1 shipped `match_declaration()` with a `known_values` parameter for entity-masking normalization — the single highest-leverage normalization found during calibration (§3.1.7: "I've completed the Veritas project" scores 0.751 against "I'm done with project" when "Veritas" is masked, versus 0.470 raw). Two gaps remain:

1. **No production call site exists.** `match_declaration()` is called only by tests. There is no runtime moment where a user declaration actually gets resolved against a compiled map set.
2. **No source for `known_values` exists.** The one test that populates it supplies values by hand. Nothing in the system knows which entity values are in play.

The compile pipeline is **not** the answer to either gap. `RiftCompiler.compile()` transforms `.rift` source into `.pi` output; its inputs are map patterns and capture names (`[project]`), never entity values ("Veritas") — no user declaration exists at compile time, so there is nothing to match and nothing to mask. Confirmed against `rift/compiler.py`: every emitter consumes `pattern`, `target_entity`, `target_field`, `state_value` from the validator IR; no declaration text appears anywhere in a compile.

The matcher's real home is a **declaration-resolution entry point**: the Intent Layer's runtime moment where a user declares something in natural language ("let's pick Veritas back up") and Rift decides which map it corresponds to. Design note Draft 2 describes this moment abstractly (Q6: "new user declaration received" triggers re-evaluation) but defines no concrete mechanism. This ruling defines it.

## 3.2.2 Where `known_values` Comes From — The Decision

Three candidate sources were evaluated:

| # | Source | Verdict |
| --- | --- | --- |
| 1 | **Caller-supplied.** Stateless, trivially safe — but pushes the problem to a caller that doesn't exist yet. | Accepted as an **explicit override parameter**, not the primary mechanism. |
| 2 | **Rift-accumulated from prior Tier 1 (exact) matches.** Exact-tier matches already extract captures (Ruling 3.1 — the semantic tier never does, §3.1.8), so every confirmed Tier 1 hit yields a real entity value. Fully self-contained in Layer 3. | **ADOPTED** as the primary mechanism. This is what "known capture values" means. |
| 3 | **Pull entity values from Pi Script's runtime state.** Pi Script does track live entity values, making this the path of least resistance. | **REJECTED.** Cross-layer state sharing, structurally identical to the Ruling 9.8 reuse trap rejected in Ruling 3.1 §3.1.3. See §3.2.4. |

Option 2's cost is that it introduces state into Rift. That state is legitimate Layer 3 property: `continuum_layer_boundaries.md` assigns Rift ownership of "user intent declarations, natural language → machine state mapping, intent lifecycle," and design note Draft 2 Q3 rules "Rift owns user-declared state." Accumulated known values derive solely from user declarations that Rift itself resolved — no other layer is consulted.

## 3.2.3 What the Accumulated State Is — and Is Not

The accumulated known-values set is a **match-quality cache, not authoritative intent state**. Losing it degrades Tier 2 match scores back to the documented unmasked baseline (Ruling 3.1 §3.1.6: "When `known_values` is empty, the raw declaration is used") — it never produces incorrect behavior, only weaker semantic separation. This is why in-memory-only is acceptable now:

- **Lifecycle/scope:** the set lives on a `RiftSession` instance (§3.2.5) and dies with it. One session = one construction of the entry point. No module-level globals — two sessions never share accumulated values.
- **Persistence is explicitly deferred.** Design note Q6 says intent persists across sessions by design — but the *intent* persistence lives in `.rift` source and generated `.pi` constraints, which already survive restarts. The known-values cache is an optimization layered on top; persisting it (file format, staleness, invalidation when maps change) is a real design problem that deserves its own ruling when a use case demands it. Deferring it costs only match quality in the first moments of a fresh session, before Tier 1 hits repopulate the set.

## 3.2.4 Independence Boundary (Hard Requirement, carried from 3.1.3)

- The new module **must not** import from, call into, or share state with `pi_script.resolver` or any other `pi_script` module.
- Specifically: `known_values` **must never** be sourced from Pi Script's runtime entity state, even though that state is real, live, and would trivially work. That is candidate 3, rejected above. Cross-layer integration is v0.4+ per `continuum_layer_boundaries.md`.
- Enforcement is testable, same mechanism as Ruling 3.1: the suite asserts the string `pi_script` does not appear in the new module's source, and that importing it loads no `pi_script` module.

## 3.2.5 API

New module `rift/session.py`. ("Session" states the in-memory lifecycle honestly; "resolver" was rejected as a name because the resolver is Layer 2 vocabulary — `pi_script/resolver.py` — and reusing it across the boundary invites exactly the confusion this project's conventions exist to prevent.)

```python
from rift.session import RiftSession

session = RiftSession(
    maps,                        # list[dict] — validator IR map entries (ir["maps"])
    threshold=0.30,              # forwarded to match_declaration
    margin=0.05,                 # forwarded to match_declaration
)
# convenience constructor for a .rift source file:
session = RiftSession.from_rift_file("rift/shelved_projects.rift")
```

**`from_rift_file` validation failure:** if the source fails parsing or validation, the constructor raises `ValueError` whose message lists the validator's errors verbatim, one per line. It never returns a session over an invalid IR — a session constructed from bad source would be undefined behavior deferred to resolve time.

```python

resolution = session.resolve(
    declaration,                 # str — the user's natural-language declaration
    known_values=(),             # Iterable[str] — caller-supplied override (option 1)
)
```

**Result contract (`Resolution` dataclass):**

| Field | Type | Meaning |
| --- | --- | --- |
| `result` | MatchResult | The Ruling 3.1 result, unchanged contract |
| `trace` | str | Human-readable trace (§3.2.7) — always populated |
| `known_values_used` | tuple[str, ...] | Exactly what was passed to `match_declaration` for this call (accumulated ∪ caller-supplied), in masking order |
| `newly_accumulated` | tuple[str, ...] | Capture values this call added to the session (empty unless Tier 1 matched) |

**Inspectability:** `session.known_values` is a read-only property returning the current accumulated tuple. State that can't be inspected is a black box.

`threshold`/`margin` validation is Ruling 3.1's — the session forwards and does not re-validate, so the `ValueError` contract is identical.

## 3.2.6 Accumulation Rules

1. **Only Tier 1 (exact) matches accumulate.** The semantic tier never extracts captures (Ruling 3.1 §3.1.8), so it never contributes values. A no-match contributes nothing.
2. **All capture values from the winning exact match accumulate**, as returned by the matcher (already whitespace-trimmed). Empty strings never accumulate.
3. **Deduplication is case-insensitive; first-seen casing is preserved.** Masking is already case-insensitive (Ruling 3.1 §3.1.6), so casing variants are redundant for matching; the preserved form is for trace readability.
4. **Masking order is longest-first.** When passed to `match_declaration`, values are ordered by descending length so that "Veritas 2" masks before "Veritas" — otherwise the substring masks first and leaves "project 2" residue in the probe. Within equal lengths, insertion order.
5. **Caller-supplied `known_values` (option 1) are used for that call only — they are never persisted into the session's accumulated set.** The accumulated set records only what Rift itself confirmed via exact matches; keeping caller values out preserves clean provenance. A caller that wants a value remembered can declare it (Tier 1) or re-supply it per call.
6. **The per-call union (accumulated ∪ caller-supplied) dedups case-insensitively, and the accumulated form wins.** If the session holds "Veritas" and the caller supplies "VERITAS", the value passed to the matcher is "Veritas" — session-confirmed casing takes precedence for trace readability (matching itself is case-insensitive either way). Caller-internal duplicates dedup the same way, first form winning. Longest-first ordering (rule 4) applies to the **merged** set, not to each source separately.

## 3.2.7 Degradation and Defined Safe States

- **Empty accumulation, nothing supplied:** `resolve()` behaves exactly as `match_declaration(..., known_values=())` — the documented Ruling 3.1 unmasked baseline. Never a crash, never a silently skipped match.
- **Embedding model unavailable:** the Ruling 3.1 §3.1.9 degraded contract passes through untouched — `degraded: True`, visible in the trace. Accumulation state is unchanged by a degraded call.
- **No match:** nothing accumulates; the trace names the failing condition per Ruling 3.1.

## 3.2.8 Trace Contract

Every `resolve()` produces a trace: the Ruling 3.1 `render_match` block (threshold/margin as configured on the session), followed by a session block making the masking state visible. The example below is byte-accurate to real `render_match` output — note that `render_match` renders numeric parameters via Python float formatting, so a threshold of `0.30` prints as `0.3` (confirmed against the shipped implementation; Ruling 3.1 §3.1.10's example showing "0.30" predates the implementation and is not byte-accurate):

```text
RIFT MATCH TRACE
├── Declaration : "let's pick Veritas back up"
├── Tier        : semantic
├── Threshold   : 0.3   Margin: 0.05
├── Candidates  :
│   ├── "let's revisit project"   score: 0.6832   ← selected
│   ├── "I'm done with project"   score: 0.5168
│   └── "I shelved project"   score: 0.4321
└── ✓ MATCHED → project.state: active
RIFT SESSION
├── Known values : "Veritas"
└── Accumulated  : (none — semantic tier extracts no captures)
```

A Tier 1 trace renders `Accumulated : [project] = "Veritas"` when new values were added. A call that used no known values renders `Known values : (none)`. The masking that lifted (or failed to lift) a score must never be invisible.

## 3.2.9 Scope Exclusions

Deliberately out of scope for this ruling:

- **Persistence of accumulated values** across process restarts (§3.2.3 — deferred to a future ruling).
- **Sourcing values from any other layer** (§3.2.4 — rejected, not deferred).
- **Dynamic constraint generation, adaptive constraints, the Execution Layer** (`@gpu`/`@quantum`/`@realtime`) — unchanged from Ruling 3.1's exclusions.
- **Grammar or compiler changes.** None. `.rift` syntax and `.pi` output remain byte-identical. The session is an additive runtime API, exactly as the matcher was.
- **Capture extraction at the semantic tier** — unchanged from Ruling 3.1 §3.1.8. The session does not attempt to recover entity values from semantic matches, even though `known_values` occurrences in the raw declaration would make a best-effort guess tempting. Same undefined-behavior objection as before.

## 3.2.10 Test Contract

```text
TestRiftSession:
  test_tier1_captures_accumulate            (exact match → capture value lands in session.known_values)
  test_accumulated_values_mask_later_calls  (Tier 1 hit, then Tier 2 call → probe passed to encode is masked)
  test_semantic_match_does_not_accumulate   (semantic match → newly_accumulated empty, state unchanged)
  test_no_match_does_not_accumulate         (no match → state unchanged)
  test_caller_values_used_for_call          (option 1 override reaches the matcher)
  test_caller_values_not_persisted          (override values absent from session.known_values afterward)
  test_dedup_case_insensitive               ("Veritas" then "VERITAS" → one entry, first casing kept)
  test_union_accumulated_form_wins          (session holds "Veritas", caller supplies "VERITAS" → matcher receives "Veritas")
  test_masking_order_longest_first          ("Veritas" + "Veritas 2" → "Veritas 2" ordered first in the merged set)
  test_empty_accumulation_baseline          (fresh session ≡ bare match_declaration with no known_values)
  test_degraded_model_visible_not_crash     (encode unavailable → degraded in result and trace, state unchanged)
  test_known_values_property_readonly       (property returns tuple; mutation attempts don't alter state)
  test_trace_shows_session_block            (trace contains known-values and accumulation lines)
  test_from_rift_file_constructor           (canonical shelved_projects.rift loads and resolves)
  test_from_rift_file_invalid_raises        (invalid .rift source → ValueError listing validator errors)

TestRiftSessionIndependence:
  test_no_pi_script_reference_in_source     (string "pi_script" absent from rift/session.py)
  test_import_does_not_load_pi_script       (fresh interpreter: importing rift.session leaves no pi_script module in sys.modules)

End-to-end (in TestRiftSession):
  test_end_to_end_accumulation_flow         (declaration resolved via Tier 1 populates a value; a second
                                             declaration resolves via Tier 2 with the masked probe; both
                                             traces visible and asserted)
```

No implementation step begins until this spec's status reads "Binding for implementation."

---

| Field | Value |
| --- | --- |
| Ruling | Rift 3.2 — Known-Values Accumulation & Declaration-Resolution Entry Point |
| Layer | Rift (Layer 3) |
| Status | Spec locked (Checkpoint 1 confirmed 2026-07-09). Implementation gate open. |
| Grammar change | None |
| Compiler change | None |
| New module | `rift/session.py` |
| Depends on | Ruling 3.1 (`rift/matcher.py`), design note Draft 2 Q3/Q6 |
| Boundary authority | `docs/continuum_layer_boundaries.md` — no `pi_script` imports, v0.4+ integration only |
| Known-values source | Option 2 (Tier 1 accumulation) primary; option 1 (caller-supplied) as per-call override; option 3 (Pi Script state) rejected |
| Persistence | Explicitly deferred — in-memory per-session only |
