# M7 — C4 Runbook Amendment 1: Single-Use Gate Integration

**Status: DRAFT — pending operator review and sign-off. Not yet in effect.**
**Subject document:** `docs/m7_c4_first_post_runbook_2026-08-21.md` (FINALIZED, signed
Kevin Brown, 2026-08-24 10:58 EDT, citing `docs/m7_operator_go_checklist.md` §C4).
**Authority:** `docs/m7_operator_go_checklist.md` §D.5 (Final Pre-Transmission Single-Use Gate),
added 2026-09-18.

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
- supersede, for the purpose of live execution only, C4 §7's sequence, replacing it with the
  complete amended sequence at §4 below;
- add to C4 §10's version binding, since the operative procedure now also depends on checklist
  §D.5.

**It does not:**
- reopen, edit, or alter a single byte of the signed `docs/m7_c4_first_post_runbook_2026-08-21.md`.
  That document remains historically FINALIZED and signed exactly as it stands, and every citation
  to it as history (e.g., the checklist's own C4 row) remains fully accurate.
- alter C4 §1, §2, §3, §4, §6, §8, or §9 in any respect. Those sections are unaffected and remain
  in force exactly as signed; a live executor still needs to read them (this amendment does not
  reproduce their content).
- independently re-derive the attempt-based consumption rule, the AVAILABLE/FROZEN/CONSUMED model,
  the attempt-record protocol, or the FROZEN-recovery evidence requirements. Checklist §D.5 is the
  sole controlling authority for all of those; this amendment binds C4's operative behavior to that
  authority and restates only what is necessary to make the live sequence followable without
  cross-referencing §D.5 mid-execution.
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
in full. A live executor needs **both documents**: this amendment for the operative §5.4/§7
content, and the original for everything else — §1 (purpose/scope), §2 (the 300-second window
rationale), §3 (the interactive-session/kill-switch execution model), §4 (the action-ID binding
finding this amendment's §4 step 7–8 directly implements), §6 (Dry Run coverage limits), §8
(forward dependency on §C5), and §9 (attestation limits).

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
11. **Call `send()`.** The operator remains present for the duration, kill switch reachable.
    Nothing between step 9's write and this call may substitute the envelope, payload, action,
    configuration, credentials, or execution candidate the gate was run against.

    `send()` performs its own existing internal sequence — `validate_envelope()`,
    `kill_switch.check_write()`, `eligibility.check_write()` — before any network call
    (`moltbook/transport.py:1472-1474`). **If any of these three raises, execution never reaches
    the transmission-attempt boundary; the boundary is not crossed; GO-2 remains FROZEN (not
    CONSUMED) pending the recovery protocol at checklist §D.5** — such an exception is exactly the
    kind of contemporaneous, control-flow-establishing evidence that protocol's "qualifying
    evidence" describes, though recovery still requires an explicit operator disposition, never an
    automatic inference.

    The instant execution reaches `self._request_fn(...)` (`moltbook/transport.py:1491-1492`), the
    transmission-attempt boundary is crossed and **GO-2 transitions from FROZEN to CONSUMED,
    permanently, regardless of what this call subsequently returns, raises, or times out as.**
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
checklist.md` §D.5 as it stands when this amendment is signed; `moltbook/transport.py` at the
commit checklist §D.5 itself is bound to. Does not inherit forward across a material change to any
of them — a material change to checklist §D.5's model, or to the cited transport code, requires a
fresh review of this amendment against the change, exactly as C4's own §10 states for itself.

---

```
Status: DRAFT — unsigned
Amended by (operator):
Amended at:
Statement: "I have reviewed original C4 (unchanged, signed 2026-08-24) and this
            amendment's superseding §5.4 and §7 content in full, confirm the
            amendment correctly integrates checklist §D.5's single-use gate
            into the live-execution sequence, and accept this amendment as the
            operative procedure for the first governed transmission. This
            acceptance does not itself grant GO-2 or authorize any
            transmission; those remain separately governed."
```
