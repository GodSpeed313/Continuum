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
preparation_baseline_commit:   008d3ba92d33d2f5a55924a5aa54e9b8551c364c  ("Note E Correction 1 …", #58)
test_result:
  passed:                      590
  xfailed:                     7
  failed:                      0
  errors:                      0
  xfail_census_reference:      TODO.md, "### xfail census (7 — deliberate known-gap pins, not
                               failures)", as it stands at 008d3ba
```

**The run behind this block was executed on `main` after #58 merged, not on the PR branch.** The
claim §A2 makes is "main at `preparation_baseline_commit` is the prepared state," not "the patch
passed review." A green PR branch does not establish the former — merge order, squash, and any
concurrent merge sit between the two — so the post-merge run on the named commit is the only run
that can satisfy this section, and it is not skipped on the grounds that the same tests already
passed once.

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| Full suite green at `preparation_baseline_commit` — no failures | Complete | `python -m pytest` executed 2026-08-05 20:01 EDT on `main` at `008d3ba`, working tree clean (`git status --porcelain` empty — a SHA alone does not prove the workspace matches it). Result: **590 passed, 7 xfailed, 0 failed, 0 errors**, 1 warning, 11.51s. Environment: Python 3.12.10, pytest 9.0.3, Windows. The single warning is `StarletteDeprecationWarning` from `tests/test_dashboard.py` (`httpx` with `starlette.testclient`) — a third-party deprecation notice, not a governed-path signal, and it does not affect any result above. This is the post-merge run on the named commit, per the discipline recorded in the header block; the pre-merge run on #58's branch is not accepted as a substitute. Counts agree with `CLAUDE.md`, `README.md`, and `TODO.md`, which #58 synced to 590. | Kevin Brown | 2026-08-06 00:00 EDT |
| Every xfail present in the committed xfail census; none added, removed, or changed without a reviewed explanation | Complete | Enumerated rather than counted — a matching total would not have detected a substitution. `pytest -rx` at `008d3ba` reports exactly 7 xfails, and each maps to a census line in `TODO.md`. **3 × CredentialIntegrity encoding exfil** (ruling §4): `test_base64_encoded_foreign_key_is_a_known_gap`, `test_reversed_foreign_key_is_a_known_gap`, `test_split_foreign_key_is_a_known_gap`. **3 × IdentityIntegrity**: `test_semantic_persona_drift_is_a_known_gap` (ruling §6, deferred to v1.1), `test_quoted_reported_speech_is_a_known_false_positive` (addendum A4 — exclusion zones deliberately not implemented, they would be an evasion channel), `test_truncated_name_with_trailing_chatter_is_a_known_false_positive` (addendum A2 residual). **1 × captcha solver**: `TestCaptchaSolver::test_whitespace_shattered_words` (Note F §F.5 residual). No xpass occurred — an xpass here would mean a pin silently outlived its gap and would require review before this row could stand. Census is unchanged at 7 across #58, which states so explicitly in its own record. Each pin cites the ruling or note that authorizes it; none is an unexplained pin. | Kevin Brown | 2026-08-06 00:00 EDT |
| Implementation Note E's required test coverage (full/empty/partial captcha config, write-with-verification flow, confirmed-failure flow, ambiguous-outcome flow, trusted-agent no-verification flow, `verification_code` binding, expiry-from-`expires_at`, no-pacing assertion) implemented and passing | Complete | Verified bullet-by-bullet against Note E's "Required test coverage (implementation pass)" list **as corrected on 2026-08-05**, all in `tests/test_moltbook_transport.py`. (1) *Config fail-closed* — `TestNoteEFailClosedConfiguration`: full accepted, empty accepted, verifier-without-submit and submit-without-verifier each rejected at construction, plus `test_fetch_captcha_challenge_is_retired`. (2) *Write-with-verification* — `TestNoteECaptchaFlow::test_passed_verification_publishes_with_one_write_and_one_verify`, challenge parsed from the committed fixture shape (`TestNoteEVerificationBlockParsing`), not an assumed one. (3) *Confirmed failure* — `test_confirmed_failure_classifies_not_published_and_counts` (`SUCCESS` transmission + `NOT_PUBLISHED`/`FAILED`, count increments) and `test_third_consecutive_failure_fires_trigger_and_blocks_next_send`. (4) *Ambiguous* — `test_ambiguous_verification_stays_pending_uncounted_unretried`: stays `PENDING_VERIFICATION`, no increment, no retry. (5) *Trusted agent* — `test_trusted_agent_path_is_first_class`: `NOT_REQUIRED` + `PUBLISHED`, zero verify calls. (6) *`verification_code` binding across all three surviving surfaces* — attempt record (`test_attempt_binds_action_and_verification_code_identifiers`), audit extra (`TestCaptchaVerifier::test_third_consecutive_confirmed_failure_activates`, asserting `entry.extra["verification_code"]`), result `detail` (`test_result_detail_carries_the_verification_code_binding`, added by #58); non-reuse across actions by `test_each_write_binds_its_own_verification_code_never_reused`. (7) *Expiry from `expires_at` only* — `test_expired_challenge_honors_platform_expires_at_only` and `test_non_default_expiry_window_flows_with_no_constant_interfering`. (8) *No pacing* — exactly one verify call per solved challenge asserted at `test_passed_verification_publishes_with_one_write_and_one_verify` (`len(write_calls) == 1 and len(verify_calls) == 1`); no sleep, scheduler, or auto-retry exists in the verification path to assert against. **This row's review is what surfaced Note E Correction 1, and the defect class matters more than the fix.** Bullet 6 previously required the binding be proven across "exception surfaces" — `CaptchaVerificationFailed` / `CaptchaVerificationAmbiguous` — which the implementation had already retired as the correct consequence of Note E point 2 (the write has reached the platform before verification runs, so a verification outcome is a classified fact on the result, never an exception that would discard the transmission facts). The specification therefore kept asserting authority over a mechanism it had itself removed. It presented as missing coverage; it was **binding-authority drift**, and it is recorded as such in the transport spec's Correction 1 rather than only in a commit message. Resolved 2026-08-05 by correcting the specification and proving the surviving surface by one test — accepted by operator ruling, which settled the governance decision and is not an attestation of Correction 1's wording. No detector, parameter, threshold, fixture, or transport behavior changed. | Kevin Brown | 2026-08-06 00:00 EDT |
| Dry Run mode (§11) exercised; structural isolation confirmed (production ingestion rejects the reserved Dry Run identifier namespace) | Complete | Exercised by `tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py`, whose expected transcript is committed alongside it; `--check` re-run at `008d3ba` on 2026-08-05 reports "transcript matches the committed expected output" (exit 0). Evidence is a committed, re-executable artifact rather than a session transcript — deliberately, after the T0–T3 provenance lesson. Observed: dry run performs real envelope validation and makes **no** network call, and `DryRunTransport` exposes no `request_fn` parameter at all, so the absence of a network seam is structural, not a runtime flag that could be flipped; it returns `DryRunOutcome` (a distinct type, not `TransportResult`) with `simulated_*` statuses and an instance-local trace; it refuses a non-namespaced production `action_id` with a loud `ValueError`. **Structural isolation was confirmed by direct attempted ingestion, bypassing the transport entirely** — the weaker test would have been to check only that the transport declines to emit. `CadenceObservationStore.ingest` and `CitationEdgeStore.ingest` both reject a `dryrun-` id (`was_new=False`, counts stay 0), while a real id ingests normally (`was_new=True`, count 1), proving the rejection is namespace-specific and not a store silently dropping everything. No production state touched; stores run in a temporary directory. | Kevin Brown | 2026-08-06 00:00 EDT |
| Kill switch (§10) manual activation (`KillSwitch.activate_manual(operator=...)`) and re-enablement (`KillSwitch.clear(operator=...)`) both exercised outside Dry Run isolation testing, with a `KillSwitchActivation` audit record produced and reviewed | Complete | Exercised by the same committed artifact (`--check` clean at `008d3ba`, 2026-08-05), and — as the row requires — **against the live `MoltbookHTTPTransport` with a recording stub in the `request_fn` seam, not against `DryRunTransport`**, so the behavior shown is the production class's. Full cycle observed: baseline disengaged, governed write transmits (`POST /posts`); `activate_manual(operator=...)` → `engaged=True`; while engaged, writes raise `KillSwitchEngaged` with **0 network calls attempted** (fail-closed — blocked before transmission, not after), reads continue to succeed, and a successful read does **not** clear the switch (no automatic recovery); `clear(operator=...)` → `engaged=False`; a governed write transmits again. Three network calls total, all accounted for. `KillSwitchActivation` records produced and reviewed field-by-field for both the engage and the clear — the log records the clearance too, not only the activation: `mode='manual'`, `trigger='operator_command'` / `'operator_clear'`, `timestamp`, `affected_action_class='*'`, `detail`, `extra`. **One defect surfaced and is recorded, not absorbed:** the operator identity reaches the audit record only as free text inside `detail` (`'operator=…'`) rather than as a structured field, so it cannot be queried or validated. Filed as issue #57 and ruled **post-GO** — it does not block GO-1 and does not move `preparation_baseline_commit`, because the record required by §10 is produced, complete, and reviewable; the gap is in its shape, not its existence. Recorded in `TODO.md` under post-GO engineering debt so the ruling survives this checklist. | Kevin Brown | 2026-08-06 00:00 EDT |

**Scaffold hooks remain explicitly non-gating for M7 deployment.** (Full finding relocated to
`docs/scaffold_hooks_reconstruction_note.md` — this checklist stays narrowly executable and does
not carry unrelated infrastructure-debt design discussion.)

### A3. Deployment packet reviewed

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| `docs/m7_first_live_post_governed_envelope.md` read in full, including its explicit terminal-state discharge condition (§5) | Complete | Attestation is bound to `docs/m7_first_live_post_governed_envelope.md` **as it stands at `e4aba53`** — 117 lines, header plus five numbered sections, `Status: DRAFT`. Coverage confirmed section by section. **§1:** the first-post rider is additive to the standard `ActionEnvelope`; no change to the dataclass, its `approve()` constructor, or `validate_envelope`'s three rejection checks (expired, config drift, payload drift); the rider is a governance artifact and does not touch `moltbook/transport.py`. **§2:** all eight required rider fields and their sources, and the rule that an empty or `"N/A"` field is a stop, not a waiver — with no interim-fallback case remaining. **§3:** the two-stage chain; GO-1 authorizes preparation including live `submit_captcha_fn` wiring but never transmission; GO-2 is single-use and bound to one `action_id`, one `payload_hash`, one `execution_candidate_commit`, and one `governance_config_version`, with an explicit expiry, any change to payload/code/configuration/credentials invalidating it; execution out of this order is a process violation of the document **independent of whether the resolver would have approved the underlying action**. **§4:** the four explicit non-effects, including that the document does not by itself authorize live captcha wiring (Note E's closing stop condition). **§5 — the terminal-state discharge condition named by this row:** obligations end only when all three hold — (1) a non-ambiguous terminal state, `publication_status` `PUBLISHED` or `NOT_PUBLISHED` and `verification_status` one of `PASSED`/`FAILED`/`EXPIRED`/`NOT_REQUIRED`, never a bare `REQUIRED`, with `OUTCOME_UNKNOWN`/`AMBIGUOUS_WRITE` explicitly **not** terminal and **no default timeout**; (2) every required trace persisted — the RESOLUTION TRACE, and the corresponding `CaptchaAttemptRecord` where verification was required; (3) a written operator act — acceptance of a `PUBLISHED` outcome, completion of §9 reconciliation for a resolved `OUTCOME_UNKNOWN`, or completion of the §C5 Correction and Withdrawal Procedure. The rider therefore cannot discharge through elapsed time, nor through transmission alone. Verified during this reading that the cited checklist sections (§C5 and §D) and the two grounding documents named by `t3_grounding_reference` are present at `e4aba53`. **This row attests to the operator's reading and understanding of the document at the identified repository state; it does not attest that the document is correct, complete, content-frozen, or independently authorized.** **This attestation is version-bound and confers no authority over the document's future contents.** The document is not content-frozen at `e4aba53`; a material change to it requires a fresh attestation rather than inheriting this one. Two findings were identified during the reading and are deliberately recorded here rather than resolved, neither affecting the truth of this row: (a) the document imposes GO-2 gating obligations while still marked `Status: DRAFT`, and (b) §3 states `t3_grounding_reference` must be populated before GO-1, whereas this checklist carries the rider only at §D (GO-2) and §E. Both are separate governance acts and were not undertaken as part of this reading. | Kevin Brown | 2026-08-07 17:55 EDT |
| This checklist read in full, including the two-stage GO-1/GO-2 split, before any item below is marked | Complete | Attestation is bound to `docs/m7_operator_go_checklist.md` **as it stands at `079b3c1`** — 233 lines, header block plus §A (A1–A4), §B, §C, §D, §E, and the closing scaffold-hooks note. Coverage confirmed section by section. **Header (lines 1–48):** `Status: DRAFT`; non-binding on the transport spec and amending no numbered section there; scope limited to the two decisions of (a) beginning live `submit_captcha_fn` wiring and (b) transmitting the first governed post or reply; the four-field rule that no item may be marked complete from memory or general confidence; the `Verified by` rule that the accountable human must always be named and that test output, trace artifacts, and Claude-assisted analysis may serve as `Evidence` but never as the verifier; and **the two-stage GO-1/GO-2 split named by this row**, including the three stated reasons a single broad GO was rejected — one signature covering both preparation and transmission, execution-critical documents left unwritten at the moment "GO" is said, and an approval outliving the exact code/payload it was granted for — together with the four identity layers pinned at GO-2. **§A:** the four subsections gating GO-1; A1 and A2 complete, A3 row 1 complete, A3 rows 2–3 and A4 open. **§B:** GO-1 requires all of §A complete, authorizes only the *start* of §C preparation, explicitly does not authorize transmission, and is recorded as its own dated artifact rather than as a row in this checklist. **§C:** C1–C5 and the ordering constraint (C1 before C2 begins; C2–C5 may run in parallel; all five before §D may be sought), plus the binding C3 wording — connectivity validated using documented non-publishing operations only, with no synthetic CAPTCHA submission or probe write, and the stated consequence that the real `POST /api/v1/verify` path is exercised for the first time only when an actual governed post legitimately produces a challenge during §E, no sandbox mechanism being known. **§D:** GO-2 is single-use, bound to one `execution_candidate_commit`, `action_id`, `payload_hash`, and `config_version` with an explicit expiry and a `consumed_at` field that voids unused on expiry; its five gating rows including full rider population; and the rule that no automated check or CI green state may substitute for the record, mirroring §10's re-enablement rule in reverse. **§E:** the six execution rows — immediate pre-send clean-tree and kill-switch rechecks with a tested reachable `activate_manual` path, exact `authorized_action_id`/`authorized_payload_hash` match, capture of all three statuses plus RESOLUTION TRACE and `CaptchaAttemptRecord` with `consumed_at` written back to GO-2, the ambiguity rule that silence is never treated as success or failure, and the correction path discharging the rider only once the §C5 procedure completes. **Scaffold-hooks note:** explicitly non-gating, full finding held in `docs/scaffold_hooks_reconstruction_note.md`. **This row's own precondition — "before any item below is marked" — was verified rather than assumed.** At `079b3c1` every table row below this one (A3 row 3, A4, §C1–C5, §D's five rows, §E's six rows) is blank in all four fields, and the §B and §D authorization blocks are unfilled. Everything already marked — A1, A2, and A3 row 1 — sits above this row. Verified during this reading that the following cited references are present at `079b3c1`: transport spec §2, §4, §8, §9, §10, §11, and §14; §10's re-enablement rule that §D cites, reading "Only the operator may clear the kill switch"; Implementation Note E; `docs/scaffold_hooks_reconstruction_note.md`; `docs/m7_identity_integrity_ruling.md`; `docs/m7_cadence_integrity_ruling_amendment_1.md`; `tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py`; and TODO.md's xfail census. §E's `transmission_status` was additionally checked against the implementation and is a real property alias of `TransportResult.outcome` (`moltbook/transport.py:335`), not a reference to a field that does not exist. **This row attests to the operator's reading and understanding of the document at the identified repository state; it does not attest that the document is correct, complete, content-frozen, or independently authorized.** **This attestation is version-bound and confers no authority over the document's future contents.** The document is `Status: DRAFT` and is not content-frozen at `079b3c1`; a material change to its content requires a fresh attestation rather than inheriting this one. Recording this attestation — this row's own Status, Evidence, and signature — registers the reading and is not itself a change to the content attested to. One finding was identified during the reading and is recorded here rather than resolved: §B's authorization statement reads "I have reviewed §A in full, at `preparation_baseline_commit`," whereas §A's rows are necessarily signed at successive commits over time. That is a §B drafting matter to settle when the GO-1 record is written, is a separate governance act, and was not undertaken as part of this reading. | Kevin Brown | 2026-08-07 18:52 EDT |
| §9 reconciliation-and-freeze path and manual kill switch understood as distinct from — and insufficient for — correcting or withdrawing an already-visible published post (this gap is exactly why §C requires a dedicated Published-Outcome Correction and Withdrawal Procedure before GO-2) | Complete | Attestation is bound to the mechanisms as specified at `af3fd24`: transport spec §9 (Reconciliation Authority) and §10 (Kill Switch). **§9:** authority is separated — the resolver determines permission only and never execution success; the transport reports only `SUCCESS`/`FAILURE`/`OUTCOME_UNKNOWN`; the reconciliation layer attempts deterministic confirmation from platform evidence (idempotency lookup, receipt lookup, deterministic action matching, deterministic payload matching), recording SUCCESS or FAILURE if resolved and, if unresolved, freezing outbound execution, escalating to the operator, and never retrying while `OUTCOME_UNKNOWN` exists. **§10:** activation is manual by explicit operator command or automated under exactly two conditions active at lock time — unresolved ambiguous writes and reconciliation contradictions, with repeated integrity failures and authentication anomalies dormant per §14; behavior is fail-closed and "immediately blocks all outbound writes" while permitting safe reads; re-enablement is operator-only; every activation produces a structured audit record, a boolean indicator being insufficient. **The insufficiency is understood in three layers.** (1) Both mechanisms act on *future outbound writes*: a freeze stops the next write, and recording an outcome describes what already happened without altering it — neither has any operation reaching a post already visible on the platform. (2) A post that transmits successfully, publishes successfully, and is simply incorrect triggers **neither** mechanism: §9 resolves it as SUCCESS, and neither active automated kill-switch condition applies because nothing is ambiguous and nothing contradicts, so a clean success carrying wrong content is invisible to both. (3) The gap is **structural, not merely procedural** — at `af3fd24` the governed action vocabulary is `ActionType = {POST, REPLY}` (`moltbook/transport.py:44-46`) with no delete, edit, or withdraw member, and the entire `moltbook/` package issues only `GET` and `POST`, with no `DELETE`, `PATCH`, or `PUT` anywhere; even where a platform supported takedown, no governed action exists today that could invoke it, and such an action would itself require a new `ActionType` and its own approved envelope. **Therefore §C5 is not redundant with §9 or §10**, and its requirement to be finalized before GO-2 follows from the fact that nothing already in the system performs its function; its required distinctions — delete when supported, edit/correction when supported, corrective follow-up when neither is available, freeze-and-escalation under §9, and audit preservation — exist because the first two mechanisms are the only tools currently available and neither addresses published state. The envelope document's `correction_procedure_reference` entry makes the same point and is deliberately named *correction and withdrawal* rather than "rollback." **This row attests to the operator's understanding of these mechanisms as specified at the identified repository state; it does not attest that §9, §10, or §C5's stated requirements are correct, complete, content-frozen, or independently authorized.** **This attestation is version-bound and confers no authority over the future contents of the cited specifications.** A material change to §9, §10, or §C5 requires a fresh attestation rather than inheriting this one. No finding was identified during this reading. | Kevin Brown | 2026-08-07 19:21 EDT |

### A4. Rehearsal

| Item | Status | Evidence | Verified by | Verified at |
|---|---|---|---|---|
| At least one Dry Run (§11) executed against a payload representative of the intended first post/reply — same shape, same `action_type` — producing detector results, Arbiter decision, approval trace, Approved Action Envelope, and simulated transport outcome, reviewed and free of surprises | Complete | Attestation is bound to the rehearsal artifact — `tools/go-checklist-exercises/a4_first_post_rehearsal.py` and its committed transcript `a4_first_post_rehearsal.expected.txt` — **as they stand at `cfd6897`**, confirmed byte-identical at the commit this row is signed at. `action_type` is **POST** by operator ruling 2026-08-08; the payload carries a POST shape (`content` only, no `parent_post_id` — the field whose absence distinguishes a POST from a REPLY), and `payload_hash` was checked against the payload rather than assumed. **All five artifacts the row names were produced in a single run and reviewed:** (1) *detector results* — `scan_content`, `scan_links`, `scan_identity` called as shipped, all clean, followed by the full `MoltbookClient.send()` pre-send gate reaching the transport boundary with all three latches false; (2) *Arbiter decision* — `resolve()` over `client.snapshot()`, exit code 0, `system_state: running`, `final_action: None`, with `CredentialIntegrity`, `LinkRestriction`, and `IdentityIntegrity` each `satisfied`, and the snapshot confirmed to carry no API key; (3) *approval trace* — the RESOLUTION TRACE as emitted by the shipped renderer; (4) *Approved Action Envelope* — every field displayed, `action_id` confirmed inside the reserved `dryrun-` namespace; (5) *simulated transport outcome* — the shipped `DryRunTransport`, returning `DryRunOutcome` (a distinct type, not `TransportResult`) with `simulated_outcome=SUCCESS`, and no network call, the class exposing no `request_fn` seam to make one through. **The row's "Arbiter decision" is §11's term for the permission decision and is the artifact recorded at (2):** per `CLAUDE.md` and transport spec §9 ("Arbiter — determines permission only"), the shipped component bearing that role is `pi_script/resolver.py`, and "resolver decision" is the current name for it, not a substitution of a different mechanism. The `arbiter MoltbookArbiter { … }` block is a distinct construct governing self-modification of the constraint system (Ruling 9.7); it is required at validation time or the policy does not load, has no runtime consumer in `pi_script/resolver.py`, and is not in scope for a content action. That inertness was identified during this review and is filed as PG-3 (issue #65), post-GO. **The two Longitudinal Constraints were exercised in their own governance passes and both render NOT EVALUABLE** — `CadenceIntegrity` at `0/4 required intervals`, `CitationClusterIntegrity` on ungrounded §5 parameters. That is the correct first-post state, not an omission: there is no posting history for a first post to compute from. They are included so this rehearsal accounts for all five enforced constraints rather than appearing to cover three. **The harness performs the trace-to-envelope binding itself, and the transcript discloses this immediately above the envelope, verbatim:** *"The trace-to-envelope binding below is performed by THIS SCRIPT. It does not assert that the shipped Moltbook client performs that join; it does not. In shipped code `as_client_transport` defaults approval_trace_id to a fresh uuid4 unbound to any resolver trace (filed: TODO.md post-GO debt)."* The binding digests only the ruling-relevant trace fields, excluding `timestamp` and `human_text` — when it ran, not what was ruled — which is what makes the transcript reproducible. The underlying gap is filed as **PG-2, issue #64**, as its own dated post-GO item rather than as a footnote to this row. **The rehearsal includes a negative control, and this row is not satisfied without it:** the same payload with an unsourced link, through the same pipeline and the same client construction, is blocked at the pre-send gate with `LinkBlocked` and produces no envelope and no dry run. Without it, a clean pass could not be distinguished from a pipeline whose detectors are inert — the control is what establishes that the gates are load-bearing rather than decorative, and that the clean pass above is a real pass. The blocked attempt still latches `link_violation`, per addendum A5. **Reproducibility is environment-scoped:** the transcript was generated and `--check`-verified on **CPython 3.12.10** only; it embeds `str`-mixin `Enum` members whose f-string formatting has changed across Python releases, and it was **not** executed on any other version, including the 3.11 pinned by CI — a `--check` difference on another interpreter is therefore not by itself evidence of a governance-relevant change. `--check` was additionally confirmed non-vacuous by tampering with one field of the committed transcript and observing exit 1. **This row attests that the operator reviewed a complete, reproducible-on-the-stated-environment rehearsal of the governed chain, with both the trace-binding limitation and the artifact's version-sensitivity explicitly disclosed. It does not attest that the harness, the transcript, or the underlying mechanisms are correct, complete, content-frozen, or independently authorized.** **This attestation is version-bound and confers no authority over the artifact's future contents.** A material change to the script or transcript requires a fresh attestation rather than inheriting this one. **It authorizes nothing and is not a pre-clearance of the first post's content:** detector results are content-dependent, this row's representativeness test is shape and `action_type` only, and the actual wording is bound at GO-2 via `payload_hash` (§D). | Kevin Brown  | 2026-08-08 21:17 EDT  |

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
| **C1.** Live CAPTCHA wiring plan completed — not required for §A's preliminary review, but required before wiring begins | Complete | Plan recorded as its own dated artifact, `docs/m7_c1_live_captcha_wiring_plan_2026-08-13.md`, following the GO-1 precedent of a dated record rather than a row-embedded decision. It amends no numbered section of this checklist, of `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` or its Implementation Notes, of `docs/moltbook_api_spec.md`, or of any ruling in `docs/`. **Scope ruled broad by operator on 2026-08-13:** C1 settles the semantic contract C2 implements, rather than describing the method by which C2 would discover it — the stated reason being that a narrow C1 would make the first live CAPTCHA submission the place where an unconfirmed platform response is interpreted for the first time, which is the decision this preparation gate exists to prevent. The plan settles: (§3.1) the classification principle generating the mapping — `CONFIRMED_*` only where the response establishes what happened to *this* challenge, `AMBIGUOUS` as the positive statement that a response is not evidence either way; (§3.2) detection precedence across the HTTP-status and response-envelope axes, needed because the 2026-07-21 capture pins envelopes for the success and incorrect-answer cases but not the HTTP status accompanying the latter, and pins statuses for 410/404/409 without their bodies; (§3.3) the eleven-row response-condition table, each row carrying its own evidence provenance and an explicit not-live-confirmed marker; (§3.4) HTTP 409 as `AMBIGUOUS`, treated as a first-class decision rather than a table entry, on the reasoning that "code already used" is consistent with a prior verification having *succeeded*, so classifying it as `CONFIRMED_FAILURE` would stamp `NOT_PUBLISHED` on live content and suppress the §C5 correction procedure — and that this classification stands independently of the retry ruling, since a lost response (row C1-10) produces the same observable 409 with no deliberate retry anywhere; (§4) the residual rule, unenumerated responses resolving to `AMBIGUOUS` with no silent coercion and no exception-raising, the latter because raising would make `AMBIGUOUS` unreachable through the route most likely to produce it and would contradict the three-status contract the plan settles; (§5) no retry at any layer, scoped deliberately below the HTTP client because adapter-level retry defaults would silently alter the semantics fixed at §3.3; (§6) `AMBIGUOUS` as final as a classification with its disposition after `verify()` recorded as unresolved; (§7) the requirement that `CaptchaAttemptRecord` identify which §3.3 condition matched or that none did, mandatory rather than nullable, so that predicted-ambiguous and residual-ambiguous outcomes remain distinguishable; (§8) ten C2 acceptance criteria; and (§9) five C2 stop conditions, including that any unanswerable question about `/verify` behaviour is a stop and never a reason to probe (GO-1 §5.3, §C3 binding wording). **Two items are deliberately left unresolved and are recorded as such rather than settled:** the disposition of an `AMBIGUOUS` outcome after `verify()` returns — the outcome is recorded on `TransportResult` (`moltbook/transport.py:1366–1378`) but nothing consumes it, no reconciliation and no escalation, where its send-layer counterpart `AMBIGUOUS_WRITE` routes to transport spec §9 — which is an architectural question for its own ruling, carried as C2 acceptance criterion 7 rather than resolved inside C1; and (§10) two items identified for operator attention, the expiry-counter asymmetry between the locally-declined and platform-confirmed routes, and `RateLimitInfo` at the verify seam. The plan is **version-bound to the 2026-07-21 `moltbook.com/skill.md` capture** and does not inherit forward across a material change to it: per the transport spec's own statement, "nothing has yet been confirmed against a live write," and the plan claims authority over the interpretation, not over the platform. **This row attests that the wiring plan required before C2 exists, is recorded, and has been read; it does not attest that its classifications have been empirically validated, and §2 of the plan states plainly that none of them have.** **This attestation is version-bound and confers no authority over the document's future contents.** No code was written, no transport behaviour changed, and `POST /api/v1/verify` was not called. | Kevin Brown | 2026-08-13 18:28 EDT |
| **C2.** `submit_captcha_fn` wired live against real `POST /api/v1/verify`; `captcha_verifier`/`submit_captcha_fn` both-or-neither invariant confirmed at construction (Note E item 7); reviewed | Complete | `moltbook/transport.py` (+245) and `tests/test_moltbook_transport.py` (+428) at `ce84d22`, tree clean. `submit_captcha_fn` wired against real `POST /api/v1/verify`; `captcha_verifier`/`submit_captcha_fn` both-or-neither invariant confirmed at construction (Note E item 7). Classification precedence implemented per C1 §3.2 as read by **Erratum 1** (`docs/m7_c1_wiring_plan_erratum_1_2026-08-17.md`, LOCKED, signed 2026-08-17 00:43 EDT), whose ratified reading is that §3.2 rule 1's parenthetical **should read** "§3.3 rows 3–9" rather than "rows 3–7", so that the enumerated rows C1-8 (400) and C1-9 (500) are matched by rule 1 rather than by no rule at all. The erratum is filed instead of an edit; C1's locked text is unchanged and no row's outcome differs under either reading. Suite green: **647 passed, 7 xfailed**, verified by run at `ce84d22` with a clean tree, not recalled. **This row attests that the required artifacts exist at the cited commit and that the suite is green; it does not attest to a reading of the implementation itself.** | Kevin Brown | 2026-08-20 00:19 EDT |
| **C3.** Endpoint connectivity validated — see wording below; **no governed post/reply and no synthetic CAPTCHA submission** issued solely as a connectivity probe | Complete | Validation recorded as its own dated artifact, `docs/m7_c3_endpoint_connectivity_validation_2026-08-21.md`, following the C1 precedent of a dated record rather than a row-embedded decision — the shape chosen by the operator on 2026-08-21 in preference to C2's row-only form. It amends no numbered section of this checklist, of `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` or its Implementation Notes, of `docs/moltbook_api_spec.md`, or of any ruling in `docs/`. **Executed once at 2026-08-21 19:10 UTC against the live platform, transport at `c1eb9ba`, three requests total, no retries and no second run.** The artifact's §2 derives the permitted operation set from §C3's binding wording — the two documented non-publishing reads, and nothing else. Observed: an unauthenticated redirect check on `GET /api/v1/agents/status` returned HTTP 401 with no `Location` and no redirect, confirming the path does not redirect before the credential is attached to it; the authenticated `GET /api/v1/agents/status` returned HTTP 200 with body `status: "claimed"`, yielding `EligibilityState.CLAIMED`; and `GET /api/v1/posts` returned HTTP 200 with a cursor-paginated body of 20 items. All four steps matched the prediction recorded at §4.7 of the artifact **before** the run, and the method was drafted and shown to the operator before any request was issued. **No governed post or reply was issued, no synthetic CAPTCHA submission was made, and `POST /api/v1/verify` was not called** — the probe was constructed with `captcha_verifier` and `submit_captcha_fn` both absent, which Implementation Note E's fail-closed invariant expressly permits, so it had no CAPTCHA submission capability wired into it at all rather than merely declining to use one. **This row attests that the two endpoints in the permitted set answered and that this credential authenticated as a claimed agent at that moment. It does not attest that a governed post will publish, that the CAPTCHA path works, that any endpoint outside that set is reachable, or that the credential will still be valid at §E.** Six items are recorded at §6 of the artifact for their own rulings rather than settled here; two are material. First: `check_eligibility()` returns `PENDING_CLAIM` for any response whose body lacks `status: "claimed"`, a 401 error envelope included, while `health_check()` reports `TransportOutcome.SUCCESS` unconditionally and discards the `HTTPResponse` — so a dead credential and a live unclaimed one are the same value on the transport's own return, and `EligibilityBlocked` would report an authentication failure as a claim problem. C3 recorded the raw HTTP status through a pass-through recorder to see past this; the underlying behaviour is unchanged by this row. Second: the live rate-limit surface is not the one `docs/moltbook_api_spec.md` §5 describes — twelve headers were returned, including a tiered short-medium-long family the transport does not parse and whose tightest window (30) is therefore invisible to `RateLimitInfo`; the generic `x-ratelimit-limit` was 60 on `/agents/status` and 200 on `/posts` in two calls 200ms apart, so it is per-endpoint rather than the flat 60 per 60s §5 documents; and `x-ratelimit-reset` is an epoch timestamp while the tiered resets are deltas, one header family carrying two value formats. Recorded, not corrected: two endpoints on one credential at one moment is not a sufficient basis for rewriting a documented limit table. **This attestation is version-bound to the transport at `c1eb9ba` and to the 2026-07-21 `skill.md` capture, describes one moment rather than a standing property of the platform, and confers no authority over the artifact's future contents.** | Kevin Brown | 2026-08-21 15:56 EDT |
| **C4.** First-post runbook finalized (step-by-step execution script for §E below) | Complete | Runbook recorded as its own dated artifact, `docs/m7_c4_first_post_runbook_2026-08-21.md`, following the C1/C3 precedent of a dated record rather than a row-embedded decision. It amends no numbered section of this checklist, of `docs/m7_moltbook_transport_boundary_and_deployment_spec.md`, of `docs/m7_first_live_post_governed_envelope.md`, or of any ruling in `docs/`. Merged to `main` at `c36161b` via PR #74 (squashed from `5ea17a1`, `a993f9e`), tree clean. The runbook sequences existing obligations rather than authorizing transmission: (§2) fixes step order around the envelope's 300-second approval window, since expiry is checked first; (§3) states the execution model the kill switch requires — an interactive operator session, not a background process; (§4) names one unenforced manual control point — `validate_envelope()` never checks `action_id` against GO-2's `authorized_action_id` — and requires the operator close it by hand; (§5) states the AMBIGUOUS-verification branch as a terminal STOP-and-escalate condition grounded in C1 §6 and the existing TODO.md ruling, without relabeling `TransportOutcome.SUCCESS` as failure; (§6) documents what dry-run rehearsal does and does not cover; (§7) the nine-step execution sequence, revised prior to merge to correct a recheck-window justification that had contradicted §3; (§8) records, without resolving, the forward dependency on C5; (§9) states the document's own attestation limits; (§10) binds three things — the transport implementation at `52a8c9c`, envelope doc §5 as quoted at its §5.3/§5.4, and checklist §D/§E as quoted — none of which inherit forward across a material change to any of them. The artifact's header remains `Status: DRAFT`; the flip to FINALIZED is pending as a follow-on commit citing this row, kept separate from the merge itself and dated to this signature. **This row attests that the runbook exists, sequences the obligations checklist §E already imposes, and identifies one unenforced control point (§4) and one terminal stop condition (§5) grounded in prior rulings. It does not attest that C5 exists, that the §4 gap is closed, or that a send executed under this sequence will succeed.** **Version-bound per §10 as stated above.** | Kevin Brown | 2026-08-24 10:58 EDT |
| **C5.** Published-Outcome Correction and Withdrawal Procedure finalized — must explicitly distinguish: delete (when supported), edit/correction (when supported), corrective follow-up (when neither is available), freeze-and-escalation (§9), and audit preservation. This is not a "rollback" in the atomic-reversal sense — most external APIs offer no such thing, and the procedure must not imply otherwise | Complete | Procedure recorded as its own dated artifact, `docs/m7_c5_published_outcome_correction_procedure_2026-08-27.md`, following the C1/C3/C4 precedent of a dated record rather than a row-embedded decision. It amends no numbered section of this checklist, of `docs/m7_moltbook_transport_boundary_and_deployment_spec.md`, of `docs/m7_first_live_post_governed_envelope.md`, of `docs/moltbook_api_spec.md`, or of any ruling in `docs/`. The procedure distinguishes the five dispositions this row's binding wording requires and states plainly that it is not an atomic rollback: (§3.1) delete and (§3.2) edit/correction, both defined structurally but **not available under Phase One**; (§3.3) corrective follow-up, a new separately governed post carrying its own `action_id`, approval and `payload_hash`, subject to every constraint governing any other post, which leaves the original live and is therefore a materially weaker remedy; (§3.4) freeze-and-escalation, distinguished at §4 from the transport spec's §9 `OUTCOME_UNKNOWN` reconciliation freeze by trigger rather than posture; and (§3.5) audit preservation, under which a platform-level delete or edit never touches the original RESOLUTION TRACE or `CaptchaAttemptRecord`. **The controlling finding is at §2:** post deletion and editing are not merely undocumented in `docs/moltbook_api_spec.md` §4 — they are **explicitly deferred out of Phase One by boundary spec §12** ("Deferred to later slices: ... deletions; edits ..."), which `moltbook/transport.py`'s `MoltbookHTTPTransport` docstring restates as an implementation invariant ("NO methods here at all, not even unused stubs — there is no 'escape hatch' endpoint surface (§6)"). §3.1 and §3.2 are therefore closed **by ruling, not by absence of evidence**: confirming a live delete endpoint would not open them, and only a formal §12 amendment under §16's Lock Condition would — which this document does not seek and which remains unopened scope. Corrective follow-up is consequently the sole operative disposition under Phase One by design of the slice. **This row attests that the procedure required before GO-2 exists, is recorded, and has been read. It does not attest that a delete or edit capability exists, that §3.3 is an adequate remedy in every case, or that any out-of-band channel to the platform is available.** Version-bound per §6 of the artifact to the sections quoted there and to `moltbook/transport.py` at `b559882`; confers no authority over the document's future contents. | Kevin Brown | 2026-08-27 20:50 EDT |

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
Transmission authority under GO-2 is consumed once a transmission **attempt** begins, not when its
outcome is later resolved — see §D.5 below for the exact attempt boundary, the required
pre-transmission gate, and the full consumption rule.

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
consumed_at:                     <records the timestamp of the §D.5 transmission-attempt boundary
                                   crossing — not that any outcome was resolved. No code writes
                                   this field; it is populated manually by the operator, either
                                   immediately after send() returns once the boundary crossing is
                                   known, or during reconciliation/evidence review if the session
                                   ended before the field could be populated. An unresolved
                                   OUTCOME_UNKNOWN / AMBIGUOUS_WRITE still receives this timestamp
                                   once known; reconciliation's later result never clears or
                                   rewrites it. Left blank + voided only where the boundary was
                                   never crossed, including expiry-unused cases. A blank value here
                                   does NOT by itself prove no attempt occurred — the session may
                                   have ended before the operator could populate it. §D.5's
                                   attempt-record protocol (AVAILABLE / FROZEN / CONSUMED) is the
                                   operative single-use evidence; this field is a record of that
                                   protocol's conclusion, not a substitute for it>
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

## D.5 — Final Pre-Transmission Single-Use Gate

**This gate is not a one-time phase transition.** It is entered fresh, from the beginning,
immediately before **every** proposed transmission attempt made under a GO-2 record — including a
second proposed attempt after an earlier one stopped here without reaching the transmission-attempt
boundary defined below. A prior PASS of this gate confers no standing authorization and may not be
relied on by a later proposed attempt; every proposed attempt performs the full sequence again from
step 1.

**The transmission-attempt boundary** is the invocation of `self._request_fn(...)` inside
`moltbook.transport.MoltbookHTTPTransport.send()` — the `try:` block opening at
`moltbook/transport.py:1491` and the call itself at `moltbook/transport.py:1492` (freshly verified;
unchanged from the prior draft of this section) — the sole point where the transport reaches the
external platform. Everything before that line is local governance computation with no external
effect (envelope freshness validation, kill-switch check, eligibility check, path/body
construction). The instant execution reaches that call — whatever it subsequently returns, raises,
or times out as — a transmission attempt has begun and cannot be un-begun.

Live execution of this gate and the send that follows it is governed operationally by
`docs/m7_c4_first_post_runbook_2026-08-21.md` **as superseded for live execution by
`docs/m7_c4_runbook_amendment_1_2026-09-18.md`** — the original C4 remains historically signed and
unchanged; the amendment carries the operative sequence. A bare reference to "C4" or "runbook §7"
below means C4 as amended, unless the original's untouched sections (§1–§4, §6, §8–§10) are meant,
in which case the original is cited directly since the amendment does not touch them.

### Three-state transmission-authority model

Writing a pre-attempt marker does **not by itself** prove the external boundary was crossed. Its
purpose is to establish durable evidence *before* the uncertain network call, precisely because the
network call's own outcome cannot always be trusted to arrive. Conflating "a marker exists" with
"the boundary was crossed" would either wrongly free authority that was actually consumed, or
wrongly retire authority that was never touched. Three states, not two, are required:

**AVAILABLE.** GO-2 has not been consumed and is presently eligible to enter or re-enter the gate
below, provided every other GO-2 condition (signed, unexpired, unchanged code/config/payload/
action/credentials) is separately satisfied. For a GO-2's first use, AVAILABLE ordinarily means no
attempt record exists yet for its `action_id`. AVAILABLE does **not** mean the gate has already
been passed — every proposed attempt re-enters the complete gate from its beginning regardless of
this state. A previously FROZEN GO-2 may return to AVAILABLE only through the recovery disposition
below; there is no other path back to AVAILABLE once a record exists.

**FROZEN.** GO-2 may not authorize a transmission while the status of the external-attempt boundary
is *unresolved* for its `action_id`. This includes: an `ATTEMPT_IN_PROGRESS` marker exists and
subsequent execution state is uncertain; a process or session failure after marker creation leaves
it unknown whether `_request_fn(...)` was invoked; available evidence is incomplete or
contradictory; or the operator cannot positively establish that execution terminated before the
boundary. **FROZEN is fail-closed. It is neither proof of consumption nor permission to retry.**

**CONSUMED.** The external transmission-attempt boundary is *known* to have been crossed for this
`action_id`. GO-2 is permanently unavailable for another transmission. There is no CONSUMED →
AVAILABLE transition under any circumstance, including any reconciliation result. A fresh GO-2 is
required for any later transmission attempt, regardless of that later attempt's relationship to
this one.

**Operative rule, replacing the earlier "any existing record permanently STOPs this GO-2"
formulation:**
- no prior record for this `action_id` → potentially AVAILABLE for first gate entry;
- a record in an unresolved/FROZEN state → STOP, remain FROZEN;
- a record showing the boundary was crossed → CONSUMED, permanent STOP, no exceptions;
- a record containing a **valid, evidence-backed** FROZEN→AVAILABLE recovery disposition (below) →
  potentially AVAILABLE for a full, fresh gate re-entry;
- anything else, including any ambiguity about which of the above applies → STOP.

No automatic inference of AVAILABLE is permitted from anything other than the two cases named
above (no prior record, or a valid recorded recovery disposition).

### Gate sequence — construct, verify, then mark

The earlier draft of this gate wrote the pre-attempt marker using GO-2's own paper values *before*
any `ActionEnvelope` object existed, binding the marker to intended values rather than to the
actual object about to be sent — this is corrected below. `action_id` is the specific field this
matters for: `payload_hash` and `governance_config_version` are independently checked by
`validate_envelope()` inside `send()` itself, or fail loudly at construction if omitted, but
`action_id` has no such backstop (C4 §4, unchanged): `ActionEnvelope.approve()` silently generates
a fresh `uuid.uuid4()` if `action_id` is omitted, and every other check in `validate_envelope()`
still passes against the wrong value. A marker written before construction cannot catch exactly
this failure; a marker written from the real, constructed object's fields can.

Performed in full, in order, immediately before every proposed transmission attempt:

1. Confirm GO-2 exists and is signed.
2. Confirm GO-2 has not expired.
3. Confirm code, configuration, payload, action, and credentials remain within the exact
   authorization (envelope doc §3's existing invalidation rule — referenced here, not restated).
4. Inspect the procedural attempt-record location (below) for this GO-2's `authorized_action_id`.
   Apply the operative rule above: STOP unless the state is "no prior record" or "a valid recovery
   disposition restores AVAILABLE."
5. Confirm no known unresolved `OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE` exists for this action, per
   transport spec §9's existing authority that such a state is never retried and is always
   escalated to reconciliation. **This is a best-effort review against available records, not a
   verified technical guarantee.**
6. Perform, or confirm already performed, the existing immediate-pre-send clean-tree check
   (checklist §E row 1) and kill-switch check (checklist §E row 2). This gate cross-references
   those controls; it does not restate or duplicate their authority. A clean tracked tree is an
   independent fact from "no previous attempt exists" — the attempt record lives outside the
   tracked tree precisely so the two are never conflated (see the Location note below).
7. **Construct and approve the actual `ActionEnvelope`**, passing `action_id=authorized_action_id`
   explicitly (C4 §4; do not let it default).
8. **Verify the actual constructed envelope's `action_id` and `payload_hash` against GO-2's
   `authorized_action_id` and `authorized_payload_hash`** — against the real object, not against
   intent. STOP if they do not match exactly; do not proceed to step 9 on a mismatch.
9. Atomically write the attempt record as `ATTEMPT_IN_PROGRESS`, populated from the **actual
   verified envelope's fields** (not from GO-2's paper values alone), with `transmission_attempt_at`
   left null (below).
10. Re-read the just-written record and verify its identity/binding fields match exactly what was
    written and what the actual envelope carries.
11. Proceed directly to `send()` (C4 §7 as amended) with no substitution of envelope, payload,
    action, configuration, credentials, or execution candidate between step 9's write and the call.
    Transport performs its own existing internal validation, kill-switch, and eligibility checks
    before `_request_fn(...)`.
12. If `_request_fn(...)` is invoked: the boundary is crossed, GO-2 transitions to CONSUMED, and the
    actual boundary-crossing timestamp is recorded once known (see `consumed_at`, §D above, and
    `transmission_attempt_at`, below).

**If steps 1–6 fail, this is a STOP and GO-2 remains AVAILABLE** (or FROZEN, if step 4 found an
unresolved record) — nothing has been constructed or written yet. **If step 7 or 8 fails, no marker
has been written; GO-2 remains AVAILABLE**, subject to the same re-entry conditions. **Once step 9's
write completes, GO-2 is FROZEN until either the boundary status resolves (step 11–12) or a
recovery disposition is recorded (below).**

### Pre-boundary failure handling

- **Failure before marker creation** (steps 1–8): no marker exists, no boundary crossed, GO-2 is
  **not** consumed by this failure. If the blocking condition is corrected and every other
  condition still holds, the operator may re-enter the complete gate from step 1.
- **Failure writing the marker itself** (step 9): treat as STOP. The atomic-write pattern
  (`tmp` file + `os.replace`) means either the complete new record exists at the destination path
  or the destination is unchanged from before the write was attempted — there is no partially
  written destination state to reason about. If the destination does not show the complete new
  record after the attempt, no marker was established; treat this identically to "failure before
  marker creation." If record state cannot be determined with confidence, do not proceed — fail
  closed and re-verify before any further action.
- **Failure after marker creation but before boundary status is established** (i.e., anywhere in
  steps 9–11 through `_request_fn(...)` itself not yet reached, or its outcome not yet knowable):
  **transition to FROZEN.** Do not retry transmission. Do not mint a new `action_id`. Apply the
  FROZEN → AVAILABLE recovery protocol below only if affirmative evidence can positively establish
  pre-boundary termination; otherwise remain FROZEN indefinitely.
- **Boundary crossed** (`_request_fn(...)` invoked): **CONSUMED, permanently.** No recovery to
  AVAILABLE exists for this case, regardless of what is subsequently learned about the outcome.

### FROZEN → AVAILABLE recovery

This is a narrow, evidence-gated exception, not a routine unfreezing procedure. **A FROZEN GO-2 may
return to AVAILABLE only if affirmative, contemporaneous evidence positively establishes that
execution terminated before `_request_fn(...)` was invoked.** The operator's recollection alone is
never sufficient.

**Qualifying evidence** must positively establish the relevant control-flow fact, not merely be
machine-generated. Examples, not an exhaustive or implementation-specific list:
- a captured traceback or exception whose control path establishes termination before
  `_request_fn(...)` (e.g., an exception raised by `validate_envelope()`, `kill_switch.check_write()`,
  or `eligibility.check_write()` — all of which execute, and can only raise, before the boundary);
- contemporaneous transport/runtime output identifying the last control point reached as
  pre-boundary;
- other contemporaneous, machine-generated evidence that positively establishes `_request_fn(...)`
  was not invoked, evaluated on its actual content, not merely its source.

**Non-qualifying evidence, explicitly insufficient by itself:** operator memory/recollection; a
blank `consumed_at`; a null `transmission_attempt_at`; absence of a platform post; absence of a
success response; lack of any platform-side record; a record remaining in `ATTEMPT_IN_PROGRESS`;
elapsed time; or a later belief that the request probably did not leave the machine. **If positive
proof is unavailable, the record remains FROZEN — indefinitely, if necessary.**

**Explicit operator recovery disposition required** — recovery never happens automatically, and no
code in this design infers it. The disposition must record, at minimum:
- the affected `action_id` and GO-2 reference;
- previous state (`FROZEN`) and resulting state (`AVAILABLE`);
- the exact reason the record entered FROZEN;
- a reference to the qualifying evidence;
- a concise statement of what that evidence proves;
- an explicit statement that the evidence establishes `_request_fn(...)` was not invoked;
- operator identity and disposition timestamp;
- a statement that recovery restores only eligibility to re-enter the gate at step 1, and does
  **not** revive any prior gate PASS, prior envelope object, prior clean-tree result, or prior
  kill-switch result — the gate is re-run in full, including expiry, and including
  code/config/payload/credential checks, as if this were a first attempt under this GO-2.
  **The `authorized_action_id` itself is not discarded or replaced — it is GO-2's own fixed
  identity binding and never changes.** What does not survive recovery is any previously
  *constructed* `ActionEnvelope` object or its approval — the gate's construct-verify-mark
  sequence builds a fresh envelope object using the same `action_id=authorized_action_id` argument
  it always uses, and re-verifies that fresh object against GO-2's bindings exactly as on a first
  attempt.

**Durable recovery history — one record per GO-2/`action_id`, an append-only event history within
it, nothing ever deleted.** There is exactly one attempt-record file per `authorized_action_id`
(matching the "one record file per `action_id`" location rule below) — recovery does not create a
second file, a second identity, or a "fresh" pairing of any kind, because the GO-2/`action_id`
identity this record is keyed to never changes. What changes over time is the record's **event
history**, an append-only list, mirroring this repository's own established pattern for
"a log of things that happened to one entity over time" (`KillSwitch._log: list[KillSwitchActivation]`
at `moltbook/transport.py:465`; `CaptchaVerifier._log: list[CaptchaAttemptRecord]` at
`moltbook/transport.py:972`) — those are in-memory lists private to one session; this is the same
append-only-list idiom, applied to a file so it survives across sessions.

A single record's event history for this `action_id` can look like:
`ATTEMPT_IN_PROGRESS` → `FROZEN` → `AVAILABLE` (via a recorded recovery disposition) →
`ATTEMPT_IN_PROGRESS` (a fresh gate entry, same GO-2, same `authorized_action_id`) → `CONSUMED` (if
this second attempt crosses the boundary), or → `FROZEN` again (if it does not, requiring its own
independent recovery evidence before any third entry). **Gate evaluation always reads the *most
recent* event in this history to determine current state** — recovery does not delete or overwrite
the FROZEN event it resolves; it appends a `RECOVERED_TO_AVAILABLE` event after it, and a
subsequent gate entry appends its own new `ATTEMPT_IN_PROGRESS` event after that. Every earlier
event remains exactly as written, so a future auditor can reconstruct the complete sequence for
this `action_id` without any state having been overwritten or inferred.

Per-event fields, in addition to the static identity fields shared by the whole record (below):
`event_type` (`ATTEMPT_IN_PROGRESS` / `FROZEN` / `RECOVERED_TO_AVAILABLE` / `CONSUMED` / a resolved
outcome), `event_timestamp`, and whatever fields that event type requires — a `FROZEN` event
carries `freeze_reason`; a `RECOVERED_TO_AVAILABLE` event carries the full recovery disposition
(`recovery_evidence_reference`, `recovery_evidence_summary`, `recovered_by_operator`,
`recovered_at`, and the explicit "`_request_fn(...)` was not invoked" statement); a `CONSUMED` or
outcome event carries `transmission_attempt_at`, `outcome`, `publication_status`,
`verification_status`, `reconciliation_reference`, `c5_reference`, `terminal` as applicable. No
event is ever mutated once appended.

### Attempt-record protocol

**Location (comes into existence only on first use — nothing in governance adoption requires it to
exist before a real governed execution session):** `moltbook/.execution_state/` — a git-ignored,
untracked directory (see `.gitignore`), one record file per `action_id`. This directory sits
outside every governed execution path; it is runtime/session evidence, not governed code or a
tracked governance artifact. Its presence, absence, or content is **independent** of the tracked
clean-tree determination (checklist §E row 1 and gate step 6) — a clean tracked tree and "no
previous attempt exists" are two separate facts, and this design deliberately keeps them separate
so that neither can be mistaken for the other.

**Minimum schema.** One record per `authorized_action_id`, split into static identity fields (set
once, unchanged across every event, since recovery never changes the GO-2/`action_id` this record
is keyed to) and the append-only `events` list described above.

*Static fields, set when the record is first created:* `action_id` (equals `authorized_action_id`
throughout the record's life), `go2_reference`, `authorized_action_id`, `payload_hash`,
`execution_candidate_commit`, `governance_config_version`, `authorization_expires_at`.

*Per-event fields (one entry per list item):* `event_type` (`ATTEMPT_IN_PROGRESS` / `FROZEN` /
`RECOVERED_TO_AVAILABLE` / `CONSUMED` / a resolved outcome), `event_timestamp`,
`record_created_at` (only meaningful on an `ATTEMPT_IN_PROGRESS` event — populated at marker-write
time, pre-boundary, by construction), `transmission_attempt_at` (**null when that specific
`ATTEMPT_IN_PROGRESS` event is created**; populated on that same event only once the operator can
establish `_request_fn(...)` was actually invoked for *that* attempt — a crash leaving this null
while the record's latest event is still `ATTEMPT_IN_PROGRESS` means that attempt's boundary status
is **unknown**, i.e. FROZEN, never "no attempt occurred"), `outcome` / `publication_status` /
`verification_status` (mirroring `moltbook.transport`'s own `TransportOutcome` /
`PublicationStatus` / `VerificationStatus` values — no new vocabulary, present on a `CONSUMED`/
outcome event), `reconciliation_reference`, `c5_reference` (only if §C5 is invoked), `terminal`
(boolean, present on an outcome event — describes only that *this attempt's* transport-level story
is closed; does not mean the First-Post Rider is discharged, see below), and — on a `FROZEN` or
`RECOVERED_TO_AVAILABLE` event only — the recovery fields from above (`freeze_reason`,
`recovery_evidence_reference`, `recovery_evidence_summary`, `recovered_by_operator`,
`recovered_at`). No operator/verifier identity field governs ordinary attempt tracking — this
checklist's own `Verified by` rule remains the human-accountability surface for governance rows;
operator identity appears in this record only on a `RECOVERED_TO_AVAILABLE` event, where
accountability for that specific act is required.

**Gate evaluation reads the record's most recent event** to determine current state (AVAILABLE /
FROZEN / CONSUMED) per the operative rule above; it never needs to re-derive state from the whole
history, though the whole history remains available for audit.

**Atomic-write procedure**, reusing this repository's existing pattern verbatim
(`moltbook/cadence.py:129-132`, `moltbook/citation.py:132-135`): write the complete record to a
temporary file in the same directory (`<path>.tmp`), then atomically replace the destination
(`os.replace(tmp, path)`). **This is process-crash-safe atomic local persistence — it is not
power-loss-safe, not fsync-backed, not machine-loss-safe, not tamper-proof, and not a concurrency
mechanism.** Neither existing store in this repository calls `fsync()`; a genuine OS crash or power
loss between the write and the rename could still lose the record despite the rename appearing to
succeed. It is designed for the current single-interactive-operator execution model (runbook §3),
not for parallel writers. Do not represent this pattern as providing stronger guarantees than this.

**Archival distinction — non-blocking, not part of the live-send critical path.** After the
record's most recent event reaches a resolved terminal state, the full record — including its
complete event history — may optionally be copied into a committed governance-evidence location
and included in a later commit, for long-term auditability — analogous to how `m5/traces/*.txt`
are committed after generation rather than at generation time. This step has no bearing on whether
a transmission may proceed and must never be inserted between a pre-send `ATTEMPT_IN_PROGRESS`
event and the actual transmission.

**GO-2 consumption is not the same claim as First-Post Rider discharge or §C5 completion.** An
event's `terminal: true` describes only that *that attempt's* transport-level story is closed.
The following are all legitimate simultaneous states: GO-2 consumed, Rider still active,
reconciliation pending; or GO-2 consumed, Rider still active, §C5 correction pending. A correction
performed under §C5 is itself a fresh governed action with its own approval — it is never a reuse
of the original, already-consumed GO-2.

### Known open items — future fresh authorization only

The following questions are recorded here, unresolved, because they will need answers before any
**future** transmission attempt following a consumed GO-2 — they do not affect, gate, or grant any
authority over the first transmission under the current, not-yet-signed GO-2 record:

1. After a consumed GO-2 whose attempt ultimately resolves to `NOT_PUBLISHED`, confirmed failure,
   or an ambiguity that reconciles to `NOT_PUBLISHED`, does a fresh GO-2 record require a new
   exact-payload Dry Run if the payload is unchanged from the consumed attempt?
2. If governed code has not changed, may the same, already-tested `execution_candidate_commit` be
   reused as the candidate for that fresh GO-2, or must candidate fixation and the full-suite test
   pass be repeated?

Neither question is answered by this section. No inference should be drawn from the current GO-2
draft's Dry Run status or execution-candidate fixation toward how either question resolves for a
future, not-yet-existing authorization. Both must be resolved before any post-consumption fresh
transmission authorization may proceed.

### Operator disposition — acceptance of this section as standing governance

§D.5 is a standing procedural rule governing every future GO-2's transmission authority, not a
one-time fact to attest (the checklist header's `Verified by` rule) and not a one-time transmission
grant (§D's `Authorized by (operator)`). Its acceptance is a third, distinct kind of act, following
the same pattern established for `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` §16
Amendment 1 and `docs/m7_eligibility_freshness_ruling_2026-09-01.md` — a standalone-rule
acceptance disposition, not a checklist-row verification and not a GO-2 authorization.

```
Status: SIGNED / LOCKED — accepted as written by Kevin Brown, 2026-09-18 22:38 EDT.

Reviewed by (operator): Kevin Brown
Reviewed at: 2026-09-18 22:38 EDT
Disposition (select one):
  [x] Accepted as written.
  [ ] Accepted with modification — operator states the modification.
  [ ] Rejected — operator states the reasoning.
Statement: "I have reviewed the AVAILABLE/FROZEN/CONSUMED model, the
            construct-verify-mark gate sequence, the FROZEN recovery
            evidentiary standard, the attempt-record protocol and its
            append-only event history, and the attempt-based GO-2
            consumption rule at §D.5, and accept it as standing governance
            for every future GO-2 transmission attempt. This acceptance
            does not itself authorize any transmission, sign any GO-2
            record, or make C4 Runbook Amendment 1 operative — those
            remain separate acts."
```

This block must be completed **before** `docs/m7_c4_runbook_amendment_1_2026-09-18.md` may be
validly signed — that amendment's own disposition presupposes §D.5 is already-accepted, settled
governance at the moment it is signed, not still-pending-review text. §D.5 acceptance and C4
Amendment 1 signature are sequential, not parallel, and neither substitutes for a later, separate
GO-2 signature.

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
