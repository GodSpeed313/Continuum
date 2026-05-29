# Pi Script v0.2 — Grammar Specification

**AI Governance Domain — Draft 6**
*A language for defining what must remain true while everything else changes.*
*May 2026*

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

## XI. Document Status

| Field | Value |
|---|---|
| Document version | Draft 6 |
| Grammar version | Pi Script v0.2 |
| Stack | Continuum |
| Domain scope | AI Governance |
| Status | Ruling 9.5 (Cross-Domain Constraint Inheritance) complete. Implementation gate open. |
| Pending rulings | Persistent violation counters (9.6), Arbiter mandatory (9.7), Semantic similarity map matching (9.8) |
| Implementation gate | Draft 6 Ruling 9.5 is the canonical spec for cross-domain imports. Grammar must match before validator code is written. |
| Base | Builds on Pi Script v0.1 Draft 4 and v0.2 Draft 5. All prior rulings (9.1–9.4) remain binding. |
| Draft history | Draft 1 — Section IX open. Draft 2 — Q1/Q2/Q3 resolved. Draft 3 — three discrepancy rulings. Draft 4 — threshold rule window optionality (Ruling 9.3). Draft 5 — bidirectional map blocks (Ruling 9.4). Draft 6 — cross-domain constraint inheritance (Ruling 9.5). |
