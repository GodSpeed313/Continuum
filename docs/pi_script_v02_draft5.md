# Pi Script v0.2 — Grammar Specification

**AI Governance Domain — Draft 9**
*A language for defining what must remain true while everything else changes.*
*May 2026*

---

## Draft 9 — Changes from Draft 8

- **Section 2.4:** Map block gains two new optional fields: `match_mode: semantic` (Tier 3 opt-in) and `similarity_threshold` (required when `match_mode` is `semantic`). Existing maps without these fields are unchanged.
- **Section IX:** Ruling 9.8 — Semantic Similarity Map Matching. Defines Tier 3 semantic matching, `similarity_threshold` validation contract, graceful degradation to Tier 1, `semantic_match` trace line, and `DEGRADED` trace warning.
- **Section XI:** Document status updated to Draft 9.

---

## Draft 8 — Changes from Draft 7

- **Section 2.6:** Arbiter block is now required in the primary domain. Files without an `arbiter` block fail validation.
- **Section IX:** Ruling 9.7 — Arbiter Mandatory. Defines arbiter-required gate, flag-as-always-additive algorithm, `flag_preserved` marker in constraint trace, and compound final action construction.
- **Section XI:** Document status updated to Draft 8.

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

```text
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

```pi
map RuntimeTopic {
    target:   ContinuumSession.session_topic
    maps_to:  "runtime"
    triggers: ["resolver", "trace", "validator", "violation"]
    label:    "Runtime & Evaluation"
}
```

**v0.1 map block without label — valid in v0.2:**

```pi
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
| --- | --- | --- |
| Forward (human text → machine state) | ✅ via `triggers` | ✅ unchanged |
| Reverse (machine state → human label) | ❌ no reverse | ✅ via `label` |

The reverse direction is **read-only**. A `label` value does not trigger state changes. It is a display annotation used by the resolver when rendering traces. The `triggers` list remains the only mechanism by which state is set.

This is not a "symmetrical trigger" system. A change in `label` does not propagate backwards. Calling this "A↔B triggering" would be incorrect. The correct description: the map block is now **addressable in both directions for lookup purposes**.

---

### 9.4.4 Grammar Extension

The map block gains one optional field. All existing fields are unchanged.

**v0.2 map block fields:**

| Field | Required | Type | Description |
| --- | --- | --- | --- |
| `target` | ✅ | `ENTITY.FIELD` | Entity state field being mapped |
| `maps_to` | ✅ | `QUOTED_STRING` | Machine state value this map block represents |
| `triggers` | ✅ | `[QUOTED_STRING, ...]` | Forward-direction trigger strings |
| `label` | optional | `QUOTED_STRING` | Human-readable name for this `maps_to` state (v0.2) |

**Grammar rule delta (Lark):**

```lark
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

```text
Evaluation : session_topic = 'runtime' (Runtime & Evaluation), matched in valid set [...]
```

Without `label`, the trace renders exactly as v0.1:

```text
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

```pi
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

```text
Import 'safety_core.ConfidenceFloor' targets 'Agent.confidence_score' but
entity 'Agent' has no field 'confidence_score' in domain 'ai_governance'.
```

---

### 9.5.4 Grammar Extension

The `domain` block gains one optional `imports` item. The existing `domain_item` alternatives are unchanged.

**Grammar rule delta (Lark):**

```lark
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

```text
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

```pi
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

```text
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

```text
├── CONSTRAINT: ConfidenceFloor [priority: critical]
│   ├── Rule kind      : range_rule
│   ├── Evaluation     : confidence_score = 0.10, below floor 0.2
│   ├── Violation count: 3 — escalation threshold met → freeze
│   └── ✗ VIOLATED — freeze
```

When violated but below all escalation thresholds (or no escalation block):

```text
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

---

## Ruling 9.7 — Arbiter Mandatory

### 9.7.1 Motivation

The Arbiter block was introduced in v0.1 as the meta-constraint layer — rules about what the governance system itself must preserve across all operational decisions. In v0.2 Rulings 9.1–9.6 it remained optional, allowing incremental adoption. Ruling 9.7 activates the Arbiter as a hard gate and delivers its first enforced meta-rule: **flag actions can never be suppressed by escalation**.

This addresses the audit-trail gap identified during Ruling 9.6 design: when escalation fires and replaces `on_violation`, a system that was flagging violations before escalation silently stops flagging. A governance tool that stops its audit log because the situation became more severe is less trustworthy, not more.

### 9.7.2 Arbiter Required in Primary Domain

As of Draft 8, every valid Pi Script v0.2 file **must** contain an `arbiter` block in the primary domain. A file that parses successfully but has no `arbiter` declaration fails at the validation stage with:

```text
Arbiter block is required in the primary domain. Add: arbiter <Name> { ... }
```

**Scope rules:**

- The requirement applies to the **primary domain only** (the last domain section in a multi-domain file, per Ruling 9.5 semantics).
- Library domains (earlier sections imported by the primary) are not required to carry an arbiter. They are constraint libraries, not governance authorities.
- If a library domain declares an arbiter, it is parsed but ignored — library arbiters are not inherited by the primary.

**Minimum valid arbiter block** — the grammar already permits empty-like blocks via `str_list: "[]"`. The simplest valid declaration satisfies the requirement:

```pi
arbiter GovernancePolicy {
    acceptable_evolution:  []
    never_acceptable:      []
    requires_human_review: []
}
```

### 9.7.3 Flag-as-Always-Additive

**Rule:** If a constraint's `on_violation` action contains `flag` (either as `flag` or as part of a compound like `flag + escalate`), that flag is preserved in the final trace action even when an escalation threshold fires and replaces the base action.

**Rationale:** `flag` is a side-channel audit action — it writes to the audit log and notifies reviewers. It is not an operational action level in the severity progression. Suppressing it when escalation kicks in creates a gap in the audit trail at precisely the moment when audit continuity matters most.

**Scope:** The preservation rule applies to the original `on_violation` declaration only. Escalation steps themselves define a severity progression — if a developer writes `at 5: freeze` without including `flag`, that is a conscious choice to transition to a halt state. The Arbiter preserves only what was already being tracked.

### 9.7.4 Flag Preservation Algorithm

The resolver applies flag preservation as a post-processing pass after Q1 violation resolution:

1. For each violated constraint where an escalation threshold fired (`escalation_fired = True`):
   - Inspect the constraint's original `on_violation` action string.
   - If the string contains `"flag"`, mark the result with `flag_preserved: True`.
   - The constraint's individual `action` field remains the escalation action (e.g., `freeze`) — the flag is preserved at the final resolution level, not per-constraint.

2. After `_resolve_violations` produces the operational `final_action`:
   - If any violated constraint has `flag_preserved: True` **and** `"flag"` is not already present in the operational `final_action`:
     - `final_action = "flag + " + operational_action`
   - Otherwise `final_action = operational_action` (unchanged).

3. `_action_to_system_state` uses substring matching (`"freeze" in action`, `"escalate" in action`) and is unaffected by the `flag +` prefix.

**Edge cases:**

- Escalation fires to `flag + escalate`: flag already present in operational action → no double-flag, `final_action = "flag + escalate"`.
- Multiple simultaneous violations: constraint A (`on_violation: flag`) escalates to `freeze`; constraint B (`on_violation: warn`) escalates to `freeze`. Only A sets `flag_preserved`. `final_action = "flag + freeze"`.
- No escalation fires: `flag_preserved` is never set. Flag-preservation rule has no effect on non-escalating violations.

### 9.7.5 Compound Final Action Table

The following compound actions are now valid outputs from the resolver. All are JSON-serializable strings.

| Final action | When produced |
| --- | --- |
| `flag + warn` | Escalation fires to `warn`; original had `flag` |
| `flag + escalate` | Existing — escalation fires to `escalate`; original had `flag` |
| `flag + rollback` | Escalation fires to `rollback`; original had `flag` |
| `flag + freeze` | Escalation fires to `freeze`; original had `flag` |
| `flag + freeze + rollback` | Escalation fires to `freeze + rollback`; original had `flag` |

### 9.7.6 Trace Format — `flag_preserved` Marker

When `flag_preserved: True` is set on a constraint result, the rendered trace shows an additional line between `Violation count` (if present) and `VIOLATION DETECTED`:

```text
├── CONSTRAINT: ConfidenceFloor [priority: critical]
│   ├── Rule kind  : range_rule
│   ├── Evaluation : confidence_score 0.28 < range floor 0.4
│   ├── Violation count: 4 — escalation threshold met → freeze
│   ├── Flag preserved : audit log maintained
│   ├── ✗ VIOLATION DETECTED
│   └── Action     : freeze
```

The final action in the `RESOLUTION` block then shows:

```text
└── RESOLUTION
    ├── Action       : flag + freeze
    ├── System state : frozen
    └── The rule 'ConfidenceFloor' was broken...
```

### 9.7.7 Grammar Changes

**None.** The `arbiter_decl` rule already exists and parses correctly. Ruling 9.7 is a validation gate change and a runtime semantic change.

### 9.7.8 IR Shape Changes

**None.** The `arbiter` key already exists in the IR (`"arbiter": null | {...}`). Ruling 9.7 makes `null` an error condition at validation time. The resolver reads `flag_preserved` from individual constraint results, not from the arbiter IR.

### 9.7.9 Backward Compatibility

Files written for v0.2 Rulings 9.4–9.6 that lack an arbiter block will now fail validation. This is a **breaking change** for those files. The fix is minimal — add an arbiter block with empty lists. All v0.1 files without an arbiter block also fail.

The flag-preservation rule is additive: existing programs without escalation blocks are unaffected. Programs with escalation that did not use `flag` in `on_violation` are unaffected.

### 9.7.10 Test Contract

```text
TestArbiterRequired:
  test_arbiter_missing_fails_validation
  test_arbiter_present_passes
  test_arbiter_library_domain_no_arbiter_ok      (primary has arbiter, library does not)
  test_arbiter_library_domain_only_fails          (library has arbiter, primary does not)

TestFlagPreservation:
  test_flag_preserved_escalation_fires            (on_violation flag + escalation → flag_preserved=True)
  test_flag_not_preserved_no_escalation           (on_violation flag, no escalation fires → no flag_preserved)
  test_flag_not_preserved_no_flag_in_original     (on_violation warn, escalation fires → no flag_preserved)
  test_flag_preserved_final_action_compound       (final_action becomes flag + freeze)
  test_flag_preserved_mixed_violations            (A: flag→freeze; B: warn→freeze → flag + freeze)
  test_flag_not_doubled_when_already_in_action    (escalation fires to flag + escalate → no double flag)
  test_flag_preserved_trace_render                (rendered trace shows Flag preserved line)
```

No implementation step begins until this spec section is locked.

---

## Ruling 9.8 — Semantic Similarity Map Matching

**Status:** Binding for implementation. No code may be written against this ruling until this section is complete. This is the canonical v0.2 spec ruling for semantic similarity map matching.

---

### 9.8.1 Problem

Pi Script v0.1 and all v0.2 rulings through 9.7 define map trigger matching as Tier 1 (substring) or Tier 2 (regex). Both tiers are lexical: a trigger fires only when its literal pattern appears in the input text. This fails for AI governance contexts where the same semantic intent surfaces in many lexical forms.

Example: a contradiction trigger `"running"` will not match the response `"the service is currently active"` even though both express the same state. Lexical matching forces governance authors to enumerate every surface form — an unbounded, brittle list.

The consequence is a governance gap: semantically equivalent inputs escape detection and governance constraints fail silently on paraphrase.

### 9.8.2 Solution

Ruling 9.8 introduces **Tier 3: Semantic Matching** as a per-map opt-in. A map block that declares `match_mode: semantic` and `similarity_threshold: <float>` causes the resolver to compare input text against trigger patterns using vector embedding cosine similarity rather than substring containment.

**Tier hierarchy (all tiers remain active; Tier 3 is additive):**

| Tier | Field value | Algorithm |
| --- | --- | --- |
| 1 | `match_mode: substring` (default) | Trigger string contained in input |
| 2 | `match_mode: exact` | Exact trigger string equality |
| 3 | `match_mode: semantic` | Cosine similarity of vector embeddings ≥ threshold |

Semantic matching is **never the default**. It requires an explicit `match_mode: semantic` declaration. Files without it are unaffected.

### 9.8.3 Syntax

Two new optional fields on map blocks:

```pi
map StatusMap {
    target:               Service.status
    maps_to:              "active"
    triggers:             ["running", "started", "online"]
    match_mode:           semantic
    similarity_threshold: 0.85
}
```

**`match_mode: semantic`** — Selects Tier 3 for this map. Required alongside `similarity_threshold`.

**`similarity_threshold: <float>`** — Cosine similarity score required for a trigger to fire. Valid range: `(0.0, 1.0]` (exclusive lower bound, inclusive upper bound). A threshold of `1.0` requires exact semantic equivalence; a threshold of `0.0` is rejected as a governance bypass (mirrors the positive-integer requirement of Ruling 9.6 escalation thresholds).

### 9.8.4 Grammar Change

Two additions to the `map_item` rule and one terminal extension:

```lark
map_item: ...
        | "similarity_threshold" ":" PI_NUMBER -> mi_sim_threshold

MATCH_MODE_KW: "substring" | "exact" | "semantic"
```

`PI_NUMBER` already exists. The range constraint `(0.0, 1.0]` is enforced by the semantic validator, not the grammar.

### 9.8.5 Validator Contract

The semantic validator must enforce:

1. **Threshold range**: `similarity_threshold` must satisfy `0.0 < value ≤ 1.0`. Values of `0.0` or below are rejected (governance bypass). Values above `1.0` are rejected (unreachable threshold).
2. **Paired requirement**: `match_mode: semantic` without `similarity_threshold` is an error.
3. **Isolation requirement**: `similarity_threshold` without `match_mode: semantic` is an error. Threshold values have no meaning in Tier 1 or Tier 2 matching.
4. **No change for existing maps**: Maps without `match_mode` or `similarity_threshold` are valid and unchanged.

### 9.8.6 IR Shape

The map entry in the IR gains two optional keys when Tier 3 is declared:

```json
{
  "maps_to": "active",
  "triggers": ["running", "started", "online"],
  "match_mode": "semantic",
  "similarity_threshold": 0.85
}
```

Maps without `match_mode` omit both keys (backwards compatible).

### 9.8.7 Resolver Contract — Semantic Matching Algorithm

**Embedding model:** `sentence-transformers/all-MiniLM-L6-v2` (lightweight, no API key, deterministic within a version).

**Algorithm (per semantic map, during contradiction detection):**

1. Collect all non-regex triggers for the map.
2. Encode `[input_text] + triggers` as normalized embeddings.
3. Compute cosine similarity between `input_text` embedding and each trigger embedding. With normalized embeddings, cosine similarity equals the dot product.
4. Select the **maximum score** across all triggers (max-wins). If `max_score ≥ similarity_threshold`, the map fires. The winning trigger and score are recorded for trace output.

**Multi-trigger rule:** Only the best-scoring trigger is reported. The map fires if any trigger exceeds the threshold.

### 9.8.8 Graceful Degradation

If the embedding model is unavailable (package not installed, import error, encoding failure), the resolver **must not crash**. Instead:

1. Fall back to Tier 1 substring matching for that map.
2. Set `semantic_degraded: True` on the constraint result.
3. Render a `⚠ DEGRADED` line in the trace (before the violation line if one fires).

The degradation is per-evaluation: a single unavailability event degrades the current resolution only. The system remains available. Degradation is always visible in the trace — silent degradation is a governance violation of the audit-first principle.

### 9.8.9 Trace Contract

For a **semantic match** (model available, threshold met):

```text
├── CONSTRAINT: TopicCompliance [priority: medium]
│   ├── Rule kind      : contradiction_rule
│   ├── Evaluation     : new response matches contradiction trigger 'running' ...
│   ├── Map match      : 'running' -> contradiction signal
│   ├── Semantic match : 'running' ~ input (score: 0.91)
│   ├── ✗ VIOLATION DETECTED
│   └── Action         : freeze
```

For a **degraded match** (model unavailable, fell back to substring, still violated):

```text
├── CONSTRAINT: TopicCompliance [priority: medium]
│   ├── Rule kind      : contradiction_rule
│   ├── Evaluation     : new response matches contradiction trigger 'running' ...
│   ├── Map match      : 'running' -> contradiction signal
│   ├── ⚠ DEGRADED    : embedding unavailable, fell back to substring matching
│   ├── ✗ VIOLATION DETECTED
│   └── Action         : freeze
```

**Ordering rule:** `⚠ DEGRADED` appears before `Semantic match` (which is omitted when degraded). Both appear before `Flag preserved` (Ruling 9.7) and `✗ VIOLATION DETECTED`.

### 9.8.10 Flag Preservation Integration

Semantic matching does not change the flag-preservation algorithm (Ruling 9.7). If a semantic map fires a constraint whose `on_violation` contains `flag`, and an escalation replaces it, `flag_preserved` is set as defined in 9.7. The trace order is:

```text
│   ├── ⚠ DEGRADED    : ...         (if degraded)
│   ├── Semantic match : ...         (if semantic, not degraded)
│   ├── Violation count: ...
│   ├── Flag preserved : audit log maintained
│   ├── ✗ VIOLATION DETECTED
│   └── Action         : ...
```

### 9.8.11 Test Contract

```text
TestSemanticMapValidation:
  test_valid_semantic_map_ir           (match_mode: semantic + threshold in IR correctly)
  test_semantic_requires_threshold     (match_mode: semantic without threshold → error)
  test_threshold_without_semantic      (similarity_threshold without semantic → error)
  test_threshold_zero_rejected         (similarity_threshold: 0.0 → error)
  test_threshold_one_accepted          (similarity_threshold: 1.0 → valid, upper bound inclusive)
  test_threshold_above_one_rejected    (similarity_threshold: 1.1 → error)
  test_existing_map_unaffected         (map without match_mode still validates)

TestSemanticMapMatching:
  test_semantic_match_fires_violation  (mock returns score ≥ threshold → violated)
  test_semantic_no_match_satisfied     (mock returns score < threshold → satisfied)
  test_semantic_result_has_score       (constraint result carries semantic_match dict)
  test_trace_shows_semantic_line       (rendered trace includes Semantic match line)
  test_degraded_substring_fallback     (model unavailable + substring hit → violated + degraded)
  test_degraded_no_match_satisfied     (model unavailable + no substring → satisfied + degraded)
  test_trace_shows_degraded_line       (rendered trace shows ⚠ DEGRADED line)
  test_non_semantic_map_unaffected     (substring map still works, no semantic fields in result)
```

No implementation step begins until this spec section is locked.

---

## XI. Document Status

| Field | Value |
| --- | --- |
| Document version | Draft 9 |
| Grammar version | Pi Script v0.2 |
| Stack | Continuum |
| Domain scope | AI Governance |
| Status | Ruling 9.8 (Semantic Similarity Map Matching) spec locked. Implementation gate open. |
| Pending rulings | None |
| Implementation gate | Draft 9 Ruling 9.8 is the canonical spec for semantic map matching, graceful degradation, and Tier 3 opt-in. Grammar change: `mi_sim_threshold` map item + `semantic` in `MATCH_MODE_KW`. |
| Base | Builds on Pi Script v0.1 Draft 4 and v0.2 Drafts 5–8. All prior rulings (9.1–9.7) remain binding. |
| Draft history | Draft 1 — Section IX open. Draft 2 — Q1/Q2/Q3 resolved. Draft 3 — three discrepancy rulings. Draft 4 — threshold rule window optionality (Ruling 9.3). Draft 5 — bidirectional map blocks (Ruling 9.4). Draft 6 — cross-domain constraint inheritance (Ruling 9.5). Draft 7 — persistent violation counters (Ruling 9.6). Draft 8 — arbiter mandatory + flag-as-always-additive (Ruling 9.7). Draft 9 — semantic similarity map matching (Ruling 9.8). |
