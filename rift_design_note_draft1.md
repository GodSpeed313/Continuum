# Rift — Layer 3 Design Notes
## Draft 1 — April 2026

---

## What Rift Is

Rift is Layer 3 of the Continuum stack. It handles intent and system design.

Pi Script (Layer 2) asks: *"Is the system still what it should be?"*
Rift (Layer 3) asks: *"What should the system be in the first place?"*

Rift declares behavioral directives. Pi Script enforces them.
Rift is the policy author. Pi Script is the policy monitor.

---

## The Boundary

| Concern | Layer |
|---------|-------|
| "Did the system violate a rule?" | Pi Script (Layer 2) |
| "What rules should govern this system?" | Rift (Layer 3) |
| "What should this system's behavior be?" | Rift (Layer 3) |
| "Did a response contradict a declared rule?" | Pi Script (Layer 2) |

Rift defines the policy. Pi Script monitors it. The two layers are
complementary — neither replaces the other.

---

## First Concrete Use Case — Shelved Project Persistence

### The Problem

A user tells an AI assistant: *"I've shelved a project called Veritas.
I'll return to it later."* The assistant acknowledges this. In subsequent
sessions, the assistant keeps referencing Veritas unprompted — in response
to unrelated topics, as a suggestion, as context.

This is a **preference drift violation** — the assistant is not respecting
a declared user state. The user's intent was explicit: Veritas is dormant
until the user resurfaces it.

A human collaborator would instinctively honor this. The AI assistant does
not — because there is no layer in the stack that declares and enforces
user intent over time.

### Why Pi Script Alone Is Insufficient

Pi Script can detect the violation after it happens:

```pi
constraint RespectShelfedProjects {
    priority:     high
    rule:         if new_response references shelved_project
                  then require user_confirmation before proceeding
    on_violation: flag + escalate
}
```

But Pi Script cannot declare *why* this rule exists or *generate* the
constraint from a higher-order intent. It can only monitor a rule that was
already written by hand.

The gap: who writes the rule? Who decides that "shelved" means "dormant
until resurface"? That is Rift's job.

### The Rift Declaration (Sketch)

```rift
intent RespectUserDeclarations {
    when user declares: "I shelved [project]"
    treat: [project] as dormant
    until: user explicitly resurfaces [project]
    enforce: do not reference [project] unprompted
    generates: Pi Script constraint RespectShelfedProjects
}
```

Rift takes the natural language declaration and produces a Pi Script
constraint automatically. Pi Script monitors it. The user never has to
write the constraint by hand.

### What This Reveals About Rift

1. **Rift is a constraint generator.** It takes intent declarations and
   produces Pi Script constraints. The output of a Rift program is a set
   of Pi Script constraints, not executable code.

2. **Rift operates on user-declared state.** "I shelved X" is a state
   declaration. Rift tracks declared states and their implications.

3. **Rift handles the semantics Pi Script deliberately excludes.** Pi
   Script v0.1 requires everything to be measurable. "Shelved means
   dormant until resurface" is semantic — it requires understanding intent.
   That's Rift's domain.

4. **Rift is the answer to "who writes the rules?"** Pi Script assumes
   rules are written by a developer. Rift allows rules to be generated
   from user intent declarations in natural language.

---

## Second Implication — Continuum as a Complete Stack

This use case clarifies what Continuum is for:

- A user declares intent in natural language (Rift)
- Rift generates constraints (Pi Script)
- Pi Script monitors system behavior against those constraints
- Violations produce auditable RESOLUTION TRACEs
- Humans review traces and decide what to do

The full loop: **intent — constraints — monitoring — traces — human review**

No existing tool covers this loop end-to-end. Output filters (Guardrails
AI, etc.) cover one step. Prompt engineering covers none of them durably.
Continuum covers all five.

---

## Open Questions — Rift v0.1

These are unresolved. They are design concerns, not implementation tasks.
Rift is explicitly out of scope for Pi Script v0.1 (see Section VII).

| Question | Why It Matters |
|----------|----------------|
| What is the Rift grammar? | Rift needs its own DSL or it's just comments |
| How does Rift map natural language to Pi Script constraints? | The mapping is the hard problem |
| Who owns declared user state? | "Shelved" is user state, not system state |
| How does Rift handle contradictory declarations? | "I shelved X" then "let's revisit X" — which wins? |
| Does Rift generate constraints statically or dynamically? | Static = compile time. Dynamic = runtime. Different architectures. |
| What triggers a Rift re-evaluation? | New user declaration? Session start? Both? |

These questions are the agenda for Rift v0.1 design. No Rift code is
written until they are resolved — same discipline as Pi Script.

---

## Document Status

| Field | Value |
|-------|-------|
| Document version | Draft 1 |
| Layer | Rift (Layer 3) |
| Stack | Continuum |
| Status | Design note — not for implementation |
| Depends on | Pi Script v0.1 complete (M4 ✓) |
| Next action | Resolve open questions before any Rift grammar work |
| Implementation gate | Pi Script M5 dogfood complete. At least 3 real violations captured. |

---

*— End of Rift Draft 1 Design Note —*
