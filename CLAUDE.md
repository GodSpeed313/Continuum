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
- `tests/` — pytest suite, 545 passing + 7 xfail (known-gap pins) across parser/validator/trace/resolver/Rift/MCP/dashboard/moltbook
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

Account `u/continuumagent` is registered, verified, and claimed. The transport/execution layer
(`moltbook/transport.py`) is governed by `docs/m7_moltbook_transport_boundary_and_deployment_spec.md`
(LOCKED, plus non-binding Implementation Notes A [claim-status eligibility gate], B [captcha
verification], C [rate-limit retry category — the one note that amends a numbered section, §8],
and D [request_fn header capture]) — it is NOT a Pi Script constraint or a 9.x grammar ruling,
just the non-semantic adapter that moves already-approved actions to the live API. **Merged to
main via PR #39** (squash commit `9b4ec71`). `MoltbookClient.send()` takes `parent_post_id`
(required for comment/reply); real endpoints (`/posts`, `/posts/{id}/comments`, `/agents/status`)
were corrected against `docs/moltbook_api_spec.md` (a reference doc describing the actual API
surface — not a governance document), including URL-routing-only `parent_post_id` (§4) and
distinct 409/410/429 status handling (§8) with `describe_retry_category()` as the canonical
exhaustive `RetryCategory` consumer (loud `ValueError` on any unrecognized category, no silent
default). Per Implementation Note D the `request_fn` seam returns `HTTPResponse` (status, body,
headers — lowercased keys), NOT the old `(status, body)` tuple, with `Retry-After`/`X-RateLimit-*`
surfaced as typed `RateLimitInfo` on `TransportResult` — capture only, no scheduling/sleeping/
auto-retry anywhere (Note C's condition (b), a scheduling spec, remains unmet). Per Implementation
Note E (signed off 2026-07-21, after the live skill.md documented the issuance protocol): the
WRITE issues the challenge inside its own response (no standalone endpoint —
`fetch_captcha_challenge` is retired, fail-closed invariant requires verifier+submit both-or-
neither), verification gates PUBLICATION not transmission, `verification_code` replaced
`challenge_id` contract-wide, and `TransportResult` carries three independent statuses
(transmission via `outcome`, `publication_status`, `verification_status` — trusted-agent
immediate-publish is first-class NOT_REQUIRED+PUBLISHED). Redacted protocol fixture:
`tests/fixtures/moltbook_captcha_issuance.json`. Both former live-deployment engineering blockers
are now closed — remaining known gap is the solver vs. the documented word-number obfuscation
style (xfail-pinned); first live post is a go decision plus its own governed envelope, not an
engineering blocker.
