# M7 — First Live Post: Governed Action Envelope

**Status: DRAFT — pending operator review and sign-off.** This is not a transport specification
and does not amend `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` (LOCKED
2026-07-20) or any of its Implementation Notes (A–F). It does not redefine `ActionEnvelope` (§4
of that spec, implemented as `moltbook.transport.ActionEnvelope`). It adds a first-instance-only
governance layer on top of the existing envelope for exactly one action: the first live governed
post or reply Continuum's deployed agent transmits to Moltbook. Once that action has resolved
(published, not published, or definitively failed), this document's obligations are discharged —
routine subsequent actions are governed by the transport spec alone, not by this document.

This distinction matters for the same reason `docs/m7_moltbook_transport_boundary_and_deployment_spec.md`
§11 (Dry Run) and Note E's stop conditions exist: the first live action is the one point where
every seam that has only ever been tested is touched by something real for the first time. The
extra requirements below exist to make that crossing observable and reversible, not to make the
action itself more "permitted" than any later one — permission is still decided by the resolver
alone (§2 of the transport spec; this document changes nothing about who authorizes an action).

---

## 1. Relationship to the standard Approved Action Envelope

Every outbound write, first or five-thousandth, still requires a standard `ActionEnvelope` per
§4: `action_id`, `action_type`, `payload`, `approval_trace_id`, `approval_timestamp`,
`approval_expiry`, `governance_config_version`, `payload_hash`. Nothing here changes that
dataclass, its `approve()` constructor, or `moltbook.transport.validate_envelope`'s three
rejection checks (expired, config drift, payload drift).

What this document adds is a **first-post rider**: a second artifact, produced alongside the
standard envelope and referencing it by `action_id`, that must exist and be reviewed before the
standard envelope for this one action is allowed to reach the transport. The rider is a governance
artifact, not a code change — it does not touch `moltbook/transport.py`.

## 2. First-Post Rider — required fields

| Field | Meaning | Source |
|---|---|---|
| `action_id` | Binds the rider to the exact standard envelope it covers. | `ActionEnvelope.action_id` |
| `t3_grounding_reference` | Pointer to the committed longitudinal grounding record: `docs/m7_identity_integrity_ruling_addendum_2.md` for IdentityIntegrity's cross-session observation — which records the T0–T3 result and **adopts no enforcement threshold** (§B4), v1.1 being post-GO work under §B5 — and `docs/m7_cadence_integrity_ruling_amendment_2.md` §A2.7 for the second A1.6 falsification check on CadenceIntegrity's ±5s grounding and its discharge. | Committed `docs/` rulings. The underlying T0–T3 capture files are held outside the repository; Addendum 2 §B6 reproduces the identity findings in full so this reference does not depend on them. |
| `dry_run_rehearsal_reference` | Pointer to a completed `DryRunTransport` run (§11) executed against this exact payload — same `payload_hash`, same `action_type` — producing detector results, Arbiter decision, approval trace, and simulated transport outcome with no external write. | `moltbook.transport.DryRunTransport` output (reserved-namespace IDs per `moltbook/dryrun.py`) |
| `captcha_configuration_state` | Confirms the transport's captcha configuration invariant (Note E, item 7: `captcha_verifier` and `submit_captcha_fn` both configured, or neither) and records which state it will be in for this send. | Constructor state at send time |
| `kill_switch_precheck` | Confirms `KillSwitch.engaged` is `False` immediately before this send, and that the operator has a tested, reachable path to call `KillSwitch.activate_manual(operator=...)` during the send if needed. | Runtime check, operator attestation |
| `operator_go_reference` | Pointer to the signed Operator GO Checklist (`docs/m7_operator_go_checklist.md`) instance covering this action — specifically the GO-2 (transmission) record, not GO-1 (preparation) alone. | Checklist artifact |
| `correction_procedure_reference` | Pointer to the finalized **Published-Outcome Correction and Withdrawal Procedure** covering what happens if `publication_status` resolves to `PUBLISHED` but the content needs to come down or be corrected, or if `AMBIGUOUS_WRITE`/`OUTCOME_UNKNOWN` freezes execution (§9). Per the checklist's GO-2 gating (`docs/m7_operator_go_checklist.md` §D), this procedure must be **finalized before GO-2 is granted** — it is no longer a deferred, non-gating item. Named deliberately as *correction and withdrawal*, not "rollback": a freeze under §9 stops further writes but cannot itself delete, edit, or otherwise reverse a post already visible on the platform, and most external APIs don't offer an atomic rollback of a public effect — the procedure must distinguish delete-when-supported, edit/correction-when-supported, corrective follow-up when neither is available, freeze-and-escalation, and audit preservation. | Published-Outcome Correction and Withdrawal Procedure (finalized under GO-1 preparation, required for GO-2) |
| `execution_commit_reference` | Pointer to the `execution_candidate_commit` (`docs/m7_operator_go_checklist.md` §D) — the exact, clean-tree commit whose code is what actually executes this send. Distinct from the `preparation_baseline_commit` reviewed at GO-1: live captcha wiring (C2) happens after GO-1, so the code reviewed at preparation time is not the code that transmits. | GO-2 record, §D |

The rider is satisfied only when every field above is filled with a real reference, not a
placeholder. An empty or "N/A" field is a stop, not a waiver — every field above is now a hard
requirement gated by GO-2 (§D of the checklist), so there is no longer an "interim fallback" case
to fall back to; if any field cannot be populated, GO-2 has not been reached.

## 3. Sequencing constraint (binding on this document only)

This document assumes and requires the two-stage authorization structure in
`docs/m7_operator_go_checklist.md`:

```
Preliminary readiness review (preparation_baseline_commit reviewed)
  → GO-1 (deployment preparation authorization)
      — permits: live submit_captcha_fn wiring, connectivity validation
        (no transmission, no synthetic /verify calls), runbook drafting,
        Published-Outcome Correction and Withdrawal Procedure drafting
  → wiring plan → live wiring → connectivity validation → runbook
    finalized → correction/withdrawal procedure finalized
    (execution_candidate_commit fixed, full suite re-run against it,
    clean tree confirmed)
  → GO-2 (first governed transmission authorization — single-use, bound
    to one action_id / payload_hash / execution_candidate_commit /
    governance_config_version, with an explicit expiry)
  → first governed post
```

GO-1 authorizes *preparation* — including starting live `submit_captcha_fn` wiring — but never
authorizes transmission. Concretely: the first-post rider's `t3_grounding_reference` field must be
populated before GO-1; `captcha_configuration_state`, `correction_procedure_reference`,
`execution_commit_reference`, and `operator_go_reference` (the GO-2 record specifically) must all
be populated before this rider is complete and the standard envelope may reach the transport.
GO-2 itself is single-use: bound to one `action_id`, one `payload_hash`, one
`execution_candidate_commit`, and one `governance_config_version`, with an explicit expiry — any
change to payload, code, configuration, or credentials invalidates it and requires a fresh GO-2
record (§D of the checklist). If live wiring or transmission happens out of this order — wiring
before GO-1, transmission before a valid, unexpired, unconsumed GO-2 — that is a process violation
of this document, independent of whether the resolver would have approved the underlying action on
its own.

## 4. What this document does not do

- It does not create a new `ActionType`, a new Pi Script constraint, or a new 9.x grammar ruling.
- It does not change §9 reconciliation authority, §10 kill-switch triggers, or §14's dormant
  automated triggers — none of those become active by virtue of this being the first post.
- It does not authorize live captcha wiring by itself (consistent with Note E's closing stop
  condition: "First live observation requires a real write; that write is itself a governed
  action needing its own approved envelope and operator go-ahead — this note does not authorize
  it.") — that authorization is the Operator GO Checklist's job, not this rider's.
- It does not replace or weaken any Note A–F requirement; it is additive and first-instance-scoped
  only.

## 5. Discharge condition

This document's obligations end **only** when all of the following are true:

1. The first live action has reached a **non-ambiguous terminal state** — `publication_status`
   is `PUBLISHED` or `NOT_PUBLISHED`, and `verification_status` is one of `PASSED`, `FAILED`,
   `EXPIRED`, or `NOT_REQUIRED` (never left at a bare `REQUIRED` with no further resolution).
   `OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE` (§9) is explicitly **not** a terminal state for this
   purpose — the rider stays active for as long as either status is open, with no default timeout
   that closes it out on its own.
2. Every required trace and verification record is persisted: the RESOLUTION TRACE for the
   action, and — if verification was required — the corresponding `CaptchaAttemptRecord`.
3. The operator has recorded, in writing, either (a) acceptance of a `PUBLISHED` outcome, or
   (b) completion of the applicable reconciliation procedure (§9) for an `OUTCOME_UNKNOWN` that
   was subsequently resolved, or (c) completion of the Published-Outcome Correction and Withdrawal
   Procedure (`docs/m7_operator_go_checklist.md` §C5) for a `PUBLISHED` outcome that required
   correction or takedown.

Only once all three are true does action #2 onward proceed under the standard transport spec
alone, with this rider closed.
