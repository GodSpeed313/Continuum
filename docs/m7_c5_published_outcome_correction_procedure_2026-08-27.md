# M7 — C5: Published-Outcome Correction and Withdrawal Procedure

**Status: DRAFT — pending operator review and sign-off.** This is the artifact required by
`docs/m7_operator_go_checklist.md` §C item **C5** ("Published-Outcome Correction and Withdrawal
Procedure finalized"). It follows the C1/C3/C4 precedent — a standalone dated record rather than a
row-embedded decision. Once reviewed, C5's row cites this document; this document is not itself
the attestation.

This document amends no numbered section of
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md`, of
`docs/m7_first_live_post_governed_envelope.md`, of `docs/m7_operator_go_checklist.md`, of
`docs/moltbook_api_spec.md`, or of any ruling in `docs/`. It defines a procedure that operates on
outcomes those documents already produce; it does not redefine any status enum, envelope field, or
transport behaviour.

**Nothing here authorizes transmission.** This document governs what happens *after* a governed
post or reply has already resolved to `PUBLISHED`. It does not touch GO-2, the runbook (C4), or
the send path itself.

## 1. Scope and trigger condition

This procedure applies only when a governed action's `publication_status`
(`moltbook.transport.PublicationStatus`) has resolved to `PUBLISHED`, and the operator determines
the published content is incorrect and needs to come down or be corrected. This is checklist §E's
"If `PUBLISHED` but incorrect" row, and it is the specific case named at envelope doc §5(3)(c):

> (c) completion of the Published-Outcome Correction and Withdrawal
> Procedure (`docs/m7_operator_go_checklist.md` §C5) for a `PUBLISHED` outcome that required
> correction or takedown.

This procedure does **not** apply to `OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE`. That condition is
already governed by boundary spec §7–§9 (operational freeze, Reconciliation Authority, and §9's
"Never retry while OUTCOME_UNKNOWN exists.") and by C1 §6 (AMBIGUOUS final as a classification,
disposition after `verify()` unresolved and carried as its own open item). This document does not
re-derive or restate that logic — see §4 for how the two connect without merging into one path.

## 2. Capability finding (grounds §3's dispositions)

Before dispositions can be defined, what is actually available has to be checked rather than
assumed. **Two independent bars stand between this procedure and a platform-level delete or edit.
Either alone is sufficient; the second is dispositive.**

**Bar 1 — the documented platform surface.** `docs/moltbook_api_spec.md` §4 ("Core Endpoints
Relevant to Phase One") lists, for posts and comments, five rows only: `POST /api/v1/posts`,
`GET /api/v1/posts`, `GET /api/v1/posts/{POST_ID}`, `POST /api/v1/posts/{POST_ID}/comments`,
`GET /api/v1/posts/{POST_ID}/comments`. No delete or edit endpoint appears. §5's rate-limit table
lists "Write requests (POST/PUT/PATCH/DELETE) | 30 / 60s" — that is a **method-class category, not
evidence that a per-resource delete or edit endpoint exists** for posts or comments. §4 adds that
the "Full endpoint surface (submolts, follows, voting, moderation, notifications, labels) exists
but is out of scope for the Phase One slice **per the boundary spec §12**."

**Bar 2 — the governing ruling, which is dispositive.** Deletions and edits are not merely
undocumented here; they are **explicitly deferred out of Phase One by boundary spec §12**, which
lists under "Deferred to later slices": DMs; mentions; notifications; **deletions**; **edits**;
account mutation; and registration automation. `moltbook/transport.py`'s `MoltbookHTTPTransport`
docstring restates the same ruling as an implementation invariant: deletions and edits "are
explicitly deferred (§12) and have **NO methods here at all, not even unused stubs** — there is no
'escape hatch' endpoint surface (§6)."

This finding is load-bearing, and its direction matters. **§3.1 and §3.2 are unavailable by
ruling, not by absence of evidence.** The distinction is operational, not academic: it means
confirming that a live delete endpoint exists would **not** make them available. Wiring one would
change transport responsibilities and execution boundaries, both of which §16's Lock Condition
places behind a formal amendment, and §6 independently prohibits the transport from "select[ing]
alternative endpoints" or "expos[ing] unrestricted request methods." Accordingly this procedure
does not treat platform-capability discovery as its open question, and does not recommend probing
for one — see §5.

Corrective follow-up (§3.3) is therefore the only operative correction-shaped disposition under
Phase One **by design of the slice**, not by accident of documentation.

## 3. The five dispositions

Per the checklist row's binding wording, this procedure distinguishes five dispositions rather than
treating correction as a single atomic action. This is explicitly **not** a "rollback" in the
atomic-reversal sense — most external APIs, including this one as documented, offer no such thing,
and no wording below may be read to imply one.

### 3.1 Delete (when supported)

**Not available under Phase One.** Deletions are deferred by boundary spec §12 and the transport
carries no method for one, by design. This branch is defined structurally so that the procedure is
complete, and so that the conditions for its availability are stated rather than left to
improvisation at the moment it is wanted.

Two conditions must both be met before this branch becomes exercisable, in this order:

1. **Governance:** a formal amendment moving deletions into scope, following §16's discipline
   (this touches transport responsibilities and execution boundaries).
2. **Capability:** a delete endpoint for the affected resource confirmed against the live platform
   by direct observation under the discipline C3 used — documented and observed, never inferred
   from §5's method-class line.

The governance condition is first because satisfying the capability condition alone establishes
nothing this procedure may act on. If and when both are met, the branch becomes: issue the delete
as a governed write, capture the resulting HTTP status and body, and record the outcome in the
RESOLUTION TRACE for the original action, cross-referenced by `action_id`.

### 3.2 Edit / correction (when supported)

**Not available under Phase One**, on identical grounds — edits are named alongside deletions in
§12's deferral list and have no transport method. The same two conditions in the same order apply.

If and when both are met: an edit is itself a governed write. It requires its own
`ActionEnvelope`, its own approval, and passes `validate_envelope()` like any other write. An edit
is not exempt from governance because its purpose is corrective.

### 3.3 Corrective follow-up (when neither is available)

**This is the currently-operative disposition**, per §2. When neither §3.1 nor §3.2 is available,
correction takes the form of a new, separately governed post or reply that:

* is issued through the standard envelope flow — its own `action_id`, its own approval, its own
  `payload_hash`. It is a new governed action, not a continuation of the original one;
* explicitly and unambiguously states that it corrects or retracts a specific prior post, named or
  linked by its platform-assigned identifier;
* does not characterize the original error beyond what is factually necessary to issue the
  correction. This procedure does not govern the content-generation judgment involved in drafting
  the correction text — that remains an operator/content decision, not a transport or governance
  one; and
* is subject to every constraint already governing any other post — `LinkRestriction`,
  `CitationClusterIntegrity`, `CadenceIntegrity` and the rest of the active constraint set.
  Correction carries no exemption. Note that `CadenceIntegrity` and the API spec §5 post-creation
  limit (1 / 30 min; 1 / 2 hours for a new agent in its first 24 hours) both apply to the
  corrective post: **a correction cannot necessarily be issued immediately**, and the delay is not
  a defect in this procedure but a property of the platform and the cadence constraint.

**The original, incorrect post is not removed under this branch.** It remains live, uncorrected at
the platform level, with the correction visible as separate content. This is a materially weaker
remedy than deletion or edit, and the gap between what this branch can do and what "correction"
might be expected to mean is a **known and deliberate limitation of the Phase One slice**, recorded
here rather than smoothed over.

### 3.4 Freeze-and-escalation

This is **not** the same freeze as §9's `OUTCOME_UNKNOWN` reconciliation freeze, though it is
modelled on it and the term is used deliberately to signal the same posture: stop, attempt no
automated remedy, put a human in the loop.

This branch applies when none of §3.1–§3.3 is an adequate response to what happened — for example,
content that should not remain visible even briefly, where §3.3 alone is insufficient because it
leaves the original live and §3.1 is unavailable to remove it. In that case:

* no further governed write is issued automatically;
* the condition is escalated to the operator for a manual decision, which may include out-of-band
  action not mediated by this stack at all. This procedure does not assume such a channel exists;
  determining whether one does is left to the operator at the time; and
* the RESOLUTION TRACE for the original action is annotated with the escalation and its outcome
  once the operator resolves it, so the record does not go silent at the point of escalation.

**This is the expected branch for a serious incorrect publication under Phase One.** Because §3.1
and §3.2 are closed by ruling and §3.3 leaves the original live, escalation is not an exotic
fallback here — it is where the genuinely urgent case lands. That should be understood before
GO-2, not discovered during it.

### 3.5 Audit preservation

Regardless of which of §3.1–§3.4 is invoked, the RESOLUTION TRACE and — if verification was
required — the `CaptchaAttemptRecord` for the original action are never deleted, edited, or
superseded by this procedure. A platform-level delete or edit (§3.1/§3.2, should they ever open)
removes or changes what is visible on Moltbook; it does not remove or change Continuum's own record
that the action was taken, what it said, and what was subsequently done about it. This applies
symmetrically to any new governed action issued under §3.1–§3.4 — each gets its own trace, and none
retroactively edits the original.

## 4. Relationship to §9 (Reconciliation Authority)

Boundary spec §9 and this document govern two different moments and must not be collapsed:

| | Boundary spec §9 | This document (C5) |
|---|---|---|
| Trigger | Execution outcome is uncertain (`OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE`) | Execution outcome is certain (`PUBLISHED`) and the content is wrong |
| Question | "Did this write happen?" | "This write happened and is visible — what now?" |
| Governed by | Reconciliation Layer; deterministic confirmation; freeze if unresolved | §3 above |

A single action can pass through §9 and then this document *in sequence*: an ambiguous write that
reconciliation later confirms as `PUBLISHED`, and is subsequently found incorrect, moves from §9's
freeze into §3 once reconciliation closes it out as `PUBLISHED`. It cannot be in both states at
once, and this document's dispositions never apply while `OUTCOME_UNKNOWN` is still open — §9's own
rule, "Never retry while OUTCOME_UNKNOWN exists.", governs until it resolves.

## 5. What this document does not attest

It does not attest that a delete or edit endpoint exists on the platform — §2 found none
documented, and this document does not manufacture one. **Nor does it treat that question as its
open item:** per §2, deletions and edits are closed by §12's ruling, so discovering such an
endpoint would not make §3.1/§3.2 available, and this document does not recommend probing for one.
The open item, if the operator wishes to open it, is a **governance** question — whether to amend
§12 — not an evidentiary one.

It does not attest that §3.3's corrective-follow-up branch is a satisfying remedy for every
incorrect-publication scenario; it attests only that it is the currently-available one, and §3.4
records where the inadequate cases go. It does not attest that the out-of-band possibility named in
§3.4 is realized by any actual channel to the platform. It does not resolve C4 §8's forward
dependency beyond supplying the procedure that dependency was waiting on; C4's own text and
attestation limits are unchanged by this document's existence.

## 6. Version binding

Bound to `docs/moltbook_api_spec.md` §4/§5 as quoted at §2; to
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md` §6 (Prohibited Behaviors), §7–§9
(freezes and Reconciliation Authority), §12 (Minimum Viable Deployment Slice) and §16 (Lock
Condition) as quoted at §2 and §4; to `docs/m7_first_live_post_governed_envelope.md` §5(3)(c) as
quoted at §1; and to `moltbook/transport.py` at commit `b559882` (no delete or update method
present, per the `MoltbookHTTPTransport` docstring quoted at §2).

Does not inherit forward across a material change to any of them. In particular, **if §12 is ever
amended to bring deletions or edits into scope, §3.1 and §3.2 must be revisited against that
amendment and against a live capability confirmation before either is treated as available** — this
version binding is what triggers that review rather than letting it happen implicitly.
