# Continuum — Pi Script

**Pi Script is a domain-specific language for declaring what must stay true about an AI system's behavior — and catching it when it drifts.**

---

## What you get

Run the resolver against a live state snapshot and get this:

```
RESOLUTION TRACE
════════════════════════════════════════════════════════════════════════
Timestamp    : 2026-04-27T23:32:44.195Z
Domain       : ai_governance
Entity       : TaskAgent [session_id: smoke-001]
Trigger      : event — state snapshot received for TaskAgent
════════════════════════════════════════════════════════════════════════
├── CONSTRAINT: ConfidenceFloor [priority: critical]
│   ├── Rule kind  : range_rule
│   ├── Evaluation : confidence_score = 0.72, within range(0.2 .. 1.0)
│   └── ✓ SATISFIED — no action
│
├── CONSTRAINT: ResponseCap [priority: high]
│   ├── Rule kind  : threshold_rule
│   ├── Evaluation : response_count = 42.0, below threshold 1000.0
│   └── ✓ SATISFIED — no action
│
├── CONSTRAINT: ModeCompliance [priority: medium]
│   ├── Rule kind  : membership_rule
│   ├── Evaluation : current_mode = 'normal_mode', matched in valid set ['normal_mode', 'safe_mode']
│   └── ✓ SATISFIED — no action
│
├── CONSTRAINT: SessionIntegrity [priority: high]
│   ├── Rule kind  : equality_rule
│   ├── Evaluation : is_active = True, equals expected True
│   └── ✓ SATISFIED — no action
│
├── CONSTRAINT: PrecautionaryPause [priority: high]
│   ├── Rule kind  : conditional_rule
│   ├── Evaluation : condition not met: confidence_score 0.72 < 0.5
│   └── ✓ SATISFIED — no action
│
└── CONSTRAINT: ConsistencyGuard [priority: critical]
│   ├── Rule kind  : contradiction_rule
│   ├── Evaluation : no prior responses on topic 'TaskAgent.response_history' within window
│   └── ✓ SATISFIED — no action
│
└── RESOLUTION
    ├── System state : running
    └── All rules were checked and passed: ConfidenceFloor, ResponseCap,
        ModeCompliance, SessionIntegrity, PrecautionaryPause, and ConsistencyGuard.
        Everything is within acceptable bounds. No action was taken.
```

Every constraint evaluated. Every result explained. A non-expert can read the last line and understand exactly what happened.

---

## What it is

Pi Script is a compiled governance layer for AI systems. You declare constraints in a formal grammar — range bounds, thresholds, equality checks, conditional triggers, contradiction detection — and a resolver evaluates them against live state snapshots, applies priority resolution when multiple constraints fire simultaneously, and emits a structured RESOLUTION TRACE every time.

It does not filter outputs. It does not wrap prompts. It watches state over time and tells you precisely when and why a system drifted from what it was designed to be.

The design rule is strict: **if a constraint cannot be formalized into something measurable, it does not belong in the language.** Vague language is a compile error, not a feature.

---

## Try it

```bash
git clone https://github.com/GodSpeed313/Continuum.git
cd Continuum
pip install -r requirements.txt
python quickstart.py
```

Or step through it manually:

```bash
# 1. Validate a Pi Script program — produces a structured IR
python -m pi_script.validator examples/tasks.pi

# 2. Run the resolver against a state snapshot
python -c "
from pi_script.validator import validate_file
import json
ok, errors, ir = validate_file('examples/tasks.pi')
with open('ir.json', 'w', encoding='utf-8') as f:
    json.dump(ir, f, indent=2)
"
python -m pi_script.resolver ir.json state.json
```

---

## A Pi Script program

```
domain ai_governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
}

entity TaskAgent {
    confidence_score: range(0.0 .. 1.0)
    response_count:   integer
    current_mode:     text
    is_active:        boolean
}

map SafeMode {
    target:   TaskAgent.current_mode
    maps_to:  "safe_mode"
    triggers: ["safe", "restricted", "limited access"]
}

constraint ConfidenceFloor {
    priority:     critical
    rule:         TaskAgent.confidence_score must remain within range(0.2 .. 1.0)
    on_violation: freeze + rollback
    decay_check:  1 hour
}

constraint PrecautionaryPause {
    priority:     high
    rule:         if TaskAgent.confidence_score < 0.5 then require confidence_review before responding
    on_violation: escalate
}

enforce {
    entity:      TaskAgent
    constraints: [ConfidenceFloor, PrecautionaryPause]
}
```

The full working example with all six rule forms is in [`examples/tasks.pi`](examples/tasks.pi).  
The grammar specification is in [`docs/pi_script_v01_draft3.md`](docs/pi_script_v01_draft3.md).

---

## How it differs from output filters

Tools like Guardrails AI filter or rewrite model outputs at inference time. Pi Script governs **state over time** — it evaluates whether a system's observable behavior has drifted from declared constraints across a time window, across a session, across multiple responses. Different problem.

| | Output filters | Pi Script |
|---|---|---|
| When it runs | At inference | On state snapshots |
| What it checks | Single output | State over time |
| What it produces | Filtered output | Auditable RESOLUTION TRACE |
| How it's defined | Validators/schemas | Formal grammar |
| Failure mode | Silent rewrite | Explicit violation + action |

---

## Build status

| Milestone | Status |
|---|---|
| M1 — Grammar specification, Draft 3 | ✅ Complete |
| M2 — Semantic validator | ✅ Complete — 12/12 tests |
| M3 — Parser formal sign-off | ✅ Complete — 9/9 tests |
| M4 — Resolver core + RESOLUTION TRACEs | ✅ Complete — 89/89 tests |
| M5 — Dogfood (30 days, real violations detected) | 🔄 In progress |
| M6 — Publish (paper + public playground) | ⬜ Pending M5 |

89 tests passing across parser, validator, trace builder, and resolver.

---

## Structure

```
continuum/
├── docs/
│   └── pi_script_v01_draft3.md   # Full grammar specification
├── examples/
│   ├── tasks.pi                   # Working example — AI task agent governance
│   └── test_happy.pi              # Happy path file exercising all rule forms
├── pi_script/
│   ├── pi_script.lark             # Lark grammar
│   ├── parser.py                  # LALR parser wrapper
│   ├── validator.py               # Semantic validator — produces IR
│   ├── resolver.py                # Constraint evaluator — produces RESOLUTION TRACEs
│   └── trace.py                   # Trace builder, renderer, human_text generator
├── tests/
│   ├── test_parser.py             # M1 + M3 — 9 tests
│   ├── test_validator.py          # M2 — 12 tests
│   ├── test_trace.py              # trace.py — 31 tests
│   └── test_resolver.py           # M4 — 38 tests
├── state.json                     # Example state snapshot (locked schema)
└── requirements.txt
```

---

## Guiding principles

1. **Spec first, always.** The grammar specification is the source of truth. Code implements the spec. The spec is never reverse-engineered from code.
2. **Measurable or it doesn't exist.** If a constraint can't be formalized into something a runtime can evaluate, it has no place in v0.1.
3. **No undefined behavior.** Every failure mode has a defined safe state. The runtime never silently fails.
4. **Human-readable traces are non-negotiable.** If a non-expert can't read the RESOLUTION TRACE and understand why the system acted, the trace format is broken — not the person.

---

## What's deliberately not in v0.1

Scope discipline is a feature. These are deferred on purpose, not forgotten:

- Bidirectional map blocks (v0.2)
- Semantic similarity map matching (v0.2)
- Cross-domain constraint inheritance (v0.2)
- Adaptive constraints that evolve within bounds (v0.3)
- Rift Layer 3 integration (v0.4)
- Natural language constraint authoring (v0.5)

---

*Pi Script v0.1 — Draft 3 — April 2026*
