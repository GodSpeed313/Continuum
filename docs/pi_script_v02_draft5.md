# Pi Script v0.2 — Grammar Specification

**AI Governance Domain — Draft 5**
*A language for defining what must remain true while everything else changes.*
*May 2026*

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

## XI. Document Status

| Field | Value |
|---|---|
| Document version | Draft 5 |
| Grammar version | Pi Script v0.2 |
| Stack | Continuum |
| Domain scope | AI Governance |
| Status | Ruling 9.4 (Bidirectional Map Blocks) complete. Implementation gate open. |
| Pending rulings | Cross-domain constraint inheritance (9.5), Persistent violation counters (9.6), Arbiter mandatory (9.7), Semantic similarity map matching (9.8) |
| Implementation gate | Draft 5 Ruling 9.4 is the canonical spec for bidirectional maps. Grammar must match before resolver code is written. |
| Base | Builds on Pi Script v0.1 Draft 4. All v0.1 rulings (9.1, 9.2, 9.3) remain binding. |
| Draft history | Draft 1 — Section IX open. Draft 2 — Q1/Q2/Q3 resolved. Draft 3 — three discrepancy rulings. Draft 4 — threshold rule window optionality (Ruling 9.3). Draft 5 — bidirectional map blocks (Ruling 9.4). |
