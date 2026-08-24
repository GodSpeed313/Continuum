# M7 — C4: First-Post Runbook

**Status: FINALIZED — signed by Kevin Brown, 2026-08-24 10:58 EDT, citing `docs/m7_operator_go_checklist.md` §C4.** This is the artifact required by
`docs/m7_operator_go_checklist.md` §C item **C4** ("First-post runbook finalized — step-by-step
execution script for §E"). It follows the C1/C3 precedent — a standalone dated record rather than
a row-embedded decision. Once reviewed, C4's row cites this document; this document is not itself
the attestation.

This document **amends no numbered section** of `docs/m7_moltbook_transport_boundary_and_deployment_spec.md`,
of `docs/m7_first_live_post_governed_envelope.md`, of `docs/m7_operator_go_checklist.md`, or of any
ruling in `docs/`. It sequences existing obligations into an executable order, names one manual
control point the code does not enforce (§4 below), and states one terminal condition (§5 below)
that those documents already imply but do not spell out as a step. **Nothing here authorizes
transmission** — GO-2 does that, and this runbook only runs once GO-2 is signed and unexpired.

**Cross-reference convention.** A bare `§N` refers to this document. References to another
document's sections are always named — "envelope doc §5", "checklist §E", "transport spec §9".

---

## 1. What this runbook is for, and what it is not

This is the step-by-step sequence executed under checklist §E, once GO-2 is signed. It exists to
fix the *order* of the human and machine steps §E already lists, because one constraint — the
300-second envelope window (§2 below) — makes order safety-relevant in a way the checklist's row
list does not itself enforce.

It does **not** decide what counts as an acceptable outcome — the envelope doc §5 and checklist §E
already do that. It does not resolve the AMBIGUOUS-verification gap (§5 below states a stop
condition grounded in an existing ruling; it does not rule on the gap itself). It does not touch
`moltbook/transport.py`.

## 2. The window that fixes the order

`ActionEnvelope.approve()` sets `approval_expiry = approved_at + 300s`
(`moltbook/transport.py:74-92`), and `validate_envelope()` checks expiry **first**, before config
drift or payload drift (`moltbook/transport.py:113-144`). Every human-executed check in checklist
§E — the clean-tree recheck, the kill-switch precheck, review of the rider — has to complete
**before** the envelope is approved, not after: approving late in the window and then running
these checks eats into a fixed 300 seconds that cannot be extended, and a check that runs past
`approval_expiry` finds an already-rejected envelope, not a rejected-in-time one.

**Consequence for step order:** approval (`ActionEnvelope.approve()`) is the *last* preparatory
step before `send()` is called, not the first. Everything else — clean-tree confirmation,
`KillSwitch.engaged` recheck, rider review, GO-2 identifier match — happens against the *candidate*
payload and commit, before an envelope for it is even constructed.

## 3. The execution model the kill switch requires

`KillSwitch` is instance state — `__init__` sets `self._engaged = False` on the object
(`moltbook/transport.py:463-465`), and `check_write()` reads that same instance's flag
(`moltbook/transport.py:475-477`). Checklist §E's second row requires "a tested, reachable
`activate_manual(operator=...)` path open during the send" — reachable means the operator can call
`activate_manual()` on the **exact same `KillSwitch` instance** the transport holds, while `send()`
is running.

A fire-and-forget script (spawned, backgrounded, or run non-interactively) cannot satisfy this: by
the time the operator could intervene, the process holding that instance may have already returned
or moved on to the next line. **The send must run inside an interactive session the operator holds
open for its duration** — a REPL, a debugger, or an interactive script that pauses for operator
input at the send call itself — so that `activate_manual()` is a call the operator can actually make
against the live instance, not a note for later.

This is not a new requirement; it is what §E row 2 already requires, stated as an execution-model
constraint because the checklist doesn't otherwise say how it's satisfied.

## 4. Action-ID binding — manual control point

> **⚠ WARNING — unenforced binding.** `validate_envelope()` (`moltbook/transport.py:113-144`)
> checks exactly three things: expiry, `governance_config_version`, and recomputed `payload_hash`.
> It **never checks `action_id`**. `send()` contains no reference to `action_id` for validation
> purposes anywhere in its body either. **No code anywhere in the transport checks a constructed
> envelope's `action_id` against GO-2's `authorized_action_id`.**

The dangerous sequence this enables: GO-2 fixes an `authorized_action_id` in writing → the operator
constructs the live envelope at step 6 of §7 below → `ActionEnvelope.approve()` silently generates
a fresh random UUID via `uuid.uuid4()` if `action_id` is omitted from the call
(`moltbook/transport.py:81-92`) → the resulting envelope has the wrong `action_id`, but still passes
every check `validate_envelope()` runs (expiry: fine; config version: fine; payload hash: fine,
since hash is a function of `payload`, not `action_id`) → `send()` transmits it without objection.

**This is the single point in the entire sequence with no structural backstop — assuming this
document's code inspection above is complete and there is no other indirect enforcement path.**
Every other GO-2 binding (`payload_hash`, `governance_config_version`) is checked mechanically by
`validate_envelope()`. `action_id` is not.

**Required control:** the operator MUST explicitly verify, before approval, that the `action_id`
about to be passed to `ActionEnvelope.approve()` equals GO-2's recorded `authorized_action_id`, and
must pass it explicitly (`action_id=authorized_action_id`) rather than omitting the argument. This
is a procedural control filling a gap the code does not fill — **not** a claim that this document
is establishing a new invariant, and not a suggestion that the code ought to be changed to enforce
it. That is an architectural question outside C4's scope. C4's job is limited to naming that the
gap exists and requiring the operator to close it by hand at this specific point.

## 5. The AMBIGUOUS-verification terminal condition

### 5.1 What the code returns

`MoltbookHTTPTransport.send()`'s verification classification (`moltbook/transport.py:1620-1647`)
has three branches. On `CaptchaOutcome.AMBIGUOUS` — the residual branch, `moltbook/transport.py:1635-1641`
— it returns, per the values set at `moltbook/transport.py:1636-1637` and the common
`TransportResult` construction at `moltbook/transport.py:1642-1647`:

```
TransportOutcome.SUCCESS
publication_status = PublicationStatus.PENDING_VERIFICATION
verification_status = VerificationStatus.REQUIRED
```

**This is not a failure and this runbook does not call it one.** The transport's own outcome is
`SUCCESS` — the write transmitted. The governance problem is narrower and different: `SUCCESS`
does not, by itself, discharge the envelope doc's rider. Labeling this branch "failure" anywhere in
this runbook would be an unauthorized semantic conversion of exactly the kind C1 §3.1's
classification principle exists to prevent, and would misdirect whoever reads the record later.
This runbook calls it what the record calls it: an open, non-discharging state.

### 5.2 Why no existing procedure routes it

Three procedures could plausibly apply. None does.

- **§9 reconciliation** (`resolve_ambiguous_write()`, `moltbook/transport.py:384-421`) operates
  only on `TransportOutcome.OUTCOME_UNKNOWN` — it raises `ValueError` if called on anything else
  (`moltbook/transport.py:404-405`). The branch in §5.1 returns `TransportOutcome.SUCCESS`, so this
  function is not callable on it, not merely inapplicable in spirit.
- **Checklist §E row 6** ("published but incorrect") requires `publication_status = PUBLISHED`.
  The branch in §5.1 sets `publication_status = PENDING_VERIFICATION`, which is not `PUBLISHED`.
  Row 6, and the §C5 procedure it invokes, is out of scope for this state on its own stated terms.
- **Checklist §E row 5** ("`OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE`") requires the transport-level
  `TransportOutcome` to be one of those two. It is `SUCCESS` here, so row 5 does not fire either.

**No row in §E names this state**, and no reconciliation function is authorized to act on it. This
matches C1 §8 item 7 and the corresponding `TODO.md` entry: the disposition of a verify-level
`AMBIGUOUS` outcome was deliberately left unresolved, "an architectural question for its own
ruling," and explicitly not closed by C2.

**Additional code-grounding for the same distinction:** the `TransportResult` construction shared
by all three verify branches uses `RetryCategory.IDEMPOTENT_WRITE` (`moltbook/transport.py:1643`).
Send-level `AMBIGUOUS_WRITE` is a different `RetryCategory` value entirely, paired with
`TransportOutcome.OUTCOME_UNKNOWN` (`moltbook/transport.py:1522`, `:1558`). Verification-level
ambiguity and send-level ambiguity are mechanically distinct paths in the transport's own
vocabulary, not merely distinct by this document's argument.

### 5.3 The existing ruling that governs this send

`TODO.md`'s carried item states the ruling directly: this gap "is not blocking GO-2, since §E is
human-executed and captures all three statuses." That ruling — not a new one — is what this
runbook executes. It was made on the premise that a human is present at exactly this moment,
watching `publication_status` and `verification_status` land, able to hold rather than proceed.

The envelope doc §5(1) independently confirms what "holding" means procedurally: `REQUIRED` is
named among the values that do **not** discharge the rider, and the rider "stays active for as
long as either status is open, with no default timeout that closes it out on its own." So this
runbook does not need to invent a resolution — the governing document already specifies the
correct state for an unresolved verification: open, and open indefinitely until further action.

### 5.4 The step

If `send()` returns `publication_status = PENDING_VERIFICATION` and
`verification_status = REQUIRED` (§5.1):

1. **Stop.** Do not retry the send. Do not call `resolve_ambiguous_write()` — it does not accept
   this outcome (§5.2) and calling it would raise, not resolve.
2. **Record**, per checklist §E row 4: the resulting statuses, the RESOLUTION TRACE, and the
   `CaptchaAttemptRecord` (mandatory per C1 §7 — `condition_id` will show which §3.3 condition
   matched, or that none did).
3. **Leave the rider open.** Per envelope doc §5(1), it is not discharged. Record the transmission
   timestamp on GO-2's `consumed_at` per §D — that field records that GO-2 was consumed by a
   transmission, not that any obligation closed.

   **Interpretation, not an explicit rule:** the materials appear to treat `consumed_at` and rider
   discharge as separate closure questions, because they arise from distinct governance artifacts
   — GO-2 (§D) authorizes one transmission; the rider (envelope doc §5) tracks a separate
   obligation with its own three-part discharge condition. Nothing in either document states this
   separation explicitly. Read it this way absent a ruling to the contrary; do not treat this
   runbook's reading as a settled rule.
4. **Escalate to the operator for a decision on next action** — resend under a fresh envelope,
   wait, or something else. This runbook claims no authority to choose among those and does not
   attempt to. That decision, if it requires anything beyond waiting, is itself a fresh governed
   action needing its own approval — this step is a stop, not a resolution.
5. **Do not treat elapsed time as resolution.** Per envelope doc §5(1), there is no default
   timeout. The rider stays open until an operator act closes it under one of envelope doc
   §5(3)'s three named paths — none of which currently covers this state, which is itself part
   of what gets escalated.

This step is a runbook stop condition, not a new governance ruling. It carries forward the
disposition already fixed by C1 §6, the `TODO.md` entry, and envelope doc §5(1); it settles
nothing that those documents left open.

## 6. Dry-run rehearsal — what it does and does not cover

`DryRunTransport.send()` requires `envelope.action_id` to start with `dryrun-`
(`moltbook/dryrun.py:13`, `moltbook/transport.py:1259-1263`) and raises `ValueError` otherwise. The
rider's `dry_run_rehearsal_reference` (envelope doc §2) must therefore be produced from a
**separately constructed envelope** carrying a reserved-namespace `action_id` — never the
`authorized_action_id` GO-2 binds. `moltbook/transport.py:1219-1221` provides
`make_dry_run_action_id()` for exactly this: use it rather than hand-building the
`dryrun-` string. Only `payload_hash` and `action_type` carry across between the rehearsal
envelope and the authorized one; `action_id` deliberately does not, and must not be made to.

`DryRunOutcome.simulated_outcome` is hardcoded to `TransportOutcome.SUCCESS`
(`moltbook/transport.py:1265`). The rehearsal therefore exercises `validate_envelope()`'s three
freshness checks (§2 above) faithfully, but **cannot rehearse** a captcha challenge, a captcha
failure, or the §5 AMBIGUOUS branch — those only exist in `MoltbookHTTPTransport.send()`'s network
path, which the dry run never calls. Nothing about §5 can be verified by rehearsal; the first time
the AMBIGUOUS branch can occur at all is during the real send. The dry run also cannot rehearse §4's
action-ID control point in any way that matters: a dry-run envelope's `action_id` is required to be
a `dryrun-` id, so it never exercises the real-envelope construction call where the omission risk
in §4 actually occurs.

## 7. Sequence

Preconditions: GO-2 signed and unexpired; `execution_candidate_commit` matches the current clean
tree; rider (envelope doc §2) fully populated, including `dry_run_rehearsal_reference` from a
completed rehearsal under a `dryrun-` id (§6 above).

1. **Open the interactive session** that will hold the `KillSwitch` instance and call `send()` —
   per §3, this is not a background process.
2. **Clean-tree recheck** — confirm the working tree still matches `execution_candidate_commit`.
3. **`KillSwitch.engaged` recheck** — confirm `False`, in this same session, on the instance that
   will be passed to the transport.
4. **Confirm the reachable `activate_manual()` path** — the operator can call it against this
   instance right now, from this session, without any additional setup.
5. **Rider re-review** — confirm `authorized_action_id` and `authorized_payload_hash` on the
   envelope about to be constructed match GO-2's recorded values exactly. See §4: this is the
   sequence's only unenforced control point.
6. **Construct and approve the standard `ActionEnvelope`** — the last step before send, per §2.
   Pass `action_id=authorized_action_id` explicitly (§4); do not let it default. This starts the
   300-second window.
7. **Call `send()`.** The operator remains present for the duration, kill switch reachable.

   **The rechecks in steps 2–5 remain the "immediately before send" checks required by checklist
   §E row 1 and by row 2's first clause; row 2's second clause — a reachable
   `activate_manual(operator=...)` path open *during* the send — is a standing condition
   discharged by the operator presence step 7 requires, not by step 4.** Steps 6 and 7 make no
   change to the working tree, and the operator's own act of initiating the send — which §3
   requires — is not such a change. For the kill switch the guarantee is stronger than an
   unbroken recheck window: `send()` calls `validate_envelope()`, `kill_switch.check_write()` and
   `eligibility.check_write()` before any network call (`moltbook/transport.py:1472-1474`), and
   `check_write()` is by contract the final outbound-boundary enforcement — "called immediately
   before the actual network write, not just once somewhere upstream"
   (`moltbook/transport.py:448-450`). Step 3's confirmation is therefore re-enforced in code at
   the instant of transmission.

   `engaged` is not thereby fixed for the whole of step 7 — the captcha-suspension-risk trigger
   (`moltbook/transport.py:495`) can engage the switch during verification. Per `send()`'s own
   contract, verification "gates PUBLICATION, not transmission — the write has already happened
   by the time it runs" (`moltbook/transport.py:1447-1448`), so it cannot affect the transmission
   that steps 2–5 gate. The operator's reachable `activate_manual(operator=...)` path — row 2's
   second clause above — stays open across that window.
8. **Record the outcome** — `transmission_status` / `publication_status` / `verification_status`,
   RESOLUTION TRACE, `CaptchaAttemptRecord` if verification ran, `consumed_at` on GO-2 (checklist
   §E row 4).
9. **Branch on outcome:**
   - `OUTCOME_UNKNOWN` / `AMBIGUOUS_WRITE` → checklist §E row 5 (freeze, escalate per §9).
   - `PUBLISHED` and correct → envelope doc §5(3)(a), operator records acceptance.
   - `PUBLISHED` but incorrect → checklist §E row 6, forward dependency on §C5 (§8 below).
   - `PENDING_VERIFICATION` / `REQUIRED` → §5 above: stop, record, escalate.
   - `NOT_PUBLISHED` with `FAILED` or `EXPIRED` → terminal per envelope doc §5(1); operator records
     disposition.

## 8. Forward dependency on §C5

Checklist §E row 6 invokes the Published-Outcome Correction and Withdrawal Procedure (§C5), which
is **not started** as of this document. This runbook records that dependency rather than resolving
it: if the first send publishes incorrect content, §7 step 9's "published but incorrect" branch
points to a procedure that does not yet exist. This is recorded here as a known forward reference,
consistent with how GO-1 authorized preparation before §C's artifacts existed — not a defect
introduced by this document, and not something C4 can close on its own.

## 9. What this document does not attest

It does not attest that C5 exists, that the AMBIGUOUS-verification gap is resolved, or that a send
executed under this sequence will succeed. It records the order forced by the envelope window
(§2), the execution model forced by the kill switch (§3), an unenforced manual control point named
rather than closed (§4), a stop condition already implied by existing rulings rather than newly
authorized here (§5), and the dry-run's actual coverage (§6). A material change to the envelope
doc, the transport spec, or the checklist requires review of this document against the change
rather than assuming it still holds.

## 10. Version binding

Bound to the transport implementation at **`52a8c9c`** (main, post-C3), to
`docs/m7_first_live_post_governed_envelope.md` §5 as quoted at §5.3 and §5.4 above, and to
`docs/m7_operator_go_checklist.md`'s §D and §E as quoted. Does not inherit forward across a
material change to any of them.
