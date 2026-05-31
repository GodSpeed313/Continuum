# Pi Script v0.2 — Grammar Specification

**AI Governance Domain — Draft 7**
*A language for defining what must remain true while everything else changes.*
*May 2026*

---

## Draft 7 — Changes from Draft 6

- **Section IX:** Ruling 9.6 — Persistent Violation Counters. Defines `violation_counts` in `state.json`, escalation resolution algorithm, counter increment semantics, trace `Violation count` line, and `log_session.py --reset-violations` flag. No grammar change.
- **Section XI:** Document status updated to Draft 7.

---

## Draft 6 — Changes from Draft 5

- **Section 2.5:** Domain block gains optional `imports` field — list of `DOMAIN.CONSTRAINT` qualified references from sibling domains in the same file. Single-domain files without `imports` are unchanged.
- **Section 5.4:** Resolver trace header annotates imported constraints with `(imported from DOMAIN)`.
- **Section IX:** Ruling 9.5 — Cross-Domain Constraint Inheritance. Defines import syntax, entity name-matching rule, IR shape with `imported_from` marker, multi-domain file semantics, and circular import rejection.
- **Section XI:** Document status updated to Draft 6.

---

## Draft 5 — Changes from Draft 4

- **Section 2.4:** Map block gains optional `label` field — canonical human-readable name for a `maps_to` state value. Reverse-lookup mechanism defined. Existing map blocks without `label` are valid v0.2 programs (backwards compatible).
- **Section 5.3:** Membership rule trace output updated — resolver uses `label` when present to display human-readable state name alongside machine value.
- **Section IX:** Ruling 9.4 — Bidirectional Map Blocks. Defines `label` field semantics, reverse-lookup algorithm, trace rendering contract, and "bidirectional" scope clarification.
- **Section X:** Resolver architecture updated — Section 10.6 (Reverse-Lookup Algorithm) added.
- **Section XI:** Document status updated to Draft 5.

---

## Ruling 9.4 — Bidirectional Map Blocks

**Status:** Binding for implementation. No code may be written against this ruling until this section is complete. This is the canonical v0.2 spec ruling for bidirectional map blocks.

---

### 9.4.1 Problem

Pi Script v0.1 maps are unidirectional: human trigger text maps forward to a machine state value (`maps_to`). The reverse direction — given a machine state value, retrieve a human-readable label — does not exist in v0.1.

The consequence appears in RESOLUTION TRACEs. When a membership rule is evaluated, the trace currently displays the raw machine state value:

```
├── CONSTRAINT: TopicCompliance [priority: medium]
│   ├── Rule kind  : membership_rule
│   ├── Evaluation : session_topic = 'runtime', matched in valid set ['runtime', 'spec', 'structure']
│   └── ✓ SATISFIED — no action
```

A non-expert reader sees `'runtime'` — a machine identifier. They cannot know without reading the policy file that this means "the session covered the resolver, trace, or validator." The trace fails the Gate Condition for this value class.

The `human_text` field at the resolution footer suffers the same problem — it can describe the action taken but cannot describe the state in human terms without hand-authoring the translation.

---

### 9.4.2 Design Decision

Add an optional `label` field to the existing map block. The `label` is the canonical human-readable name for the state that `maps_to` represents.

**New map block syntax (v0.2):**

```
map RuntimeTopic {
    target:   ContinuumSession.session_topic
    maps_to:  "runtime"
    triggers: ["resolver", "trace", "validator", "violation"]
    label:    "Runtime & Evaluation"
}
```

**v0.1 map block without label — valid in v0.2:**

```
map RuntimeTopic {
    target:   ContinuumSession.session_topic
    maps_to:  "runtime"
    triggers: ["resolver", "trace", "validator", "violation"]
}
```

Both forms are valid. `label` is optional. Omitting it preserves exact v0.1 behavior.

---

### 9.4.3 Scope Clarification — "Bidirectional" Defined

The term "bidirectional" in this ruling refers to **lookup direction only**, not trigger direction.

| Direction | v0.1 | v0.2 |
|---|---|---|
| Forward (human text → machine state) | ✅ via `triggers` | ✅ unchanged |
| Reverse (machine state → human label) | ❌ no reverse | ✅ via `label` |

The reverse direction is **read-only**. A `label` value does not trigger state changes. It is a display annotation used by the resolver when rendering traces. The `triggers` list remains the only mechanism by which state is set.

This is not a "symmetrical trigger" system. A change in `label` does not propagate backwards. Calling this "A↔B triggering" would be incorrect. The correct description: the map block is now **addressable in both directions for lookup purposes**.

---

### 9.4.4 Grammar Extension

The map block gains one optional field. All existing fields are unchanged.

**v0.2 map block fields:**

| Field | Required | Type | Description |
|---|---|---|---|
| `target` | ✅ | `ENTITY.FIELD` | Entity state field being mapped |
| `maps_to` | ✅ | `QUOTED_STRING` | Machine state value this map block represents |
| `triggers` | ✅ | `[QUOTED_STRING, ...]` | Forward-direction trigger strings |
| `label` | optional | `QUOTED_STRING` | Human-readable name for this `maps_to` state (v0.2) |

**Grammar rule delta (Lark):**

```
// v0.1
map_decl : "map" PASCAL_ID "{" map_field+ "}"
map_field : target_field | maps_to_field | triggers_field

// v0.2 — label_field added as optional
map_decl  : "map" PASCAL_ID "{" map_field+ "}"
map_field : target_field | maps_to_field | triggers_field | label_field

label_field : "label" ":" QUOTED_STRING
```

A map block with `label` is a valid v0.2 program. A map block without `label` is also a valid v0.2 program. No compile error is issued for either form.

---

### 9.4.5 Resolver Semantics

**Reverse-lookup definition:**

Given a `(state_ref, current_value)` pair, find the map block where:
- `target` equals `state_ref`
- `maps_to` equals `current_value`

If found and `label` is present: return `label`.
If found and `label` is absent: return `current_value` unchanged (v0.1 behavior).
If not found: return `current_value` unchanged.

**Trace rendering contract:**

When a `membership_rule` constraint is evaluated and the current value matches a map block that has a `label`, the RESOLUTION TRACE evaluation line renders as:

```
Evaluation : session_topic = 'runtime' (Runtime & Evaluation), matched in valid set [...]
```

Without `label`, the trace renders exactly as v0.1:

```
Evaluation : session_topic = 'runtime', matched in valid set [...]
```

The `(Label Name)` annotation appears inline, parenthetical, immediately after the raw machine value. It never replaces the machine value — both are shown. This preserves machine-readability while satisfying the Gate Condition for non-expert readers.

---

### 9.4.6 Validator Behavior

The semantic validator (`validator.py`) must:

1. Accept `label` as a valid map block field (no error on presence).
2. Validate `label` value is a non-empty quoted string when present.
3. Not require `label` — its absence is not an error.
4. Not enforce uniqueness of `label` values across map blocks (labels may repeat; `maps_to` is the identity key).

No new IR field is needed beyond storing `label` alongside `maps_to` and `triggers` in the map IR entry.

**IR shape delta (map entry):**

```json
{
    "maps_to":  "runtime",
    "triggers": ["resolver", "trace", "validator", "violation"],
    "label":    "Runtime & Evaluation"
}
```

`label` is absent when not declared. Resolver checks with `.get("label")`.

---

### 9.4.7 Backwards Compatibility

Every valid Pi Script v0.1 program is a valid Pi Script v0.2 program. No existing map block requires modification. No new required fields are introduced.

A v0.2 validator running against a v0.1 program produces identical output to the v0.1 validator for all constructs that do not use `label`.

---

### 9.4.8 Implementation Gate

This ruling is complete. Implementation proceeds in the following order:

1. **Grammar** — Update `pi_script.lark` to add `label_field` to `map_decl`
2. **Validator** — Accept and store `label` in map IR; validate non-empty string
3. **Resolver** — Add `_label_for(ref, value, maps_ir)` helper; update membership rule trace rendering
4. **Tests** — Map block with label parses clean; reverse-lookup returns label; trace output includes annotation; v0.1 programs produce identical output

No implementation step begins until the previous step has passing tests.

---

---

## Ruling 9.5 — Cross-Domain Constraint Inheritance

**Status:** Binding for implementation. No code may be written against this ruling until this section is complete. This is the canonical v0.2 spec ruling for cross-domain constraint import.

---

### 9.5.1 Problem

Pi Script v0.1 programs are single-domain: every constraint, entity, and map is declared within one `domain` block. When a governance policy spans multiple concerns — a `safety_core` domain with universal safety floors and an `ai_governance` domain with operational rules — the shared constraints must be copy-pasted into each domain. Copy-paste means drift: the `safety_core` floor can silently diverge from the `ai_governance` version.

There is no current mechanism to declare a constraint once and reuse it across domains without duplication.

---

### 9.5.2 Design Decision

Add an optional `imports` field to the `domain` block. The `imports` field lists one or more `DOMAIN_NAME.CONSTRAINT_NAME` references from sibling domains declared in the same file.

**Ruling scope:** v0.2 import is **same-file only**. Multi-file resolution is deferred to v0.3.

**Import is read-only and non-overridable.** The importing domain uses the imported constraint verbatim — its `priority`, `rule`, and `on_violation` cannot be changed at the import site. If a domain needs a modified version of a constraint, it declares a new constraint.

**New domain block syntax (v0.2):**

```
domain safety_core {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
}

entity Agent {
    confidence_score: range(0.0 .. 1.0)
}

constraint ConfidenceFloor {
    priority:     critical
    rule:         Agent.confidence_score must remain within range(0.2 .. 1.0)
    on_violation: freeze + escalate
}

domain ai_governance {
    audit_interval: 24 hours
    tiebreaker:     timestamp_asc
    imports:        [safety_core.ConfidenceFloor]
}

entity Agent {
    confidence_score: range(0.0 .. 1.0)
    current_mode:     text
}

constraint ModeCompliance {
    priority:     high
    rule:         Agent.current_mode must match mapped_values
    on_violation: escalate
}

enforce {
    entity:      Agent
    constraints: [ConfidenceFloor, ModeCompliance]
}
```

The importing domain's `enforce` block references the imported constraint by **simple name** (not qualified). The validator resolves `ConfidenceFloor` to the `safety_core.ConfidenceFloor` declaration.

---

### 9.5.3 Entity Name Matching

An imported constraint targets a specific `ENTITY.FIELD` state ref. For the import to be valid, **the importing domain must declare an entity with the same name and the same field name as the constraint's target ref**.

In the example above, `safety_core.ConfidenceFloor` targets `Agent.confidence_score`. The `ai_governance` domain declares `entity Agent { confidence_score: ... }`. The names match — import is valid.

The field **type** is not required to be identical — the validator only checks name existence. Type widening/narrowing at import boundaries is a v0.3 concern.

If the importing domain does not have a matching entity and field, the validator emits an error:

```
Import 'safety_core.ConfidenceFloor' targets 'Agent.confidence_score' but
entity 'Agent' has no field 'confidence_score' in domain 'ai_governance'.
```

---

### 9.5.4 Grammar Extension

The `domain` block gains one optional `imports` item. The existing `domain_item` alternatives are unchanged.

**Grammar rule delta (Lark):**

```
// v0.1
domain_item : duration
            | tiebreaker_mode

// v0.2 — imports_item added
domain_item : duration
            | tiebreaker_mode
            | imports_item

imports_item : "imports" ":" "[" import_ref ("," import_ref)* "]"
import_ref   : PASCAL_ID "." PASCAL_ID
```

`SNAKE_ID.PASCAL_ID` is the qualified reference `domain_name.ConstraintName`. Domain names use `SNAKE_ID` (snake_case); constraint names use `PASCAL_ID` (PascalCase) — consistent with existing Pi Script naming conventions.

An empty `imports: []` is a parse error — the field is present but contains nothing. Validators must reject it. A domain with no imports simply omits the `imports` field entirely.

---

### 9.5.5 Resolver Semantics

The resolver receives a merged IR. The validator is responsible for resolving imports before handing the IR to the resolver — the resolver sees **no difference** between a natively declared constraint and an imported one.

**Import resolution (validator responsibility):**

When the validator processes `imports: [safety_core.ConfidenceFloor]`:

1. Find domain `safety_core` in the same parse tree.
2. Locate constraint `ConfidenceFloor` in `safety_core`'s namespace.
3. Copy the full constraint IR entry into the importing domain's `constraints` dict under key `"ConfidenceFloor"`.
4. Mark the entry with `"imported_from": "safety_core"` (for trace transparency).

**Trace annotation:**

When an imported constraint appears in a RESOLUTION TRACE, the constraint header line includes the source domain in parentheses:

```
├── CONSTRAINT: ConfidenceFloor [priority: critical] (imported from safety_core)
```

This annotation is purely informational — it does not affect evaluation order, violation handling, or exit codes.

---

### 9.5.6 Validator Behavior

The semantic validator (`validator.py`) must:

1. Parse `imports` items in domain blocks and record `(source_domain, constraint_name)` pairs.
2. For each import reference, verify the source domain is declared in the same file.
3. For each import reference, verify the constraint name exists in the source domain.
4. For each import reference, verify the importing domain has a matching entity+field for the constraint's state_ref.
5. Copy the constraint IR entry into the importing domain's IR, adding `imported_from`.
6. Reject duplicate names: if the importing domain declares a constraint with the same name as an import, emit an error.
7. Reject circular imports: domain A imports from B, B imports from A → error.

**IR shape delta (imported constraint entry):**

```json
{
    "priority":     "critical",
    "rule":         { "kind": "range_rule", "ref": "Agent.confidence_score", "lo": 0.2, "hi": 1.0 },
    "on_violation": ["freeze", "escalate"],
    "escalation":   [],
    "decay_check":  null,
    "imported_from": "safety_core"
}
```

`imported_from` is absent for natively declared constraints. Resolver checks with `.get("imported_from")`.

---

### 9.5.7 Multi-Domain IR Structure

When a file contains multiple domain blocks, the validator builds **one IR per domain** and resolves imports before returning. The resolver always receives a single-domain IR — the primary (last declared) domain's IR with all imports merged in.

For v0.2, the primary domain is the **last** `domain` block in the file. Earlier domains are treated as source libraries. This convention avoids a new "primary" keyword and keeps the grammar minimal.

---

### 9.5.8 Backwards Compatibility

Every valid Pi Script v0.1 and v0.2 (Ruling 9.4) program is a valid v0.2 (Ruling 9.5) program. Single-domain files with no `imports` field are processed identically to before. No existing field changes meaning.

---

### 9.5.9 Implementation Gate

This ruling is complete. Implementation proceeds in the following order:

1. **Grammar** — Add `imports_item` and `import_ref` rules to `pi_script.lark`
2. **Validator** — Parse imports; resolve source domain + constraint; copy IR with `imported_from`; enforce entity name matching; reject circular imports and duplicate names
3. **Resolver** — Read `imported_from` from constraint IR; annotate trace header line with `(imported from DOMAIN)` when present
4. **Tests** — Single-domain file unaffected; import from sibling domain resolves correctly; missing source domain errors; missing entity/field errors; circular import errors; duplicate name errors; trace annotation present for imported constraints

No implementation step begins until the previous step has passing tests.

---

---

## Ruling 9.6 — Persistent Violation Counters

**Status:** Binding for implementation. No code may be written against this ruling until this section is complete. This is the canonical v0.2 spec ruling for persistent violation counters.

---

### 9.6.1 Problem

The `escalation_block` grammar has existed since v0.1:

```
constraint ConfidenceFloor {
    priority:     critical
    rule:         TaskAgent.confidence_score must remain within range(0.2 .. 1.0)
    on_violation: warn
    escalation {
        at 3 violations: escalate
        at 10 violations: freeze
    }
}
```

The intent is clear — escalate the response as a constraint is violated repeatedly. But the resolver is stateless: it evaluates each snapshot independently and discards the result. There is no counter. `at 3 violations: escalate` is currently a no-op in every evaluation.

---

### 9.6.2 Design Decision

**Store violation counts in `state.json`** as a new top-level key `violation_counts`. Shape: `{ "ConstraintName": int }`. This follows the same pattern as `response_history` (Ruling Q2): the state file is the persistence layer for runtime context that accumulates across sessions.

**The resolver reads and returns counts** — it does not write to disk. The caller (CLI tool, API layer, or test) decides whether to persist the returned counts back to `state.json`. This keeps the resolver pure: no I/O side effects.

**Escalation fully replaces `on_violation`** when a threshold is met. This is the intentional v0.2 contract — escalation means the base action is no longer appropriate. Flag-as-always-additive (audit trail preservation) is deferred to the Arbiter layer (Ruling 9.7/9.8), which is the correct architectural home for meta-constraint rules about what can never be suppressed.

---

### 9.6.3 Counter Semantics

**What increments the counter:** A constraint violation — any status of `"violated"` in the resolved constraint result. Suspended or satisfied constraints do not affect the counter.

**What does NOT increment the counter:** A clean resolution (status `"satisfied"`). Counters only go up on violation.

**What resets the counter:** Explicit `--reset-violations` flag on `log_session.py`. With no argument, resets all counters. With a constraint name, resets only that constraint. Counters do not auto-reset on clean runs — they accumulate across sessions until explicitly cleared.

**Counter key:** `ConstraintName` (unqualified). Constraint names are unique within a domain.

---

### 9.6.4 Escalation Resolution Algorithm

Given a violated constraint with an `escalation` list and its current (post-increment) violation count:

1. Find all escalation steps where `step["at"] <= current_count`.
2. Take the step with the **highest** `at` value (i.e. the most severe threshold that has been met).
3. If a step is found: use its action as the effective action for this violation — `on_violation` is **replaced entirely**.
4. If no step threshold is met (count is below the lowest `at`): use `on_violation` as normal.

**Example:** `escalation: [{at: 3, action: "escalate"}, {at: 10, action: "freeze"}]`, count = 4.
- Step `at 3` is met (4 >= 3). Step `at 10` is not met (4 < 10).
- Effective action: `escalate` (replaces base `on_violation: warn`).

**Example:** count = 11.
- Both steps met. Highest threshold is `at 10`.
- Effective action: `freeze`.

---

### 9.6.5 Grammar Changes

**None.** The `escalation_block` and `escalation_step` rules already exist and parse correctly. Ruling 9.6 is a purely semantic and runtime change.

---

### 9.6.6 Validator Changes

The validator gains one new semantic check: **escalation thresholds must be positive integers**.

`PI_NUMBER` in the grammar allows floats (e.g. `1.5`). `at 1.5 violations` parses but is semantically invalid — violation counts are whole numbers. The validator must reject any escalation step where the threshold value has a fractional part or is zero or negative.

**Error message:**
```
Constraint 'ConfidenceFloor': escalation threshold must be a positive integer (got 1.5).
```

**No change to IR shape.** The escalation list is already stored as `[{"at": float, "action": str}]`. The resolver treats any `at` value as an integer comparison (`int(at) <= count`).

---

### 9.6.7 Resolver Changes

**State input:** The resolver reads `violation_counts` from the state dict:

```python
violation_counts: dict[str, int] = state.get("violation_counts", {})
```

**Per-constraint evaluation update:**

For each violated constraint:
1. `count = violation_counts.get(cname, 0) + 1` — increment (not yet persisted)
2. Find the highest-threshold escalation step where `int(step["at"]) <= count`.
3. If found: effective action = step action (replaces `on_violation`).
4. If not found: effective action = `on_violation` (unchanged).
5. Store `count` in the result dict as `"violation_count"`.
6. Store effective action as `"action"` in the result dict (already exists).

For each satisfied constraint: counter is not touched.

**Return value update:** The trace dict gains an `updated_violation_counts` field:

```json
{
    "updated_violation_counts": {
        "ConfidenceFloor": 3
    }
}
```

Only constraints that were violated in this evaluation appear in `updated_violation_counts`. The caller merges these into the full `violation_counts` dict before persisting.

---

### 9.6.8 Trace Rendering

When a constraint is **violated** and has a non-zero violation count, the RESOLUTION TRACE includes a `Violation count` line:

```
├── CONSTRAINT: ConfidenceFloor [priority: critical]
│   ├── Rule kind      : range_rule
│   ├── Evaluation     : confidence_score = 0.10, below floor 0.2
│   ├── Violation count: 3 — escalation threshold met → freeze
│   └── ✗ VIOLATED — freeze
```

When violated but below all escalation thresholds (or no escalation block):

```
├── CONSTRAINT: ConfidenceFloor [priority: critical]
│   ├── Rule kind      : range_rule
│   ├── Evaluation     : confidence_score = 0.10, below floor 0.2
│   ├── Violation count: 2 — next escalation: escalate at 3
│   └── ✗ VIOLATED — warn
```

When the constraint is **satisfied**, no `Violation count` line appears — satisfied evaluations do not touch the counter.

---

### 9.6.9 `log_session.py` Extension

`log_session.py` gains a `--reset-violations` flag:

- `python log_session.py --reset-violations` — clears the entire `violation_counts` dict in `state.json`
- `python log_session.py --reset-violations ConfidenceFloor` — resets only that constraint's count to 0

This is the only supported write path for counter resets. No Pi Script syntax is added for programmatic resets — that is a v0.3 concern.

---

### 9.6.10 `state.json` Shape After Ruling 9.6

```json
{
    "trigger_type": "event",
    "entity": "TaskAgent",
    "entity_state": {
        "confidence_score": 0.10,
        "current_mode": "normal_mode",
        "is_active": true
    },
    "response_history": [],
    "violation_counts": {
        "ConfidenceFloor": 3,
        "ModeCompliance": 1
    }
}
```

`violation_counts` is optional in the state input. If absent, all counts are treated as 0.

---

### 9.6.11 Backwards Compatibility

Constraints without an `escalation` block are unaffected. The `on_violation` action is used as before. No new required fields are added to `state.json`. Programs that do not pass `violation_counts` in state behave identically to before.

---

### 9.6.12 Implementation Gate

This ruling is complete. Implementation proceeds in the following order:

1. **Validator** — Add positive-integer check for escalation step thresholds
2. **Resolver** — Read `violation_counts` from state; increment on violation; apply escalation algorithm; return `updated_violation_counts` in trace
3. **Trace** — Add `Violation count` line for violated constraints
4. **`log_session.py`** — Add `--reset-violations [CONSTRAINT_NAME]` flag
5. **Tests** — Counter increments on violation; escalation fires at threshold; escalation replaces `on_violation`; highest-threshold step wins when multiple met; satisfied constraints do not increment; reset works; no-escalation constraints unaffected

No implementation step begins until the previous step has passing tests.

---

## XI. Document Status

| Field | Value |
|---|---|
| Document version | Draft 7 |
| Grammar version | Pi Script v0.2 |
| Stack | Continuum |
| Domain scope | AI Governance |
| Status | Ruling 9.6 (Persistent Violation Counters) complete. Implementation gate open. |
| Pending rulings | Arbiter mandatory (9.7), Semantic similarity map matching (9.8) |
| Implementation gate | Draft 7 Ruling 9.6 is the canonical spec for violation counters. No grammar change required. |
| Base | Builds on Pi Script v0.1 Draft 4 and v0.2 Drafts 5–6. All prior rulings (9.1–9.5) remain binding. |
| Draft history | Draft 1 — Section IX open. Draft 2 — Q1/Q2/Q3 resolved. Draft 3 — three discrepancy rulings. Draft 4 — threshold rule window optionality (Ruling 9.3). Draft 5 — bidirectional map blocks (Ruling 9.4). Draft 6 — cross-domain constraint inheritance (Ruling 9.5). Draft 7 — persistent violation counters (Ruling 9.6). |
