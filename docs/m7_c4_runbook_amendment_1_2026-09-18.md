# M7 — C4 Runbook Amendment 1: Single-Use Gate Integration

**Status: DRAFT — pending operator review and sign-off. Not yet in effect.**
**Subject document:** `docs/m7_c4_first_post_runbook_2026-08-21.md` (FINALIZED, signed
Kevin Brown, 2026-08-24 10:58 EDT, citing `docs/m7_operator_go_checklist.md` §C4).
**Authority:** `docs/m7_operator_go_checklist.md` §D.5 (Final Pre-Transmission Single-Use Gate),
added 2026-09-18, as amended by
`docs/m7_checklist_d5_amendment_1_eligibility_freshness_2026-09-24.md`
(D.5 Amendment 1 — SIGNED / LOCKED, Kevin Brown, 2026-09-24 21:44 EDT).

---

## 1. What this amendment is, and what it is not

This amendment integrates checklist §D.5's pre-transmission single-use gate into C4's operative
live-execution sequence. It is filed as its own dated artifact rather than as an edit to the
signed runbook, following the precedent that a signed document is corrected or extended by a new
standalone document rather than reopened (`docs/m7_c1_wiring_plan_erratum_1_2026-08-17.md` §1;
`docs/m7_eligibility_freshness_ruling_2026-09-01.md` §8, "the erratum precedent... establishes that
a signed document is corrected by a new standalone document, never reopened").

**It does:**
- supersede, for the purpose of live execution only, C4 §5.4 step 3's treatment of `consumed_at`
  and rider discharge, replacing a previously-disclaimed interpretation with a pointer to now-settled
  checklist authority;
- supersede, for the purpose of live execution only, C4 §6's Dry Run carry-across statement, adding
  `governance_config_version` as a required-match value alongside `payload_hash` and `action_type`
  — see §3a below; `action_id` remains, unchanged, the one value that must not carry across;
- supersede, for the purpose of live execution only, C4 §7's sequence, replacing it with the
  complete amended sequence at §4 below;
- add to C4 §10's version binding, since the operative procedure now also depends on checklist
  §D.5 and on D.5 Amendment 1.

**It does not:**
- reopen, edit, or alter a single byte of the signed `docs/m7_c4_first_post_runbook_2026-08-21.md`.
  That document remains historically FINALIZED and signed exactly as it stands, and every citation
  to it as history (e.g., the checklist's own C4 row) remains fully accurate.
- alter C4 §1, §2, §3, §4, §8, or §9 in any respect. Those sections are unaffected and remain
  in force exactly as signed; a live executor still needs to read them (this amendment does not
  reproduce their content). §6 is unaffected except for the single carry-across statement §3a below
  narrowly supersedes — the rest of §6 (Dry Run coverage limits on captcha/verification/AMBIGUOUS
  and on §4's action-ID control point) is unaffected and remains in force exactly as signed.
- independently re-derive the attempt-based consumption rule, the AVAILABLE/FROZEN/CONSUMED model,
  the attempt-record protocol, or the FROZEN-recovery evidence requirements. Checklist §D.5, as
  amended by D.5 Amendment 1, is the sole controlling authority for all of those; this amendment
  binds C4's operative behavior to that authority and restates only what is necessary to make the
  live sequence followable without cross-referencing §D.5 or D.5 Amendment 1 mid-execution.
- grant GO-2. GO-2 remains a separate, later signature event under checklist §D, gated on its own
  outstanding requirements (exact payload, Dry Run, etc. — none of which this amendment touches).
- authorize any transmission by its own existence. Nothing here executes anything.
- change `moltbook/transport.py` or any other governed implementation, or any test.
- alter `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` or its §16 Amendment 1 in any
  respect.
- alter Finding A (status/metadata discard on the eligibility read path) — remains separate, open,
  non-blocking, unsequenced against this amendment.
- reopen §12 (post delete/edit deferral) in any respect.
- alter `docs/m7_c5_published_outcome_correction_procedure_2026-08-27.md` in any respect; §C5
  remains the sole correction/withdrawal authority for a `PUBLISHED`-but-incorrect outcome, invoked
  exactly as C4 §7 as amended (§4 below) directs, never bypassed or duplicated here.
- alter GO-1 or the completion status of C1–C5 in any respect.
- change the retry taxonomy (transport spec §8) or §9 reconciliation authority. Reconciliation
  determines facts; it does not restore transmission authority, exactly as checklist §D.5 states.
- decide either of the two questions checklist §D.5's "Known open items" section parks — whether a
  fresh GO-2 after a consumed-but-not-published attempt requires a new exact-payload Dry Run, and
  whether an unchanged `execution_candidate_commit` may be reused for that fresh GO-2. Both remain
  open, unresolved by this amendment, exactly as parked.

## 2. Relationship to the original C4

Where this amendment is silent, the original `docs/m7_c4_first_post_runbook_2026-08-21.md` governs
in full. A live executor needs **both documents**: this amendment for the operative §5.4/§6/§7
content, and the original for everything else — §1 (purpose/scope), §2 (the 300-second window
rationale), §3 (the interactive-session/kill-switch execution model), §4 (the action-ID binding
finding this amendment's §4 step 7–8 directly implements), §6 (Dry Run coverage limits — as
superseded on carry-across values only by §3a below; its captcha/verification/AMBIGUOUS-branch and
action-ID coverage limits are unaffected), §8 (forward dependency on §C5), and §9 (attestation
limits).

A citation to "C4" or "the runbook" for the purpose of identifying **what governs a live send today**
means C4 as superseded by this amendment. A citation to C4 for **historical or provenance**
purposes (e.g., "C4's row cites this document," "signed 2026-08-24") means the original, unchanged,
and is unaffected by this amendment's existence.

## 3. Amended §5.4 step 3

Original C4 §5.4 step 3 read, in relevant part: "Record the transmission timestamp on GO-2's
`consumed_at` per §D — that field records that GO-2 was consumed by a transmission, not that any
obligation closed... **Interpretation, not an explicit rule**... Read it this way absent a ruling to
the contrary; do not treat this runbook's reading as a settled rule."

**This is now settled by checklist §D.5, not independently ruled on here.** For live execution, C4
§5.4 step 3 is superseded to read: record the transmission-attempt boundary crossing on GO-2's
`consumed_at`, per the corrected wording at checklist §D (the `consumed_at` template field) and the
full consumption rule at checklist §D.5. GO-2 consumption, First-Post Rider discharge, and §C5
completion remain three distinct closure questions — checklist §D.5's own text states this
explicitly, and this amendment does not restate it, only binds to it.

## 3a. Amended §6 — Dry Run carry-across requirement

Original C4 §6 read, in relevant part: "Only `payload_hash` and `action_type` carry across between
the rehearsal envelope and the authorized one; `action_id` deliberately does not, and must not be
made to."

**This is now widened by explicit finding, not independently re-derived.** `validate_envelope()`
(`moltbook/transport.py:113-136`) checks an envelope's `governance_config_version` against a
caller-supplied `live_config_version` — both are plain strings with no canonical or global source
anywhere in this repository (`DryRunTransport.__init__` and `MoltbookHTTPTransport.__init__` both
take `live_config_version` as a bare constructor argument, the latter defaulting to `""`). A Dry
Run's config-drift check therefore only proves self-consistency between whatever value the operator
chose for the rehearsal envelope and whatever value the operator chose for the `DryRunTransport`
instance — it carries no evidentiary weight about the real live transport unless that same value is
deliberately held constant through to live construction.

For live execution, C4 §6 is superseded to read: the exact-payload Dry Run and the authorized/live
action must correspond across three values, not two — `payload_hash`, `action_type`, and
`governance_config_version` — held identical across the Dry Run `ActionEnvelope`,
`DryRunTransport.live_config_version`, GO-2's `authorized_config_version`, the eventual live
`ActionEnvelope.governance_config_version`, and the real `MoltbookHTTPTransport.live_config_version`.
`action_id` is unchanged by this widening — it remains the one value that deliberately does not
carry across, and must not be made to (C4 §6, unchanged on this point).

This section does not introduce a repository-wide `governance_config_version` convention or choose
a value — none is fixed here, and none is fixed by original C4 §6 either. It states only that
whatever value is eventually chosen must be held constant across the five points named above.
Original C4 §6's remaining content — Dry Run's inability to rehearse a captcha challenge, a captcha
failure, the §5 AMBIGUOUS branch, or §4's action-ID control point — is unaffected and remains in
force exactly as signed.

## 4. Amended §7 — operative sequence for live execution

This section reproduces the complete sequence a live executor follows. It supersedes original C4
§7 in full for execution purposes; the original's preconditions paragraph is unchanged and still
applies.

**Preconditions** (unchanged from original C4 §7): GO-2 signed and unexpired; `execution_candidate_
commit` matches the current clean tree; rider (envelope doc §2) fully populated, including
`dry_run_rehearsal_reference` from a completed rehearsal under a `dryrun-` id (C4 §6).

1. **Open the interactive session** that will hold the `KillSwitch` instance and call `send()` —
   per C4 §3, this is not a background process.
2. **Clean-tree recheck** — confirm the working tree still matches `execution_candidate_commit`
   (checklist §E row 1).
3. **`KillSwitch.engaged` recheck** — confirm `False`, in this same session, on the instance that
   will be passed to the transport (checklist §E row 2).
4. **Confirm the reachable `activate_manual()` path** — the operator can call it against this
   instance right now, from this session, without any additional setup (checklist §E row 2, second
   clause).
5. **Rider re-review** — confirm the intended `authorized_action_id` and `authorized_payload_hash`
   for the envelope about to be constructed match GO-2's recorded values (C4 §4's finding; this is
   a review of *intent*, not yet a check against a constructed object — that check happens at step
   8 below, against the real object).
6. **Enter checklist §D.5 through its attempt-record inspection (§D.5 gate steps 1–5).** Confirm
   GO-2 is signed and unexpired, confirm code/config/payload/action/credentials are unchanged,
   inspect the attempt-record location for this `action_id`, and confirm no known unresolved
   `OUTCOME_UNKNOWN`/`AMBIGUOUS_WRITE` exists. **STOP here — remaining AVAILABLE, nothing yet
   written — unless the record state is "no prior record" or "a valid recovery disposition restores
   AVAILABLE."** If this step stops, resolve the blocking condition and re-enter this step from its
   own beginning; the same GO-2 remains usable, no consumption has occurred.
7. **Construct and approve the standard `ActionEnvelope`** — the last local step before `send()`,
   per C4 §2. Pass `action_id=authorized_action_id` explicitly (C4 §4); do not let it default. This
   starts the 300-second approval window.
8. **Verify the actual constructed envelope's `action_id` and `payload_hash` against GO-2's
   `authorized_action_id` and `authorized_payload_hash`** — against the real object just
   constructed at step 7, not against step 5's statement of intent. **If they do not match exactly,
   STOP. No marker has been written. GO-2 remains AVAILABLE.** Correct the construction and
   re-enter this step; do not proceed to step 9 on a mismatch.
9. **Atomically write the attempt record as `ATTEMPT_IN_PROGRESS`**, using the envelope's actual
   verified fields from step 8 (checklist §D.5's attempt-record protocol), with
   `transmission_attempt_at` left null. **GO-2 transitions from AVAILABLE to FROZEN at this write.**
10. **Re-read the just-written record** and verify its identity/binding fields match exactly what
    was written and what the envelope from step 7 carries.

**10a.** **Live eligibility read.** On the exact same transport instance that will perform the write
    at step 11, call `check_eligibility()` (`moltbook/transport.py:1418–1427`). This is the live
    platform read Transport §16 Amendment 1 §1.1 requires
    (`docs/m7_moltbook_transport_boundary_and_deployment_spec.md:754–756`), at the placement D.5
    Amendment 1 §3.3 item 3 fixes (`docs/m7_checklist_d5_amendment_1_eligibility_freshness_2026-09-24.md:188–193`).
    No operation of any kind — local or external, governed or otherwise — occurs between this read
    and step 11's call to `send()`. This read is not the transmission-attempt boundary (see step
    11). It adds no enforcement call: enforcement remains with the existing
    `eligibility.check_write()` inside `send()`.

11. **Call `send()`.** The operator remains present for the duration, kill switch reachable.
    Nothing between step 9's write and this call may substitute the envelope, payload, action,
    configuration, credentials, or execution candidate the gate was run against — all six
    protections stand exactly as before. The step 10a eligibility read is a permitted operation
    ahead of this call: it substitutes none of them, exists solely to satisfy Transport §16
    Amendment 1's eligibility-freshness requirement, and is followed immediately by this call, with
    no additional intervening operation of any kind permitted between step 10a and this call (D.5
    Amendment 1 §3.3 item 3 and §3.5, lines 188–193 and 251–262).

    `send()` performs its own existing internal sequence — `validate_envelope()`,
    `kill_switch.check_write()`, `eligibility.check_write()` — before any network call
    (`moltbook/transport.py:1472-1474`). **If any of these three raises, execution never reaches
    the transmission-attempt boundary; the boundary is not crossed; GO-2 remains FROZEN (not
    CONSUMED) pending the recovery protocol at checklist §D.5** — such an exception is exactly the
    kind of contemporaneous, control-flow-establishing evidence that protocol's "qualifying
    evidence" describes, though recovery still requires an explicit operator disposition, never an
    automatic inference.

    `eligibility.check_write()` here enforces the observation taken at step 10a, not any earlier or
    stored value (D.5 Amendment 1 §3.3 item 4, lines 194–199); no enforcement call is added outside
    `send()`.

    A qualifying failure at step 10a, or at `eligibility.check_write()` inside `send()` enforcing
    it, occurs after step 9's write and before the boundary: the boundary is not crossed, and GO-2
    becomes/remains FROZEN (not CONSUMED), subject to the same evidence-gated recovery protocol
    (D.5 Amendment 1 §3.3, lines 206–211). The uncaught exception paths D.5 Amendment 1 §4
    identifies at this call site (lines 333–365) apply; this amendment neither restates nor
    extends them.

    **Evidence capture.** Where either step 10a's `check_eligibility()` call, or
    `eligibility.check_write()` inside `send()` enforcing its result, fails or raises, the operator
    (or the session's own tooling) contemporaneously captures and preserves the resulting
    exception, traceback, or other applicable control-flow evidence — the same category of evidence
    `checklist:377–381` already recognizes, applied at this call site (D.5 Amendment 1 §3.6, lines
    276–282). This is a procedural evidence-capture instruction only: it creates no recovery
    authority, does not infer recovery from captured evidence, and does not transition GO-2 from
    FROZEN to AVAILABLE, which remains an explicit, evidence-gated operator disposition
    (`docs/m7_operator_go_checklist.md:393–411`; D.5 Amendment 1 §3.6).

    Consumption is defined solely by whether `self._request_fn(...)` inside `send()`'s **write**
    path was reached (D.5 Amendment 1 §2, lines 115–116). The instant execution reaches that call
    (`moltbook/transport.py:1491-1492`), the transmission-attempt boundary is crossed and **GO-2
    transitions from FROZEN to CONSUMED, permanently, regardless of what this call subsequently
    returns, raises, or times out as.** The step 10a read is not that boundary: per D.5 Amendment 1
    §2 it "is not, and does not become, the transmission-attempt boundary: it authorizes nothing,
    transmits no governed content, and its own occurrence — successful, failed, or
    exception-raising — does not by itself consume GO-2" (lines 113–116).
    Record the actual crossing timestamp on GO-2's `consumed_at` once known (checklist §D,
    `consumed_at` field) — immediately if control returns promptly, or during reconciliation if the
    session ends before this can be done. A blank `consumed_at` after a session ending here does
    **not** mean the boundary was not crossed; it means the field could not yet be populated — the
    attempt record, not `consumed_at`, is the operative single-use evidence.

    Kill-switch engagement is not fixed for the whole of this step — the captcha-suspension-risk
    trigger (`moltbook/transport.py:495`) can engage the switch during verification, which "gates
    PUBLICATION, not transmission — the write has already happened by the time it runs"
    (`moltbook/transport.py:1447-1448`) and so cannot affect a transmission that has already crossed
    the boundary. The operator's reachable `activate_manual(operator=...)` path (step 4) stays open
    across this window.
12. **Record the outcome** — `transmission_status` / `publication_status` / `verification_status`,
    RESOLUTION TRACE, `CaptchaAttemptRecord` if verification ran, `consumed_at` on GO-2 (checklist
    §E row 4). Update the same attempt record written at step 9 with the resolved outcome per
    checklist §D.5's attempt-record protocol — a second write to the *same* record, not a new one,
    separate from and additional to `consumed_at` on the GO-2 document itself.
13. **Branch on outcome** (unchanged from original C4 §7 step 9 / original §5, which remain in
    force and are not reproduced here):
    - `OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE` → checklist §E row 5 (freeze, escalate per transport
      spec §9). GO-2 is already CONSUMED per step 11 above; reconciliation determines the platform
      fact and never restores transmission authority.
    - `PUBLISHED` and correct → envelope doc §5(3)(a), operator records acceptance. GO-2 CONSUMED;
      Rider discharge follows envelope doc §5's own condition, independently.
    - `PUBLISHED` but incorrect → checklist §E row 6, C5 governs correction. GO-2 remains CONSUMED;
      a §C5 correction is a fresh governed action with its own approval, never a reuse of this GO-2.
    - `PENDING_VERIFICATION` / `REQUIRED` → original C4 §5: stop, record, escalate. GO-2 CONSUMED
      per step 11 regardless of this branch.
    - `NOT_PUBLISHED` with `FAILED` or `EXPIRED` → terminal per envelope doc §5(1); operator records
      disposition. GO-2 remains CONSUMED — a further live attempt, even of unchanged content,
      requires a fresh GO-2 record (checklist §D.5's "Known open items" notes what remains
      unresolved about exactly what that fresh authorization must repeat).

**No path in this sequence writes or relies on an attempt-record binding value that was not first
verified against the actual constructed `ActionEnvelope`** (steps 7–8 precede step 9's write) —
this is the specific defect this amendment corrects relative to the sequence briefly staged and
then withdrawn during this document's own drafting process.

## 5. Version binding

Bound to: `docs/m7_c4_first_post_runbook_2026-08-21.md` as signed 2026-08-24 10:58 EDT (unchanged,
verified byte-identical to that signature as of this amendment's drafting); `docs/m7_operator_go_
checklist.md` §D.5 as it stands when this amendment is signed; `docs/m7_checklist_d5_amendment_1_eligibility_freshness_2026-09-24.md`
(D.5 Amendment 1), SIGNED / LOCKED 2026-09-24 21:44 EDT; `moltbook/transport.py` at the
commit checklist §D.5 itself is bound to. Does not inherit forward across a material change to any
of them — a material change to checklist §D.5's model, or to the cited transport code, requires a
fresh review of this amendment against the change, exactly as C4's own §10 states for itself.

## Open before signature (non-operative note)

This note is **not part of the operative sequence** (§4), does not modify §3a, §5, or the
signature Statement below, and does not resolve either question it records. It states two open
questions only; it proposes no answer and creates no requirement, recommendation, default, or
implied disposition. Per operator disposition, 2026-09-30, both are to be resolved before this
amendment is signed.

1. **Version-binding commit (§5).** §5 binds `moltbook/transport.py` "at the commit checklist
   §D.5 itself is bound to." Checklist §D.5 (`docs/m7_operator_go_checklist.md:230–564`)
   identifies no commit, so the phrase has no identified referent. This predates D.5 Amendment 1
   and was exposed, not created, by the conformity review against it. **Open question:** to which
   commit, if any, this amendment's transport binding refers.
2. **§3a / `governance_config_version`.** §3a widens original C4 §6's carry-across requirement
   to include `governance_config_version`, and the signature Statement below attests acceptance
   of "§6 (narrowly, via §3a)". D.5 Amendment 1 takes no position on §3a
   (`docs/m7_checklist_d5_amendment_1_eligibility_freshness_2026-09-24.md:34–38`). Signing this amendment as
   structured would accept §3a. **Open question:** whether §3a is accepted as governance.

---

```
Status: DRAFT — unsigned
Amended by (operator):
Amended at:
Statement: "I have reviewed original C4 (unchanged, signed 2026-08-24) and this
            amendment's superseding §5.4, §6 (narrowly, via §3a), and §7
            content in full, confirm the amendment correctly integrates
            checklist §D.5's single-use gate, as amended by D.5 Amendment
            1, into the live-execution sequence, and accept this amendment
            as the operative procedure for the first governed transmission.
            This acceptance does not itself grant GO-2 or authorize any
            transmission; those remain separately governed."
```
