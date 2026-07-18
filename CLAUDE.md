# Continuum — Project Constitution

Continuum is a three-layer AI governance stack: Pi Script (Layer 2, constraint language +
resolver) + Rift (Layer 3, intent/declaration grammar). This file is always-on context. Keep it
under 200 lines — anything longer belongs in a skill, not here.

## Working philosophy (non-negotiable)
- **Spec first, build second.** No code until there's a written spec or ruling for the feature.
  If I ask for code without a spec, ask me for the spec first, or draft one together before
  touching files. Grammar specs live in `docs/`; the spec is the source of truth, never
  reverse-engineered from code.
- **State over time, not single-output filters.** Every enforcement decision is evaluated against
  a state snapshot in context (history, session, prior violation counts) — not just a single
  output. This is the core differentiator vs. tools like Guardrails AI — don't collapse it into a
  one-shot filter by accident.
- **The resolver rules autonomously, system-wide.** `pi_script/resolver.py` evaluates constraints
  against state and executes `on_violation` deterministically (freeze, rollback, escalate,
  freeze + escalate) — no human-in-the-loop step for a flagged violation. Don't design constraint
  logic that assumes someone reviews and approves the ruling before it takes effect.
  (Note: earlier notes/specs called this component "the Arbiter." The shipped implementation is
  `pi_script/resolver.py` — same autonomous-ruling behavior, correct current name. Use "resolver.")

## Repo map
- `pi_script/` — constraint grammar (`pi_script.lark`), parser, validator, resolver, trace builder
  (see `.claude/skills/pi-script-constraint`)
- `rift/` — intent grammar, parser, validator, compiler, two-tier declaration matcher + session
  runtime (see `.claude/skills/rift-intent-declaration`)
- `es/` — Elasticsearch adapter, canonical example of the Layer-1-to-Pi-Script adapter pattern
- `m5/` — M5 dogfood policy, state, and traces (reference for the adapter/dogfood pattern)
- `tests/` — pytest suite, 405 passing + 6 xfail (known-gap pins) across parser/validator/trace/resolver/Rift/MCP/dashboard/moltbook
- `docs/` — grammar specs and rulings; source of truth per spec-first principle
- `mcp_server.py` — exposes the resolver pipeline as an MCP tool, `check_governance`
- No top-level `traces/`. Traces write to a `traces/` directory sibling to whatever `state_path`
  is in use for that system (e.g. `m5/traces/`) — follow this convention for new systems, don't
  invent a shared global traces folder.
- No `arbiter/` directory — see resolver note above.

## Naming conventions
- Constraints: PascalCase, behavior-first (`IdentityIntegrity`, `ManipulationFlag`, `LinkRestriction`)
- Test files: pytest convention matching existing suite (`test_resolver.py`, `test_rift.py`, etc.)
  — new constraint tests are functions added to the relevant test file, not standalone `.test` files.
- Milestones: `M<n>`. **M6 is already used and complete** (Publish — paper + public playground,
  see `docs/m6_paper_draft1.md`). The Moltbook deployment milestone is **M7** — don't reuse M6.

## Test expectations
- Every new constraint ships with a deliberate-violation test case (the trace that proves it
  fires) AND a clean-pass test case (proves it doesn't false-positive), as pytest functions.
- Full suite must stay green. If a change breaks tests, that's a stop — not a "fix later."
- CI runs via GitHub Actions (`.github/workflows/`) with Discord webhook alerts on failure
  (established in M5). Test runner is **pytest**, not npm — this is a Python project (92% Python).

## Governance boundary
- Hessian-Core (algorithmic trading) is governed BY Continuum but is not a component OF it.
  Never fold Hessian-Core logic into `pi_script/` or `rift/` — it stays a separate governed project.

## Current milestone: M7
Goal: deploy a Continuum-governed agent inside Moltbook (live social platform for autonomous
agents) to test enforcement in a real adversarial environment. Active constraints for M7 (all with locked rulings in `docs/`):
`IdentityIntegrity`, `LinkRestriction`, `CadenceIntegrity`, and `CitationClusterIntegrity` —
`ManipulationFlag` was split into the latter two (the "Longitudinal Constraints").
CitationClusterIntegrity's §5 thresholds are deliberately UNDEFINED until a grounding
amendment (first real M7 citation activity); ungrounded it renders NOT EVALUABLE and cannot fire. Suggested new system directory:
`moltbook/` (follow the `m5/` dogfood pattern — policy `.pi` file, `state.json`, sibling
`traces/`), not the `es/` adapter pattern, since this is agent-session monitoring, not
infrastructure-state monitoring. Draft Rift intent declaration exists — see
`.claude/skills/rift-intent-declaration` before extending it. Recon findings (submolt structure,
the moltbook_pyclaw/Ting_Fodder/doctor_crustacean coordinated-manipulation pattern) live in the
M7 scoping notes — cross-agent coordinated manipulation is an explicit v1.1/v2 `ManipulationFlag`
extension, out of scope for the first M7 pass. Don't fold it in early.
