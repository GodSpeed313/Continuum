# M7 — Operator GO Checklist (First Live Post)

**Status: DRAFT — pending operator review and sign-off.** Non-binding on
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md`; amends no numbered section there.
This checklist exists to make the go decision itself auditable — a discrete, dated, signed
artifact — rather than an informal judgment call. It governs only the decision to (a) begin live
`submit_captcha_fn` wiring against the real `POST /api/v1/verify` endpoint and (b) transmit the
first live governed post or reply. It does not re-decide anything the transport spec, its Notes,
or the Pi Script constraint rulings already settled.

**No item on this checklist may be marked complete from memory or general confidence.** Each item
carries four fields — `Status` / `Evidence` / `Verified by` / `Verified at` — and all four must be
filled before the item counts as satisfied.

**Who may fill `Verified by`.** In Continuum's current single-operator deployment model, the
operator may serve as `Verified by`. This checklist does not invent a second reviewer that doesn't
exist. But `Verified by` must always name the accountable human, never an automated agent or tool
— test output, trace artifacts, and Claude-assisted analysis may all serve as `Evidence`, but none
of them may be recorded as the verifier. A human reviews and signs; automation only produces
material for that review.

**Two-stage authorization, with four immutable identity layers.** A single broad GO would
authorize preparation and transmission under one signature, leaving execution-critical documents
unwritten at the moment "GO" is said, and would let an approval outlive the exact code/payload it
was granted for. This checklist splits authorization into GO-1 (permits preparation) and GO-2
(permits one specific transmission, single-use):

```
GO-1
  preparation_baseline_commit

Preparation (§C)
  wiring implementation and operational documents

GO-2
  execution_candidate_commit
  action_id
  payload_hash
  config_version
  authorization expiry

Execution (§E)
  clean-tree confirmation
  immediate kill-switch precheck
  transmission and terminal evidence
```

---

## A. Preliminary Readiness Review — gates GO-1

### A1. Longitudinal grounding

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| T3 cohort re-sample complete (~2026-07-30 target) | Complete | T3 captured 2026-08-02 at T0+17d — three days after the ~2026-07-30 target. The slip is recorded as it occurred and is not adjusted. Capture file `Moltbook_Longitudinal_Cohort_T3__2026-08-02.md` is held outside this repository as of this entry; committing the grounding result is row 4 of this table and remains open. | Kevin Brown | 2026-08-03 12:56 EDT |
| IdentityIntegrity cross-session change-rate grounding record derived from real T0–T3 cohort data and committed to `docs/` — no number invented, no enforcement threshold adopted (mirrors §14.1/§14.2's discipline) | Complete | Grounding delivered as a documentation act: `docs/m7_identity_integrity_ruling_addendum_2.md`, which amends base ruling §5 (the named cross-session gap). Observation: 0 of 8 profiles changed any of the six defined identity-stable fields across four independent reads (T0 2026-07-16 → T3 2026-08-02) = 136 profile-days, 0 events; 95% upper bound by the rule of three ≈ 0.022 changes/profile-day. **No enforcement threshold was adopted.** §B2 records why the observation cannot validate one: no positive example of a legitimate cross-session change exists, so the false-positive rate of any detector tuned to this data is unmeasured rather than measured-low, and the identity-stable field set is not closed (T3 surfaced platform-awarded badges outside the T0 taxonomy — had they been in scope the read would have scored 3/8 "drift" from a platform schema change no agent initiated). The T3 boundary statement is carried verbatim into §B2. §B5 rules IdentityIntegrity v1.1 post-GO under four named preconditions and makes this checklist the single authoritative readiness document; `TODO.md` was amended in the same change to remove the conflicting implication that GO-1 is blocked on v1.1 implementation. | Kevin Brown | 2026-08-04 12:10 EDT |
| CadenceIntegrity's second A1.6 falsification check (±5s grounding, Amendment 1) executed against T3; outcome reviewed and resolved through Amendment 2 (see Evidence) | Complete | Executed at T3 (2026-08-02). Check (a) passed — the flagship metronome satisfied the expected grounding condition. Check (b) triggered the Amendment 2 review condition: the observed result contradicted A1.2's account-specific wording. Amendment 2 (`docs/m7_cadence_integrity_ruling_amendment_2.md`, LOCKED 2026-08-03, merged `8115876`) resolved this as a specification-language defect rather than a detector defect by replacing account-specific references with shape-based language. No parameter, detector behavior, code, fixture, or test changed. §A2.7 records completion of the standing falsification process. | Kevin Brown | 2026-08-03 13:10 EDT |
| Grounding result committed to `docs/` (addendum to `m7_identity_integrity_ruling.md` / `m7_cadence_integrity_ruling_amendment_1.md`, or a new dated note) — not left only in session memory | Complete | Both grounding dimensions are now committed. **Identity:** `docs/m7_identity_integrity_ruling_addendum_2.md` (addendum to `m7_identity_integrity_ruling.md`), which reproduces the cohort, the six-field set, the per-read result, the exposure and rule-of-three bound, the badge method finding, and the verbatim boundary statement — §B6. **Cadence:** `docs/m7_cadence_integrity_ruling_amendment_2.md` (LOCKED 2026-08-03, merged `8115876`), which resolved the T3 falsification outcome and, at §A2.7, discharged Amendment 1's standing A1.6 check. Provenance limit stated plainly: the four raw capture files `Moltbook_Longitudinal_Cohort_T0–T3` remain outside version control in the operator's local `Downloads` directory. §B6 reproduces the identity findings in full inside the repository so the evidence chain does not depend on them; archiving the raw captures (or an equivalent mechanism) remains an open provenance item and is not a GO-1 precondition. | Kevin Brown | 2026-08-04 12:11 EDT |

### A2. Engineering completeness (per CLAUDE.md test expectations)

Do not gate on a fixed pass count — the number will legitimately change as scaffold work, T3
documentation, or captcha-wiring tests are added. Gate on a named commit and its own recorded
result instead. This is the **preparation baseline** only — a separate, later commit is what
actually executes under GO-2 (see §D):

```
preparation_baseline_commit:   <git sha reviewed at GO-1>
test_result:
  passed:
  xfailed:
  xfail_census_reference:      <doc/commit where the current xfail census is enumerated>
```

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| Full suite green at `preparation_baseline_commit` — no failures | | | | |
| Every xfail present in the committed xfail census; none added, removed, or changed without a reviewed explanation | | | | |
| Implementation Note E's required test coverage (full/empty/partial captcha config, write-with-verification flow, confirmed-failure flow, ambiguous-outcome flow, trusted-agent no-verification flow, `verification_code` binding, expiry-from-`expires_at`, no-pacing assertion) implemented and passing | | | | |
| Dry Run mode (§11) exercised; structural isolation confirmed (production ingestion rejects the reserved Dry Run identifier namespace) | | | | |
| Kill switch (§10) manual activation (`KillSwitch.activate_manual(operator=...)`) and re-enablement (`KillSwitch.clear(operator=...)`) both exercised outside Dry Run isolation testing, with a `KillSwitchActivation` audit record produced and reviewed | | | | |

**Scaffold hooks remain explicitly non-gating for M7 deployment.** (Full finding relocated to
`docs/scaffold_hooks_reconstruction_note.md` — this checklist stays narrowly executable and does
not carry unrelated infrastructure-debt design discussion.)

### A3. Deployment packet reviewed

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| `docs/m7_first_live_post_governed_envelope.md` read in full, including its explicit terminal-state discharge condition (§5) | | | | |
| This checklist read in full, including the two-stage GO-1/GO-2 split, before any item below is marked | | | | |
| §9 reconciliation-and-freeze path and manual kill switch understood as distinct from — and insufficient for — correcting or withdrawing an already-visible published post (this gap is exactly why §C requires a dedicated Published-Outcome Correction and Withdrawal Procedure before GO-2) | | | | |

### A4. Rehearsal

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| At least one Dry Run (§11) executed against a payload representative of the intended first post/reply — same shape, same `action_type` — producing detector results, Arbiter decision, approval trace, Approved Action Envelope, and simulated transport outcome, reviewed and free of surprises | | | | |

---

## B. GO-1 — Deployment Preparation Authorization

Requires all of §A complete (every item's four fields filled). Authorizes the *start* of
preparation work in §C — it does **not** authorize transmitting the first live post.

```
Status:
Evidence (pointer to completed §A record):
Authorized by (operator):
Authorized at:
Statement: "I have reviewed §A in full, at preparation_baseline_commit, and
            authorize deployment preparation — live submit_captcha_fn wiring,
            connectivity validation without transmission, and drafting of the
            runbook and correction/withdrawal procedure — to begin. This
            authorization does not permit the first live post."
```

This record is saved as its own dated artifact (e.g. `docs/m7_go1_decision_<date>.md`), not left
as an unrecorded verbal/mental decision.

---

## C. Preparation Work — performed under GO-1, gates GO-2

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| **C1.** Live CAPTCHA wiring plan completed — not required for §A's preliminary review, but required before wiring begins | | | | |
| **C2.** `submit_captcha_fn` wired live against real `POST /api/v1/verify`; `captcha_verifier`/`submit_captcha_fn` both-or-neither invariant confirmed at construction (Note E item 7); reviewed | | | | |
| **C3.** Endpoint connectivity validated — see wording below; **no governed post/reply and no synthetic CAPTCHA submission** issued solely as a connectivity probe | | | | |
| **C4.** First-post runbook finalized (step-by-step execution script for §E below) | | | | |
| **C5.** Published-Outcome Correction and Withdrawal Procedure finalized — must explicitly distinguish: delete (when supported), edit/correction (when supported), corrective follow-up (when neither is available), freeze-and-escalation (§9), and audit preservation. This is not a "rollback" in the atomic-reversal sense — most external APIs offer no such thing, and the procedure must not imply otherwise | | | | |

C1 must be satisfied before C2 begins. C2–C5 may proceed in parallel once C1 is done, but all five
must be complete before §D can be sought.

**C3 wording (binding):** Live API authentication and required endpoint reachability are validated
using **documented non-publishing operations only** (e.g. auth handshake, health check, feed
read). No synthetic CAPTCHA submission, governed post, reply, or other write is issued solely as a
connectivity probe — `POST /api/v1/verify` is not assumed to be safely callable outside a real
challenge, since a verification endpoint may require a genuine challenge and may mutate
server-side state. The real `/verify` path is exercised for the first time only when an actual
governed post legitimately produces a challenge during §E, unless the platform documents an
explicit sandbox or validation mechanism (none is currently known).

---

## D. GO-2 — First Governed Transmission Authorization

**GO-2 is single-use.** It authorizes exactly one transmission, bound to one exact combination of
code, payload, and configuration — not a standing permission that stays open across later changes.

```
execution_candidate_commit:      <git sha actually executing the send — distinct from
                                   preparation_baseline_commit; must postdate C1–C5>
test_result:
  passed:
  xfailed:
  xfail_census_reference:
tree_state:                      clean / <describe any diff> — must be clean to proceed

authorized_action_id:
authorized_payload_hash:
authorized_execution_commit:
authorized_config_version:
authorization_expires_at:
consumed_at:                     <filled only after §E executes, or left blank + voided if
                                   authorization_expires_at passes unused>
```

Requires:

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| §C1–C5 all complete, each with recorded evidence | | | | |
| Full suite green at `execution_candidate_commit`; no uncommitted changes in governed execution paths (a SHA does not prove the running workspace matches it unless the tree is clean) | | | | |
| First-Post Rider (`docs/m7_first_live_post_governed_envelope.md` §2) fully populated — `action_id`, `t3_grounding_reference`, `dry_run_rehearsal_reference`, `captcha_configuration_state`, `kill_switch_precheck`, `operator_go_reference` (this GO-2 record), `correction_procedure_reference` (pointing to the now-finalized C5 procedure), `execution_commit_reference` (pointing to `execution_candidate_commit`) | | | | |
| Exact payload and its `payload_hash` reviewed and approved by the operator | | | | |
| `KillSwitch.engaged` confirmed `False` at review time | | | | |

```
Status:
Evidence (pointer to completed §C + rider record):
Authorized by (operator):
Authorized at:
Statement: "I have reviewed the completed wiring, runbook, and
            correction/withdrawal procedure, the exact payload, envelope,
            and execution_candidate_commit for this action, and authorize
            exactly one live governed transmission bound to the identifiers
            above. Any payload, configuration, envelope, governed-code,
            credential, or target-action change invalidates this
            authorization and requires a new GO-2 record."
```

Saved as its own dated artifact (e.g. `docs/m7_go2_decision_<date>.md`). This section is
intentionally manual — mirrors §10's kill-switch re-enablement rule (only the operator restarts
execution) applied in reverse: only the operator starts it. No automated check or CI green state
may substitute for this record.

---

## E. Execution — under GO-2

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| Clean-tree confirmation re-checked immediately before send (workspace still matches `execution_candidate_commit`) | | | | |
| `KillSwitch.engaged` reconfirmed `False` immediately before send; operator has a tested, reachable `activate_manual(operator=...)` path open during the send | | | | |
| First live send executed under the standard `ActionEnvelope` referenced by the First-Post Rider; `authorized_action_id` and `authorized_payload_hash` match exactly | | | | |
| Resulting `transmission_status` / `publication_status` / `verification_status` recorded; RESOLUTION TRACE and, if verification ran, `CaptchaAttemptRecord` captured; `consumed_at` recorded on GO-2 | | | | |
| If outcome is `OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE`: no retry, freeze, escalate to operator per §9 — silence/ambiguity is never treated as success or failure. Per the envelope doc §5, the rider stays **active** (not discharged) until this resolves to a non-ambiguous terminal state | | | | |
| If `PUBLISHED` but incorrect: Published-Outcome Correction and Withdrawal Procedure (§C5) executed; rider discharged per envelope doc §5(3)(c) only once that procedure completes | | | | |

---

## Scaffold-hooks debt — one line, non-gating

Scaffold hooks remain explicitly non-gating for M7 deployment. The fuller finding (PR #30 hooks
were never committed — `.gitignore` excludes `.claude/*` except `.claude/skills/`, so any hook
files were always local-only; recovery vs. reconstruction is an open architectural question about
whether hooks are user-local tooling or tracked project infrastructure) lives in
`docs/scaffold_hooks_reconstruction_note.md`, kept separate from this operational checklist.
