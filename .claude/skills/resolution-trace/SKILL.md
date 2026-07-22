---
name: resolution-trace
description: Use when generating a RESOLUTION TRACE artifact — the log proof of the resolver acting on a constraint evaluation. Used for dogfooding evidence, LinkedIn/community proof points, and M7 adversarial-environment logging. Triggers on "trace", "resolution trace", "proof point", "violation log".
---

# Generating a RESOLUTION TRACE

A RESOLUTION TRACE is the artifact the resolver (`pi_script/trace.py`) emits every time it
evaluates constraints against a state snapshot — every constraint checked, every result
explained, whether or not anything violated. It's both a debugging record and the public-facing
proof point (used in the LinkedIn post format already established).

## The status contract (authoritative)

A constraint result has exactly one of three statuses — this is the complete set:

- `satisfied` — the rule was checked and passed.
- `violated` — the rule was checked and failed. The ONLY status that may render the
  `✗ VIOLATION DETECTED` glyph or violation language, in the tree or in prose.
- `suspended` — the rule could not be evaluated (required state unavailable). Renders its
  own distinct line: `⏸ SUSPENDED — not evaluated; rule paused, no action`. A suspended
  rule is NOT a violation and must never be rendered or described as one.

Both rendering paths — the tree renderer (`render_trace`) and the plain-English gate field
(`human_text`) — validate against the same contract (`validate_constraint_statuses` in
`pi_script/trace.py`) before rendering. Rules enforced there:

- An unrecognized status **fails loudly** (`ValueError`). It is never mapped to violated,
  never rendered as satisfied, never silently dropped from the narrative, and can never
  produce a false all-clear ("all rules passed / no action taken").
- Every non-satisfied result (`violated` or `suspended`) must carry a non-empty
  explanation in its `evaluation` field. `satisfied` may omit it.

Do not hand-write trace snippets that show a suspended rule under a violation glyph, and
don't describe the world as binary satisfied/violated — M7's longitudinal constraints
(CadenceIntegrity / CitationClusterIntegrity) routinely report `suspended` as a healthy state.

## Real format
Matches what `trace.py` actually renders — don't invent a shorter ad hoc format for proof points,
use the real output (trim only per the external-use rules below):

```
RESOLUTION TRACE
════════════════════════════════════════════════════════════════════════
Timestamp    : <ISO8601>
Domain       : <domain name>
Entity       : <Entity> [session_id: <id>]
Trigger      : <what produced this snapshot>
════════════════════════════════════════════════════════════════════════
├── CONSTRAINT: <Name> [priority: <critical|high|medium>]
│   ├── Rule kind  : <range_rule|threshold_rule|membership_rule|equality_rule|conditional_rule|contradiction_rule>
│   ├── Evaluation : <the actual values checked — the reason, required for any non-satisfied result>
│   └── ✓ SATISFIED — no action
│       |   ⏸ SUSPENDED — not evaluated; rule paused, no action
│       |   ✗ VIOLATION DETECTED
│           └── Action     : <on_violation actions taken, only if violated>
...
└── RESOLUTION
    ├── System state : <running|frozen|escalated>
    └── <one-line plain-language summary>
```

A non-expert should be able to read the last line and understand exactly what happened — that's
the bar, not "technically complete."

## RIFT MATCH TRACE is a separate artifact

Rift's declaration matcher (`rift/matcher.py`) emits its own `RIFT MATCH TRACE` — do not mix
it into a RESOLUTION TRACE or map its outcomes onto constraint statuses. They are different
axes: Rift describes declaration-resolution confidence and matcher behavior; Pi Script
describes constraint-evaluation state and enforcement. Match uncertainty is never a Pi Script
evaluation status.

The Rift result is not a flat outcome enum. It is the composed `MatchResult` contract:

- `matched` (bool) × `tier` (`exact` | `semantic` | `none`) × `degraded` (bool) ×
  `explanation` (the reason, required non-empty for any unmatched or degraded result),
  plus `score`, threshold, margin, and candidate list where the semantic tier ran.

The trace preserves the distinct no-match reasons the matcher computes — empty declaration,
no maps declared, semantic tier unavailable (`⚠ DEGRADED`), best score below threshold, and
ambiguous top candidates within the margin. Never flatten these into a generic "no match",
and keep every score/threshold/margin/candidate line visible — an uninspectable similarity
decision is a black box. Internally invalid field combinations fail loudly
(`validate_match_result`), never fall through to a generic rendering path.

## When it's for external use (LinkedIn, Discord, Reddit)
- Strip anything that reveals internal implementation details of the Pi Script grammar or
  resolver internals — the trace should demonstrate governance working, not hand out a bypass map.
- Pair with one line of plain-language context (what a non-technical reader needs to understand
  why this matters) — matches the "self-taught, still learning, honest feedback" voice already
  established for Continuum's public posts.
- For M7, traces generated inside Moltbook are the actual test of enforcement in an adversarial
  environment — flag anything where the trigger came from another agent's behavior, not your own
  test harness, since those are the higher-value proof points. Write these to `moltbook/traces/`
  (sibling to `moltbook/state.json`), following the `m5/traces/` convention — not a shared
  top-level `traces/` directory.
