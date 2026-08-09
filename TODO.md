# Continuum — TODO

Live milestone + debt tracker. Suite: **590 passing + 7 xfail** (known-gap pins).

## Open items

### M7 — remaining before/at live deployment

- [x] **T2 longitudinal cohort re-sample (2026-07-22/23)** — identity 0/8 (no drift), first
      A1.6 falsification check on CadenceIntegrity's ±5s grounding passed. T3 follows ~2026-07-30.
- [ ] **First live post — a GO DECISION, not an engineering task.** Requires its own governed
      envelope + operator go-ahead + live wiring of a real `submit_captcha_fn` against
      `POST /api/v1/verify` (the seam is injected everywhere in tests; live wiring has
      deliberately never happened). Transport spec Note E stop conditions apply.
- [x] **IdentityIntegrity cross-session grounding — DELIVERED as a documentation act**
      (`docs/m7_identity_integrity_ruling_addendum_2.md`). T0–T3 closed at 0/8 identity-field
      changes over 136 profile-days; 95% upper bound ≈ 0.022 changes/profile-day. The addendum
      records the observation and its boundary: zero observed events bounds legitimate churn from
      above, it does **not** validate a threshold for enforcement. No threshold was adopted.
- [ ] CitationClusterIntegrity §5 grounding amendment — trigger is first real M7 citation
      activity by our deployed agent; until then the constraint is structurally NOT EVALUABLE.

> **Readiness authority.** `docs/m7_operator_go_checklist.md` is the authoritative document
> defining GO readiness. This tracker records work; it does not define preconditions for GO-1.
> Where the two appear to disagree, the checklist governs.

### M7 — post-GO governance milestones (NOT prerequisites for GO-1)

- [ ] **IdentityIntegrity v1.1 — cross-session identity change detection.** Ruled post-GO by
      `docs/m7_identity_integrity_ruling_addendum_2.md` §B5: v1.1 is new detection code plus its
      own ruling, not a number dropped into an existing path (no cross-session comparison
      mechanism exists — the identity baseline is constructor-supplied per session and a fresh
      session start is a legitimate reset point by design, base ruling §2). Requires, before any
      threshold is enforced: (1) explicit field-set **versioning**, with a newly appearing profile
      field defaulting to NOT EVALUABLE and never to "changed"; (2) at least one observed
      **positive example** of a legitimate cross-session identity change; (3) **false-positive
      characterization**, not assumption from zero-event data — required by §6's
      confidence-paired-to-severity discipline given `freeze + escalate`; (4) its own **spec-first
      implementation ruling**, including threshold selection as an explicit governance decision.

### M7 — post-GO engineering debt (NOT prerequisites for GO-1)

- [ ] **`KillSwitchActivation` records the operator as free text, not a structured field**
      (**issue #57**). `activate_manual(operator=...)` / `clear(operator=...)` both take an
      operator, but the audit record has no `operator` field — the identity is embedded in
      `detail` as an `operator=` prefix, recoverable only by string-parsing. Workable for manual
      inspection, weak for structured auditing of the mechanism that halts a live agent. Raised
      during the §A2 row 5 kill-switch exercise and ruled post-GO by the operator 2026-08-05:
      it does not move the GO-1 preparation baseline.

- [ ] **`approval_trace_id` on a live envelope is bound to no resolution trace.**
      `as_client_transport` (`moltbook/transport.py`) defaults `approval_trace_id_fn` to
      `lambda: str(uuid.uuid4())`, so an envelope built on the live path carries a fresh random
      identifier that references no RESOLUTION TRACE. The injection seam exists and is unused;
      nothing in the repository derives the id from `resolve()`'s output, and a RESOLUTION TRACE
      carries no identifier of its own for it to be derived from (`pi_script/trace.py` builds no
      id field). Consequence: an envelope's stated approval provenance is not currently
      traversable back to the ruling that authorized it — the audit chain has a break at exactly
      the join between the governance decision and the execution record. This is a gap in
      binding, not in enforcement: the resolver still rules, the gates still block, and the
      envelope is still validated (§4). Raised during the §A4 rehearsal 2026-08-08, where the
      exercise harness had to perform the trace-to-envelope binding locally
      (`tools/go-checklist-exercises/a4_first_post_rehearsal.py`) precisely because shipped code
      does not. **Filed as its own post-GO item by operator direction 2026-08-08** rather than
      left as a footnote in §A4's evidence. Deciding what an `approval_trace_id` should be — a
      trace identifier added to `pi_script/trace.py`, a content digest of the ruling, or a
      persisted trace-store reference — is a governance decision, not an implementation detail,
      and is deliberately not settled here. Does not move the GO-1 preparation baseline.
      *(GitHub issue not yet opened — number to be added here when it is.)*

### Infrastructure / process debt

- [x] Claude Code scaffold hooks (PR #30) installed 2026-07-24 — reworked from the scaffold's
      bash/`CLAUDE_*`-env-var shape to the current stdin-JSON hook interface as three Python
      scripts in `.claude/hooks/` (pre-Bash destructive-command guard, post-Write/Edit targeted
      pytest for `pi_script/`/`rift/`/`moltbook/`, Stop-time full suite + Discord notify) wired
      via `.claude/settings.json`. Canonical sources now TRACKED in `tools/claude-hooks/`
      (install-hooks.ps1 / verify-hooks.ps1; `.claude/` stays local and generated — see
      `docs/scaffold_hooks_reconstruction_note.md` Resolution 2026-07-24). `DISCORD_WEBHOOK_URL`
      env var enables the notify path; unset = suite still runs, result printed only.
- [x] `PISCRIPTGOVERNANCE` PAT expiry debt CLOSED 2026-07-23: pre-flight expiry-warning step +
      run-failure Discord net shipped to Melody-Maestro `governance.yml` (PR #1 `c3f5822`),
      token rotated (90-day fine-grained, Contents R/W both repos, expires 2026-10-21 —
      auto-warns #pi-logs at ≤14d ~10/07 and ≤3d ~10/18), renewal doc corrected (PR #2
      `ed17351`). If #pi-logs goes quiet anyway: `gh run list -R GodSpeed313/Melody-Maestro`.

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
