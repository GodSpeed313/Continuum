# Continuum — TODO

Live milestone + debt tracker. Suite: **589 passing + 7 xfail** (known-gap pins).

## Open items

### M7 — remaining before/at live deployment

- [x] **T2 longitudinal cohort re-sample (2026-07-22/23)** — identity 0/8 (no drift), first
      A1.6 falsification check on CadenceIntegrity's ±5s grounding passed. T3 follows ~2026-07-30.
- [ ] **First live post — a GO DECISION, not an engineering task.** Requires its own governed
      envelope + operator go-ahead + live wiring of a real `submit_captcha_fn` against
      `POST /api/v1/verify` (the seam is injected everywhere in tests; live wiring has
      deliberately never happened). Transport spec Note E stop conditions apply.
- [ ] IdentityIntegrity v1.1 cross-session change-rate threshold — blocked on T2/T3 data.
- [ ] CitationClusterIntegrity §5 grounding amendment — trigger is first real M7 citation
      activity by our deployed agent; until then the constraint is structurally NOT EVALUABLE.

### Infrastructure / process debt

- [ ] Claude Code scaffold hooks (PR #30) never installed — bash/`CLAUDE_*`-env-var shaped,
      need Windows + current-JSON-interface rework before enabling.
- [ ] `PISCRIPTGOVERNANCE` PAT (Melody-Maestro governance watcher) expires again ~early
      September 2026 (60-day fine-grained default, regenerated ~2026-07-08). No expiry
      warning exists — if #pi-logs Discord goes quiet, check the PAT first
      (`gh run list -R GodSpeed313/Melody-Maestro`).

### xfail census (7 — deliberate known-gap pins, not failures)

- 3 × CredentialIntegrity encoding exfil (base64 / reversed / split-within-prefix)
- 3 × IdentityIntegrity (semantic persona-drift; A4 quoted-speech; A2 residual truncation)
- 1 × captcha solver: whitespace-shattered words (Note F §F.5 residual)

---

## Milestone tracker

- [x] M1 — Grammar finalized
- [x] M2 — Semantic validator, 12/12 tests passing
- [x] M3 — Parser — 9/9 tests passing
- [x] M4 — Resolver core — 89/89 tests passing
- [x] M5 — Dogfood — gate met (6+ violations across two independent systems: 2 Continuum session + 4+ Melody Maestro automated, 23-day active run)
- [x] M6 — Publish — ConsistencyGuard activated, Rift v0.1 shipped, Jupyter playground live (paper at docs/m6_paper_draft1.md)
- [ ] M7 — Moltbook deployment — **engineering complete, not yet live** (see open items above)

## v0.2 ruling tracker

- [x] Ruling 9.4 — bidirectional map blocks (PR #10)
- [x] Ruling 9.5 — cross-domain constraint inheritance (PR #11)
- [x] Ruling 9.6 — persistent violation counters (PR #12)
- [x] Ruling 9.7 — arbiter mandatory + flag-as-always-additive (PR #13)
- [x] Ruling 9.8 — semantic similarity map matching (PR #14, #15)
- [x] Ruling 9.9 — standing bound rule / Form 7 (PR #16)

Pending rulings: none. Spec doc (`docs/pi_script_v02_draft5.md`, Draft 10) confirms.

## Tooling / integration (post-9.9)

- [x] MCP server exposing governance checks as a tool (PR #18)
- [x] Persistence + cross-process write-queue for `check_governance` (PR #19)
- [x] Read-only governance dashboard (PR #20)
- [x] Quantization-governance domain example — corrected to valid v0.2 syntax, proves grammar is domain-general (PR #21)

## Rift v0.2 (Layer 3 rulings)

- [x] Ruling 3.1 — two-tier semantic declaration matching, independent MiniLM instance (PR #26, `4ff5e7f`)
- [x] Ruling 3.2 — known-values accumulation, `RiftSession` (PR #27, `04b747f`)

## M7 shipped log

- [x] Claude Code scaffold: CLAUDE.md + three skills (PR #30, `3172e5a`)
- [x] CredentialIntegrity — ruling + key isolation + pre-send gate (PR #31, `0db3f2e`)
- [x] LinkRestriction — provenance check + allowlist + reshare log (PR #32, `a3a5be6`)
- [x] IdentityIntegrity v1 — within-session, mechanical-only detection (PR #33, `6c558e5`)
- [x] IdentityIntegrity Addendum 1 — A1–A6 external-review fixes (PR #34, `c5f51aa`)
- [x] CadenceIntegrity — longitudinal constraint, provisional §5 params (PR #35, `7dbbed9`)
- [x] CitationClusterIntegrity — directional edges, ungrounded-§5-by-design (PR #36, `e8dbb92`)
- [x] README M7 section (PR #37, `71c5031`)
- [x] CadenceIntegrity Amendment 1 — J ±3s→±5s, grounded from T1 cohort (PR #38, `809b5c1`)
- [x] Moltbook transport boundary — locked spec + Notes A/B/C (PR #39, `9b4ec71`)
- [x] Implementation Note D — request_fn header capture, RateLimitInfo (PR #40, `819cfa0`)
- [x] Implementation Note E — captcha issuance protocol, verification gates publication (PR #41, `1bbead6`)
- [x] Trace status contract — suspended rendering, fail-loud unknown statuses (PR #42, `a27b4e5`)
- [x] Implementation Note F — solver extension for documented obfuscation style (PR #43, `ec1f6a0`)
- [x] `tests/test_validator_unit.py` recreated — hand-built Lark Tree harness, 26 tests
      (11 happy-path IR extraction, 7 semantic errors, 5 malformed-AST None-guard, 3
      conditional-rule variants). Oldest open item (M4 era), never committed before.
