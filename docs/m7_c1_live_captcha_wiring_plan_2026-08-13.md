# M7 — C1: Live CAPTCHA Wiring Plan

**Status: DRAFT — awaiting operator signature.** Drafted 2026-08-13 for review. C1's row in
`docs/m7_operator_go_checklist.md` §C is not satisfied until that row carries an operator
signature; this document is the artifact that row's `Evidence` will cite, not a substitute for it.

This is the artifact required by `docs/m7_operator_go_checklist.md` §C item **C1** ("Live CAPTCHA
wiring plan completed — not required for §A's preliminary review, but required before wiring
begins"), and authorized as preparation work by `docs/m7_go1_decision_2026-08-10.md` §5.2, which
makes §C's ordering binding: **C1 must be satisfied before C2 begins.**

This document **amends no numbered section** of `docs/m7_operator_go_checklist.md`, of
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md` (including its Implementation Notes),
of `docs/moltbook_api_spec.md`, or of any ruling in `docs/`. It settles one contract and states
what implementing it requires.

**Nothing here authorizes transmission.** GO-1 §5.1 and §5.3 continue to govern: no governed post
or reply may be sent, and `POST /api/v1/verify` is exercised for the first time only when a real
governed post legitimately produces a challenge during §E.

**Cross-reference convention.** A bare `§N` in this document refers to this document, and is
written as "§N below" or "§N above" wherever the number also exists in a document cited here.
References to another document's sections are always named — "transport spec §9", "GO-1 §5.2",
"§C3" of the checklist. This is stated because `§9` in particular exists in both this document
(stop conditions) and the transport spec (reconciliation), and an unlabelled `§9` resolves to a
real but wrong destination rather than to nothing.

---

## 1. What C1 decides, and what it does not

By operator ruling on 2026-08-13, C1 is **broad**: it settles the semantic contract that C2
implements, rather than describing the method by which C2 would discover it.

The reason is the one that makes this a preparation gate at all. If C1 only described method, the
first live CAPTCHA submission would be the place where an unconfirmed platform response gets
interpreted for the first time — a consequential governance decision made inside an implementation
commit, under a five-minute expiry, against live content already created in a hidden `pending`
state. The preparation gate exists to prevent exactly that.

The division of labour:

| Stage | Question it answers |
|---|---|
| **C1** (this document) | What does a given platform response *mean*? |
| **C2** | How does the existing architecture faithfully carry that already-defined meaning? |
| **§E** | Does the live platform actually exhibit the documented behaviour? |

**§E is not the semantic discovery phase.** It is empirical validation of a model fixed here. That
is the property this document exists to protect, and §7's recording requirement is what makes the
validation answerable rather than nominal.

C1 does **not** decide:

- The disposition of an `AMBIGUOUS` outcome after `CaptchaVerifier.verify()` returns. See §6 — that
  question is named, scoped, and deliberately left unresolved here.
- Any change to `CaptchaVerifier`'s existing responsibilities (solve-once policy, the consecutive-
  confirmed-failure counter, the `captcha_suspension_risk` threshold). C1 settles the transport
  contract and invents no new responsibility for the verifier beyond what §7 requires to record it.
- The wording or content of the first governed post, which is bound at GO-2 via `payload_hash`.
- Anything about `docs/m7_first_live_post_governed_envelope.md`'s `Status: DRAFT` question (GO-1 §6
  finding (a), open) or the `approval_trace_id` binding gap (issue #64 / PG-2, ruled post-GO). Both
  are out of scope by ruling; folding either in would blur the GO-1 preparation boundary.

---

## 2. Evidence boundary — documented is not live-confirmed

**Every classification in §3 derives from a single evidence source:** the verbatim capture of
`moltbook.com/skill.md` taken **2026-07-21**, preserved at
`Downloads/Moltbook_skill_md_live_capture_2026-07-21.md`, with its redacted structural fixture
committed at `tests/fixtures/moltbook_captcha_issuance.json`, and its consequences recorded in
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md` Implementation Note E and
`docs/moltbook_api_spec.md` §6.

The transport spec states the limit of that evidence directly, and this document inherits it
without widening it:

> Discovery required zero live API calls — a verbatim capture of the updated skill.md was taken
> 2026-07-21 and is the sole source for everything below. Nothing here was inferred from probing,
> and **nothing has yet been confirmed against a live write.**

**C1 therefore claims authority over the interpretation, not over the platform.** It is authoritative
as to what Continuum shall do when a given response arrives. It does not assert that the documented
contract is complete, that the platform will honour it, or that it cannot change. Those are §E's
questions, and §3's per-row provenance column exists so that §E can ask them row by row.

This document is **version-bound to the 2026-07-21 capture.** A material change to the platform's
documented verification protocol — a new skill.md revision, a response shape not enumerated in §3,
or any live observation contradicting a row — requires a fresh C1 review and a fresh signature. It
does not inherit forward.

---

## 3. The response-condition contract

### 3.1 The classification principle

The table in §3.3 is generated by one rule, stated first so that the rows are checkable against it
and so that §4's residual case has a principled answer rather than a default:

> **A response classifies as `CONFIRMED_*` only when it establishes what happened to *this*
> challenge.**
>
> - **`CONFIRMED_SUCCESS`** — the platform evaluated the submitted answer and accepted it; the
>   content is published.
> - **`CONFIRMED_FAILURE`** — the platform's response establishes that this challenge cannot result
>   in publication, either by rejecting the answer or by declaring the code definitively unusable
>   for a reason not caused by Continuum's own submission.
> - **`AMBIGUOUS`** — the response establishes neither: the answer was never evaluated, or the
>   response is consistent with more than one history, or the response is not enumerated here.

`AMBIGUOUS` is not a residual bucket for inconvenience. It is the positive statement that the
response is **not evidence either way**, which is the same meaning `CaptchaVerifier` already assigns
it (`moltbook/transport.py:885–895`, docstring: "an ambiguous result is simply not evidence either
way").

### 3.2 Detection precedence

The capture pins response *envelopes* for the success and incorrect-answer cases but does not pin
the HTTP status accompanying the incorrect-answer envelope; it pins HTTP *statuses* for the 410 /
404 / 409 cases without giving their bodies. Classification must therefore read both axes, in a
fixed order:

1. **An enumerated non-2xx HTTP status (§3.3 rows 3–7) is authoritative** and classifies the
   response regardless of body content.
2. **On HTTP 2xx, the response envelope's `success` field is authoritative** — `true` → row 1,
   `false` → row 2.
3. **A 2xx response whose body is absent, non-JSON, or missing a boolean `success` field is not
   classifiable** and falls to §4 below.
4. **A non-2xx status not enumerated in §3.3 matches none of the rules above** and falls to §4
   below. Rules 1–3 are not a complete decision procedure on their own — rule 1 covers only
   *enumerated* non-2xx statuses and rules 2–3 are both conditioned on 2xx — so a response such as
   `403` or `503` would otherwise terminate this procedure without a verdict. This clause closes
   it. The resolution is the residual one and carries the residual marking of §4 below; it is not
   a fourth classification.

C2 must not key classification on HTTP status alone, and must not key it on the `error` or `hint`
strings, which are human-facing text of unpinned stability. Row 2 is detected by
`success === false` on a 2xx response, not by matching `"Incorrect answer"`.

### 3.3 The mapping

| ID | Condition | Detection | Outcome | Evidence provenance |
|---|---|---|---|---|
| **C1-1** | Verification accepted; content published | HTTP 2xx, body `success: true` | `CONFIRMED_SUCCESS` | **Documented.** Fixture `verify_response_success`; structure byte-faithful to the 2026-07-21 capture. Not live-confirmed. |
| **C1-2** | Answer evaluated and rejected | HTTP 2xx, body `success: false` | `CONFIRMED_FAILURE` | **Documented, with a gap.** Fixture `verify_response_failure` (`error: "Incorrect answer"`, `hint` present). The capture does not pin the accompanying HTTP status; §3.2 rule 2 makes the envelope authoritative on any 2xx. Not live-confirmed. |
| **C1-3** | Expired code | HTTP 410 | `CONFIRMED_FAILURE` | **Documented.** `docs/moltbook_api_spec.md` §6 corrected note (2026-07-21); transport spec Note E. Consistent with the send-layer treatment of 410 as "unambiguous and terminal" (spec line 947). Not live-confirmed. |
| **C1-4** | Invalid code | HTTP 404 | `CONFIRMED_FAILURE` | **Documented, and model-contradicting.** A code Continuum received from the platform's own write response should not be unknown to it. The outcome is nonetheless confirmed — publication cannot follow from this challenge — but the condition contradicts the captured model and is a stop condition under §9 below. Not live-confirmed. |
| **C1-5** | Code already used | HTTP 409 | **`AMBIGUOUS`** | **Documented code, unconfirmed causal meaning.** See §3.4 — this row carries the most reasoning and the least certainty. Not live-confirmed. |
| **C1-6** | Rate limited | HTTP 429 | `AMBIGUOUS` | **Documented.** 30 verification attempts/minute (`docs/moltbook_api_spec.md` §6). The answer was rejected before evaluation, so the response is not evidence about the answer. Not live-confirmed. |
| **C1-7** | Unauthenticated / unauthorised | HTTP 401 | `AMBIGUOUS` | **Documented status code** (`docs/moltbook_api_spec.md` §6 error envelope list); never observed against `/verify`. Not evaluated → not evidence. Also a stop condition under §9 below. |
| **C1-8** | Malformed request | HTTP 400 | `AMBIGUOUS` | **Documented status code**; semantics against `/verify` unknown. Not evaluated → not evidence. Also a stop condition under §9 below. |
| **C1-9** | Platform error | HTTP 500 | `AMBIGUOUS` | **Documented status code.** Whether the answer was evaluated before the error is unknowable from the response. |
| **C1-10** | No response | Timeout, connection failure, TLS failure, or a response that cannot be read | `AMBIGUOUS` | **Inferred, not documented.** No platform documentation covers this; it is a property of networks. The submission may or may not have been evaluated — the defining ambiguous case, and the one that makes C1-5 ambiguous too. |
| **C1-R** | Anything else | Any response not matching a row above | `AMBIGUOUS` | **Residual.** See §4. Not a classification of the platform's behaviour but of our own model's incompleteness. |

**Rows carrying an unconfirmed causal model, flagged for §E's attention:** C1-2 (HTTP status
unpinned), C1-4 (contradicts the captured model), C1-5 (causal meaning inferred, not documented),
C1-10 (not documented at all).

### 3.4 C1-5 (HTTP 409) — the reasoning, in full

409 is the row most likely to be got wrong, and the one where getting it wrong is worst. It is
recorded here as a first-class decision rather than a table entry.

**The tempting classification is `CONFIRMED_FAILURE`, and it is wrong.** "Code already used" does
not mean the verification failed. It most plausibly means a verification *succeeded* — and
therefore that the content is **published and live on Moltbook**. Classifying it as
`CONFIRMED_FAILURE` would stamp `publication_status = NOT_PUBLISHED` on live content. Both §E's
capture step and the §C5 Published-Outcome Correction and Withdrawal Procedure key off publication
status, so the correction procedure would not run on a post that is public. That is a worse error
than a spurious kill-switch trip, because it is silent.

**409 cannot be excluded by pointing at our own no-retry policy.** `CaptchaVerifier.verify()`
provably submits once and never resubmits (`moltbook/transport.py:909–948`), and §5 of this
document prohibits retry at every layer below it. But a submission whose *response* is lost —
C1-10 — is indistinguishable from a submission never made, and produces a genuine 409 on any later
attempt with zero deliberate retries anywhere. The no-retry policy narrows the set of causes; it
does not close it.

**Therefore 409 → `AMBIGUOUS` stands independently of the retry ruling.** The retry policy in §5
matters on its own terms, but it is not the premise this classification rests on. That
independence is deliberate: it means a future change to the retry policy does not silently
re-open this classification.

**Relationship to the send-layer 409.** `send()` already classifies a write-layer 409 as
`RetryCategory.AMBIGUOUS_WRITE`, routed to **transport spec §9** reconciliation, "never assumed
success or failure, never retried by the transport itself" (transport spec lines 944–947). This
document reaches the same classification at the verify layer by parallel reasoning about a
different fact — the write layer's 409 concerns whether the *content* exists; the verify layer's
concerns whether the *verification* already happened. The consequence is that the two layers agree
on classification and diverge on disposition, which is precisely the gap §6 below records.

---

## 4. The residual rule

**Any response not matching an enumerated row in §3.3 resolves to `AMBIGUOUS`.**

This closes the loophole that would otherwise defeat the C1/C2 separation entirely. If C1 named
unclassifiable conditions without prescribing their runtime treatment, C2 would have to invent
behaviour for the unenumerated case — which is exactly the semantic decision C1 exists to make.

The rule has three parts, and the second two are what keep it honest:

1. **Resolution.** The outcome is `AMBIGUOUS`. `CaptchaOutcome` gains no fourth member; the
   three-status contract is part of what this document settles.
2. **No silent coercion.** The implementation must not fall through, default, coerce, or otherwise
   treat an unenumerated response as success or failure. It must not infer a classification from
   partial resemblance to an enumerated row.
3. **Observability.** The resulting ambiguity must remain observable *as residual* — see §7. A
   residual outcome and an enumerated ambiguous outcome carry opposite epistemic weight and must
   not be flattened into each other.

**"Fail loud" here does not mean "raise".** Raising an exception on the residual path would make
`AMBIGUOUS` unreachable through the very route most likely to produce it, and would contradict the
three-status contract this document settles. Note E has already retired
`CaptchaVerificationFailed` / `CaptchaVerificationAmbiguous` for the closely related reason that a
verification outcome is a classified fact on the result, never an exception that discards the
transmission facts (`moltbook/transport.py:877–882`). The residual rule follows that ruling: the
loudness lives in the record, not in the control flow.

---

## 5. Retry policy

**No retry of a CAPTCHA submission is permitted at any layer.** Not in `submit_captcha_fn`, not in
whatever HTTP client backs it, not in a connection pool or adapter, and not in
`CaptchaVerifier.verify()` (which already never retries).

The scope is deliberately broader than "the HTTP client" because the meaning of a response depends
on it. Any mechanism that can cause a second submission of the same `verification_code` — including
adapter-level retry configuration that a library enables by default — changes what a subsequent 409
can mean and would silently alter the semantics fixed in §3.

Consequences, stated so they are not inferred:

- C2 must **positively establish** that no retry occurs below `submit_captcha_fn`, rather than
  relying on a library's default. Whatever client is used, its retry configuration must be set
  explicitly and evidenced. See §8.
- This is not a pacing, scheduling, or backoff policy, and C2 must not introduce one. Note E point
  5 and Implementation Note C both stand: the documented 30-attempts-per-minute limit is context
  only, and Note C's condition (b) — an explicit scheduling spec — remains unmet.
- A `429` (C1-6) is therefore recorded, classified `AMBIGUOUS`, and **not** re-attempted.

---

## 6. `AMBIGUOUS`: final as a classification, unresolved as a disposition

**By this document:** `AMBIGUOUS` is **final as a classification.** It is not further
reinterpretable. No downstream code may convert it to success, to failure, to a governance denial,
or to an instruction to invent a resolution.

**Its disposition after `verify()` returns is unresolved, and is recorded here as unresolved.**

What exists today. The outcome is not lost: `verify()` appends a `CaptchaAttemptRecord` before
branching, and `send()` carries the result outward as `publication_status =
PENDING_VERIFICATION` + `verification_status = REQUIRED` with an explanatory `detail`
(`moltbook/transport.py:1366–1378`). The outcome is **recorded**.

What does not exist. Nothing **consumes** that record. The outcome is not counted (by design — an
ambiguous result is not evidence), not reconciled, and not escalated. Note E point 6 supports this,
and the support is stated precisely because the point's own bolded conclusion asserts something
narrower: that "no existing resolver, constraint, audit, cadence, or reconciliation logic *equates
transmission with publication*." What bears here is point 6's analysis rather than that sentence.
Its survey found that the surfaces exposing outcome outward "have no downstream consumer that
interprets them further today," and it closes by treating any future constraint's consumption of
publication status as "a governance question for its own ruling — explicitly not resolved here,"
which presumes none consumes it now. That is the claim relied on, and it is not widened past what
point 6 checked. Its send-layer counterpart, by contrast, has somewhere to go — `AMBIGUOUS_WRITE`
routes to **transport spec §9** reconciliation.

**Why this document does not resolve it.** Giving `CaptchaVerifier` reconciliation or escalation
routing would be an architectural change to a component whose responsibilities C1 was ruled not to
extend (§1). It is a governance question for its own ruling, on the same principle Note E point 6
applied when it declined to decide whether a future constraint may consume publication status.

**Why it does not block GO-2.** §E is human-executed and requires capture of all three statuses,
so an ambiguous verification outcome on the first live post is seen by the operator, and §E's
ambiguity rule — silence is never treated as success or failure — already governs the response. The
gap binds unattended operation after the first post, not the first post itself.

**What C2 must do with it.** The unresolved disposition is a C2 acceptance criterion (§8 item 7),
not a licence to improvise: C2 may not silently discard, reinterpret, or convert an `AMBIGUOUS`
outcome, and must leave it observable for a later ruling to route.

**One consequence, stated because it follows from §3.3 and should not be discovered later:** since
`AMBIGUOUS` never increments the consecutive-confirmed-failure counter, a systematic condition
producing only ambiguous outcomes — repeated 409s, sustained 429s, a persistent network fault —
will never engage `captcha_suspension_risk`, and content will accumulate in `PENDING_VERIFICATION`
without any automatic signal. That is the correct behaviour under the counter's own semantics
(ambiguity is not evidence of failure), and it is exactly why the disposition question above needs
its own ruling before unattended operation.

---

## 7. Recording requirement — preserving the epistemic distinction

**`CaptchaAttemptRecord` must record which §3.3 condition matched, or that none did.**

Without this, a documented-ambiguous response (C1-6, C1-9, C1-10) and a response C1 never
enumerated (C1-R) are indistinguishable in the record: both appear as `AMBIGUOUS` with a
`platform_response` blob. Those two facts carry opposite weight. The first confirms the documented
model held. The second falsifies it.

This is what makes §E answerable. §E's question is *did the live platform conform to the model C1
established?* — and that question cannot be answered from a record in which conformance and
non-conformance look identical. A C1 that fixes classifications but leaves them unverifiable would
protect the first submission from improvisation while leaving the model itself unfalsifiable.

**The requirement:**

1. Every `CaptchaAttemptRecord` carries the matched condition identifier — one of `C1-1` … `C1-10`,
   or an explicit residual marker for `C1-R`.
2. The field is **required, not optional.** An attempt record that does not identify its condition
   must not be constructible. A nullable field whose absence is indistinguishable from "residual"
   does not satisfy this.
3. It records **classification provenance, not platform content.** `platform_response` remains a
   faithful record of what the platform said and must not be mixed with Continuum's interpretation
   of it.
4. This adds **no fourth `CaptchaOutcome` member.** The three-status contract is unchanged.

**On shape — C1 states the requirement, C2 chooses the mechanism.** The condition identifier is
determined where classification happens, inside `submit_captcha_fn`, whose current contract returns
`(CaptchaOutcome, dict | None)` and has no place to carry it. Implementation Note D faced the same
problem at the `request_fn` seam and replaced a bare `(status, body)` tuple with a typed
`HTTPResponse`; that precedent is available and is the obvious candidate. Choosing between it and
any equivalent is C2's, provided requirements 1–4 hold.

---

## 8. C2 acceptance criteria

C2 is complete when all of the following are evidenced. C2 implements this contract; it does not
extend, reinterpret, or supplement it.

1. **`submit_captcha_fn` implements §3.3 exactly** — every enumerated condition classified as
   specified, with the §3.2 precedence order applied in that order.
2. **The residual rule (§4) is implemented** — unenumerated responses resolve to `AMBIGUOUS`,
   marked residual, with no coercion or partial-resemblance inference.
3. **No new semantic classification appears in the implementation.** Any response condition C2
   encounters that is not in §3.3 is handled by the residual rule, never by a fresh judgement about
   what it probably means.
4. **No retry at any layer (§5),** with the client's retry configuration set explicitly rather than
   inherited, and that configuration evidenced.
5. **Classification inputs are observable at the seam** — HTTP status, response body, and response
   headers must all reach the classifier. A seam that surfaces only status and body cannot
   implement §3.2, and cannot carry `RateLimitInfo` for C1-6. Routing `submit_captcha_fn` through
   the existing `request_fn` seam is the natural way to satisfy this and to keep tests fake-driven;
   any alternative must deliver the same three inputs and the same testability.
6. **§7's recording requirement is satisfied,** including that an attempt record without a
   condition identifier is not constructible.
7. **`AMBIGUOUS` is neither discarded, reinterpreted, nor converted** (§6), and its unresolved
   disposition is carried as an explicit, visible item rather than quietly resolved.
8. **The Note E both-or-neither construction invariant still holds** (`moltbook/transport.py:1094`)
   — C2's checklist row requires this confirmed at construction (Note E item 7).
9. **Test coverage, all fake-driven, no live calls:** one test per §3.3 row including `C1-R`; a test
   proving no retry occurs on each of C1-5, C1-6, C1-9 and C1-10; a test proving residual and
   enumerated-ambiguous records are distinguishable; a test proving the condition identifier is
   mandatory. Per repo convention these are functions added to `tests/test_moltbook_transport.py`,
   and each new condition ships with both a deliberate-violation and a clean-pass case.
10. **The full suite is green** — 611 passing, 7 xfail — and the tree is clean at the reviewed
    commit.

---

## 9. C2 stop conditions

Each of these halts C2 and returns to the operator. None is resolved by C2's own judgement.

1. **A response condition arrives in testing or review that §3.3 does not enumerate** and that
   appears to be a documented platform behaviour rather than a network artifact. The residual rule
   covers it at runtime; it does not license amending §3.3 without a fresh C1 signature.
2. **The captured protocol is contradicted** — a `verification` block missing documented fields, a
   non-ISO-8601 `expires_at`, or a 404 (C1-4) against a code the platform itself issued.
   `parse_verification_block` already raises loudly on the first two
   (`moltbook/transport.py:641–682`, "re-fixture against the live response, do not guess"); C1-4
   joins them as a stop rather than a routine failure.
3. **`moltbook.com/skill.md` is found to have changed** from the 2026-07-21 capture. §2's version
   binding makes this a fresh-C1 event, not a C2 patch.
4. **Any impulse to call `/verify` to find out.** GO-1 §5.3 and §C3's binding wording are absolute:
   documented non-publishing operations only, no synthetic CAPTCHA submission as a probe. An
   unanswerable question about `/verify` behaviour is a stop condition, never a reason to probe.
5. **Any requirement here proving unimplementable without changing `CaptchaVerifier`'s
   responsibilities** beyond §7's recording requirement.

---

## 10. Identified for operator attention

Two items surfaced in drafting. Neither is resolved here; both are recorded so they are not
discovered later.

**(a) An asymmetry in expiry handling, now visible.** `send()` detects a locally-expired challenge
before submitting and explicitly does not move the failure counter, on the stated reasoning that
nothing was submitted so nothing is platform-confirmed (`moltbook/transport.py:1334–1350`). Under
§3.3, a **C1-3** (HTTP 410) *does* count, because it is a platform-confirmed response to a real
submission. The two are different facts — declining to submit versus submitting too late — and the
divergence is defensible, but it means expiry reaches the kill-switch counter by one route and not
the other. Recorded as a consequence of §3.3, not a change to existing behaviour.

**(b) `RateLimitInfo` at the verify seam.** Implementation Note D surfaced `Retry-After` and
`X-RateLimit-*` as typed `RateLimitInfo` on `TransportResult` for the write path. C1-6 makes the
same headers meaningful on the verify path, and §8 item 5 requires them to reach the classifier.
Whether they are surfaced onward is not settled here. Capture-only continues to apply either way:
no scheduling, sleeping, or auto-retry, per §5 and Note C.

---

## 11. Version binding and the limits of this document

This document is bound to the **2026-07-21 `moltbook.com/skill.md` capture** and to the repository
state at which it is signed. It does not inherit forward across a material change to either.

It settles what Continuum shall do when a given response arrives. It does not attest that the
platform's documented contract is correct or complete, that the platform will honour it, or that
the classifications in §3.3 have been empirically validated — §2 states plainly that none of them
have. It confers no authority over the future contents of any document it cites, and it is not an
operator signature; the signature that records operator verification lives in C1's row in
`docs/m7_operator_go_checklist.md` §C.

C2 may not begin until that row is signed.

Nothing has been transmitted. Recording this plan does not change that.

---

**Verified by:**
**Verified at:**
