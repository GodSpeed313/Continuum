# Continuum

> *A language for defining what must remain true while everything else changes.*

---

## What It Is

Continuum is a three-layer stack for AI governance. At its core is **Pi Script** — a purpose-built language that lets you declare measurable constraints on AI system behavior, monitor violations in real time, and produce auditable resolution traces that a non-engineer can read and understand.

Pi Script does not tell AI systems how to act. It defines what must remain true while they change.

### The Stack

```
┌─────────────────────────────────────────┐
│  RIFT (Layer 3)                         │
│  Intent & System Design                 │
│  "What should this system be?"          │
├─────────────────────────────────────────┤
│  PI SCRIPT (Layer 2)                    │
│  Governance & Coherence                 │
│  "Is it still what it should be?"       │
├─────────────────────────────────────────┤
│  Execution Layer (Layer 1)              │
│  Classical / GPU / Quantum backends     │
└─────────────────────────────────────────┘
```

Pi Script is Layer 2. It sits between your execution environment and your intent — watching, evaluating, and flagging when the system drifts from what it was designed to be.

---

## Why It Exists

AI systems change. Models are updated, policies shift, tone drifts, responses contradict earlier responses. Most governance approaches try to solve this at the prompt level or the output filter level — both of which are fragile and hard to audit.

Continuum takes a different approach: **treat governance as a language problem, not a filtering problem.**

If you can write down what must remain true — in a precise, measurable grammar — then a runtime can monitor it, flag violations, and produce a trace that explains exactly what happened and why. No black boxes. No silent failures. No "the model just changed."

The design principle is strict: if a constraint cannot be formalized into something measurable, it does not belong in the language. Vague language is a compile error, not a feature.

---

## How It Works

A Pi Script program has six constructs:

- **`domain`** — scopes the program and sets the global audit cadence
- **`entity`** — the AI system being governed, with named, typed observable states
- **`constraint`** — a rule that must remain true, with priority, violation actions, and a decay check interval
- **`map`** — translates human language patterns into measurable machine states
- **`enforce`** — binds constraints to entities
- **`arbiter`** — the meta-constraint layer; defines what kinds of change are acceptable and what requires human sign-off

Every constraint evaluation produces a **RESOLUTION TRACE** — a structured, human-readable record of what was monitored, what was detected, and what action was taken. The gate condition for the trace format is simple: a non-expert must be able to read it and understand why the system acted.

### Example

```pi
domain governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
}

entity CustomerServiceAgent {
    state response_history : sequence(text)
    state tone_score       : range(0.0 .. 1.0)
    state policy_version   : integer
}

map 'actually,'         -> revision_event: potential_contradiction
map 'on second thought' -> revision_event: potential_contradiction

constraint NeverContradictPolicy {
    monitor      : CustomerServiceAgent.response_history
    against      : company_policy.current_version
    window       : 30 days
    rule         : if new_response contradicts prior_response(same_topic)
                   then require flag_revision before responding
    priority     : critical
    on_violation : flag + escalate
    decay_check  : every 24 hours
}

enforce {
    entity:      CustomerServiceAgent
    constraints: [NeverContradictPolicy]
}
```

---

## Current Status

Pi Script v0.1 is under active development. This is a research and build project — not production software.

| Milestone | Status |
|-----------|--------|
| M1 — Grammar specification | ✅ Complete |
| M2 — Semantic validator | ✅ Complete — 12/12 tests passing |
| M3 — Parser formal sign-off | ⬜ In progress |
| M4 — Resolver core (constraint evaluation + RESOLUTION TRACEs) | ⬜ Next |
| M5 — Dogfood (30 days, real violations) | ⬜ Pending |
| M6 — Publish (paper + public playground) | ⬜ Pending |

The grammar is spec-compliant as of Draft 3. The validator produces a fully correct IR. The resolver architecture is designed and ready to build.

---

## What's Deliberately Not Here Yet

Pi Script v0.1 is intentionally minimal. The following are known future features, deferred on purpose:

- Bidirectional map blocks (v0.2)
- Semantic similarity map matching (v0.2)
- Cross-domain constraint inheritance (v0.2)
- Adaptive constraints that evolve within bounds (v0.3)
- Rift Layer 3 integration (v0.4)
- Natural language constraint authoring (v0.5)

Scope discipline is a feature. A v0.1 that tries to do everything will do nothing correctly.

---

## Known Issues

- `test_validator_unit.py` — hand-built Lark Tree unit test harness was never saved to source. Needs to be recreated in `tests/`. Covers happy path IR extraction, semantic error cases, malformed AST None guard tests, and conditional rule variants.

---

## Structure

```
continuum/
├── pi_script/
│   ├── pi_script.lark      # Grammar
│   ├── parser.py           # Lark parser wrapper
│   └── validator.py        # Semantic validator — produces IR
├── tests/
│   ├── test_validator.py   # 12 M2 tests — all passing
│   └── test_parser.py
├── examples/
│   └── tasks.pi            # Working example
└── test_happy.pi           # Happy path test file
```

---

## Guiding Principles

1. **Spec first, always.** The grammar specification is the source of truth. Code implements the spec. The spec is never reverse-engineered from code.
2. **Measurable or it doesn't exist.** If a constraint can't be formalized into something a runtime can evaluate, it has no place in v0.1.
3. **No undefined behavior.** Every failure mode has a defined safe state. The runtime never silently fails.
4. **Human-readable traces are non-negotiable.** The RESOLUTION TRACE gate condition is not a nice-to-have. If a non-expert can't read the trace, the trace format is broken.

---

*Pi Script v0.1 — Draft 3 — April 2026*
