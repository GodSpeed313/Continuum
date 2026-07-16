---
name: resolution-trace
description: Use when generating a RESOLUTION TRACE artifact — the log proof of the resolver acting on a constraint evaluation. Used for dogfooding evidence, LinkedIn/community proof points, and M7 adversarial-environment logging. Triggers on "trace", "resolution trace", "proof point", "violation log".
---

# Generating a RESOLUTION TRACE

A RESOLUTION TRACE is the artifact the resolver (`pi_script/trace.py`) emits every time it
evaluates constraints against a state snapshot — every constraint checked, every result
explained, whether or not anything violated. It's both a debugging record and the public-facing
proof point (used in the LinkedIn post format already established).

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
│   ├── Evaluation : <the actual values checked>
│   └── ✓ SATISFIED — no action   |   ✗ VIOLATION DETECTED
│       └── Action     : <on_violation actions taken, if violated>
...
└── RESOLUTION
    ├── System state : <running|frozen|rolled_back|...>
    └── <one-line plain-language summary>
```

A non-expert should be able to read the last line and understand exactly what happened — that's
the bar, not "technically complete."

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
