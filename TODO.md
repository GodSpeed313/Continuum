# Continuum — TODO

Live milestone + debt tracker. Suite: **647 passing + 7 xfail** (known-gap pins).

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

### M7 — §C / C2 parked items (2026-08-16 / 17)

Items surfaced during C2 and deliberately not resolved by it. Three came from extracting
the request/auth seam for the live captcha path (commit `203c016`); the `AMBIGUOUS`
disposition entry came from the classification-contract pass, where C1 §8 item 7 requires
it to be carried as an explicit, visible item rather than quietly resolved. Each is
recorded here so the deferral is a decision on the record rather than something a later
reviewer reconstructs from a commit body — deliberately NOT filed under post-GO debt
below, because GO-1 is already granted and two of these may bear on GO-2.

- [ ] **Redirect posture on the live verify path — open, and deliberately not classified as
      post-GO.** `_real_request` / `request_fn` follow redirects via urllib's default opener.
      Verified on CPython 3.12.10: on POST it redirects for 301/302/303 only and rebuilds the
      `Request` WITHOUT `data`, so a captcha answer body is never resubmitted and **C1 §5 is not
      violated**; 307/308 raise `HTTPError` and fall to C1 §4 residual, which is correct. Two
      concerns remain. (a) **Classification fidelity:** a followed redirect means the status
      reaching the classifier may not be `/verify`'s own — a 303 landing on a 404 would classify
      as C1-4 `CONFIRMED_FAILURE`, a C1 §9 stop condition, from a response `/verify` never gave.
      C1 §3.2 makes HTTP status authoritative for the enumerated non-2xx rows, so this is
      load-bearing, not cosmetic. (b) **Credential safety:** `docs/moltbook_api_spec.md` §1
      documents that a bare-domain request triggers a redirect that STRIPS the `Authorization`
      header. The transport hardcodes the `www` base URL, so no known path reaches that case
      today, but it establishes that redirect behaviour here has a credential dimension and not
      only a classification one. **Whether this must be settled before GO-2 is not decided here.**
      Parked by operator direction 2026-08-16 during the §10(b) ruling, explicitly to keep the
      §10(b) work from absorbing an unrelated change to shared request behaviour.

- [ ] **`moltbook/client.py:144` duplicates the Authorization-header derivation, and its comment
      is stale.** `client.py`'s `_auth_header()` and `transport.py`'s former `_auth_headers()`
      both spelled `f"Bearer {api_key}"` independently; `client.py:143` still describes itself as
      "the ONLY place the key is touched", which `transport.py` has made inaccurate. C2's DRY
      helper (`auth_headers()`) is deliberately **transport-scoped** and does not consolidate the
      cross-module pair: doing so would reach outside C2's authorized boundary and would ripple
      into `tests/test_moltbook_credential_integrity.py:196`, which asserts on
      `client._auth_header()`. Parked by operator direction 2026-08-16. Note this duplication is
      the same drift class the transport-scoped helper exists to prevent, observed one layer up.

- [ ] **The disposition of an `AMBIGUOUS` verification outcome is unresolved — carried
      here as C1 §8 item 7 requires, not quietly resolved by C2.** C1 §6 records the gap
      and declines to close it: the outcome is *recorded* (`CaptchaAttemptRecord`, and
      `send()` reports `PENDING_VERIFICATION` + `REQUIRED`), but **nothing consumes it** —
      not counted (by design; ambiguity is not evidence), not reconciled, not escalated.
      Its send-layer counterpart has somewhere to go: `AMBIGUOUS_WRITE` routes to transport
      spec §9 reconciliation. C2 implemented the classification and preserved the evidence
      **without** inventing a route, because giving `CaptchaVerifier` reconciliation or
      escalation responsibilities is an architectural change C1 §1 ruled out of C1's scope
      and which needs its own ruling. **Consequence stated in C1 §6 and not to be
      rediscovered later:** since `AMBIGUOUS` never increments the consecutive-confirmed-
      failure counter, a systematic condition producing only ambiguous outcomes — repeated
      409s, sustained 429s, a persistent network fault — will never engage
      `captcha_suspension_risk`, and content accumulates in `PENDING_VERIFICATION` with no
      automatic signal. That is correct under the counter's own semantics and is exactly
      why this needs settling **before unattended operation**, though C1 §6 records it as
      not blocking GO-2, since §E is human-executed and captures all three statuses.

- [x] **Test-count sync deferred to the C2-complete commit — DONE 2026-08-17.** `CLAUDE.md`,
      `TODO.md` and `README.md` stated a suite count that active C2 work had moved. Deferred by
      operator decision 2026-08-16 to be synced **once**, at the C2-complete count, rather than
      resynced at each intermediate commit — each restatement being another opportunity to
      record a wrong number. Unlike PR #69's situation, that mismatch was an intermediate count
      inside active work, not a completed state the docs failed to follow. All three synced to
      **647 passing + 7 xfail** in the C2 classification-contract commit.

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

- [ ] **PG-2 — `approval_trace_id` on a live envelope is bound to no resolution trace**
      (**issue #64**).
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

- [ ] **PG-3 — `arbiter` block is mandatory at validation time but has no runtime consumer**
      (**issue #65**). `_check_arbiter_required` (`pi_script/validator.py:608`) refuses to load a
      policy without an `arbiter` block; `_process_arbiter` parses it into `ir["arbiter"]`. Nothing
      then reads it: `pi_script/resolver.py` has zero references, and across the whole `pi_script/`
      package the identifier appears in `validator.py` only. All four fields —
      `acceptable_evolution`, `never_acceptable`, `requires_human_review`, `acceptance_monitor` —
      are parsed, stored, and never consulted. **Not currently an enforcement defect:** no runtime
      self-modification pathway exists anywhere in `pi_script/` or `rift/` for the arbiter to
      govern, so the block has nothing to rule on and nothing is escaping a control that would
      otherwise fire. **The risk is misreading, not bypass** — `moltbook.pi`'s `never_acceptable`
      names `credential_integrity_removal`, `key_isolation_bypass`, and `presend_gate_disable`,
      which read as live prohibitions and are inert text; and `rift/compiler.py:173` already emits
      an empty `acceptable_evolution:  []` placeholder whose only purpose is to satisfy the gate.
      No ruling records enforcement as deferred, so the block's status is undocumented rather than
      decided. Whether to wire a consumer when a self-modification pathway lands, document the
      block as declarative until then, or relax the mandatory requirement is a governance decision
      about Ruling 9.7 and is not settled here. Surfaced 2026-08-08 during operator review of the
      §A4 rehearsal evidence, in the course of establishing that the row's "Arbiter decision" means
      the resolver's permission decision (transport spec §9/§11, `CLAUDE.md`) and not this block.
      Does not move the GO-1 preparation baseline.

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
