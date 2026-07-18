---
name: pi-script-constraint
description: Use whenever writing, editing, or reviewing a Pi Script constraint (the rule units that Continuum's resolver enforces, e.g. IdentityIntegrity, CadenceIntegrity, LinkRestriction). Triggers on "new constraint", "add a Pi Script rule", "constraint for M7", or when reviewing pi_script/ files.
---

# Writing a Pi Script Constraint

A constraint is a named, testable rule the resolver (`pi_script/resolver.py`) evaluates against
state snapshots over time — not a single-output filter. Every constraint follows this shape.

## 1. Ruling first
Before writing the constraint file, write a one-paragraph ruling: what behavior is being
restricted, why, and what "violation" looks like concretely. This is the spec-first step —
don't skip straight to the constraint syntax. Rulings live in `docs/`.

## 2. Constraint structure
Real Pi Script syntax (from `docs/pi_script_v01_draft3.md` / `docs/pi_script_v02_draft5.md`),
not a placeholder — six rule kinds exist: range, threshold, membership, equality, conditional,
contradiction. Shape:

```
constraint IdentityIntegrity {
    priority:     critical | high | medium
    rule:         <entity>.<field> must remain within range(...)   // or threshold / equal / membership / conditional / contradiction form
    on_violation: freeze | rollback | escalate | freeze + rollback | freeze + escalate
    decay_check:  <interval>   // optional, for time-bound re-checks
}
```

Check the actual grammar doc before writing — don't guess field names. If a needed rule shape
isn't one of the six kinds, that's a spec conversation before it's a code change.

## 3. Required test pair
For every constraint, add both to the relevant pytest file (`tests/test_resolver.py` or a new
`tests/test_moltbook_*.py` for M7-specific constraints — match the existing suite's convention,
don't invent a `.test`-file convention):
- **Deliberate-violation test** — state sequence that SHOULD trigger the flag
- **Clean-pass test** — a superficially similar sequence that should NOT trigger it (guards
  against false positives)

## 4. Wire into the existing suite
New constraint tests must run in the existing GitHub Actions workflow (`.github/workflows/`) and
report through the Discord webhook alert path already established in M5 — don't create a
parallel test runner. Test command is `pytest`, not `npm test`.

## 5. Current M7 constraint set (reference)
- `IdentityIntegrity` — agent identity claims stay consistent with declared identity over session
- `CadenceIntegrity` — near-exact periodic posting by the governed agent itself (timing only,
  never content or other accounts; docs/m7_cadence_integrity_ruling.md). First of the two
  Longitudinal Constraints that `ManipulationFlag` was split into.
- `CitationClusterIntegrity` — the governed agent's own outbound citations sustaining a
  small, tightly reciprocal, low-external-degree cluster (directional edges, causal
  attribution — incoming citations never establish a violation;
  docs/m7_citation_cluster_integrity_ruling.md). Second of the two Longitudinal Constraints.
  §5 thresholds are UNDEFINED until a grounding amendment — ungrounded, it renders
  NOT EVALUABLE and cannot fire.
- `LinkRestriction` — restricts what external links/references the agent can surface

When extending or reviewing these, check them against the ruling paragraph before touching the
constraint file — if the ruling doesn't exist yet, write it first.
