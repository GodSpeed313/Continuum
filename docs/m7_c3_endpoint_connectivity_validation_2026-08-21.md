# M7 — C3: Endpoint Connectivity Validation

**Status: EXECUTED 2026-08-21 — SIGNED 2026-08-21 15:56 EDT.** Drafted and run 2026-08-21. The validation described
in §4 was executed once against the live platform on operator authorization; the results are at
§5 and all four steps passed. **C3's row in `docs/m7_operator_go_checklist.md` §C is signed** —
`Kevin Brown, 2026-08-21 15:56 EDT`. This document is the artifact that row's
`Evidence` cites — not a substitute for it, and not itself an attestation.

**Method was written before results existed.** §4 and the §4.7 prediction were drafted and shown
to the operator before any request was issued, so §5 records an observation against a stated
expectation rather than a description written around whatever came back.

This is the artifact required by `docs/m7_operator_go_checklist.md` §C item **C3** ("Endpoint
connectivity validated — see wording below; **no governed post/reply and no synthetic CAPTCHA
submission** issued solely as a connectivity probe"), and authorized as preparation work by
`docs/m7_go1_decision_2026-08-10.md` §5.2. It follows the C1 precedent — a standalone dated record
rather than a row-embedded decision — chosen by the operator on 2026-08-21 in preference to C2's
row-only shape, because C3 produces observations that need to be reproducible and dated, not just
summarized.

This document **amends no numbered section** of `docs/m7_operator_go_checklist.md`, of
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md` (including its Implementation Notes),
of `docs/moltbook_api_spec.md`, or of any ruling in `docs/`. It records what was executed and what
was observed.

**Nothing here authorizes transmission.** GO-1 §5.1 and §5.3 continue to govern. C3's own binding
wording is narrower still and is reproduced in full at §2 below, because everything this document
permits is derived from it.

**Cross-reference convention.** A bare `§N` refers to this document. References to another
document's sections are always named — "transport spec §8", "api spec §5", "§C3" of the checklist,
"GO-1 §5.3".

---

## 1. What C3 validates, and what it does not

C3 asks one question: **do the endpoints this deployment depends on answer, and does this
credential authenticate?** It is a reachability and authentication gate, not a behavioural one.

It does **not** validate:

- that a governed post will succeed — no write is issued, so nothing about the write path is
  observed;
- that the CAPTCHA classification contract settled by C1 and implemented by C2 is correct against
  the live platform — `POST /api/v1/verify` is not called here, and per §C3's binding wording and
  GO-1 §5.3 it is exercised for the first time only during a real §E challenge;
- that the rate limits documented at api spec §5 are the real ones — only the headers actually
  returned by the two reads below are recorded, as facts, with no inference beyond them;
- that the agent is publishable. Claim state is read (§4.3), not established.

**The distinction C1 §2 draws applies here unchanged, in the opposite direction.** C1 recorded
classifications that were documented but not live-confirmed. C3 records observations that *are*
live-confirmed but cover only the read surface. Neither document's confirmations transfer to the
other's subject matter.

## 2. The binding wording, and the operation set it permits

§C3 of the checklist states, verbatim:

> **C3 wording (binding):** Live API authentication and required endpoint reachability are
> validated using **documented non-publishing operations only** (e.g. auth handshake, health
> check, feed read). No synthetic CAPTCHA submission, governed post, reply, or other write is
> issued solely as a connectivity probe — `POST /api/v1/verify` is not assumed to be safely
> callable outside a real challenge, since a verification endpoint may require a genuine challenge
> and may mutate server-side state. The real `/verify` path is exercised for the first time only
> when an actual governed post legitimately produces a challenge during §E, unless the platform
> documents an explicit sandbox or validation mechanism (none is currently known).

Two independent conditions have to hold for an operation to be permitted here: it must be
**documented** (api spec, which derives from the 2026-07-21 `skill.md` capture), and it must be
**non-publishing**. The permitted set is therefore exactly:

| Operation | Endpoint | Documented at | Publishing? |
|---|---|---|---|
| Claim-status read / health check | `GET /api/v1/agents/status` | api spec §3 item 5 | No — read |
| Feed read | `GET /api/v1/posts` | api spec §4 | No — read |

Everything else on the Phase One surface is either a write (`POST /api/v1/posts`,
`POST /api/v1/posts/{id}/comments`, `POST /api/v1/verify`) or outside the §12 MVP slice. The
transport class has **no methods at all** for the deferred surface, so the restriction is not
merely observed here — there is nothing to call.

`GET /api/v1/posts/{POST_ID}` and `GET /api/v1/posts/{POST_ID}/comments` are documented reads and
would be permitted, but are **not exercised**: they require a real post ID, and the feed read
already answers the reachability question for the posts surface without one.

## 3. The probe is constructed so the forbidden act is impossible, not merely avoided

`MoltbookHTTPTransport.__init__` (`moltbook/transport.py:1350`) enforces Implementation Note E's
fail-closed invariant: `captcha_verifier` and `submit_captcha_fn` must be both configured or both
absent, and **both absent is legal** — a write that returns pending-verification is then reported
outward as exactly that, never guessed at.

The C3 probe constructs the transport with **both absent**. The consequence is the point: the
probe object has no CAPTCHA submission capability wired into it at all, so "no synthetic CAPTCHA
submission was issued" is a structural property of the object, not a claim about restraint. The
same holds for the write path in the weaker sense that `send()` exists but is never called.

The probe passes a `request_fn` that is a **pass-through recorder, not a substitute**: it calls the
production `real_request` with the production base URL and returns its `HTTPResponse` unchanged —
same urllib call, same 10s timeout, same header derivation, same redirect posture. It appends the
status code and response headers to a list and does nothing else. The network behaviour observed is
therefore the behaviour §E will run; a probe that validated a different transport posture would
validate nothing.

The seam is used because it is the only way to see the answer. `health_check()` returns a
`TransportResult` with `platform_headers=None`, `rate_limit=None`, and no HTTP status field at all
(`moltbook/transport.py:1414`) — the `HTTPResponse` is discarded inside `check_eligibility()` after
one `body.get("status")` lookup. Without this recorder the probe could not report the HTTP status
of `GET /agents/status`, which is the single most load-bearing observation in C3. §6 item 1
records the consequence of that discard, which is larger than C3.

## 4. Method

Base URL is the module constant `MOLTBOOK_BASE_URL = "https://www.moltbook.com/api/v1"`
(`moltbook/transport.py:39`), asserted rather than assumed by the script (§4.1), because api spec
§1 records that a bare-domain request triggers a redirect that **strips the `Authorization`
header** — the credential-integrity failure mode the `www` prefix exists to prevent.

The credential is read from `MOLTBOOK_API_KEY` in `.env` (gitignored). **No key material, and no
prefix or suffix of it, is written to this document, to the log, or to any commit.** The script
records only whether a key was found and its length.

**The script is `tools/c3_connectivity_probe.py`**, committed so that §4 is reproducible by
someone other than its author rather than merely described. It is the script that produced §5,
committed as it ran, with one deviation made when it moved into the repo — the log destination,
which defaults to the system temp directory instead of writing beside the script, so that running
it does not drop an untracked log into the governed tree. Its own header records that. **It is not
a test-suite fixture: nothing in `tests/` imports it, and re-running it is a live act that sends
the real credential to the real platform**, permitted only within §C3's binding wording.

### 4.1 Pre-flight, offline

Assert the base URL constant matches `https://www.moltbook.com/api/v1` exactly, and that a key is
present. Neither step touches the network. If either fails, the run stops before any request.

### 4.2 Unauthenticated redirect check

A single `GET https://www.moltbook.com/api/v1/agents/status` **with no `Authorization` header**,
with redirects disabled, recording the status code and any `Location`. This runs **before** the
credential is attached to anything.

Its purpose is narrow and specific: to observe whether the exact path we are about to send the key
to redirects. `real_request` uses `urllib.request.urlopen`, which **follows redirects silently and
does not record the final URL** — so if the authenticated call below were redirected, the recorded
evidence could not show where the credential actually went. This check closes that blind spot
without spending the credential to do it. A `401` here is the expected and healthy result: the
endpoint exists, requires auth, and does not redirect.

### 4.3 Claim status / health check — the authenticated read

`transport.health_check()` (`moltbook/transport.py:1405`).

**One call, not two.** `health_check()` is implemented as
`self._status_result(self.check_eligibility())` — it *is* `check_eligibility()`, wrapped to return
a `TransportResult`. Its own docstring records why: Moltbook documents no dedicated health
endpoint, so the claim-status read serves as both the health check and the eligibility check, and
"one real network call serves both purposes." Calling `check_eligibility()` and `health_check()`
separately would issue two identical requests to `/agents/status` and record them as though two
distinct things had been validated. **This document therefore treats "auth handshake", "health
check", and "claim-status read" as one observation of one endpoint, and says so rather than
presenting three.**

Recorded: the raw HTTP status and rate-limit headers **from the §3 recorder** (the
`TransportResult` carries neither), the `EligibilityState` derived (`claimed` or `pending_claim`),
the returned `TransportOutcome`, and elapsed wall time.

**The raw status is recorded because the derived state cannot be trusted to carry it.**
`check_eligibility()` returns `CLAIMED` only when the response body's `status` field equals
`"claimed"`, and `PENDING_CLAIM` in every other case — including a `401` on a revoked or invalid
key, whose error envelope has no `status` field at all. `health_check()` then reports
`TransportOutcome.SUCCESS` unconditionally. So the two outcomes C3 exists to tell apart — "the
credential authenticated and the agent is not yet claimed" and "the credential did not
authenticate" — are the same value on the transport's own return. Only the HTTP status
distinguishes them, and that is what this step records.

### 4.4 Feed read

`transport.read_feed()` (`moltbook/transport.py:1429`) — `GET /api/v1/posts`. Recorded: HTTP
status, `TransportOutcome`, elapsed wall time, rate-limit headers, and the **shape** of the
response (top-level keys, item count, presence of `next_cursor` and `has_more`). **No post
content, author, or body text is recorded** — the question is whether the endpoint answers, not
what is on the platform today.

### 4.5 Failure handling

`real_request` catches `urllib.error.HTTPError` and returns it as an `HTTPResponse`, so 4xx and
5xx are data, not exceptions. It does **not** catch `URLError`, DNS failure, or timeout — those
propagate. The script catches them per step and records the exception type and message as the
observation for that step, so a connection failure is recorded evidence rather than a traceback,
and a failure in one step does not discard the steps already completed.

### 4.6 Rate-limit budget

Three requests total, at most two of them authenticated, against a documented read budget of
60 per 60s (api spec §5). The probe consumes at most 5 percent of one minute's read allowance and
none of any write, post, comment, or verification-attempt budget.

### 4.7 Expected result, recorded before the run

Written down here **before** execution so that the observation can contradict it. `CLAUDE.md`
states that account `u/continuumagent` is "registered, verified, and claimed." The prediction that
follows from that is: §4.2 returns `401` with no `Location`; §4.3 returns HTTP `200` with body
`status: "claimed"`, yielding `EligibilityState.CLAIMED`; §4.4 returns HTTP `200` with a
cursor-paginated body.

Two outcomes would be findings rather than passes, and neither is to be smoothed over:

- **`pending_claim` at §4.3 with HTTP `200`** contradicts `CLAUDE.md` — the claim lapsed, or the
  claim was never what the file says it was.
- **HTTP `401` at §4.3** means the credential is dead or wrong, and — per §6 item 1 — would be
  reported by the transport as `pending_claim` anyway. This is the case the raw status exists to
  catch.

## 5. Results — executed 2026-08-21

Executed once, at **2026-08-21 19:10:41–19:10:42 UTC** (15:10 EDT), on operator authorization
given in-session. Three requests, no retries, no second run. Transport at **`c1eb9ba`**; working
tree clean apart from this document itself, which was untracked at the time of the run.

| Step | Endpoint | HTTP | Observed | At (UTC) |
|---|---|---|---|---|
| §4.1 pre-flight | none — offline | — | Base URL constant matches; key present, 44 chars; network untouched | 19:10:41.696 |
| §4.2 redirect check | `GET /agents/status`, unauthenticated | **401** | No `Location`, `redirected: false` — endpoint exists, requires auth, does not redirect | 19:10:42.196 |
| §4.3 health and claim status | `GET /agents/status`, authenticated | **200** | `status: "claimed"` → `EligibilityState.CLAIMED`; `TransportOutcome.SUCCESS`; `RetryCategory.SAFE_READ`; 0.328s | 19:10:42.528 |
| §4.4 feed read | `GET /posts`, authenticated | **200** | Keys `success`, `posts`, `next_cursor`, `has_more`; 20 items; `has_more: true`; 0.204s | 19:10:42.732 |

**All four steps match the §4.7 prediction. Neither of the two recorded failure cases occurred.**
The credential is live, it authenticates, and `u/continuumagent` is `claimed` — which is what
`CLAUDE.md` asserted and what was, until this run, unverified.

**Reachability is established for both endpoints in the §2 permitted set, and for no others.**

### 5.1 Rate-limit headers as actually returned

Recorded in full because they do not match `docs/moltbook_api_spec.md` §5, which documents three
headers and a flat "Read requests (GET) 60 / 60s".

`GET /agents/status` returned **twelve** rate-limit headers:

| Header | Value | Header | Value |
|---|---|---|---|
| `x-ratelimit-limit-short` | 30 | `x-ratelimit-reset-short` | 1 |
| `x-ratelimit-limit-medium` | 600 | `x-ratelimit-reset-medium` | 60 |
| `x-ratelimit-limit-long` | 10000 | `x-ratelimit-reset-long` | 300 |
| `x-ratelimit-limit` | 60 | `x-ratelimit-reset` | 1787339502 |

(`-remaining-short/medium/long` were 29 / 599 / 9999, and `x-ratelimit-remaining` 59.)

`GET /posts` returned, via typed `RateLimitInfo`: `limit=200`, `remaining=199`,
`reset=1787339503`, `retry_after_delay_seconds=None`.

Three facts follow, and each is an observation, not an inference:

1. **The generic limit is per-endpoint, not global.** `x-ratelimit-limit` was **60** on
   `/agents/status` and **200** on `/posts`, in two calls 200ms apart on one credential. api spec
   §5's single "60 / 60s" figure for all GETs does not describe what the platform sent.
2. **`x-ratelimit-reset` is an epoch timestamp.** `1787339502` is `2026-08-21T19:11:42Z`, exactly
   60 seconds after the call. api spec §5 explicitly left epoch-vs-delta undocumented and
   `RateLimitInfo` records why it passes the integer through unparsed; that question is now
   settled by observation, for this header.
3. **The tiered `-short`/`-medium`/`-long` resets are deltas, not epochs** — `1`, `60`, `300`,
   consistent with their own window names. **So one header family carries two different value
   formats**, and anything that treats `reset` uniformly across all eight will be wrong on six of
   them.

`RateLimitInfo.from_headers` parses only the four generic names (`x-ratelimit-limit`,
`-remaining`, `-reset`, `retry-after`) and **ignores all six tiered headers**. They survive on
`TransportResult.platform_headers` for the feed read. They do not survive the eligibility path at
all, which discards headers entirely (§6 item 1).

**None of this is a C3 failure and none of it is C3's to fix.** C3 asked whether the endpoints
answer; they do. What the true rate limits are, and which header a backoff should key off, is
recorded in §6 item 6 for its own ruling.

## 6. Raised by preparing and running this document, not settled by it

Six things surfaced — five while deriving the method, and item 6 from the run itself. Items 1 and
6 are the ones that matter beyond C3. None blocks C3; each is recorded here because C3 is the
first time any of them stops being theoretical.

1. **A `401` and an unclaimed agent are the same value on the eligibility path — the transport
   cannot distinguish a dead credential from a live unclaimed one.** `check_eligibility()`
   (`moltbook/transport.py:1418`) reads exactly one field, `response.body.get("status")`, and
   returns `PENDING_CLAIM` for everything that is not the literal string `"claimed"` — a `401`
   error envelope, a `500`, an empty body. `_status_result()` (`:1414`) then hard-codes
   `TransportOutcome.SUCCESS` and constructs a `TransportResult` with `platform_headers=None` and
   `rate_limit=None`, so the status code, the headers, and the rate-limit state of the call are
   all discarded before any caller sees them. The consequence at execution time is that
   `EligibilityBlocked` would report "platform eligibility is `pending_claim`" for an
   authentication failure, sending the operator to the claim lifecycle for a credential problem.
   **C3 works around this with the §3 recorder; the underlying behaviour is not changed by this
   document and is not C3's to change.** Recorded here for its own ruling.

2. **`EligibilityGate.state` defaults to `CLAIMED`** (`moltbook/transport.py:1210`). A transport
   that has never called `check_eligibility()` will pass `check_write()`. The gate is therefore
   fail-open until a real read moves it, which matters for §D and §E, not for C3 — but it means
   "the eligibility gate is configured" and "the eligibility gate has been informed by the
   platform" are different states, and only the second one is worth anything at execution time.

3. **`real_request` does not record the final URL** (`moltbook/transport.py:1370`), and urllib
   follows redirects by default. §4.2 works around this for C3. The general fix is the parked
   redirect-posture item in `TODO.md`, which C3 does not close.

4. **The redirect-posture TODO item is now live, not theoretical.** It was parked during C2 as a
   question about the verify path. api spec §1 records that a bare-domain request strips the
   `Authorization` header, which makes it a credential-integrity question on *every* authenticated
   call, and C3 is the first time this code sends the credential anywhere at all.

5. **`read_feed()` classifies any non-200 as `FAILURE`** (`moltbook/transport.py:1433`) with none
   of the condition-level nuance C1 §3.3 settled for the verify path. That is not wrong for a safe
   read, but it means a 429 and a 500 are indistinguishable in the returned `TransportOutcome`;
   this document records the raw HTTP status alongside it for exactly that reason.

6. **The live rate-limit surface is not the one `docs/moltbook_api_spec.md` §5 describes, and the
   transport parses the minority of it** — the only item on this list produced by the run rather
   than by reading the code. §5.1 above has the observed headers in full. Three separate
   questions come out of it, none of which C3 answers: which limit actually governs a given
   endpoint, given that the generic figure was 60 on one and 200 on the other 200ms apart; whether
   `RateLimitInfo` should parse the tiered headers at all, given that the tightest observed
   constraint (`-short`: 30) is invisible to it; and whether `reset` can keep passing an unparsed
   integer through when the generic header is an epoch and the tiered ones are deltas. **api spec
   §5 is a reference doc, not a governance document, so this is a correction to a reference — but
   transport spec §8's retry/backoff posture is downstream of it, and Note C's condition (b), a
   scheduling spec, is still deliberately unmet.** Recorded here; not corrected here, because C3
   observed two endpoints on one credential at one moment and that is not a sufficient basis for
   rewriting a documented limit table.

## 7. What this document does not attest

It does not attest that a governed post will publish, that the CAPTCHA path works, that the
platform's documented behaviour matches its real behaviour outside the two endpoints read, or that
the credential will still be valid at §E. It records what answered, when, and with what headers,
at one moment in time, against one credential.

## 8. Version binding

Bound to the 2026-07-21 `moltbook.com/skill.md` capture as transcribed in
`docs/moltbook_api_spec.md`, and to the transport implementation at **`c1eb9ba`**, the commit
recorded in §5. It does not inherit forward across a material change to either. A connectivity
observation is a fact about a moment, not a standing property of the platform — §5 records what
answered at 2026-08-21 19:10 UTC, and §5.1 is direct evidence that the capture it is bound to has
already drifted from the live surface in at least one respect.
