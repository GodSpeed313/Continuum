# M7 — GO-1 Decision Record (Deployment Preparation Authorization)

**Status: DRAFT — `Status` and `Evidence` drafted for operator review; `Authorized by` and
`Authorized at` are unfilled. This record authorizes nothing until those two fields are signed.**

This is the dated artifact required by `docs/m7_operator_go_checklist.md` §B, which directs that
the GO-1 decision "is saved as its own dated artifact (e.g. `docs/m7_go1_decision_<date>.md`), not
left as an unrecorded verbal/mental decision." It is not a row in that checklist and does not add
one.

This record **amends no numbered section** of `docs/m7_operator_go_checklist.md`, of
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md`, or of any ruling in `docs/`. It
records one decision and the ruling required to write it.

---

## 1. The two commits, and what each one binds

§B's authorization statement names a single commit. Two distinct repository states are relevant to
this decision, and conflating them is the drafting problem §A3 recorded. They are separated here.

| | Commit | What it is | Role in this record |
|---|---|---|---|
| **Preparation baseline** | `008d3ba` | The engineering state gated by §A2 — 590 passed, 7 xfailed, 0 failed, 0 errors, on `main`, clean tree | The code state this authorization is **granted over**. Unchanged by this record. |
| **§A record completion** | `334db60` | The commit at which §A's final signature landed, making the §A record complete at 13/13 rows | The state from which the completed §A record is **read**. |

`preparation_baseline_commit` remains `008d3ba` as fixed by §A2. This record does not move it, and
nothing here re-baselines it. Moving it would be a fresh §A2 act, not a GO-1 act.

---

## 2. Ruling — the reading of "at `preparation_baseline_commit`" in §B's statement

**The discovery fact.** During the §A3 row 2 reading on 2026-08-07, a finding was identified and
deliberately recorded rather than resolved. In that row's own Evidence: §B's authorization
statement reads "I have reviewed §A in full, at `preparation_baseline_commit`," whereas §A's rows
are necessarily signed at successive commits over time. That row recorded it as "a §B drafting
matter to settle when the GO-1 record is written," and explicitly did not undertake the settlement.

The finding is real and is restated plainly here: §A was **not** complete at `008d3ba`. At that
commit §A3 rows 2–3 and §A4 were blank in all four fields; they were signed on 2026-08-07 and
2026-08-08 respectively. Read as an assertion that the §A *record* was complete at `008d3ba`, the
statement would be false.

**The ruling.** By operator ruling on 2026-08-10: **the clause binds the code, not the record.**
"at `preparation_baseline_commit`" identifies the engineering state over which preparation is
authorized — the §A2 baseline. It does not assert that §A's record was complete at that commit,
and it does not assert that the operator's review occurred at that commit.

**Consequences of the ruling, stated so they are not inferred:**

- The statement is **carried verbatim** into §4 below. Under this reading it is true as written,
  so no amendment to §B is made, required, or implied by this record.
- This is a ruling on how an existing sentence is to be read. It is not a signature, and it does
  not attest that §B's wording is well-drafted, optimal, or content-frozen.
- The reading is consistent with how the term is already used elsewhere and was not invented for
  this record: §A2 frames its own claim as "main at `preparation_baseline_commit` is the prepared
  state," and `docs/m7_first_live_post_governed_envelope.md` §2 distinguishes the
  `preparation_baseline_commit` reviewed at GO-1 from the `execution_commit_reference` that
  actually transmits, precisely because live captcha wiring (C2) happens *after* GO-1.
- This ruling discharges the §A3 row 2 finding and that finding only. The two findings recorded at
  §A3 row 1 are separate, are **not** addressed here, and remain open. See §6.

---

## 3. Precondition check — §A complete

§B's gate: "Requires all of §A complete (every item's four fields filled)."

The §A record at `334db60`: **13 of 13 rows COMPLETE**, all four fields filled, no row signed over
blank evidence, no partial signature.

| Subsection | Rows | Signed |
|---|---|---|
| A1. Longitudinal grounding | 4 | 2026-08-03 / 2026-08-04 |
| A2. Engineering completeness | 5 | 2026-08-06 |
| A3. Deployment packet reviewed | 3 | 2026-08-07 |
| A4. Rehearsal | 1 | 2026-08-08 |

All thirteen name **Kevin Brown** as `Verified by`, satisfying the checklist header's rule that the
verifier is always the accountable human and never an automated agent or tool.

The checklist file is **byte-identical from `334db60` through current `main` at `7483d80`**
(`git diff 334db60..7483d80 -- docs/m7_operator_go_checklist.md` is empty). The intervening merge
(#67) added tooling and README content and did not touch the record. The §A record read for this
decision is therefore the same record that was signed.

**Mechanical corroboration, offered as evidence and not as verification.**
`python tools/verify_go_checklist.py --require-complete A` at `7483d80` reports
`SATISFIED — all 13 rows COMPLETE`, and reports `0 defective` across all 29 rows of the checklist.
Per the checklist header, automation may serve as `Evidence` but may never be recorded as the
verifier. This tool checks **structural** completeness only — that four fields are filled and that
no row carries a signature over blank Status or Evidence. It does not and cannot judge whether the
evidence recorded in those rows is *true*. That judgment is the operator's and is what the
signature in §4 carries.

---

## 4. Authorization

```
Status:      §A complete — 13/13 rows, all four fields filled, at 334db60; file unchanged
             through 7483d80. §B's precondition is satisfied. This authorization takes
             effect on the operator signature below and not before.

Evidence (pointer to completed §A record):
             docs/m7_operator_go_checklist.md §A, as it stands at 334db60 (identical at
             7483d80): A1 four rows signed 2026-08-03/2026-08-04; A2 five rows signed
             2026-08-06 against preparation_baseline_commit 008d3ba (590 passed, 7 xfailed,
             0 failed, 0 errors, clean tree, post-merge run on main); A3 three rows signed
             2026-08-07 covering the governed envelope at e4aba53, this checklist at
             079b3c1, and transport spec §9/§10 at af3fd24; A4 one row signed 2026-08-08
             over the rehearsal artifact at cfd6897, action_type POST, with negative
             control. All thirteen Verified by Kevin Brown. Structural corroboration:
             tools/verify_go_checklist.py --require-complete A → SATISFIED, 0 defective.
             The reading of "at preparation_baseline_commit" is ruled at §2 of this record.

Authorized by (operator):

Authorized at:

Statement: "I have reviewed §A in full, at preparation_baseline_commit, and
            authorize deployment preparation — live submit_captcha_fn wiring,
            connectivity validation without transmission, and drafting of the
            runbook and correction/withdrawal procedure — to begin. This
            authorization does not permit the first live post."
```

---

## 5. What this authorization does not do

Stated explicitly so none of it is inferred from silence.

1. **It does not authorize transmission.** No governed post or reply may be sent under GO-1. The
   first live transmission requires GO-2 (§D), which is single-use and bound to its own
   `execution_candidate_commit`, `action_id`, `payload_hash`, `config_version`, and expiry.
2. **It does not authorize wiring to begin immediately.** §C's ordering is binding: **C1 must be
   satisfied before C2 begins.** GO-1 authorizes preparation *work* to start, and the first
   preparation item is the live CAPTCHA wiring plan. Wiring against the real endpoint is
   authorized by this record only once C1 is complete.
3. **It does not authorize any connectivity probe that writes.** §C3's binding wording governs:
   documented non-publishing operations only; no synthetic CAPTCHA submission, governed post,
   reply, or other write issued solely as a probe. `POST /api/v1/verify` is exercised for the
   first time only when a real governed post legitimately produces a challenge during §E.
4. **It does not pre-clear the first post's content.** §A4's representativeness test was shape and
   `action_type` only. The actual wording is bound at GO-2 via `payload_hash`.
5. **It does not move `preparation_baseline_commit`**, re-open any §A row, or confer any authority
   over the future contents of the documents it cites.
6. **It does not attest that the documents cited in §A's evidence are correct, complete,
   content-frozen, or independently authorized.** Each §A row carries its own version-bound
   attestation and its own disclaimer to that effect; this record inherits their scope and does
   not widen it.

---

## 6. Open items, ruled post-GO — granted with these in view

This authorization is granted in knowledge of the following, each previously ruled non-blocking for
GO-1. Listing them here records that they were in view at the moment of authorization rather than
overlooked.

| Item | Issue | Ruling |
|---|---|---|
| `KillSwitchActivation` records the operator as free text in `detail`, not a structured field | #57 | Post-GO (2026-08-06, §A2 row 5). The §10 record is produced, complete, and reviewable; the gap is in its shape, not its existence. |
| `approval_trace_id` on a live envelope is bound to no resolution trace — `as_client_transport` defaults it to a fresh `uuid4` | #64 (PG-2) | Post-GO (2026-08-08, §A4). Disclosed verbatim in the rehearsal transcript. |
| The `arbiter MoltbookArbiter { … }` block is mandatory at validation time but has no runtime consumer | #65 (PG-3) | Post-GO (2026-08-08, §A4). Governs self-modification (Ruling 9.7), not content actions. |
| `docs/m7_first_live_post_governed_envelope.md` imposes GO-2 gating obligations while still marked `Status: DRAFT` | — | **Open, unresolved.** Finding (a) of §A3 row 1 (2026-08-07). |
| Envelope §3 states `t3_grounding_reference` must be populated before GO-1, whereas this checklist carries the rider only at §D (GO-2) and §E | — | **Open, unresolved.** Finding (b) of §A3 row 1 (2026-08-07). A rider-population question falling due at §D. |

The last two rows are **not** post-GO rulings. They are open governance questions, identified
during the §A3 reading and deliberately not settled there, and they are not settled by this record
either. They are named here so that granting GO-1 is not read as having disposed of them.

**Finding (b) bears directly on this record and is treated at length, because its own wording makes
it a GO-1 precondition rather than a later question.** `docs/m7_first_live_post_governed_envelope.md`
§3 states: "the first-post rider's `t3_grounding_reference` field must be populated before GO-1."

What was verified for this record, and no more than this:

- Both referents named by the field's definition (envelope §2) exist and are committed:
  `docs/m7_identity_integrity_ruling_addendum_2.md`, and
  `docs/m7_cadence_integrity_ruling_amendment_2.md`, whose §A2.7 ("Standing falsification check —
  status going forward") is present as cited.
- The commitment of both is what §A1 rows 2 and 4 attest, signed 2026-08-04.
- **No first-post rider instance exists in the repository.** The rider is assembled at GO-2 under
  §D. There is therefore no populated field today, because there is no instance to carry one.

The two available readings are set out without choosing between them:

1. **Substance.** §3 requires the grounding record to exist and be committed before GO-1, so that
   the field has a real referent when the rider is later assembled. On this reading the
   requirement is satisfied, and no rider instance is needed now. This reading is supported by the
   field's own `Source` column — "Committed `docs/` rulings" — and by the fact that the rider
   cannot be fully populated before GO-1 by construction, since `execution_commit_reference` and
   `correction_procedure_reference` both derive from work that GO-1 is what authorizes.
2. **Form.** §3 means an actual rider instance with the field filled must exist before GO-1 is
   granted. On this reading GO-1 cannot be signed until such an instance is created.

**This record does not rule between them.** Selecting a reading is an operator act, as the
`preparation_baseline_commit` clause at §2 was. If reading 2 is adopted, this record is not
signable as it stands and the rider instance must come first.

---

## 7. Version binding and the limits of this record

This record is bound to the repository states it names: the §A record at `334db60` (identical at
`7483d80`), and `preparation_baseline_commit` `008d3ba`.

A material change to §A's content requires a fresh review and a fresh GO-1 record; this one does
not inherit forward. This record attests to the operator's decision to authorize preparation on the
evidence identified above. It does not attest that the underlying mechanisms are correct or
complete, and it confers no authority over the future contents of any document it cites.

Nothing has been transmitted. Recording this authorization does not change that.
