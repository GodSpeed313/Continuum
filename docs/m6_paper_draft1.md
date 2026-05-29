# Pi Script v0.1 — M6 Publication
## A Governance Coherence Layer for AI Systems
### Findings from M5 Dogfooding · May 2026

**Author:** GodSpeed313  
**Stack:** Continuum (Pi Script · Rift · Execution Layer)  
**Status:** Draft 1 — M6 publication candidate  
**Repository:** https://github.com/GodSpeed313/Continuum

---

## Abstract

Pi Script is a domain-specific language for declaring what must remain true about an
AI system's behavior over time. Unlike output filters that inspect single responses,
or rule engines that require hand-authored policies with no intent layer, Pi Script
governs state continuity — evaluating whether a system's observable behavior has
drifted from declared constraints across a session, a day, or a month.

This paper documents findings from M5: a 23-day active dogfooding run in which Pi Script
governed two independent production systems simultaneously — its own development workflow
(Continuum) and a live AI music production tool deployed to end users (Melody Maestro).
The two systems share no domain, no codebase, and no operator. The same resolver, the
same trace format, and the same violation semantics ran across both. The dogfood
captured real violations, not manufactured test cases.

The paper is honest about what v0.1 does not do. Scope discipline is the contribution.

---

## 1. The Problem Pi Script Addresses

AI governance tooling as of May 2026 addresses three distinct problems with three
distinct approaches:

**Output filters** (Guardrails AI, NeMo Guardrails) inspect individual model outputs
at inference time. They are fast and practical. They do not address drift — the pattern
of behavior changing gradually over a session or across sessions without any single
output triggering a violation.

**Rule engines** (Open Policy Agent, Rego) provide deterministic policy enforcement
against structured data. They are powerful and battle-tested. They require policies
to be hand-authored in a formal language. There is no mechanism to express or capture
human intent — policies are written by engineers, not the people whose intent they
are meant to enforce.

**Agent governance toolkits** (Microsoft Agent Governance Toolkit, April 2026) provide
sub-millisecond enforcement against known agentic risk patterns. They are comprehensive
within their scope. They have no intent layer — rules are authored manually, and there
is no mechanism for a user to describe what they want their system to do in natural
language and have that declaration become an enforced policy.

The gap none of these tools closes: **the full loop between human intent, policy
generation, runtime monitoring, and human-reviewed violation capture in a single
coherent architecture.**

Pi Script closes two of these four steps. Rift (Layer 3, v0.1 shipped) closes the third.
Human review through the Continuum loop closes the fourth. This paper documents what
the first two steps look like in production, and reports the completion of the third.

---

## 2. Architecture Overview

Continuum is a three-layer governance stack:

| Layer | Name | Responsibility |
|---|---|---|
| Layer 3 | Rift | Intent and system design — "What should this system be?" |
| Layer 2 | Pi Script | Governance and coherence — "Is it still what it should be?" |
| Layer 1 | Execution | Classical / GPU / Quantum backends |

Pi Script v0.1 is Layer 2. Rift v0.1 (Layer 3, Intent Layer) shipped alongside
this publication. Layer 1 is out of scope for v0.1.

The full Continuum loop:

```
User declares intent in natural language         [Rift — Layer 3]
        ↓
Rift generates Pi Script constraint set          [Rift → Pi Script]
        ↓
Pi Script monitors system behavior               [Pi Script — Layer 2]
        ↓
Violations produce auditable RESOLUTION TRACEs   [Pi Script — Layer 2]
        ↓
Humans review traces and decide what to do       [Human review]
        ↓
Decision feeds back as a new user declaration    [Rift — Layer 3]
```

v0.1 delivers steps 1–4. Rift v0.1 ships the Intent Layer (grammar, parser,
validator, compiler — 33 tests, full loop proven end-to-end). Step 6 (human
review loop) is operational — every violation in M5 was reviewed by a human,
and in two cases directly influenced subsequent development decisions.

---

## 3. Design Decisions: What Was Excluded and Why

The v0.1 scope is narrow by design. Every excluded feature represents a deliberate
tradeoff between correctness and capability.

**The core design principle:** If a constraint cannot be formalized into something
measurable, it does not belong in the language. Vague language is a compile error,
not a feature.

This is not a limitation. It is the contribution.

**Excluded in v0.1:**

| Feature | Reason | Target |
|---|---|---|
| Natural language constraint authoring | Rift's domain — Layer 3 | v0.5 |
| Adaptive constraints | Requires full multi-phase resolver | v0.3 |
| Cross-domain constraint inheritance | Interaction semantics not yet specified | v0.2 |
| Bidirectional map blocks | v0.2 | v0.2 |
| Semantic similarity map matching | Requires inference engine | v0.2 |
| Multiple arbiters per domain | v0.3 | v0.3 |
| Rift Semantic Layer — `agent`, `state`, `behavior evolves` | Intent Layer shipped; Semantic Layer is next | Rift v0.2 |
| Rift dynamic constraint generation | Requires full multi-phase resolver | Rift v0.2 |

**Why scope discipline is the contribution:** A governance layer that silently
accepts vague constraints provides false safety. A constraint that "should try to
maintain tone" cannot be evaluated, cannot be violated, and cannot produce a
meaningful trace. The resolver would always report SATISFIED — not because the
system is governed, but because the constraint says nothing. Pi Script v0.1
rejects this at compile time.

Every constraint in a valid Pi Script program is measurable. Every violation is
detectable. Every trace is human-auditable. If those three properties hold, the
governance layer is honest.

---

## 4. M5 Findings: Real Violations in Production

M5 ran across two independent production systems simultaneously — one governed
manually by a single developer (Continuum), one running automated checks every
12 hours against a live deployed application (Melody Maestro). The two systems
share no domain, no codebase, and no operator. This is the strongest available
evidence that Pi Script is a domain-independent governance layer, not a tool
built for one specific use case.

### 4.1 Continuum Internal Dogfood

The `m5/dogfood.pi` policy governed the Continuum development workflow — specifically,
AI assistant usage during Pi Script design sessions. Four constraints were enforced:

- **SpecAlignment** (critical): `spec_version must equal 3` — no working on outdated spec
- **ScopeGuard** (critical): `scope_flag must equal false` — no scope drift during sessions
- **TopicCompliance** (medium): `session_topic` must match declared valid set
- **ConsistencyGuard** (high): contradiction detection — dormant in M5, activates in M6

**Violation 1 — ScopeGuard** · `2026-05-17T22:15:11Z`

`scope_flag` was `True` when expected `False`. A development session drifted outside
the declared project scope. Action: `flag + escalate`. The trace was human-reviewed
and the session was redirected. This is the governance layer doing exactly what it
was designed to do: catching real behavior drift, not a manufactured test.

**Violation 2 — SpecAlignment** · `2026-05-17T23:50:34Z`

`spec_version` was `2` when expected `3`. A session referenced the pre-Draft 3 spec.
Action: `flag + escalate`. The trace confirmed that working against a superseded spec
version produces detectable, traceable behavior — not just a note in a TODO file.

### 4.2 Production Deployment: Melody Maestro

During M5, Pi Script was also deployed to govern a live, public-facing application:
[Melody Maestro](https://melody-maestro-a8qfdpv46bjrtbakbd39gh.streamlit.app) — an
AI music production tool for FL Studio producers. The governance policy ran every 12
hours via GitHub Actions, evaluating three constraints against the state of the
production repository.

This was not a planned M5 deployment. It emerged from applying Pi Script to a real
project that needed governance. The violations it produced are M5 evidence from a
completely different domain — not AI assistant usage, but software repository coherence.

**59 runs over 30 days. 4+ distinct violations captured.**

Key violations:

- **SchemaIntegrity** — the repo's Prisma scaffold was stripped during a clean-slate
  commit, leaving a constraint that unconditionally required `migration_exists == true`.
  The resolver caught it, froze the system state, and escalated. The root cause was
  a design flaw in the constraint itself — an unconditional equality rule where a
  conditional rule was the correct design. The violation exposed an imprecise policy,
  not just a broken codebase. Human review redesigned the constraint.

- **ReadmeCoherence** — a Python hotfix committed without a corresponding README update.
  The constraint caught it within 12 hours. Under normal development pressure, a
  single-line bug fix would never trigger a documentation review. The resolver made
  it automatic.

The Melody Maestro violations are qualitatively different from the internal dogfood
violations. They emerged from real development workflow under deadline pressure — the
exact conditions where governance needs to be automatic, not voluntary.

### 4.3 What M5 Revealed

**The resolver does not know what it governs.** The same resolver ran against an AI
assistant usage policy and a software repository coherence policy. The domain is
declared in the IR. The resolver evaluates constraints. Pi Script is not a tool for
software governance or AI governance specifically — it is a governance coherence layer
for any domain where intent can be expressed as measurable constraints.

**Violations are more informative than passes.** The SchemaIntegrity violation revealed
a constraint design error that no unit test caught. SATISFIED traces confirm compliance.
VIOLATED traces reveal intent that was imprecisely specified. Both are valuable. Only
one is uncomfortable.

**ConsistencyGuard activated in M6.** In M5, the contradiction detection constraint
satisfied trivially because `response_history` was not logged — manual logging overhead
was too high for daily runs. M6 added structured history logging to `log_session.py`
and produced the first `contradiction_rule` violation on record: two responses logged
on the same topic, the second containing a mapped trigger keyword, fired ConsistencyGuard
at high priority with action `flag + escalate`. Trace saved to `m5/traces/2026-05-29_163949.txt`.

---

## 5. The Architectural Gap

The gap this architecture addresses is not a feature gap. It is an architectural
philosophy gap.

| Tool | Intent Layer | Policy Generation | Runtime Monitoring | Human Review Loop |
|---|---|---|---|---|
| OPA / Rego | None — manual | Manual | ✅ | None |
| Microsoft AGT (April 2026) | None — manual | Manual | ✅ | Approval workflow (bolt-on) |
| Guardrails AI | None | None | Output only | None |
| **Continuum** | **✅ Rift v0.1** | **✅ Rift → Pi Script** | **✅ Pi Script** | **✅ Continuum loop** |

The specific gap in the approval workflow approach: humans review behavior.
In Continuum, humans review **divergence from their own stated intent**. The human
is not approving a flag. They are completing a cycle that began with their own
declaration. That is accountability, not just oversight.

### 5.1 Agentic AI Governance

Pi Script applies directly to agentic AI pipelines. The `ContinuumSession` entity
in `m5/dogfood.pi` is an AI agent — it has observable state fields, constraints
governing those fields over time, and a resolver that evaluates behavior across
sessions. The same architecture that governs a software repository governs an agent
session. The domain boundary is the only difference.

As multi-agent pipelines become standard infrastructure, the need for a governance
layer that watches state over time — not just at inference — becomes critical
infrastructure. Pi Script is positioned as that layer.

### 5.2 Cross-System Coherence

Every existing governance tool governs one system at a time. OPA governs one pipeline.
Microsoft's toolkit governs one agent runtime. Legitify governs one repository.

Cross-domain constraint inheritance (v0.2) will govern decisions across interconnected
systems — ensuring that a policy change in one repository does not violate the intent
declared for a connected system. No existing tool does this. This is documented here
as a named v0.2 design goal and a timestamped original claim.

### 5.3 Governance Accessible to Indie Developers

The EU AI Act's General Purpose AI documentation requirements take effect August 2026.
Every existing compliance tool is designed for enterprises with legal and compliance
teams. Independent developers, solo builders, and small teams have no accessible path.

Rift's intent-native model — describe what you want your system to do, receive an
enforced policy — addresses this directly. The compliance posture is a byproduct of
expressing intent, not a separate documentation exercise. This is Rift's most
immediate practical application.

---

## 6. M6 Additions

M6 activates what M5 left dormant and opens what M5 gated.

**`response_history` logging shipped.** Defined in the spec (`sequence(text)`) but
excluded from the M5 state snapshot due to logging overhead. `log_session.py` now
accepts `--response TEXT` to append structured entries to `response_history` in
`m5/state.json` before resolving. History persists across sessions. `--clear-history`
resets it for a clean run.

**ConsistencyGuard activated.** With `response_history` populated, contradiction
detection is now a live constraint. The first `contradiction_rule` violation is on
record: `m5/traces/2026-05-29_163949.txt`. Two responses on the same topic; the
second containing trigger keyword `constraint` against a prior response —
ConsistencyGuard fired at high priority, action `flag + escalate`.

**Rift v0.1 shipped.** The Rift Intent Layer is complete — grammar (`rift/rift_v01.lark`),
parser, semantic validator, and compiler. The compiler takes a validated Rift IR and emits
a Pi Script `.pi` file that passes the Pi Script validator and resolves clean. 33 tests.
Full loop proven: `.rift → parse → validate → compile → .pi → Pi Script validator → resolver`.

**Public playground shipped.** `playground.ipynb` — a Jupyter notebook that walks through
the full Continuum stack interactively: write a policy, validate it, run the resolver, trigger
a violation, write a Rift program, compile it to Pi Script, and resolve it. All cells execute
clean. A non-expert can run it and read the output without reading this paper first.

---

## 7. What This Paper Does Not Claim

This paper does not claim that Pi Script solves AI safety.

It does not claim that governed systems are safe systems — a system that perfectly
satisfies every declared constraint can still behave in ways its designer did not
anticipate, if the constraints were imprecisely specified. The SchemaIntegrity
violation in M5 is evidence of this.

It does not claim the Continuum stack is complete. Two of six loop steps are roadmap.

**What this paper claims:**

1. A governance layer that rejects unmeasurable constraints at compile time is more
   honest than one that accepts them silently.

2. Violation traces are structured, human-readable records of intent vs. behavior
   divergence. They are a publishable format. The traces in `m5/traces/` and in
   `GodSpeed313/Melody-Maestro/governance/traces/` are not logs — they are evidence.

3. No existing tool closes the loop between intent authoring, policy generation,
   runtime monitoring, and human review in a single coherent architecture. Continuum
   is designed to close it. Two steps are working in production as of this publication.

The M6 paper is the flag. The M5 traces are the evidence. The claims are timestamped
here because the window to name this architecture is open and the market is moving.

---

## Appendix A: Violation Trace Format

The RESOLUTION TRACE is part of the language specification. A runtime that does not
produce compliant traces is not a valid Pi Script runtime.

Gate condition: a non-expert must be able to read a RESOLUTION TRACE and understand
why the system acted. If they cannot, the trace format is broken — not the person.

**Sample — M5 ScopeGuard violation (2026-05-17):**

```
RESOLUTION TRACE
════════════════════════════════════════════════════════
Timestamp    : 2026-05-17T22:15:11.178Z
Domain       : ai_usage_governance
Entity       : ContinuumSession [session_id: session-2026-05-17]
Trigger      : event — state snapshot received for ContinuumSession
════════════════════════════════════════════════════════
├── CONSTRAINT: ScopeGuard [priority: critical]
│   ├── Rule kind  : equality_rule
│   ├── Evaluation : scope_flag is True, expected False
│   ├── ✗ VIOLATION DETECTED
│   └── Action     : flag + escalate
└── RESOLUTION
    ├── Action       : flag + escalate
    ├── System state : escalated
    └── The rule 'ScopeGuard' was broken: scope_flag is True, expected False.
        This has been logged and sent to a human reviewer.
```

**Sample — Melody Maestro SchemaIntegrity violation (2026-05-20):**

```
[I FAILED] · GodSpeed313/Melody-Maestro · 2026-05-20T15:40:28Z
System state: frozen  |  Final action: freeze + escalate

🔴 SchemaIntegrity [critical] — migration_exists is False, expected True
```

Human review finding: the constraint was an unconditional equality rule. The correct
design was a conditional rule — only check `migration_exists` when `schema_changed`
is true. The violation revealed an imprecise constraint, not a broken codebase.
The constraint was redesigned. The system unfroze.

---

## Appendix B: Milestone Status

| Milestone | Status |
|---|---|
| M1 — Grammar specification, Draft 4 | ✅ Complete |
| M2 — Semantic validator — 12/12 tests | ✅ Complete |
| M3 — Parser — 9/9 tests | ✅ Complete |
| M4 — Resolver core — 89/89 tests | ✅ Complete |
| M5 — Dogfood — 6+ violations across two independent systems, 23-day active run | ✅ Gate met |
| Rift v0.1 — Intent Layer — 33/33 tests, full loop proven | ✅ Complete |
| M6 — Publish (this paper) + public playground | ✅ Complete |

---

*Pi Script v0.1 · Continuum Stack · May 2026*  
*GodSpeed313 · https://github.com/GodSpeed313/Continuum*
