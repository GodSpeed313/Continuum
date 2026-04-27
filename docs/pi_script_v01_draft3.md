# Pi Script v0.1 — Grammar Specification
**AI Governance Domain — Draft 3**
*A language for defining what must remain true while everything else changes.*
*April 2026*

---

## Draft 3 — Changes from Draft 2

- **Section 2.1:** `audit_interval` scope clarified — domain-level only, not per-constraint.
- **Section 2.3:** `decay_check` added as a `constraint_decl` field. Removed from enforce block.
- **Section 2.5:** enforce block canonicalized to Shape B. Shape A retired. Exactly two fields.
- **Section 2.4:** map union behavior specified for multiple map blocks sharing a target.
- **Section IX:** Three discrepancy rulings added alongside Q1/Q2/Q3 resolutions.
- **Section X:** Resolver architecture updated to reflect all rulings.
- **Section XI:** Document status updated to Draft 3.

---

## I. Overview

Pi Script is the governance and coherence layer of the Continuum stack. It does not tell systems how to act. It defines what must remain true while systems change.

This document specifies Pi Script v0.1 — the minimal viable grammar for the AI Governance domain. Scope is deliberately narrow. Every construct included has a direct, demonstrable use case. Nothing speculative is included.

**Design principle:** If a construct cannot be formalized into a measurable constraint, it does not belong in v0.1. Vague language is a compile error, not a feature.

### 1.1 What Pi Script Does

| Pi Script Does | Pi Script Does Not Do |
|---|---|
| Define entities and their measurable states | Execute tasks or perform actions |
| Declare constraints that must remain true | Replace Python, Rust, or any execution language |
| Monitor system state against constraints | Understand abstract concepts natively |
| Flag, escalate, or freeze on violation | Guarantee execution performance |
| Produce auditable resolution traces | Self-modify its own constraint rules |
| Map human language to machine states | Infer meaning without explicit map blocks |

### 1.2 Where Pi Script Sits

| Layer | Name | Responsibility |
|---|---|---|
| Layer 3 | RIFT | Intent & System Design — *What should this system be?* |
| Layer 2 | PI SCRIPT | Governance & Coherence — *Is it still what it should be?* |
| Layer 1 | Execution Layer | Classical / GPU / Quantum backends |

---

## II. Core Language Constructs

Pi Script v0.1 has six primitive constructs. Every valid Pi Script program is composed exclusively of these. No others exist in v0.1.

### 2.1 domain

Every Pi Script file begins with a domain declaration. The domain scopes all entities, constraints, and maps within the file. Domains do not interact in v0.1 — cross-domain constraint inheritance is a v0.2 feature.

> **Draft 3 change:** `audit_interval` is a domain-level field only. It controls how often the resolver runs a full domain coherence pass across all constraints. It is not a per-constraint setting. Per-constraint re-evaluation cadence is controlled by `decay_check` on `constraint_decl` (Section 2.3).

```
domain governance {
    audit_interval: 24 hours  // domain-wide coherence pass cadence
    tiebreaker: timestamp_asc
}
```

| Field | Description |
|---|---|
| domain name | identifier (snake_case) — Required. Must be first line. |
| audit_interval | Duration. How often the resolver runs a full domain coherence pass. Domain-wide. One value. |
| tiebreaker | Tie-breaking rule when constraint evaluations produce equal priority. `timestamp_asc` or `timestamp_desc`. |

### 2.2 entity

An entity is the subject of governance. It has a name and a set of named states. States have types. In v0.1, states are observable — they are read by the monitor, never written by Pi Script directly.

```
entity LLMAgent {
    state response_history : sequence(text)
    state policy_version   : integer
    state tone_score       : range(0.0 .. 1.0)
    state session_id       : identifier
}
```

| Type | Description |
|---|---|
| `text` | Unstructured string. Requires map block to be constrained. |
| `integer` | Whole number. Comparable directly. |
| `range(min .. max)` | Decimal value within bounds. Violations outside bounds. |
| `sequence(type)` | Ordered list of typed values. Constrainable by window. |
| `identifier` | Opaque unique string. Equality only — no comparison. |
| `boolean` | True or false. Direct conditional use. |

### 2.3 constraint

A constraint is a rule that must remain true about an entity's state. Constraints are the core primitive of Pi Script. Every other construct exists to support constraint definition and enforcement.

> **Draft 3 change:** `decay_check` is now a field on `constraint_decl`, not on `enforce`. It controls the cold-path fallback re-evaluation interval for this constraint specifically. It is independent of `audit_interval`. A high-sensitivity constraint may have `decay_check: 1 hour` while `audit_interval` is `24 hours`.

```
constraint NeverContradictPolicy {
    monitor    : LLMAgent.response_history
    against    : company_policy.current_version
    window     : 30 days
    rule       : if new_response contradicts prior_response(same_topic)
                 then require flag_revision before responding
    priority   : critical
    on_violation: flag + escalate
    decay_check: every 24 hours  // cold-path fallback for this constraint
}
```

| Field | Description |
|---|---|
| monitor | The entity state being watched. Format: `entity.state` |
| against | External reference state to compare against. Optional. |
| window | Time window for historical evaluation. Format: `N (days\|hours\|minutes)` |
| rule | The condition that must hold. Uses if/then/require syntax. |
| priority | Determines resolution order when constraints conflict. |
| on_violation | Action taken when rule is broken. See violation actions table. |
| decay_check | Optional. Cold-path fallback re-evaluation interval for this constraint. Fires only when no new state has arrived within the interval. Independent of `audit_interval`. |

**Priority levels:**

| Priority | Meaning |
|---|---|
| `critical` | Never violated. Overrides all lower priorities. Freeze on conflict. |
| `high` | Violated only if critical constraint requires it. Escalate on conflict. |
| `medium` | Standard enforcement. Warn on conflict. |
| `low` | Advisory only. Log on conflict. No automated action. |

**Violation actions:**

| Action | Effect |
|---|---|
| `flag` | Log violation with full RESOLUTION TRACE. No system halt. |
| `warn` | Surface warning to operator interface. System continues. |
| `escalate` | Route to human review queue with trace attached. |
| `freeze` | Halt entity output until human review clears violation. |
| `rollback` | Revert entity state to last verified snapshot. |
| `flag + escalate` | Compound: both actions execute simultaneously. |
| `freeze + rollback` | Compound: halt and revert simultaneously. |

### 2.4 map

A map block translates human-language expressions into measurable machine states. Map blocks make human meaning a first-class governance concern.

> **Draft 3 change:** Multiple map blocks may share the same `target` field. The resolver unions the `maps_to` values across all matching map blocks to form the complete valid membership set for a `membership_rule`. This is the only non-obvious behavior of the implicit map-to-constraint link.

```
map StatusMap {
    target:   Sensor.status
    maps_to:  "ok"
    triggers: ["nominal", "good", "running"]
}

map StatusMapWarn {
    target:   Sensor.status  // same target — values are unioned by resolver
    maps_to:  "warn"
    triggers: ["degraded", "slow", regex: "err.*"]
}
```

Maps are unidirectional in v0.1: human text → machine state. Bidirectional maps are v0.2.

The link between a map block and a constraint is implicit. A `membership_rule` matches all map blocks whose `target` field equals the rule's `state_ref`. No `uses_map` declaration exists in v0.1.

### 2.5 enforce

An enforce block activates a set of constraints against a named entity. Constraints are inert until enforced. This separation allows constraints to be defined once and enforced selectively.

> **Draft 3 change:** Shape B is the canonical v0.1 enforce syntax. Shape A (with `on`, `since`, `decay_check` fields) is retired and produces a compile error. `enforce` has exactly two fields: `entity` and `constraints`. No exceptions for v0.1. `decay_check` has moved to `constraint_decl` (Section 2.3).

```
enforce {
    entity:      CustomerServiceAgent
    constraints: [NeverContradictPolicy, MaintainProfessionalTone, PolicyVersionCurrent]
}
```

| Field | Description |
|---|---|
| entity | The entity name constraints are activated against. Required. |
| constraints | List of constraint names to enforce on this entity. Required. At least one. |

### 2.6 arbiter (meta-constraint)

The arbiter block defines what kinds of system evolution are acceptable. Arbiter definitions are immutable at runtime. They can only be changed through versioned spec updates, never through runtime proposals.

```
arbiter ContinuumArbiter {
    acceptable_evolution: [
        weight_adjustment within bounds(minus 15%, plus 15%),
        threshold_shift within bounds(minus 10%, plus 10%),
        priority_reorder if no_critical_constraints_affected
    ]
    never_acceptable: [
        constraint_removal,
        constraint_inversion,
        priority_escalation_above(critical)
    ]
    requires_human_review: [
        new_constraint_introduction,
        domain_boundary_expansion,
        any_change_affecting(safety_critical)
    ]
    acceptance_monitor: flag if acceptance_rate > baseline(plus 20%) over 7 days
}
```

---

## III. Resolution Trace Format

Every constraint evaluation produces a RESOLUTION TRACE. This is the Semantic Debugger's core output. It is machine-generated and human-auditable. The trace is not optional — it is part of the language spec. A runtime that does not produce compliant traces is not a valid Pi Script runtime.

**Gate condition:** A non-expert must be able to read a RESOLUTION TRACE and understand why the system acted. If they cannot, the trace format is broken, not the person.

### 3.1 Trace Fields Reference

| Field | Description |
|---|---|
| Timestamp | Required. ISO 8601. Millisecond precision. |
| Domain | Required. Must match domain declaration. |
| Entity | Required. Name + session_id if available. |
| Triggered by | Required. What state change caused evaluation. |
| CONSTRAINT blocks | One block per active constraint. All must appear. |
| Map match | If a map block triggered, show the match explicitly. |
| Evaluation | The rule evaluation result. Show prior and new states. |
| CONFLICT RESOLUTION | Required when 2+ constraints active. Show priority logic. |
| RESOLUTION | Required always. Action + rationale + human text + state. |
| Human text | Plain English. No jargon. Non-expert readable. Gate condition field. |

---

## IV. Complete Working Example

The following is a complete, valid Pi Script v0.1 program. It reflects all Draft 3 rulings: Shape B enforce, `decay_check` on `constraint_decl`, `audit_interval` on domain.

```
domain governance {
    audit_interval: 24 hours
    tiebreaker: timestamp_asc
}

entity CustomerServiceAgent {
    state response_history  : sequence(text)
    state policy_version    : integer
    state tone_score        : range(0.0 .. 1.0)
    state escalation_count  : integer
    state session_id        : identifier
}

constraint NeverContradictPolicy {
    monitor    : CustomerServiceAgent.response_history
    against    : company_policy.current_version
    window     : 30 days
    rule       : if new_response contradicts prior_response(same_topic)
                 then require flag_revision before responding
    priority   : critical
    on_violation: flag + escalate
    decay_check: every 24 hours
}

constraint MaintainProfessionalTone {
    monitor    : CustomerServiceAgent.tone_score
    rule       : tone_score must remain within range(0.4 .. 1.0)
    window     : session
    priority   : high
    on_violation: warn after 2 violations, freeze after 4 violations
    decay_check: every 6 hours
}

constraint PolicyVersionCurrent {
    monitor    : CustomerServiceAgent.policy_version
    against    : company_policy.version_number
    rule       : policy_version must equal company_policy.version_number
    priority   : critical
    on_violation: freeze + escalate
    decay_check: every 1 hour
}

enforce {
    entity:      CustomerServiceAgent
    constraints: [NeverContradictPolicy, MaintainProfessionalTone, PolicyVersionCurrent]
}

arbiter ContinuumArbiter {
    acceptable_evolution:  ["weight_adjustment within bounds(minus 15%, plus 15%)"]
    never_acceptable:      ["constraint_removal", "constraint_inversion"]
    requires_human_review: ["new_constraint_introduction"]
    acceptance_monitor: {
        threshold: 0.8
        window:    7 days
    }
}
```

---

## V. Formal Grammar Rules

### 5.1 File Structure Rules

| Rule | Enforcement |
|---|---|
| domain declaration must be first | Compile error if absent or misplaced |
| One domain per file | Compile error if multiple domain declarations found |
| All entity references must be declared | Compile error if constraint references undeclared entity |
| All constraint references must be declared | Compile error if enforce references undeclared constraint |
| enforce has exactly two fields: entity, constraints | Compile error if any other field present (Shape A retired) |
| decay_check belongs on constraint_decl, not enforce | Compile error if decay_check appears in enforce block |
| At least one enforce block required | Warning if no enforce blocks present |
| Arbiter block optional in v0.1 | Warning if absent; required in v0.2+ |

### 5.2 Naming Rules

| Construct | Naming Rule |
|---|---|
| domain | snake_case. Lowercase. No spaces. |
| entity | PascalCase. Must be unique within domain. |
| state | snake_case. Must be unique within entity. |
| constraint | PascalCase. Must be unique within domain. |
| map trigger | Quoted string. Case-insensitive match at runtime. |
| arbiter | PascalCase. Only one arbiter per domain in v0.1. |

### 5.3 Constraint Rule Syntax

Only the following rule forms are valid in v0.1:

```
// Form 1: Direct comparison
rule : state_name must remain within range(min .. max)

// Form 2: Equality
rule : state_name must equal reference_value

// Form 3: Threshold
rule : state_name must remain below N within window

// Form 4: Conditional
rule : if condition then require action before outcome

// Form 5: Contradiction detection
rule : if new_response contradicts prior_response(same_topic)
       then require flag_revision before responding

// NOT valid in v0.1:
rule : system should try to maintain tone  // too vague — compile error
rule : agent must feel helpful             // unmeasurable — compile error
```

---

## VI. Failure Modes & Safe States

Every failure mode has a defined safe state. Pi Script runtimes must implement all of the following. There is no undefined behavior.

| Failure Mode | Detection | Safe State |
|---|---|---|
| All proposals rejected by Arbiter | Stall counter exceeds 10 in 24h | Freeze evolution layer. Surface stall log to operator. |
| Arbiter deadlock | Resolution timeout > 5 seconds | Fail to last known good state. Human review required. |
| Evolution Observer gaming Arbiter | Acceptance rate > baseline + 20% | Freeze evolution layer. Full audit triggered. |
| Constraint drift by proxy | Coherence metric divergence > threshold | Rollback to last verified snapshot. |
| Resolver timeout (Tier 2) | Resolution exceeds time budget | Graceful degradation to last resolved state. |
| Entity state unreadable | Monitor returns null or error | Constraint evaluation suspended. Warning issued. |
| Policy reference unavailable | against target unreachable | Constraint suspended. Critical alert issued. |

---

## VII. Explicitly Out of Scope — v0.1

| Feature | Target Version |
|---|---|
| Adaptive constraints (behavior evolves) | v0.3 |
| Bidirectional map blocks | v0.2 |
| Semantic similarity map matching | v0.2 |
| Cross-domain constraint inheritance | v0.2 |
| uses_map explicit constraint-to-map declaration | Not planned — implicit link is canonical |
| Quantum state types | v1.0 |
| Rift Layer 3 integration (full stack) | v0.4 |
| Multi-arbiter federation | v0.3 |
| Natural language constraint authoring | v0.5 |

---

## VIII. Phase 0 Build Milestones

**Gate condition:** A non-expert reads a RESOLUTION TRACE from a real AI governance scenario and understands why the system acted.

| Milestone | Status |
|---|---|
| M1 — Formalization: Grammar finalized. All v0.1 constructs specified. | ✅ Complete |
| M2 — Semantic Validator: IR extraction, None guards, 12/12 tests passing. | ✅ Complete |
| M3 — Parser: Accepts valid programs. Rejects invalid with human-readable errors. | ⬜ Next |
| M4 — Resolver Core: CSP resolver. Evaluates constraints. Produces RESOLUTION TRACEs. | ⬜ Pending M3 |
| M5 — Dogfood: 30 days. 3+ real violations detected and traced. | ⬜ Pending M4 |
| M6 — Publish: Negative result paper. Public playground. Grammar spec public. | ⬜ Pending M5 |

---

## IX. Open Questions & Discrepancy Rulings — All Resolved

All questions from Draft 1 and all spec/grammar discrepancies identified in Draft 3 review are resolved below. These rulings are binding for implementation.

### 9.1 Draft 1 Open Questions

**Resolution — Q1 — Two simultaneous critical violations: what wins?**

When two or more critical constraints are violated simultaneously, the most restrictive violation action executes. Restrictiveness order: `freeze+rollback > freeze > flag+escalate > escalate > flag > warn`. All active violations are logged as co-active in the RESOLUTION TRACE regardless of which action executes. No violation is silently dropped. The human reviewer sees the full set.

**Resolution — Q2 — How is same_topic determined in contradiction detection?**

`same_topic` means responses that reference the same named state field (`Entity.state`). The resolver matches prior responses by their state field ref, already present in the `contradiction_rule` IR as `"ref"`. No inference required. The response history input to the resolver must include the state field ref touched by each response. The state field ref is the topic key. Response history entry shape: `{ "text": "...", "state_ref": "Entity.state", "timestamp": "ISO8601" }`

**Resolution — Q3 — How does decay_check interact with window?**

Constraint evaluation is event-driven. New state input triggers immediate re-evaluation of the full window. `decay_check` is a fallback heartbeat — it fires only when no new state has arrived within the specified interval. `window` = how much history to evaluate. `decay_check` = how often to check if nothing else triggered it. Two independent axes.

- TRIGGER 1: new state arrives → evaluate immediately
- TRIGGER 2: `decay_check` interval elapsed, no new state → evaluate as heartbeat
- Both → look back across full window → produce RESOLUTION TRACE

### 9.2 Draft 3 Discrepancy Rulings

**Ruling — Discrepancy 1 — audit_interval vs decay_check**

Both constructs exist and are not duplicates. `audit_interval` is a domain-level field set once in the domain block. It controls how often the resolver runs a full domain coherence pass across all constraints. `decay_check` is a per-constraint field on `constraint_decl`. It controls the cold-path fallback re-evaluation interval for that specific constraint only. They are independent. A constraint's `decay_check` can fire more or less frequently than `audit_interval`. Both are valid v0.1 constructs.

**Ruling — Discrepancy 2 — enforce block structure**

Shape B is the canonical v0.1 enforce syntax. `enforce` has exactly two fields: `entity` and `constraints`. Shape A (with `on`, `since`, `decay_check` fields) is retired and produces a compile error. `decay_check` has moved to `constraint_decl` where it belongs — per-constraint, not per-enforce. The enforce block's single responsibility is: bind a named entity to a list of named constraints. Nothing else.

**Ruling — Discrepancy 3 — map-to-constraint linking**

The link is implicit and canonical for v0.1. A `membership_rule` matches all map blocks whose `target` field equals the rule's `state_ref`. The resolver unions the `maps_to` values across all matching map blocks to form the complete valid membership set. No `uses_map` declaration exists in v0.1. The validator's `_check_membership_rules_have_maps` check is the enforcement mechanism. Multiple map blocks may share the same target — this is valid and expected.

---

## X. M4 Resolver Architecture

The resolver takes the validated IR and evaluates constraints against live entity state. It emits RESOLUTION TRACEs. All rulings from Section IX are reflected here.

### 10.1 Inputs

| Input | Description |
|---|---|
| Validated IR (JSON) | Output of M2 validator. Fully trusted. |
| Entity state snapshot | Current observable state for the entity under evaluation. |
| Response history | Sequence of `{ text, state_ref, timestamp }` entries. Required for contradiction detection (Q2). |
| Trigger type | `"event"` (new state arrived) or `"heartbeat"` (`decay_check` fired per Q3). |

### 10.2 Outputs

| Output | Description |
|---|---|
| RESOLUTION TRACE (JSON + human text) | Full evaluation record. Always produced, even on SATISFIED. |
| Action directives | Ordered list of violation actions to execute. Empty if all constraints satisfied. |
| System state | Final entity state: `running`, `frozen`, or `escalated`. |

### 10.3 Evaluation Order

1. Evaluate all active constraints against current state snapshot.
2. Collect all violations. Tag each with its priority level.
3. If zero violations: emit SATISFIED trace. Done.
4. If one violation: execute its `on_violation` action. Emit trace.
5. If two+ violations at critical: most restrictive action wins (Q1). All violations logged as co-active.
6. If mixed priorities: critical overrides high overrides medium overrides low.
7. Emit RESOLUTION TRACE with full co-active violation log regardless of action taken.

### 10.4 Contradiction Detection Algorithm

Applies only to `contradiction_rule` kind. Implements Q2 resolution.

1. For each response in history, key it by `state_ref` (the topic key).
2. Group prior responses by `state_ref`.
3. When new response arrives for `state_ref` X: compare against all prior responses keyed to X within window.
4. Contradiction is flagged by map block triggers matching the new response text (e.g. `'actually,'`, `'on second thought'`).
5. If contradiction detected: emit violation. Action per constraint `on_violation` field.

### 10.5 decay_check Trigger Logic

Implements Q3 resolution. Per-constraint. Independent of `audit_interval`.

- On new state arrival for entity E: immediately evaluate all constraints monitoring E. Reset decay timer for those constraints.
- On `decay_check` timer expiry for constraint C (no new state arrived): evaluate C against last known state snapshot. Emit trace regardless of result.
- `audit_interval` fires independently: run full domain coherence pass across all constraints. Produces domain-level trace.

---

## XI. Document Status

| Field | Value |
|---|---|
| Document version | Draft 3 |
| Grammar version | Pi Script v0.1 |
| Stack | Continuum |
| Domain scope | AI Governance |
| Status | All open questions and discrepancies resolved. |
| Next action | Begin M3 parser milestone. |
| Implementation gate | Draft 3 is the canonical spec. Grammar must match before any resolver code is written. |
| Draft history | Draft 1 — Section IX open. Draft 2 — Q1/Q2/Q3 resolved, resolver architecture added. Draft 3 — three discrepancy rulings merged, grammar canonicalized. |

---

*— End of Draft 3 —*
