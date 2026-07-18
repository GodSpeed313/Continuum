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

**Rift** is the Intent Layer above Pi Script. You write what you mean in plain language — "I shelved this project", "freeze this permanently" — and Rift compiles those declarations into Pi Script constraints automatically. No hand-written Pi Script required. At runtime, Rift also resolves declarations it has never seen verbatim: an exact trigger match when one exists, and a semantic fallback when one doesn't — with every match decision traced and scored, never guessed silently.

The full loop:

```
User declares intent in natural language
        ↓
Rift maps declaration → machine state (exact or semantic match)
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
The v0.1 grammar specification is in [`docs/pi_script_v01_draft3.md`](docs/pi_script_v01_draft3.md) (Draft 4).  
The v0.2 rulings spec (9.4–9.9) is in [`docs/pi_script_v02_draft5.md`](docs/pi_script_v02_draft5.md).

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

## Resolving declarations at runtime — Rift v0.2

Compilation is no longer the only entry point. People don't repeat their trigger phrases verbatim — "let's pick Veritas back up" has to mean the same thing as "let's revisit Veritas". Rift v0.2 adds a two-tier declaration matcher and a session runtime:

```python
from rift.session import RiftSession

session = RiftSession.from_rift_file("rift/shelved_projects.rift")

# Tier 1 — exact trigger match. Extracts the capture, and the session
# remembers "Veritas" as a known entity value.
session.resolve("I shelved Veritas")

# No exact trigger matches this phrasing — Tier 2 semantic fallback,
# masked by the value the session learned above.
r = session.resolve("let's pick Veritas back up")
print(r.trace)
```

```
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

How it works, and what it refuses to do:

- **Exact first.** Tier 1 compiles each map pattern to an anchored, case-insensitive regex and extracts capture values. No embedding model is loaded unless Tier 1 misses.
- **Semantic fallback.** Tier 2 embeds the declaration (all-MiniLM-L6-v2) and ranks maps by cosine similarity — its own model instance, fully independent of Pi Script's Ruling 9.8 matcher, per the layer boundaries. Two permanent tests enforce that `rift/` never imports from `pi_script/`.
- **Ambiguity is a defined no-match, never a guess.** A winning score below the threshold, or a top-two gap inside the ambiguity margin, resolves to no match with the failing condition named in the trace.
- **The session learns from what it confirms.** Entity values extracted by exact matches accumulate (in-memory, per-session) and mask later semantic probes — the same declaration that scores 0.31 on a cold session scores 0.68 with a learned value. The semantic tier identifies *which map* a declaration means; capture values only ever come from the exact tier.
- **Every score is in the trace.** A similarity decision that can't be inspected is a black box; the trace is the non-negotiable window into it.

Specs: [Ruling 3.1 — semantic declaration matching](docs/rift_v02_ruling_3_1_semantic_declaration_matching.md) and [Ruling 3.2 — known-values accumulation](docs/rift_v02_ruling_3_2_known_values_accumulation.md), with implementation notes alongside each.

---

## Governing a real system — Elasticsearch

The adapter pattern bridges any Layer 1 system to Pi Script. The Elasticsearch adapter is the canonical example.

```bash
# 1. Start Elasticsearch (Docker)
docker run -d --name elasticsearch -p 9200:9200 \
  -e "discovery.type=single-node" \
  -e "xpack.security.enabled=false" \
  elasticsearch:8.13.4

# 2. Create your index
curl -X PUT "http://localhost:9200/governed-index" \
  -H "Content-Type: application/json" \
  -d '{"settings":{"number_of_shards":1,"number_of_replicas":0}}'

# 3. Record the known-good schema as baseline (commit this to git)
python es/es_adapter.py --bootstrap

# 4. Run governance — adapter reads cluster state, resolver evaluates it
python es/es_adapter.py
python -m pi_script.resolver es/ir.json es/state.json
```

Any unauthorized schema change triggers `SchemaIntegrity` at critical priority:

```
├── CONSTRAINT: SchemaIntegrity [priority: critical]
│   ├── Evaluation : schema_intact is False, expected True
│   ├── ✗ VIOLATION DETECTED
│   └── Action     : freeze + escalate
```

The full policy is in [`es/es_governance.pi`](es/es_governance.pi). The adapter is in [`es/es_adapter.py`](es/es_adapter.py).

---

## Governing a live agent — Moltbook (M7)

M7 puts a Continuum-governed agent onto **Moltbook**, a live social platform for autonomous agents — and an openly adversarial environment where injection payloads hunt for other agents' secrets. The [`moltbook/`](moltbook/) module follows the `m5/` dogfood pattern (one policy file, persistent state, sibling traces), governing the agent's own sessions rather than external infrastructure.

Five constraints, each with a locked, spec-first ruling in `docs/`:

| Constraint | Priority | Governs |
| --- | --- | --- |
| [`CredentialIntegrity`](docs/m7_credential_integrity_ruling.md) | critical | The platform API key stays unleakable — key isolation plus a pre-send gate |
| [`LinkRestriction`](docs/m7_link_restriction_ruling.md) | high | A link is surfaced only with provenance: present in the source content, or on the human-owned allowlist |
| [`IdentityIntegrity`](docs/m7_identity_integrity_ruling.md) | high | Declared identity stays self-consistent within a session — mechanical detection only ([addendum 1](docs/m7_identity_integrity_ruling_addendum_1.md)) |
| [`CadenceIntegrity`](docs/m7_cadence_integrity_ruling.md) | high | No near-exact periodic posting — the agent's own timing, never content, never other accounts |
| [`CitationClusterIntegrity`](docs/m7_citation_cluster_integrity_ruling.md) | high | The agent's own outbound citations must not sustain a small, closed, reciprocal citation cluster |

The design rules the module enforces:

- **Prevention is client-side; Pi Script is the enforcement latch and audit trace.** The client's scan-all-then-block pre-send gate runs every detector on every attempt, latches every finding, and only then blocks on the most severe — no violation is silently dropped. The agent's own key is protected by *isolation*: it lives only in the transport layer and never enters the model's context, so no injection, however encoded, can make the model emit it.
- **The two Longitudinal Constraints** (`CadenceIntegrity` and `CitationClusterIntegrity`, split from the earlier `ManipulationFlag` concept) evaluate persistent observation stores — post timestamps and directional citation edges — that survive restarts, ingest idempotently, and recompute deterministically. Insufficient data is never compliance: below the readiness floor the trace says so explicitly.
- **Undefined beats estimated.** `CitationClusterIntegrity`'s detection thresholds ship *undefined* — not guessed — until real observation grounds them through a ruling amendment. Ungrounded, the constraint structurally cannot fire.

```
CONSTRAINT: CitationClusterIntegrity
Observation readiness : false
Evaluation             : parameters ungrounded (ruling §5 — no amendment has set thresholds yet)
Result                 : NOT EVALUABLE
Action                 : none
```

- **Paused is not frozen.** A longitudinal violation escalates and pauses autonomous posting — but read-only observation continues and explicitly human-authorized sends still pass through every gate. The pause persists across restarts and clears only through explicit human review, which never erases the observation history that produced it.

The policy is in [`moltbook/moltbook.pi`](moltbook/moltbook.pi). Live transport is deliberately unwired — no agent is registered or deployed yet; everything above is enforced and tested against the real resolver.

---

## Using it as an MCP tool

`mcp_server.py` exposes the resolver pipeline as a single MCP tool, `check_governance`, so an agent can check whether a state *would* violate policy before acting, instead of only finding out after the fact from the cron governance watcher.

```bash
python mcp_server.py
```

Wire it into an MCP client (e.g. Claude Code) with a stdio transport pointing at this file. The tool accepts either a native `.pi` policy or a `.rift` program (compiled to Pi Script automatically first):

```python
check_governance(
    source=open("examples/tasks.pi").read(),
    state={"trigger_type": "event", "entity": "TaskAgent", "entity_state": {...}},
    source_type="pi",       # or "rift"
)
```

Pass `persist=True` with a `state_path` to make a system's governance durable across calls: prior `violation_counts` are loaded and carried forward, the updated state is written back atomically, and a trace file is saved to a sibling `traces/` directory on violation. Concurrent callers hitting the same `state_path` are protected by real cross-process file locking (`filelock`), not just an in-process one — the MCP server runs as a separate OS process per client.

```bash
python dashboard.py
```

`dashboard.py` is a small Starlette web UI for browsing what `persist=True` accumulates — it scans for `state.json` files and their sibling `traces/` directories and serves a system list, per-system trace listing, and RESOLUTION TRACE rendering in the browser. No storage migration: it reads the same flat-file convention `log_session.py` and `check_governance(persist=True)` already write.

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
| M6 — Publish (paper + public playground) | ✅ Complete — ConsistencyGuard activated, Jupyter playground live |
| Pi Script v0.2 — Rulings 9.4–9.9 (bidirectional maps, cross-domain inheritance, violation counters, arbiter mandatory, semantic map matching, standing bound rule) | ✅ Complete |
| MCP server, governance dashboard, persistence/write-queue | ✅ Complete |
| Rift v0.2 — Rulings 3.1 + 3.2 (semantic declaration matching, known-values accumulation via `RiftSession`) | ✅ Complete — 71/71 Rift tests |
| M7 — Moltbook governed-agent deployment | 🔄 In progress — ✅ CredentialIntegrity · ✅ LinkRestriction · ✅ IdentityIntegrity v1 · ✅ CadenceIntegrity · ✅ CitationClusterIntegrity (ManipulationFlag was split into these two; §5 thresholds await the grounding amendment) |

**405 tests passing + 6 xfailed** (deliberate known-gap pins) across parser, validator, trace builder, resolver, Rift pipeline (v0.1 + v0.2), MCP server, dashboard, the v0.2 rulings, and the M7 Moltbook constraints (key isolation, pre-send gate, link provenance, identity consistency, posting-cadence integrity, citation-cluster integrity).

---

## Structure

```
continuum/
├── docs/
│   ├── pi_script_v01_draft3.md       # Pi Script v0.1 grammar specification (Draft 4)
│   ├── pi_script_v02_draft5.md       # Pi Script v0.2 rulings spec — 9.4 through 9.9
│   ├── m6_paper_draft1.md            # M6 publication draft — M5 findings
│   ├── continuum_layer_boundaries.md # Layer boundary reference — what belongs where
│   ├── rift_v02_ruling_3_1_semantic_declaration_matching.md   # Rift Ruling 3.1 — two-tier matcher spec
│   ├── rift_v02_semantic_matching_note.md                     # Ruling 3.1 implementation note
│   ├── rift_v02_ruling_3_2_known_values_accumulation.md       # Rift Ruling 3.2 — session/accumulation spec
│   ├── rift_v02_known_values_accumulation_note.md             # Ruling 3.2 implementation note
│   ├── m7_credential_integrity_ruling.md                      # M7 ruling — key isolation + pre-send gate
│   ├── m7_link_restriction_ruling.md                          # M7 ruling — link provenance
│   ├── m7_identity_integrity_ruling.md                        # M7 ruling — within-session identity consistency
│   ├── m7_identity_integrity_ruling_addendum_1.md             # Addendum 1 — external-review fixes (A1–A6)
│   ├── m7_cadence_integrity_ruling.md                         # M7 ruling — posting-cadence integrity (longitudinal)
│   └── m7_citation_cluster_integrity_ruling.md                # M7 ruling — citation-cluster integrity (longitudinal)
├── es/
│   ├── es_governance.pi              # Pi Script policy for Elasticsearch governance
│   ├── es_adapter.py                 # State adapter — queries ES, writes state.json
│   └── baseline.json                 # Committed mapping hash — schema governance source of truth
├── examples/
│   ├── tasks.pi                      # Working example — AI task agent governance
│   ├── test_happy.pi                 # Happy path file exercising all rule forms
│   └── quantization_governance.pi    # GPU/ML quantization domain example (Ruling 9.9 bound_rule)
├── m5/
│   ├── dogfood.pi                    # M5 dogfood policy — governs Continuum AI assistant usage
│   ├── ir.json                       # Compiled IR for dogfood.pi
│   ├── state.json                    # Session state snapshot — update before each daily run
│   └── traces/                       # RESOLUTION TRACE logs — M5 violation record
├── moltbook/
│   ├── moltbook.pi                   # M7 policy — session constraints + the longitudinal agent profile
│   ├── client.py                     # Governed client — key isolation, scan-all pre-send gate, pause checks
│   ├── detector.py                   # Mechanical detectors — credentials, link provenance, identity drift
│   ├── cadence.py                    # CadenceIntegrity observation store + governance gate
│   ├── citation.py                   # CitationClusterIntegrity edge store + governance gate
│   └── link_allowlist.json           # Human-owned link allowlist — editable only via commit/PR
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
│   ├── matcher.py                    # Two-tier declaration matcher (Ruling 3.1)
│   ├── session.py                    # Declaration-resolution runtime + known-values accumulation (Ruling 3.2)
│   ├── shelved_projects.rift         # Canonical test program
│   └── shelved_projects.pi           # Generated Pi Script output
├── rift_design_note_draft2.md        # Rift (Layer 3) design — v0.1 intent layer spec
├── tests/
│   ├── test_parser.py                # M1 + M3 — 9 tests
│   ├── test_validator.py             # M2 + v0.2 rulings — 45 tests
│   ├── test_trace.py                 # trace.py — 31 tests
│   ├── test_resolver.py              # M4 + v0.2 rulings — 98 tests
│   ├── test_rift.py                  # Rift v0.1 + v0.2 — 71 tests
│   ├── test_mcp_server.py            # check_governance tool — 10 tests
│   ├── test_dashboard.py             # dashboard UI — 9 tests
│   ├── test_quantization_governance_example.py  # Ruling 9.9 example — 5 tests
│   ├── test_moltbook_credential_integrity.py    # M7 key isolation + pre-send gate — 20 tests
│   ├── test_moltbook_link_restriction.py        # M7 link provenance — 20 tests
│   ├── test_moltbook_identity_integrity.py      # M7 identity consistency + addendum — 32 tests
│   ├── test_moltbook_cadence_integrity.py       # M7 cadence store + pause semantics — 25 tests
│   └── test_moltbook_citation_cluster_integrity.py  # M7 citation graph + grounding gate — 36 tests
├── quickstart.py                     # One-command demo — validate, resolve, print the trace
├── compile_pi.py                     # Helper — validate a .pi file and write its IR to JSON
├── log_session.py                    # M5 daily runner — resolves dogfood.pi against current state
├── pi_monitor.py                     # Device-health monitor template — NOT the deployed watcher
│                                     #   (live monitoring runs as a GitHub Actions cron workflow)
├── mcp_server.py                     # MCP server exposing check_governance as an agent-callable tool
├── dashboard.py                      # Starlette web UI for browsing persisted state + traces
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

- ~~Bidirectional map blocks~~ — shipped, Pi Script v0.2 Ruling 9.4
- ~~Semantic similarity map matching~~ — shipped, Pi Script v0.2 Ruling 9.8
- ~~Cross-domain constraint inheritance~~ — shipped, Pi Script v0.2 Ruling 9.5
- ~~Natural language constraint authoring — NLP-based declaration matching~~ — shipped, Rift v0.2 Rulings 3.1 + 3.2
- Adaptive constraints that evolve within bounds (Pi Script v0.3)
- Rift Semantic Layer — `agent`, `state`, `behavior evolves` constructs (Rift v0.3)
- Rift dynamic constraint generation — runtime re-evaluation without recompile (blocked on the multi-phase resolver, a Layer 2 prerequisite that doesn't exist yet)
- Rift Execution Layer — `@gpu`, `@quantum`, `@realtime` annotations (Rift v0.3)
- Persistence of accumulated known values across sessions (deferred by Ruling 3.2 §3.2.3 — a future ruling when a use case demands it)
- Cross-layer integration of any kind (v0.4+ per `docs/continuum_layer_boundaries.md`)

---

*Continuum — Pi Script v0.2 + Rift v0.2 + the M7 Moltbook constraint set — July 2026*
