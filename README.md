# Continuum — Pi Script + Rift

**Pi Script declares what must stay true about an AI system's behavior. Rift maps what users declare in natural language to the constraints Pi Script enforces. Together they close the loop from human intent to machine accountability.**

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

Continuum is a three-layer governance stack for AI systems:

| Layer | Name | What it does |
| --- | --- | --- |
| Layer 1 | Your system | Emits state — metrics, flags, session data |
| Layer 2 | Pi Script | Declares constraints; resolver evaluates them against state snapshots |
| Layer 3 | Rift | Maps natural language declarations to Pi Script constraints |

**Pi Script** is a compiled governance language. You declare constraints in a formal grammar — range bounds, thresholds, equality checks, conditional triggers, contradiction detection — and a resolver evaluates them against live state snapshots, applies priority resolution when multiple constraints fire simultaneously, and emits a structured RESOLUTION TRACE every time.

**Rift** is the Intent Layer above Pi Script. You write what you mean in plain language — "I shelved this project", "freeze this permanently" — and Rift compiles those declarations into Pi Script constraints automatically. No hand-written Pi Script required.

The full loop:

```
User declares intent in natural language
        ↓
Rift maps declaration → machine state (map blocks)
        ↓
Rift compiles → Pi Script constraint set (.pi file)
        ↓
Pi Script resolver evaluates constraints against live state
        ↓
RESOLUTION TRACE — auditable, human-readable, every time
        ↓
Violations feed back as new user declarations (Rift)
```

Neither layer filters outputs or wraps prompts. They watch state over time and tell you precisely when and why a system drifted from what it was designed to be.

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
The grammar specification is in [`docs/pi_script_v01_draft3.md`](docs/pi_script_v01_draft3.md) (Draft 4).

---

## A Rift program

Write intent declarations in plain language. Rift compiles them to Pi Script automatically.

```
map "I shelved [project]"     -> project.state: dormant
map "let's revisit [project]" -> project.state: active
map "I'm done with [project]" -> project.state: closed

intent RespectShelfedProjects {
    when user declares: "I shelved [project]"
    treat: [project] as dormant
    until: user declares "let's revisit [project]"
    enforce: "do not reference [project] unprompted"
    generates: Pi Script constraint ShelvedProjectGuard
}

intent ReactivateProject {
    when user declares: "let's revisit [project]"
    treat: [project] as active
    releases: RespectShelfedProjects for [project]
    generates: Pi Script constraint ActiveProjectGuard
}
```

Compile it:

```bash
python -m rift.compiler rift/shelved_projects.rift
```

Output — valid Pi Script, ready for the resolver:

```
constraint ShelvedProjectGuard {
    priority:     medium
    rule:         Project.state must equal "dormant"
    on_violation: escalate
}

constraint ActiveProjectGuard {
    priority:     medium
    rule:         Project.state must equal "active"
    on_violation: escalate
}
```

The full canonical example is in [`rift/shelved_projects.rift`](rift/shelved_projects.rift). The generated output is in [`rift/shelved_projects.pi`](rift/shelved_projects.pi).

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
| --- | --- |
| M1 — Grammar specification, Draft 4 | ✅ Complete |
| M2 — Semantic validator | ✅ Complete — 12/12 tests |
| M3 — Parser formal sign-off | ✅ Complete — 9/9 tests |
| M4 — Resolver core + RESOLUTION TRACEs | ✅ Complete — 89/89 tests |
| M5 — Dogfood (23-day active run, 6+ violations across two independent systems) | ✅ Complete |
| Rift v0.1 — Intent Layer (grammar, parser, validator, compiler) | ✅ Complete — 33/33 tests |
| M6 — Publish (paper + public playground) | 🔄 In progress |

122 tests passing across parser, validator, trace builder, resolver, and Rift pipeline.

---

## Structure

```
continuum/
├── docs/
│   ├── pi_script_v01_draft3.md       # Full grammar specification (Draft 4)
│   ├── m6_paper_draft1.md            # M6 publication draft — M5 findings
│   └── continuum_layer_boundaries.md # Layer boundary reference — what belongs where
├── es/
│   ├── es_governance.pi              # Pi Script policy for Elasticsearch governance
│   ├── es_adapter.py                 # State adapter — queries ES, writes state.json
│   └── baseline.json                 # Committed mapping hash — schema governance source of truth
├── examples/
│   ├── tasks.pi                      # Working example — AI task agent governance
│   └── test_happy.pi                 # Happy path file exercising all rule forms
├── m5/
│   ├── dogfood.pi                    # M5 dogfood policy — governs Continuum AI assistant usage
│   ├── ir.json                       # Compiled IR for dogfood.pi
│   ├── state.json                    # Session state snapshot — update before each daily run
│   └── traces/                       # RESOLUTION TRACE logs — M5 violation record
├── pi_script/
│   ├── pi_script.lark                # Lark grammar
│   ├── parser.py                     # LALR parser wrapper
│   ├── validator.py                  # Semantic validator — produces IR
│   ├── resolver.py                   # Constraint evaluator — produces RESOLUTION TRACEs
│   └── trace.py                      # Trace builder, renderer, human_text generator
├── rift/
│   ├── rift_v01.lark                 # Lark grammar — Intent Layer
│   ├── parser.py                     # Earley parser wrapper
│   ├── validator.py                  # Semantic validator — extracts intent IR
│   ├── compiler.py                   # Pi Script emitter — generates .pi from .rift
│   ├── shelved_projects.rift         # Canonical test program
│   └── shelved_projects.pi           # Generated Pi Script output
├── rift_design_note_draft2.md        # Rift (Layer 3) design — v0.1 intent layer spec
├── tests/
│   ├── test_parser.py                # M1 + M3 — 9 tests
│   ├── test_validator.py             # M2 — 12 tests
│   ├── test_trace.py                 # trace.py — 31 tests
│   ├── test_resolver.py              # M4 — 38 tests
│   └── test_rift.py                  # Rift v0.1 — 33 tests
├── log_session.py                    # M5 daily runner — resolves dogfood.pi against current state
├── pi_monitor.py                     # Pi device health monitor — posts resolver status to Discord
├── state.json                        # Example state snapshot (locked schema)
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

- Bidirectional map blocks (Pi Script v0.2)
- Semantic similarity map matching (Pi Script v0.2)
- Cross-domain constraint inheritance (Pi Script v0.2)
- Adaptive constraints that evolve within bounds (Pi Script v0.3)
- Rift Semantic Layer — `agent`, `state`, `behavior evolves` constructs (Rift v0.2)
- Rift dynamic constraint generation — runtime re-evaluation without recompile (Rift v0.2)
- Rift Execution Layer — `@gpu`, `@quantum`, `@realtime` annotations (Rift v0.3)
- Natural language constraint authoring — NLP-based map matching (Rift v0.2+)

---

Continuum v0.1 — Pi Script Draft 4 + Rift Intent Layer — May 2026
