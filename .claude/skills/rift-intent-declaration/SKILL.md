---
name: rift-intent-declaration
description: Use when drafting or editing a Rift intent declaration — the grammar that states what an agent is trying to do before Pi Script constraints evaluate it. Triggers on "intent declaration", "Rift draft", "M7 intent", or edits to rift/ files.
---

# Writing a Rift Intent Declaration

An intent declaration is the agent's stated purpose for a session/action, written BEFORE
constraints are evaluated against it. It's what the resolver checks behavior against — if
there's no declared intent, there's nothing for a constraint like `IdentityIntegrity` to compare
actual behavior to.

## Structure
Real Rift v0.1 grammar (`rift_design_note_draft2.md`, `rift/rift_v01.lark`):

```
map "<trigger phrase>" -> <entity>.<field>: <value>

intent <Name> {
    when user declares: "<trigger phrase>"
    treat: [<capture>] as <state>
    until: user declares "<release trigger phrase>"     // optional
    enforce: "<plain-language behavioral constraint>"
    generates: Pi Script constraint <ConstraintName>
}
```

Rift v0.2 adds a two-tier runtime matcher (`rift/matcher.py`, `rift/session.py`) — exact trigger
match first, semantic fallback (all-MiniLM-L6-v2) if no exact match, never a silent guess. Check
`docs/rift_v02_ruling_3_1_semantic_declaration_matching.md` before assuming behavior at runtime.

## Rules for a good declaration
- `enforce` should be specific enough that a drift from it is detectable. "Be helpful" is not
  checkable. "Respond to posts in a submolt without initiating DMs" is.
- Every constraint named in `generates` must exist (or be written alongside) in `pi_script/` —
  don't declare intent generating a constraint you haven't written yet.
- One intent declaration per deployment context. Don't reuse the same declaration across Moltbook
  and a future environment without re-checking whether `enforce` still applies.
- `rift/` never imports from `pi_script/` — this is a permanent, tested layer boundary (two tests
  enforce it). Compilation is one-directional: Rift emits Pi Script, never the reverse.

## Before extending the M7 draft
The M7 draft intent declaration + constraint set (`IdentityIntegrity`, `LinkRestriction`,
`CadenceIntegrity`, and `CitationClusterIntegrity` — the two halves of the
`ManipulationFlag` split, all with locked rulings) already exists. Read it first. If you're adding a new constraint to
`generates`, write the constraint (see `pi-script-constraint` skill) before wiring it in here —
not the other way around.
