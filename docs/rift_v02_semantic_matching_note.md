# Rift v0.2 — Semantic Declaration Matching
### Implementation Note · July 2026

**Author:** GodSpeed313
**Stack:** Continuum (Pi Script · Rift · Execution Layer)
**Layer:** Rift (Layer 3)
**Spec:** Rift Ruling 3.1 (`rift_v02_ruling_3_1_semantic_declaration_matching.md`)

---

## What Was Built

Rift v0.1 maps user declarations to machine states through exact string patterns
with named captures. A declaration that doesn't fit a pattern exactly produces
nothing — the user's intent silently fails to become policy. This note documents
the v0.2 answer: a two-tier declaration matcher, `rift/matcher.py`.

Tier 1 compiles each map pattern to an anchored, case-insensitive regex and
extracts captures on match. Tier 2 runs only when Tier 1 finds nothing: it
compares the declaration against each map's pattern text by embedding cosine
similarity (all-MiniLM-L6-v2) and selects the best candidate only when the
score clears a calibrated threshold (default 0.30) *and* clears the runner-up
by an ambiguity margin (default 0.05). Anything less is a defined no-match —
the system never makes a silent arbitrary choice between candidates it cannot
distinguish.

Every decision is inspectable. The result carries every candidate's score, and
`render_match()` produces a human-readable trace in the house style:

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
```

Thresholds were set from measurement, not intuition: the calibration table in
Ruling 3.1 §3.1.7 records the observed separation band (unrelated declarations
top out at 0.247; true intent paraphrases bottom out at 0.342 once known entity
names are masked with the capture name — the single highest-leverage
normalization found during calibration).

## Zero Cross-Layer Imports — Confirmed

Ruling 9.8 already implements semantic similarity matching inside
`pi_script/resolver.py`. That capability belongs to Layer 2 and was not reused:
`rift/matcher.py` contains its own sentence-transformers loader and its own
module-level model cache — a deliberate second instantiation, per the layer
boundary doc's rule that cross-layer integration is a v0.4+ feature.

This is not left to code review. Two tests enforce it permanently:
`test_no_pi_script_reference_in_source` asserts the string `pi_script` does not
appear anywhere in `rift/matcher.py`, and `test_import_does_not_load_pi_script`
imports `rift.matcher` in a fresh interpreter and asserts no `pi_script` module
was loaded.

## Test Results

Baseline before this work: 240 passing. After: **260 passing** (240 + 20 new,
per the Ruling 3.1 test contract). No existing test was modified — the only
change to `tests/test_rift.py` outside the new test classes is the module
docstring and one import line. The suite mocks the embedding call, so it stays
fast (~5s) and does not download the model.

## What v0.2 Semantic Matching Does Not Do

The paper is honest about what this does not do. Scope discipline is the
contribution.

- **No capture extraction at the semantic tier.** Tier 2 identifies *which map*
  a declaration means, not the entity value inside it. Guessing a capture span
  from an embedding comparison would be undefined behavior; `captures` is
  always empty for semantic matches (Ruling 3.1 §3.1.8).
- **No dynamic constraint generation.** That requires the full multi-phase
  resolver — a separate Layer 2 problem, deliberately untouched.
- **No adaptive constraints, no Execution Layer** (`@gpu` / `@quantum` /
  `@realtime`). Out of scope, not pulled in.
- **No grammar or compiler change.** `.rift` syntax and `.pi` output are
  byte-identical to v0.1. The matcher is an additive API.
- **Not governance-grade discrimination.** all-MiniLM-L6-v2 does not reliably
  separate subtle lifecycle states (dormant vs closed). The calibration data
  shows one wrong-ranking case that survives the default margin. The mitigation
  is honesty, not concealment: every score is in the trace, ambiguous cases
  fall to no-match, and governance-critical callers should raise the threshold
  or require exact matches.
