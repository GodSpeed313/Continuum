# M7 — Moltbook Transport Boundary and Deployment Specification

**Status:** LOCKED / binding for implementation (signed off 2026-07-20). This is the canonical
spec-first specification required by `CLAUDE.md` and the M7 spec-first discipline for the
`MoltbookClient` transport/execution layer. No transport implementation, deployment code,
authentication layer, API integration, or Moltbook execution logic may be written before this
document is locked — it now is. Build order: transport module implementing this spec → wired as
the `transport` param to `MoltbookClient` → acceptance tests (§13) → THEN, separately, the manual
account-creation/API-key step (never a code task, see §12).

This document is **not**:

* a Pi Script constraint;
* a 9.x grammar ruling; or
* a seventh M7 behavioral constraint.

It is an architectural specification governing the infrastructure beneath Continuum's enforcement
layer.

Per Continuum's **spec-first discipline**, no transport implementation shall be written until
this document is explicitly approved and locked.

---

# 1. Purpose

The purpose of this specification is to define the execution boundary separating Continuum
governance from the Moltbook execution layer.

Continuum determines **whether** an action is permitted.

The transport determines **how** an already-approved action reaches Moltbook.

The transport is not a governance component and must never become one.

---

# 2. Core Architectural Invariant

The Moltbook transport is a **non-semantic execution adapter**.

It may transmit only **Approved Action Envelopes** explicitly approved by the Continuum
governance pipeline.

It must preserve the approved payload without reinterpretation and return normalized execution
outcomes for deterministic reconciliation.

The transport must never independently:

* authorize actions;
* deny actions;
* reinterpret intent;
* generate content;
* modify content;
* rewrite links;
* change cadence;
* schedule behavior;
* retry governance-denied actions;
* alter governance decisions.

In short:

> **Transport executes. Continuum decides.**

---

# 3. Architectural Flow

```text
Agent Intent
      │
      ▼
Continuum Governance
      │
      ▼
Detector Evaluation
      │
      ▼
Arbiter Resolution
      │
      ▼
Approved Action Envelope
      │
      ▼
Moltbook Transport
      │
      ▼
Moltbook API
      │
      ▼
Normalized Platform Outcome
      │
      ▼
Deterministic Reconciliation
      │
      ▼
Cadence Store
Identity Store
Citation Store
```

Nothing beneath the Arbiter may modify governance decisions.

---

# 4. Approved Action Envelope

Every outbound write must originate from an Approved Action Envelope.

Minimum required fields:

* action_id
* action_type
* payload
* approval_trace_id
* approval_timestamp
* approval_expiry
* governance_config_version
* payload_hash

The transport shall reject execution when:

### Approval Expired

Current time exceeds approval_expiry.

### Governance Drift

Current governance version differs from governance_config_version.

### Payload Drift

Current payload hash differs from payload_hash.

No outbound network transmission shall occur after any of these failures.

---

# 5. Transport Responsibilities

The transport is responsible only for:

* authentication;
* request construction;
* serialization;
* network transmission;
* timeout handling;
* response normalization;
* deterministic reconciliation inputs; and
* structured audit logging.

The transport is explicitly **not** responsible for:

* semantic interpretation;
* policy evaluation;
* intent resolution;
* cadence enforcement;
* citation analysis;
* identity analysis;
* rule arbitration.

---

# 6. Prohibited Behaviors

The transport shall never:

* generate content;
* modify approved content;
* rewrite URLs;
* inject metadata;
* select alternative endpoints;
* dynamically schedule posts;
* suppress detector output;
* bypass governance;
* expose unrestricted request methods;
* log credentials;
* retry governance-denied actions; or
* infer success from uncertainty.

---

# 7. Operational Freezes vs Governance Violations

Operational freezes and governance violations are separate event classes.

Operational freezes include:

* ambiguous write outcomes;
* reconciliation uncertainty;
* authentication anomalies; and
* transport safety conditions.

Governance violations include enforcement of:

* CredentialIntegrity;
* LinkRestriction;
* IdentityIntegrity;
* CadenceIntegrity; and
* CitationClusterIntegrity.

Operational freezes are **not** Pi Script violations.

They must never be recorded through the Arbiter's violation-trace path.

Violation traces and operational safety traces shall remain permanently distinct.

---

# 8. Retry Taxonomy

## Safe Reads

Normal retry policy permitted.

Examples:

* feed retrieval;
* profile retrieval.

---

## Idempotent Writes

Retries permitted only when:

* platform idempotency guarantees exist; or
* deterministic duplicate detection exists.

---

## Ambiguous Writes

If execution cannot be determined:

Outcome becomes:

OUTCOME_UNKNOWN

No retry occurs.

Proceed immediately to reconciliation.

---

## Governance Denials

Never retry.

Governance decisions are terminal.

---

## Rate Limited (added by Implementation Note C, 2026-07-20)

**This fifth category extends the four originally locked above.** See Implementation Note C
(after Notes A/B) for the full binding treatment; summarized here for §8's own completeness.

HTTP 429 maps to `RATE_LIMITED` — distinct from `GOVERNANCE_DENIAL`, `AMBIGUOUS_WRITE`, and a
terminal `FAILURE` with no further path. A `RATE_LIMITED` result means the platform
deterministically refused THIS attempt because of rate limiting; the underlying governed action
may remain eligible for a later, newly authorized attempt — it is not terminal in the way
`GOVERNANCE_DENIAL` is, and it is not uncertain in the way `AMBIGUOUS_WRITE` is.

The transport must never initiate that later retry itself. Retry timing must never be guessed or
hard-coded. Automated retry stays disabled until (a) the request seam exposes `Retry-After` and
the relevant `X-RateLimit-*` headers, and (b) the resulting scheduling behavior is itself
explicitly specified — neither exists yet (§8 is intentionally silent on scheduling until then).
A future retry attempt must revalidate approval freshness, governance configuration version, and
payload hash (§4) exactly as any other send would — never reuse an expired approval blindly just
because the underlying content hasn't changed.

---

# 9. Reconciliation Authority

Authority is deliberately separated.

## Arbiter

Determines permission only.

Never determines execution success.

---

## Transport

Reports only:

* SUCCESS
* FAILURE
* OUTCOME_UNKNOWN

Nothing more.

---

## Reconciliation Layer

Attempts deterministic confirmation using factual platform evidence such as:

* idempotency lookup;
* platform receipt lookup;
* deterministic action matching; and
* deterministic payload matching.

If resolved:

Record SUCCESS or FAILURE.

If unresolved:

Freeze outbound execution.

Escalate to operator.

Never retry while OUTCOME_UNKNOWN exists.

---

# 10. Kill Switch

## Activation Authority

Activation may occur through either:

### Manual

Explicit operator command.

### Automated

Only the following exhaustive conditions are **active** at lock time:

* unresolved ambiguous writes; and
* reconciliation contradictions.

This list is exhaustive. Any additional automated trigger requires a formal specification
amendment.

**Active automated triggers at lock time are therefore exactly two: unresolved ambiguous writes,
and reconciliation contradictions.** Repeated integrity failures and authentication anomalies are
both **dormant** pending amendment — see §14 for both, and for why neither is active yet.

---

## Activation Behavior

Activation is fail-closed.

Immediately blocks all outbound writes.

Safe read operations may continue where explicitly permitted.

---

## Re-enablement

Only the operator may clear the kill switch.

No detector, reconciliation process, retry routine, health check, or successful subsequent
request may automatically restore outbound execution.

Multiple trusted paths may stop execution.

Only the operator may restart it.

---

## Structured Activation Audit

Every activation event shall record:

* activation mode (manual or automated);
* triggering condition;
* detector state (if applicable);
* authentication state (if applicable);
* reconciliation state (if applicable);
* timestamp;
* affected action class; and
* triggering trace identifier where available.

A boolean "kill switch active" indicator is insufficient.

---

# 11. Dry Run Mode

Dry Run executes the complete governance pipeline without performing external writes.

Generated artifacts include:

* detector results;
* Arbiter decision;
* approval trace;
* Approved Action Envelope; and
* simulated transport outcome.

No external write occurs.

---

## Structural Isolation

Dry Run identifiers shall use a reserved namespace.

Production ingestion must reject these identifiers structurally.

Rejection shall never depend on developer convention.

Dry Run artifacts are permanently incompatible with production state.

---

# 12. Minimum Viable Deployment Slice

Phase One includes:

* authentication;
* health check;
* feed reads;
* governed public posts;
* governed replies;
* normalized transport outcomes;
* structured audit logging;
* kill switch; and
* dry-run mode.

**Phase One supports two action types, not one: governed public posts AND governed public
replies.** This is a deliberate scope decision, not scope creep. CitationClusterIntegrity's edge
store requires reply-level activity to ever ground past its structurally inert (`params=None`,
NOT EVALUABLE) state — standalone posts alone don't exercise the conversational citation behavior
(directional edges, reciprocal pairs, external-degree ratio) the constraint was built to observe.
A posts-only Phase One would leave CitationClusterIntegrity permanently ungroundable even after
deployment, which defeats the purpose of shipping this slice.

Deferred to later slices:

* DMs;
* mentions;
* notifications;
* deletions;
* edits;
* account mutation; and
* registration automation.

### Coverage Note

Because DMs and mentions are deferred, CredentialIntegrity's foreign-key relay path remains
untested against live adversarial traffic until Slice Two.

This limitation is intentional.

It shall not be interpreted as grounding.

---

# 13. Acceptance Tests

### Core Boundary

Attempt outbound execution without an Approved Action Envelope.

Expected:

* rejected;
* no network transmission.

---

### Approval Freshness

Expired approval.

Expected:

Rejected.

---

Configuration drift.

Expected:

Rejected.

---

Payload hash mismatch.

Expected:

Rejected.

---

### Transport Authority

Attempt payload modification.

Rejected.

---

Attempt endpoint substitution.

Rejected.

---

Attempt unrestricted outbound request.

Rejected.

---

### Retry Policy

Safe reads retry successfully.

---

Governance denials never retry.

---

Ambiguous writes enter OUTCOME_UNKNOWN.

No retry occurs.

---

### Reconciliation

Confirmed success updates state.

Confirmed failure updates state.

Unresolved outcomes freeze execution and escalate.

---

### Kill Switch

Manual activation blocks all outbound writes.

---

Automated activation blocks all outbound writes. **This test exercises only the currently-active
triggers — unresolved ambiguous writes and reconciliation contradictions. It shall not use, and
does not depend on, either dormant trigger (§14).**

---

**Dormant-trigger non-activation (companion negative test, required):** attempt to fire the
dormant authentication-anomaly path (e.g., simulate repeated authentication failures) and confirm
the kill switch does **NOT** activate. This is what actually proves the trigger stays inert,
rather than merely asserting that it should. An equivalent negative test applies to the §14
repeated-integrity-failures trigger.

---

Permitted reads continue.

---

Operator-only re-enablement verified.

Automatic recovery rejected.

---

Structured activation audit verified.

---

### Dry Run Isolation

Generate Dry Run outcome.

Attempt ingestion into:

* Cadence Store;
* Identity Store; and
* Citation Store.

Expected:

* structural rejection;
* no production mutation;
* no grounded longitudinal data mutation.

---

# 14. Dormant Automated Triggers

Two automated kill-switch triggers are **defined but inactive** at the time this specification is
locked. Both follow the identical discipline: defined, rationale stated, inactive pending a
formal amendment. No implementation may invent or infer either threshold. This section states
that pattern once and applies it to both triggers identically — the structure below is shared,
not duplicated with drift.

## 14.1 Repeated Integrity Failures

Not interpreted subjectively. No implementation may invent or infer its activation threshold.

**Initial Lock State:** at the time this specification is first locked, the repeated integrity
failures trigger is **defined but inactive**. This inactive state is intentional and fail-safe.
The transport shall not infer, select, estimate, or hard-code a threshold during implementation.

Activation of this trigger requires a formal amendment defining, at minimum:

* the qualifying event type;
* whether only confirmed governance violations qualify;
* the numeric threshold;
* the counting window;
* whether counting is global or scoped by constraint, identity, endpoint, or action class;
* duplicate-event handling;
* counter reset and decay semantics; and
* the audit evidence required when the threshold is reached.

Until such an amendment is approved and locked, this trigger shall never activate the kill
switch.

## 14.2 Authentication Anomalies

Not interpreted subjectively. No implementation may invent or infer its activation threshold.

**Initial Lock State:** at the time this specification is first locked, the authentication
anomaly trigger is **defined but inactive**, mirroring §14.1 exactly. This inactive state is
intentional and fail-safe. The transport shall not infer, select, estimate, or hard-code a
threshold during implementation.

**Rationale for dormancy (why this is inactive rather than merely undefined):** authentication
failures primarily indicate loss of connectivity to the platform rather than uncertainty about
governance decisions. However, a genuine credential-compromise or credential-stuffing pattern
could also present as repeated authentication failure, which is precisely why a principled
threshold — not an invented one — is required before this trigger can safely distinguish the two.
Until operational experience establishes reliable anomaly criteria, manual operator review
provides a safer fail-closed response than threshold-based automatic activation.

Activation of this trigger requires a formal amendment defining, at minimum:

* the qualifying event type (e.g., authentication failure distinct from routine credential
  expiry);
* the numeric threshold (failure count);
* the counting window (time-bounded);
* reset conditions (e.g., an intervening successful authenticated request clears the count);
* whether counting is global or scoped by endpoint/action class; and
* the audit evidence required when the threshold is reached.

Until such an amendment is approved and locked, this trigger shall never activate the kill
switch. **Isolated, non-repeated authentication failures and routine credential expiry are not
governed by this trigger at all** — they are ordinary operational conditions handled by normal
error surfacing, not kill-switch material at any threshold.

## 14.3 Consistency

§14.1 and §14.2 are structured identically on purpose: definition, dormancy statement, rationale,
required-amendment-contents list, and an explicit "shall never activate" clause. The same
"no invented thresholds" discipline applies to both without exception. A future amendment
activating either trigger must supply everything its subsection lists before the trigger may
fire — no partial activation.

This does **not** disable the remaining approved activation paths.

The following remain fully active:

* manual operator activation;
* unresolved ambiguous writes; and
* reconciliation contradictions.

---

# 15. Resolution of Open Questions

This document is approved as:

* a standalone transport and deployment specification;
* not a Pi Script grammar ruling; and
* not a seventh M7 behavioral constraint.

The Phase One deployment slice is approved as specified, **as two action types (governed public
posts and governed public replies)** — see §12 for the CitationClusterIntegrity grounding
rationale.

The Slice Two CredentialIntegrity coverage limitation is accepted and documented.

Kill-switch behavior is approved with:

* manual activation;
* a closed-set automated activation list containing **exactly two active triggers at lock time**
  (unresolved ambiguous writes, reconciliation contradictions);
* both repeated-integrity-failures and authentication-anomaly triggers **defined but dormant**
  pending their own formal amendments (§14); and
* operator-only re-enablement.

Structural Dry Run isolation is mandatory.

Production ingestion shall reject Dry Run identifiers at the ingestion boundary.

This requirement is a lock condition.

---

# 16. Lock Condition

This specification is now authoritative.

No transport implementation, deployment code, authentication layer, API integration, or Moltbook
execution logic may be written before this specification is locked — it now is locked. Transport
implementation work is the separate, spec-approved next step (not part of this lock) and has not
been started.

Any modification affecting:

* execution authority;
* transport responsibilities;
* retry behavior;
* reconciliation ownership;
* approval validation;
* kill-switch triggers;
* Dry Run isolation; or
* execution boundaries

requires a formal amendment following the same governance discipline established throughout M7.

---

# Implementation Note A: Claim-Status Eligibility Gate (2026-07-20, non-binding)

**This is an implementation note, not an amendment. The spec above remains LOCKED as of
2026-07-20 and this note does not reopen, modify, or supersede any numbered section.** It exists
to record a clarification discovered after lock — Moltbook's `heartbeat.md` convention, unknown at
lock time — and to state how it is implemented within the existing locked boundaries, per §16
(only changes to the eight listed categories require a formal amendment; this note touches none
of them).

**What it is:** Claim-status polling (`GET /agents/status`, Bearer auth) is an implementation of
the health-check responsibility already defined in §5 and §12. It is a safe read per §8 — no new
retry category, no new transport responsibility.

**Why it's a third category, not §7's two:** Platform claim state (`claimed` / `pending_claim`)
represents **platform eligibility** — a known, platform-asserted fact — not governance state and
not transport uncertainty. It is neither:

* a **governance violation** (no Pi Script constraint evaluates it, no entity field, no resolver
  involvement), nor
* an **operational freeze** per §7 (it is not ambiguous, not unresolved, not a reconciliation or
  authentication anomaly — the platform is telling the transport a definite fact, not leaving it
  guessing).

**Behavior:**

* Eligibility `claimed` → writes proceed normally.
* Eligibility `pending_claim` → outbound writes are rejected, the eligibility state is logged, and
  an operator notification is emitted. Reads continue.
* This is **not** a kill-switch activation, **not** an Arbiter event, and **not** a reconciliation
  freeze. It is the platform declining execution because the account is not currently eligible —
  a simple, ungoverned state gate, distinct in kind from every mechanism in §7–§10.

**Why no kill-switch trigger, threshold, or amendment path:** unlike the §14 dormant triggers
(repeated integrity failures, authentication anomalies), eligibility state requires no threshold,
no counting window, and no "no invented numbers" discipline — because there is nothing to invent.
It is a direct pass-through of a platform-declared boolean-shaped fact, permanently. It does not
graduate into a kill-switch trigger the way §14's triggers might via future amendment; it isn't
that kind of thing.

**Out of scope (explicitly not part of this note or this spec):** the other half of
`heartbeat.md` — periodic skill-file version checks (fetching `skill.json`, re-pulling skill
docs) — is agent-content freshness, not execution. It does not belong in the transport spec and
is not addressed here.

**Status:** transport implementation is clear to begin against the locked spec plus this note.

---

# Implementation Note B: Captcha Verification (2026-07-20, non-binding)

**Partially superseded 2026-07-21: the issuance seam this note left to deployment wiring
(`fetch_captcha_challenge`) is retired by Implementation Note E below — the live platform issues
the challenge inside the write response, not via any standalone fetch. Note B's core framing
(captcha as a transport-mechanical publishing precondition, never a governed action or its own
envelope) stands unchanged; the original text below is preserved for the audit trail.**

**This is an implementation note, not an amendment. The spec above remains LOCKED as of
2026-07-20 and this note does not reopen, modify, or supersede any numbered section.** It exists
to record a clarification discovered mid-implementation — Moltbook requires solving an obfuscated
math-word-problem challenge before any post/comment publishes, and ten consecutive failures
suspends the account (`docs/moltbook_api_spec.md` §6, sourced from `moltbook.com/skill.md`,
unknown at lock time) — and to state how it is implemented within the existing locked boundaries.

**Treatment (operator decision):** captcha verification is a **transport-mechanical publishing
precondition**, not a new governed action type and not a new Approved Action Envelope. It may run
only against a write that already has a valid, freshness-checked envelope (§4) — never on its own
authority, never before an envelope exists.

**Solver constraints (binding on this note):** the solver is deterministic and narrowly scoped to
the platform's documented challenge shape. It must never use unrestricted model generation, and it
must never alter the approved post/reply payload — solving the challenge is orthogonal to what
gets posted, exactly as §5/§6 already require of the transport generally.

**Binding requirement:** every verification attempt is bound to the originating `action_id`,
`approval_trace_id`, and `challenge_id` (`CaptchaAttemptRecord`, `moltbook/transport.py`). The
audited facts per attempt are: the challenge identifier, the deterministic solve outcome, the raw
platform response, and the running consecutive-confirmed-failure count. An ambiguous response
(timeout, unclear platform reply) is never counted as a confirmed wrong answer, is never blindly
retried, and the same answer is never resubmitted across challenges — each attempt uses a fresh
challenge and a freshly-computed answer.

**New active kill-switch trigger: `captcha_suspension_risk`.** Added to §10's active automated
set. As of this note, the active automated triggers are:

1. unresolved ambiguous writes (§10, original lock);
2. reconciliation contradictions (§10, original lock);
3. **`captcha_suspension_risk`** (this note) — engages on the 3rd CONSECUTIVE
   PLATFORM-CONFIRMED captcha failure.

The two §14 dormant triggers (repeated integrity failures, authentication anomalies) are
unaffected by this note and remain inactive pending their own amendments. **This trigger is
deliberately NOT routed through §14.1's dormant "repeated integrity failures" trigger** — that one
stays undefined on purpose; this one is scoped, active immediately, and uses a number Continuum
chose as a safety margin, not one supplied by Moltbook.

**The two numbers, and why they differ:** Moltbook's documented suspension boundary is **10**
consecutive failed verification attempts (`docs/moltbook_api_spec.md` §6) — this is
**platform-grounded**. Continuum's local threshold is **3** consecutive **platform-confirmed**
failures — this is a **deliberately conservative Continuum safety margin**, chosen to engage the
kill switch well before the platform's own suspension limit could ever be reached, not a number
Moltbook supplied or endorsed.

**Counter semantics (binding):**

* Counts only failures **explicitly confirmed by Moltbook** as failed verification attempts
  (`CaptchaOutcome.CONFIRMED_FAILURE`) — never a timeout, never an ambiguous response.
* Scoped to the deployed agent/account (one `CaptchaVerifier` instance per session/account).
* Resets to zero only after an **explicitly confirmed successful** verification
  (`CaptchaOutcome.CONFIRMED_SUCCESS`) — an ambiguous outcome neither increments nor resets it.
* Activates the kill switch **immediately** on the 3rd consecutive confirmed failure — no grace
  window, no additional confirmation step.

**Kill-switch semantics (standard, unchanged from §10):** fail-closed for all outbound writes;
safe reads may continue; only an explicit operator `clear()` re-enables writes, with no automatic
recovery path. This is an **operational condition, not a governance violation** — it produces a
`KillSwitchActivation`, never a Pi Script entity-state change, and must never enter the Arbiter's
violation-trace path (§7).

**Audit event contents (binding, extends §10's structured-audit requirement):** every
`captcha_suspension_risk` activation records — via `KillSwitchActivation.extra`, not folded into
the free-text `detail` alone — the triggering `action_id`, the `challenge_id` of the confirming
attempt, the confirmed failure count, the local threshold (3), the documented platform suspension
limit (10), the last platform response, the affected action class, and the activation timestamp.

**Implementation:** `moltbook/transport.py` — `CaptchaChallenge`, `CaptchaOutcome`,
`CaptchaAttemptRecord`, `solve_captcha_deterministic`, `CaptchaVerifier`,
`KillSwitch.activate_captcha_suspension_risk`. Optionally wired into
`MoltbookHTTPTransport.send()` via `captcha_verifier` / `fetch_captcha_challenge` /
`submit_captcha_fn` — unwired, behavior is unchanged from before this note. `CaptchaVerificationFailed`
and `CaptchaVerificationAmbiguous` block the current write attempt specifically; they are distinct
from `KillSwitchEngaged`, which blocks all future writes once the switch has actually engaged.

**Known limitation, stated rather than hidden:** the exact wording of Moltbook's live challenge
text has not been observed — `solve_captcha_deterministic` is a best-effort deterministic parser
against the documented shape ("numeric string, 2 decimals, e.g. `15.00`") and may need its
operator-word list extended once real challenge text is seen. It never silently guesses on
unrecognized wording; it raises instead, which by construction cannot be miscounted as a
CONFIRMED_FAILURE (a solver error never reaches `submit_fn`, so it never touches the
consecutive-failure counter).

**Status:** resolved. Transport implementation may proceed against the locked spec plus Notes A
and B. `tests/test_moltbook_transport.py` covers both this note and the separately-resolved
reply-parent-identifier gap (`MoltbookClient.send()` now requires and forwards `parent_post_id`,
covered by the existing §4 payload-hash mechanism — no new invariant, no note required for that
part). Full suite green (466 passed + 6 xfailed) at time of writing. Nothing has been committed —
this remains at the same commit gate as the rest of M7.

---

# Implementation Note C: Rate-Limit Retry Category (2026-07-20, non-binding note; §8 itself amended)

**Status of this note is different from A and B: this one DOES extend a numbered section.**
`RetryCategory` is one of §16's eight lock-affecting categories ("retry behavior"), and this note
adds a fifth member, `RATE_LIMITED`, to the four §8 originally locked. §8 above now carries a
"Rate Limited" subsection added by this note, explicitly marked as such — the original four
categories are left untouched and un-reordered, so the historical lock record stays intact; this
note is the authoritative explanation of the addition, and §8's own text is now consistent with it.

**Binding content of this note:**

* HTTP 429 maps to `RATE_LIMITED`.
* `RATE_LIMITED` is distinct from `GOVERNANCE_DENIAL` (terminal, no further path),
  `AMBIGUOUS_WRITE` (meaning genuinely uncertain, resolved via §9 reconciliation), and any other
  terminal `FAILURE` outcome.
* A `RATE_LIMITED` result means the platform **deterministically refused this specific attempt**
  because of rate limiting — there is no ambiguity about what happened. The underlying governed
  action, however, **may remain eligible for a later, newly authorized attempt**; a 429 says
  nothing about whether the action itself is still wanted or approved.
* The transport must **never** initiate that later retry itself — §2's invariant ("the transport
  never independently... retries governed behavior") applies to `RATE_LIMITED` exactly as it does
  to every other outcome. `RATE_LIMITED` is a fact reported outward, not a license to act.
* Retry timing must never be guessed or hard-coded. No sleep-and-retry loop, no fixed backoff
  constant, no "usually N seconds is safe" heuristic — anywhere.
* **Automated retry stays disabled** until both: (a) the request seam exposes the real
  `Retry-After` and relevant `X-RateLimit-*` header values (it does not yet — `request_fn`
  currently returns `(status_code, json_body)` only, no headers at all, a real pre-live-deployment
  gap, not papered over), and (b) the resulting scheduling behavior is itself explicitly specified
  in a future note or amendment. Until then, `RATE_LIMITED` is report-only.
* **A future retry attempt must revalidate approval freshness, governance configuration version,
  and payload hash (§4)** exactly as any other send would — it must never reuse an expired approval
  just because the underlying content is unchanged. Time has passed since the original approval by
  definition (that's what triggered the 429 in the first place), so §4's freshness checks are not
  optional the second time around.

**Test coverage:** `tests/test_moltbook_transport.py` proves 429 maps only to `RATE_LIMITED` (never
`GOVERNANCE_DENIAL`, never `AMBIGUOUS_WRITE`); that the transport performs no autonomous retry after
a 429 (single call count assertion); that a hypothetical unsupported `RetryCategory` value fails
loudly wherever categories are treated exhaustively, rather than silently defaulting; and that a
simulated "later retry" using a stale envelope is rejected by ordinary §4 freshness validation, not
by any bespoke rate-limit-specific logic.

**Status:** resolved and locked as of this note. Repo-wide, every place that pattern-matches over
`RetryCategory` has been searched and given an explicit `RATE_LIMITED` branch (or a loud failure for
any unhandled category) — see the "Post-lock corrections and known gaps" section below for the
inventory of what was checked.

---

# Post-lock corrections and known gaps (2026-07-20, cross-checked against docs/moltbook_api_spec.md)

Non-binding, same status as Notes A/B — implementation-level corrections and flags found by
cross-checking the built transport against the actual documented API surface, not new invariants
(Implementation Note C above is the one exception that does extend a numbered section, §8).

**Corrected (implemented):**
* `parent_post_id` is no longer transmitted in the reply request body — docs/moltbook_api_spec.md
  §4 puts the post ID only in the URL path (`/posts/{POST_ID}/comments`), not the body. It remains
  part of `envelope.payload` (so it's still covered by the §4 payload-hash check) but is stripped
  before transmission. The platform's own **documented optional `parent_id`** field (nested
  comment-threading, distinct from the routing-only `parent_post_id`) now passes through
  unmodified if present in the payload — deliberately NOT wired at the `MoltbookClient.send()`
  level yet; Phase One supports flat, top-level comments only, and nested threading is deferred,
  not silently dropped.
* `send()`'s status classification (§8) now branches 409/410/429 distinctly instead of falling
  through to a generic case: **409** (documented conflict) is treated as a candidate for §9's
  reconciliation duplicate-detection path (`OUTCOME_UNKNOWN`/`AMBIGUOUS_WRITE` — never assumed
  success or failure, never retried by the transport itself); **410** (documented gone/expired) is
  unambiguous and terminal (`FAILURE`/`GOVERNANCE_DENIAL`); **429** (documented rate limit) gets
  `RetryCategory.RATE_LIMITED` per Implementation Note C above.
* Every repo-wide consumer of `RetryCategory` that treats the categories exhaustively (audit
  rendering, reconciliation helpers, tests) now has an explicit `RATE_LIMITED` branch or fails
  loudly on an unrecognized category — see Note C for the binding requirement and the test list
  proving it.

**Known gap, flagged and NOT resolved here:** `X-RateLimit-Limit` / `X-RateLimit-Remaining` /
`X-RateLimit-Reset` / `Retry-After` header values are documented (docs/moltbook_api_spec.md §5)
but not yet captured anywhere in this transport. The `request_fn` seam
(`MoltbookHTTPTransport`) currently returns `(status_code, json_body)` only — no response headers
at all — so the 429 branch above can classify the *fact* of a rate limit but cannot yet report
*how long* to wait. This is a real pre-live-deployment gap, not an oversight papered over: honoring
it properly means widening the `request_fn` contract to also return headers, which touches every
existing fake in the test suite and is deliberately left for its own pass rather than folded in
under this correction. **(That pass happened: resolved by Implementation Note D, 2026-07-21,
below.)**

---

# Implementation Note D: request_fn Header Capture (2026-07-21, non-binding)

The transport-contract note for closing the header-capture gap flagged above and in Note C.
Same status as Notes A/B: transport-mechanical, no numbered section amended, no new invariants —
§2's "the transport never independently retries" is untouched and restated below.

**Binding content of this note:**

* `request_fn`'s return contract changes shape from the bare `(status_code, json_body)` two-tuple
  to an explicit frozen dataclass: `HTTPResponse(status_code: int, body: dict,
  headers: Mapping[str, str])`. The shape change is deliberate and visible — headers are not
  smuggled into the body or bolted on as a side-channel.
* **No compatibility adapter.** The consumer sweep (2026-07-21) found the tuple shape lives in
  exactly one test file (`tests/test_moltbook_transport.py`: one `_fake_request` factory plus a
  dozen inline closures) and three internal call sites in `moltbook/transport.py`. Churn that
  confined does not earn a second live shape — and a tuple-accepting adapter would let a
  header-discarding wiring pass silently, which is the exact silent failure this note closes.
* **Generic capture, both paths.** ALL response headers are captured, with names normalized to
  lowercase at construction (case-insensitive lookup by normalization), on BOTH response paths —
  the normal `urlopen` success path and the `urllib.error.HTTPError` path. A 429 arrives via
  `HTTPError`, so single-path capture would silently fail on the one case this exists for.
* **Normalized fields compose with (never bypass) the generic capture.** The four headers
  documented in `docs/moltbook_api_spec.md` §5 — `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
  `X-RateLimit-Reset` (all responses), `Retry-After` (429 only) — are exposed as a typed
  `RateLimitInfo` derived from the captured headers: `limit`/`remaining`/`reset` as best-effort
  integer parses (§5 does not document `Reset`'s value format — epoch vs. delta is unknown, so
  the raw string stays available in `headers`), and `Retry-After` parsed supporting both RFC 9110
  forms: `retry_after_delay_seconds` (non-negative integer) or `retry_after_http_date` (HTTP-date).
  Malformed values parse to `None`, never raise — the transport reports facts.
* **Surfacing:** `TransportResult` gains optional `platform_headers` (the generic capture) and
  `rate_limit` (the normalized fields), populated whenever a result is built from a real platform
  response; `None` where no response exists (e.g. transport-level failure before any response).
* **Explicit non-scope:** this is metadata capture only. No sleeping, no scheduling, no automatic
  retry, no "if remaining < N, wait" policy anywhere. Note C's two conditions for ever enabling
  automated retry: condition (a) — the seam exposes the real header values — is satisfied by this
  note; condition (b) — scheduling behavior explicitly specified — remains unmet, so automated
  retry remains disabled. `RATE_LIMITED` is still report-only, now with the wait-time facts
  attached.

---

# Implementation Note E: Captcha Issuance Protocol (2026-07-21, non-binding; SIGNED OFF)

**Status: signed off 2026-07-21** (drafted and reviewed same day). Same non-binding status as
Notes A/B/D — transport-mechanical, no numbered section amended. It supersedes Note B's issuance
seam (`fetch_captcha_challenge`) but leaves Note B's core framing — captcha as a
transport-mechanical precondition, never a governed action or its own envelope — intact. This
note is spec only; the implementation pass follows separately and must match it.

**Discovery provenance (2026-07-21):** the live `moltbook.com/skill.md` now documents the full
issuance protocol that the repo's `docs/moltbook_api_spec.md` §7 "Open Items" flagged as
unresolved. Discovery required zero live API calls — a verbatim capture of the updated skill.md
was taken 2026-07-21 and is the sole source for everything below. Nothing here was inferred from
probing, and nothing has yet been confirmed against a live write.

## The observed protocol (why Note B's seam cannot represent it)

There is **no standalone issuance endpoint**. The write itself issues the challenge:

1. `POST /api/v1/posts` (or `/posts/{id}/comments`, `/submolts`) succeeds immediately — the
   content is created in a hidden `pending` state (`verification_status: "pending"`).
2. The challenge arrives **inside the write response**: `post.verification` carrying
   `verification_code`, obfuscated `challenge_text`, `expires_at`, `instructions`.
3. The answer goes to `POST /api/v1/verify` as `{verification_code, answer}`. Success publishes
   the content. Documented failures: incorrect answer (with hint), `410` expired code, `404`
   invalid code, `409` code already used.
4. **Trusted agents/admins may receive no `verification` block at all** — the content publishes
   immediately off the write.

Note B's flow (fetch challenge → solve → submit → *then* transmit the write) is inverted relative
to reality: verification gates **publication, not transmission**. The `fetch_captcha_challenge()`
pre-write callback has nothing real to represent and is retired, not adapted.

## Proposed binding content

**1. Flow reorder and seam change.** `send()` becomes: transmit the write → parse the
`verification` block from the write response (if present) → solve → submit via `submit_fn` →
classify the final outcome. `fetch_captcha_challenge` is removed from the constructor and from
`send()` — retired entirely, no deprecation shim, for the same no-second-live-shape reasoning as
Note D. The submission seam survives with its key renamed: `submit_fn(verification_code, answer)`.

**`verification_code` fully replaces `challenge_id` as the lookup key — contract-wide, not a
call-site rename.** Enumerated consumers of `challenge_id` today, every one of which switches to
`verification_code`: the `submit_fn` call (`transport.py` CaptchaVerifier.verify), the
`CaptchaChallenge` dataclass field, the `CaptchaAttemptRecord` binding field (failure tracking),
the kill-switch `captcha_suspension_risk` activation's structured audit `extra`, and the
`CaptchaVerificationFailed`/`CaptchaVerificationAmbiguous` exception messages raised from
`send()`. If implementation turns up any consumer not on this list, that's a stop-and-report,
not a silent addition.

**2. Three independent status fields — no single "success".** The write response can no longer be
collapsed into one outcome. `TransportResult` (or a captcha-specific result carried by it) gains
three fields, each answering a different question, none derivable from the others:

* `transmission_status` — did the write reach the platform at all (the §8 taxonomy's existing
  concern, unchanged).
* `publication_status` — is the content actually public: `PENDING_VERIFICATION` /
  `PUBLISHED` / `NOT_PUBLISHED` (verification failed or expired; the platform documents no
  publication path for that content — a fresh write with a fresh challenge is the only recovery).
* `verification_status` — `REQUIRED` / `PASSED` / `FAILED` / `EXPIRED` / `NOT_REQUIRED`.

The trusted-agent immediate-publish path is **first-class**: `verification_status=NOT_REQUIRED`
with `publication_status=PUBLISHED` directly off the write response, not a degenerate case folded
into either of the other paths. The documented detector is the *absence* of the `verification`
block / `verification_required: true` — its absence is a positive, classifiable fact.

**3. Expiry is read, never assumed.** Challenge expiry comes exclusively from the response's
`expires_at` field. The documented windows (5 minutes for posts/comments, 30 seconds for
submolts) differ by content type and are context only — no constant anywhere encodes either
number. `CaptchaChallenge.expires_at` already exists and simply starts being populated from the
platform's value instead of a caller-invented one.

**4. Threshold relationship stated precisely.** Continuum's `captcha_suspension_risk` trigger
fires on the **3rd consecutive platform-confirmed failure**. The platform suspends when the
**last 10 attempts are all failures (expired or incorrect)**. These are different rules over
different windows: ours is consecutive-confirmed-only (ambiguous outcomes never count, success
resets), theirs is a trailing-10 window that counts expiry as failure. Ours is deliberately the
stricter margin by design — it is NOT equivalent to, a mapping of, or an approximation of the
platform rule, and no text or trace may describe it as such. The platform rule is recorded here
as context for why a conservative margin exists at all.

**5. No timing synthesis — existing rules unchanged.** Verification requests are subject to the
same no-guessed-timing / no-autonomous-retry rules as every other transport action (§2, Note C).
The documented "30 verification attempts per minute" limit is context only — it is not
permission to synthesize pacing, spacing, sleeping, or scheduling logic, and no implementation
of this note may contain any. Only observed response metadata surfaced under the existing
rate-limit contract (Note D's `RateLimitInfo`, populated from real response headers) could ever
inform timing behavior, and then only once Note C's condition (b) — an explicit scheduling
spec — exists. It still does not.

**6. Consumer analysis: the new status fields are transport-visible only.** Checked 2026-07-21
against the working tree, looking for any existing consumer that equates transmission success
with publication:

* `MoltbookClient.send()` returns the transport's result dict verbatim to its caller; it takes
  no action keyed on outcome. The cadence/citation stores are consulted pre-send for `paused`
  only — **ingestion is observation-driven (feed reads), never keyed off a TransportOutcome** —
  so no store records a "post happened" fact from a transport success today.
* The Pi Script resolver and every M7 constraint consume latch/state fields
  (`credential_exposed`, `link_violation`, `identity_drift`, cadence/citation store state) —
  none derive from `TransportOutcome`.
* `reconcile()`/`resolve_ambiguous_write()` gate on `OUTCOME_UNKNOWN` only.
* The two surfaces that expose "success" outward — `as_client_transport`'s returned dict
  (`"outcome": "success"`) and `DryRunTransport.simulated_outcome` — have no downstream
  consumer that interprets them further today.

Conclusion: **no existing resolver, constraint, audit, cadence, or reconciliation logic equates
transmission with publication**, so the three status fields land as transport-visible facts with
no governance semantics attached by this note. Two mechanical follow-ons are in-scope for the
implementation (not layer questions): `as_client_transport`'s dict must carry the new fields
(additively), and `DryRunTransport` must decide what a simulated verification/publication status
is. If a future constraint wants to *consume* publication status (e.g. cadence observations
distinguishing published from pending-never-published posts), that is a governance question for
its own ruling — explicitly not resolved here.

**7. Fail-closed configuration, reshaped for the no-fetch seam.** With `fetch_captcha_challenge`
retired, the captcha configuration surface is exactly two pieces: `captcha_verifier` and
`submit_captcha_fn`. The constructor invariant: **both configured, or neither.** Any partial
configuration raises `ValueError` at construction — never a latent crash after a live challenge
has already been issued (the failure mode the old three-optional constructor permitted, observed
live in `send()`'s guard which never checked `submit_captcha_fn`). Unconfigured remains legal
and means: a write that comes back `PENDING_VERIFICATION` is left pending — reported outward as
exactly that, never silently dropped, never guessed at.

**8. Reference-doc and fixture updates (part of this note's implementation).**
`docs/moltbook_api_spec.md` §7's "Open Items" entry for issuance is resolved from the 2026-07-21
capture (with a dated pointer, same audit-trail style as §8/Note C — the original open-item text
stays visible). The captured write-response and verify-response shapes land as a checked-in
fixture for tests, **redacted before commit**: `verification_code` values, the obfuscated
`challenge_text` (its structure is described, its literal text replaced — it is
platform-generated content of unknown entropy), and any account-identifying fields (IDs, names,
karma) are replaced with synthetic placeholders. Response *structure* — field names, nesting,
status values — is preserved byte-faithful.

## Required test coverage (implementation pass)

* Full captcha configuration accepted; empty configuration accepted; each partial configuration
  rejected at construction (fail-closed).
* Write response with `verification` block → challenge parsed from the real fixture shape (not
  an assumed one); solve + submit flow runs; `PASSED` → `PUBLISHED` with exactly the one write
  and one verify call.
* Confirmed verification failure → `NOT_PUBLISHED`, failure count increments, third consecutive
  fires `captcha_suspension_risk` (existing threshold tests adapt to the new flow).
* Ambiguous submit outcome → write stays `PENDING_VERIFICATION`, failure count does NOT
  increment, no retry.
* Trusted-agent path: no `verification` block → `NOT_REQUIRED` + `PUBLISHED`, zero verify calls.
* `verification_code` binding preserved across the attempt record / audit extra / exception
  surfaces; a code is never reused across actions (platform 409 documented) and never reused
  after a terminal outcome.
* Expiry honored from `expires_at` only — a fixture with a non-default window must flow through
  with no constant interfering.
* No pacing/scheduling logic exists: exactly one verify call per solved challenge, regardless of
  documented per-minute limits.

## Stop conditions carried into implementation

* If the live write-response shape contradicts the skill.md capture (fields missing, different
  nesting), stop and re-fixture — do not bridge the gap with guesses.
* If `submit_fn(verification_code, answer)` proves unable to represent the live protocol (e.g.
  submission turns out to need the content ID as well), stop and amend this note — do not
  silently widen the seam.
* First live observation requires a real write; that write is itself a governed action needing
  its own approved envelope and operator go-ahead — this note does not authorize it.
