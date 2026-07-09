# Rift v0.2 — Known-Values Accumulation
### Implementation Note · July 2026

**Author:** GodSpeed313
**Stack:** Continuum (Pi Script · Rift · Execution Layer)
**Layer:** Rift (Layer 3)
**Spec:** Rift Ruling 3.2 (`rift_v02_ruling_3_2_known_values_accumulation.md`)
**Builds on:** Rift Ruling 3.1 (`rift/matcher.py`)

---

## What Was Built

Ruling 3.1 shipped `match_declaration()` with a `known_values` parameter —
entity-masking normalization, the single highest-leverage lever found during
calibration — but left it unfed: zero production call sites, and no source for
the values. This note documents the v0.2 answer: `rift/session.py`, the Intent
Layer's declaration-resolution entry point.

`RiftSession` holds a compiled map set and resolves natural-language
declarations against it at runtime. Its contribution beyond delegation is
**known-values accumulation**: every confirmed Tier 1 (exact) match yields real
capture values, which the session remembers and uses to mask later
declarations before Tier 2 semantic comparison. The system gets better at
recognizing paraphrased intent as a natural consequence of being used — no
caller wiring required, though caller-supplied values remain available as an
explicit per-call override.

The source of `known_values` was a real design decision, settled in Ruling 3.2
before implementation. Three candidates were evaluated: caller-supplied
(accepted as override only), Rift-accumulated from Tier 1 captures (adopted),
and pulling from Pi Script's live entity state — rejected outright as
cross-layer sourcing, structurally identical to the Ruling 9.8 reuse trap
Ruling 3.1 refused. The accumulated set is deliberately framed as a
**match-quality cache, not authoritative intent state**: losing it degrades
Tier 2 scores to the documented unmasked baseline, never produces incorrect
behavior. That framing is what makes in-memory-only acceptable — persistence
is explicitly deferred to a future ruling.

Every resolution is inspectable. `resolve()` returns a `Resolution` carrying
the Ruling 3.1 `MatchResult`, the exact values used for masking, the values
newly accumulated, and a trace extending the Ruling 3.1 block with a session
block:

```text
RIFT MATCH TRACE
├── Declaration : "let's pick Veritas back up"
├── Tier        : semantic
├── Threshold   : 0.3   Margin: 0.05
├── Candidates  :
│   ├── "let's revisit project"   score: 0.6831   ← selected
│   ├── "I shelved project"   score: 0.5168
│   └── "I'm done with project"   score: 0.5127
└── ✓ MATCHED → project.state: active
RIFT SESSION
├── Known values : "Veritas"
└── Accumulated  : (none — semantic tier extracts no captures)
```

## Measured, Not Asserted

The end-to-end demonstration (real model, canonical `shelved_projects.rift`):
a Tier 1 resolve of "I shelved Veritas" accumulates `Veritas`; a subsequent
"let's pick Veritas back up" resolves semantically at **0.6831** with the
accumulated masking — reproducing the Ruling 3.1 calibration value exactly.
The control run on a fresh session (no accumulation) scored **0.3055**: still
a match, but 0.0055 above the 0.30 threshold — a hair's-breadth pass that any
stricter threshold or slightly different phrasing tips into no-match. Masking
moved the decision from fragile to clear. The honest caveat: in this instance
it widened the winning score, not the match/no-match outcome itself.

## Zero Cross-Layer Imports — Confirmed

`rift/session.py` imports `dataclasses`, `typing`, `rift.matcher`, and
(lazily) `rift.validator`. Nothing else. `known_values` has exactly two
sources in the code: capture values from this session's own Tier 1 results,
and the explicit caller parameter. Pi Script's runtime entity state — which
tracks live values and would trivially have worked — is never read. That was
this session's specific trap, named and rejected in Ruling 3.2 §3.2.2.

As with Ruling 3.1, enforcement is not left to code review. Two permanent
tests: `test_no_pi_script_reference_in_source` asserts the string `pi_script`
does not appear in `rift/session.py`, and `test_import_does_not_load_pi_script`
imports `rift.session` in a fresh interpreter and asserts no `pi_script`
module was loaded.

## Test Results

Baseline before this work: 260 passing. After: **278 passing** (260 + 18, per
the Ruling 3.2 §3.2.10 test contract). No existing test was modified — the
only changes to `tests/test_rift.py` outside the new test classes are the
module docstring and one import line. Semantic-tier tests mock the embedding
call; the suite stays fast (~5s) and downloads nothing.

## What This Does Not Do

Scope discipline is still the contribution.

- **No persistence.** Accumulated values live and die with the `RiftSession`
  instance. Surviving restarts is a real design problem (format, staleness,
  invalidation when maps change) deferred to its own ruling — not absorbed
  silently into "just wiring." The cost is only match quality in a fresh
  session's first moments, before Tier 1 hits repopulate the set.
- **No cross-layer sourcing.** Rejected, not deferred. `known_values` never
  comes from `pi_script/*`, per `continuum_layer_boundaries.md`.
- **No capture extraction at the semantic tier.** Unchanged from Ruling 3.1
  §3.1.8 — the session does not guess entity values out of semantic matches,
  and its trace says so explicitly.
- **No dynamic constraint generation, no adaptive constraints, no Execution
  Layer.** Untouched, as before.
- **No grammar or compiler change.** `.rift` syntax and `.pi` output remain
  byte-identical. The session is an additive runtime API, exactly as the
  matcher was.
