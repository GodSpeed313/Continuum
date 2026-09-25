# Checklist §D.5 — Amendment 1: Eligibility-Freshness Integration

**Status: DRAFT — cold-reviewed; pending separate operator acceptance and sign-off. Not yet in effect.**
**Subject document:** `docs/m7_operator_go_checklist.md` §D.5 (Final Pre-Transmission Single-Use
Gate), SIGNED / LOCKED by Kevin Brown, 2026-09-18 22:38 EDT (`checklist:541–557`, the sole signed
disposition block covering both the gate text and its standing-rule acceptance together).
**Authority:** `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` §16 Amendment 1 —
Eligibility Freshness Requirement, SIGNED / LOCKED by Kevin Brown, 2026-09-13 19:12 EDT.
**Placement:** the live eligibility-read placement (§3 below) reflects **operator direction,
2026-09-24** — a placement instruction only, not acceptance or signature of this amendment. See §3.7.

---

## 1. What this amendment is, and what it is not

Checklist §D.5 was signed 2026-09-18 — five days after Transport §16 Amendment 1 became binding —
without operationalizing that amendment's invariant. §16 Amendment 1 §1.3 itself explicitly
declines to authorize any checklist or runbook change on its own authority (`docs/m7_moltbook_
transport_boundary_and_deployment_spec.md:816–818`, "It does not itself authorize any code, test,
runbook (C4), or checklist (§D) change... Those remain separately gated on this amendment being
signed and locked, and on the implementation/test verification described in 1.2."). This document
is that separate, subsequent instrument. Following the precedent that a signed document is
corrected by a new standalone document rather than reopened (`docs/m7_c1_wiring_plan_erratum_1_
2026-08-17.md` §1; `docs/m7_eligibility_freshness_ruling_2026-09-01.md` §8), it is filed as its own
dated artifact rather than as an edit to §D.5's signed text.

**Scope, deliberately narrow.** This amendment addresses **only** Transport §16 Amendment 1's
eligibility-freshness requirement as it bears on Checklist §D.5. It does not address, and takes no
position on:

- Checklist §D.5's separate, independently-identified `governance_config_version` carry-across
  gap (raised by DRAFT `docs/m7_c4_runbook_amendment_1_2026-09-18.md` §3a). That gap depends on
  whether the operator accepts §3a's underlying three-way-match requirement at all — a determination
  this document does not make and is not blocked on. If and when that determination is made, it is
  its own, separate correcting instrument.
- Checklist §D.5 §252's stale description of which C4 sections DRAFT `docs/m7_c4_runbook_amendment_
  1_2026-09-18.md` leaves "untouched." That amendment's substantive content is itself still settling
  (see D.5's own text, "§D.5 acceptance and C4 Amendment 1 signature are sequential, not parallel" —
  `docs/m7_operator_go_checklist.md:563–564`); correcting §D.5's description of it now would risk
  needing a second correction once C4 Amendment 1's content is finalized. Left parked for a
  subsequent, separate correction once C4 Amendment 1 settles.
- Checklist §D's requires-table (a different, currently-unsigned section gating GO-2's own
  signature, not §D.5's execution-time gate). Separate governance act, separate timing.
- Finding A (status/metadata discard on the eligibility read path). Remains separately parked. See
  §4 below for exactly how this document treats it.
- Any code, test, GO-2, envelope, Dry Run, or transmission activity. Confers no such authority.

**It does:**
- correct §D.5's description of what occurs "before the transmission-attempt boundary" so that it
  no longer implies no platform contact of any kind occurs there (§2 below);
- incorporate the live eligibility-read step Transport §16 Amendment 1 requires, at the placement
  directed by the operator, 2026-09-24 (§3 below) — presenting that incorporation as a placement
  instruction only, not as acceptance of the completed amendment (§3.7);
- expressly qualify signed §D.5 step 11's "proceed directly" language so that the directed
  placement's required operation is unambiguously permitted, without weakening any of step 11's
  existing no-substitution protections (§3.5);
- direct contemporaneous evidence capture for a qualifying failure at the new step, without
  creating, weakening, or auto-invoking any recovery authority (§3.6);
- state the governance consequence of a qualifying eligibility-check failure at that new step,
  grounded in Implementation Note A's existing invariant, without claiming a diagnostic precision
  the current implementation does not support (§4 below).

**It does not:**
- redefine the transmission-attempt boundary. That remains exactly what §D.5 already states:
  the invocation of `self._request_fn(...)` inside `moltbook.transport.MoltbookHTTPTransport.
  send()` (`moltbook/transport.py:1491–1492`). A live platform READ performed by the eligibility
  check is not, and does not become, that boundary. See §2.
- resolve Finding A. See §4.
- create new FROZEN → AVAILABLE recovery authority, weaken the existing evidence standard, infer
  recovery automatically, or transition FROZEN → AVAILABLE automatically. See §3.6.
- constitute operator acceptance or signature. The placement direction recorded in §3 is a
  narrower, distinct act from accepting this amendment as a whole — see §3.7. Acceptance remains a
  separate, later, operator acceptance/sign-off act — not itself accomplished by the cold review
  already performed against this document.
- authorize any transmission, sign any GO-2, or make itself operative by its own existence.

## 2. Correction to §D.5's external-contact description

Signed §D.5 currently reads (`docs/m7_operator_go_checklist.md:239–246`):

> **The transmission-attempt boundary** is the invocation of `self._request_fn(...)` inside
> `moltbook.transport.MoltbookHTTPTransport.send()`... — the sole point where the transport reaches
> the external platform. Everything before that line is local governance computation with no
> external effect (envelope freshness validation, kill-switch check, **eligibility check**,
> path/body construction).

**This sentence is now inaccurate as a factual description**, once a fresh `check_eligibility()`
call is added anywhere in the gate: `check_eligibility()` (`moltbook/transport.py:1418–1427`)
performs a real `GET /agents/status` call through the same `self._request_fn(...)` seam `send()`
itself uses — it is not, and was never truthfully, an operation "with no external effect." Under
the *signed, current* text, this was accurate only because no eligibility read of any kind occurred
in the gate — the gate relied entirely on `eligibility.check_write()` (`moltbook/transport.py:
1209–1214`), which reads only in-memory stored state and performs no network call. Once a live read
is added, the sentence as written would mislead a future reader into treating the new step as
contact-free.

**Correction — superseding this sentence's parenthetical and its "no external effect" claim, and
this sentence only:**

> The transmission-attempt boundary — the point at which GO-2's transmission authority is consumed,
> permanently and without exception — remains exactly and only the invocation of
> `self._request_fn(...)` inside `moltbook.transport.MoltbookHTTPTransport.send()`
> (`moltbook/transport.py:1491–1492`), unchanged by this amendment. This is the sole point at which
> a governed **outbound write** reaches the external platform, and the sole point whose crossing
> the AVAILABLE/FROZEN/CONSUMED model below governs.
>
> This is distinct from platform **contact**. Per Transport §16 Amendment 1, the gate now performs
> a live platform **read** (`check_eligibility()`, itself a `GET` — a safe read under transport spec
> §8, not a governed write) at the point fixed by §3 below. That read does reach the external
> platform. It is not, and does not become, the transmission-attempt boundary: it authorizes
> nothing, transmits no governed content, and its own occurrence — successful, failed, or
> exception-raising — does not by itself consume GO-2. Consumption remains defined solely by
> whether `self._request_fn(...)` inside `send()`'s **write** path was reached, exactly as before.
> Envelope freshness validation, kill-switch check, and path/body construction remain accurately
> described as local computation with no external effect; the eligibility check no longer is, and
> this document's own text is corrected accordingly.

**Also qualified — the FROZEN-recovery "qualifying evidence" list** (`docs/m7_operator_go_
checklist.md:377–385`), which names "an exception raised by `validate_envelope()`,
`kill_switch.check_write()`, or `eligibility.check_write()` — all of which execute, and can only
raise, before the boundary" as an example of qualifying evidence. That list is explicitly
non-exhaustive ("Examples, not an exhaustive or implementation-specific list," line 378) and
therefore not itself inaccurate — but for the avoidance of doubt, this amendment states explicitly
that an exception raised by the new `check_eligibility()` call (§3 below) qualifies on the same
basis: it, too, can only execute and can only raise before the transmission-attempt boundary. See
§3.6 for how this evidence must be captured and preserved, without altering the recovery standard
itself.

## 3. Placement of the live eligibility read — Option 2, incorporated per operator direction, 2026-09-24

### 3.1 What is settled, and cited

- **The requirement itself is settled and binding**, independent of this document: Transport §16
  Amendment 1 §1.1 (`docs/m7_moltbook_transport_boundary_and_deployment_spec.md:748–762`) — a
  qualifying observation must be "obtained by a live read... not assumed, not defaulted, not
  inherited," taken "on the exact transport instance that will perform the write," satisfying "an
  operator-determined freshness relationship to the write attempt," and explicitly excludes "any
  uninitialized or constructor-default value" and any observation "taken in a prior session, on a
  different transport instance, or at a different validation step."
- **A contemporaneous design — a fresh `check_eligibility()` call made immediately before `send()`
  — is explicitly pre-authorized as a candidate mechanism**, without requiring a separate
  numeric-bound instrument (§1.2, `spec:766–782`, quoting the underlying signed ruling: "a fresh
  `check_eligibility()` call made immediately before send would satisfy this invariant even with
  Finding A unresolved... near-zero elapsed time between observation and write falls inside any
  operator-determined freshness relationship").
- **§D.5's AVAILABLE/FROZEN/CONSUMED consequences are structurally anchored to the attempt-record
  marker write (existing gate step 9), not to any semantic notion of "pre-flight,"** and are
  already fully determined by existing signed text for a step landing on either side of it:
  - A failure in existing steps 1–8 (before the marker write): "no marker exists, no boundary
    crossed, GO-2 is **not** consumed by this failure... the operator may re-enter the complete
    gate from step 1" (`docs/m7_operator_go_checklist.md:352–354`). GO-2 remains AVAILABLE.
  - A failure after the marker write but before the boundary is reached (existing steps 9–11):
    "transition to FROZEN. Do not retry transmission... Apply the FROZEN → AVAILABLE recovery
    protocol below only if affirmative evidence can positively establish pre-boundary termination;
    otherwise remain FROZEN indefinitely" (`docs/m7_operator_go_checklist.md:362–366`). GO-2
    becomes/remains FROZEN, requiring the evidence-gated recovery disposition (`checklist:
    370–411`) before any further gate entry. **This is the consequence that governs the placement
    directed at §3.3 below.** FROZEN is not CONSUMED and is not necessarily permanent — recovery
    remains available under the existing evidence-gated protocol (§3.6).
- **The directed placement never consumes GO-2 by itself.** Per §2 above, the read is not the
  boundary; only `self._request_fn(...)` inside `send()` is.

### 3.2 A structural point the placement must not obscure

Placement of the **read** and placement of the **enforcement** (the actual stop-on-failure) are two
separate design choices, not one. `check_eligibility()` (`moltbook/transport.py:1418–1427`) itself
never raises on a non-CLAIMED result — it returns `EligibilityState.PENDING_CLAIM` and updates the
gate; only a subsequent call to `eligibility.check_write()` (`moltbook/transport.py:1209–1214`)
raises `EligibilityBlocked`. Under existing, unmodified `send()` behavior, that enforcing call
happens **only** inside `send()` itself (`moltbook/transport.py:1474`) — structurally within
existing steps 9–11, after the marker write. **The placement directed at §3.3 relies on exactly
this existing behavior**, rather than adding any new enforcement call: the fresh read is taken
immediately before `send()`, and `send()`'s own existing internal `eligibility.check_write()`
enforces it, unmodified, exactly as it already runs today.

### 3.3 The adopted placement (Option 2) — read immediately before `send()`

**Per operator direction, 2026-09-24**, the fresh eligibility read is placed between existing gate
step 10 (marker re-read) and existing gate step 11 (proceed to `send()`):

1. Existing step 9 — the `ATTEMPT_IN_PROGRESS` marker is written, exactly as signed §D.5 already
   requires. Unchanged.
2. Existing step 10 — the marker is re-read and its identity/binding fields verified, exactly as
   signed §D.5 already requires. Unchanged.
3. **New step — on the exact same transport instance that will perform the write**, call
   `check_eligibility()` (`moltbook/transport.py:1418–1427`). This is the live platform read
   Transport §16 Amendment 1 §1.1(a)/(b) requires, taken at the position §1.2 itself names as its
   candidacy example: "a fresh `check_eligibility()` call made immediately before send" (`spec:
   772–773`). No operation of any kind — local or external, governed or otherwise — occurs between
   this read and existing step 11's call to `send()`.
4. Existing step 11 — proceed immediately to `send()` (C4 §7 as amended). `send()` performs its own
   existing, unmodified internal sequence — `validate_envelope()`, `kill_switch.check_write()`,
   `eligibility.check_write()` (`moltbook/transport.py:1472–1474`) — before any network call. The
   `eligibility.check_write()` call at this point enforces the observation taken at step 3, not any
   earlier or stored value, because `EligibilityGate.state` (`moltbook/transport.py:1198`) is a
   single field that step 3's `update()` call (`moltbook/transport.py:1426`) has just overwritten.
5. Only `self._request_fn(...)` inside `send()` (`moltbook/transport.py:1491–1492`) constitutes the
   GO-2 consumption boundary, exactly as §2 above preserves.

**AVAILABLE/FROZEN/CONSUMED under this placement:**
- Failure before existing step 9 (unrelated to the new step, e.g. clean-tree or kill-switch
  failure): GO-2 remains AVAILABLE, unchanged from existing signed behavior (`checklist:352–354`).
- **A qualifying failure at the new step 3, or at `eligibility.check_write()` inside `send()`
  enforcing it, occurs after the marker write (existing step 9).** Per `checklist:362–366`, GO-2
  becomes/remains **FROZEN** — not CONSUMED, and not necessarily permanent. Recovery to AVAILABLE
  remains available only through the existing evidence-gated FROZEN → AVAILABLE protocol
  (`checklist:370–411`); see §3.6 for the evidence this amendment directs be captured to support
  that protocol, without altering it.
- Crossing `self._request_fn(...)`: GO-2 becomes CONSUMED, permanently, exactly as signed
  (`checklist:239–246, 278–282, 367–369`), regardless of any outcome of the new step.

**Relationship to Transport §16 Amendment 1:** this placement is the specific design §1.2 names as
its own candidacy example, with nothing intervening between the observation and the write it gates
— same instance (§3.1 above), immediately-before-send timing, no intervening operation of any kind.
No further operator-accepted numeric freshness bound is invoked or required for this placement; a
bound would only become relevant to a design tolerating measurable elapsed time between observation
and write (`spec:784–789`), which this placement does not do.

### 3.4 Option 1 (read and enforce before the marker) — considered, not adopted

For the audit record: an alternative placement — a live read paired with an explicit, immediate
fail-fast enforcement call, both inserted among existing steps 1–8, before the marker write — was
also analyzed. That alternative would have preserved AVAILABLE-on-failure (per `checklist:352–354`)
at the cost of a weaker, and possibly reclassifying, match to §16 Amendment 1 §1.2's contemporaneity
test — envelope construction, the marker write, and the marker re-read would all have intervened
between the observation and the actual write, and whether that counts as disqualifying "intervening
state mutation" under `spec:778–782` is not resolved by signed text. **Per operator direction,
2026-09-24, this alternative is not adopted.** It is retained here only as a record of what was
considered and why, consistent with this corpus's practice of recording superseded reasoning rather
than silently discarding it; it is not part of the operative procedure in §3.3.

### 3.5 Express qualification of signed §D.5 step 11

Signed §D.5 step 11 currently reads (`docs/m7_operator_go_checklist.md:336–339`):

> 11. Proceed directly to `send()` (C4 §7 as amended) with no substitution of envelope, payload,
>     action, configuration, credentials, or execution candidate between step 9's write and the
>     call. Transport performs its own existing internal validation, kill-switch, and eligibility
>     checks before `_request_fn(...)`.

Whether this text, unamended, already permits an inserted live eligibility read between steps 10
and 11 is a genuinely open textual question: "no substitution of [the six named items]" may define
the entire scope of what "directly" forbids, or may instead be one specific instance of a broader,
freestanding "proceed directly" requirement that a new step's mere insertion — even one that
substitutes nothing — would violate. Signed text does not resolve which reading controls, and this
amendment does not resolve it either.

**Correction — expressly qualifying step 11, so this question need not be resolved for the directed
placement to be operative:**

> For the purpose of the placement directed at §3.3, step 11 is qualified to read: proceed to the
> new eligibility-read step at item 3 of §3.3's numbered sequence and then directly to `send()`, with no substitution of
> envelope, payload, action, configuration, credentials, or execution candidate between step 9's
> write and the call, exactly as signed. The permitted eligibility-read operation:
> - does not authorize substitution of the envelope, payload, action, configuration, credentials,
>   or execution candidate — all six protections stand exactly as signed;
> - exists solely to satisfy the signed Transport §16 Amendment 1 eligibility-freshness requirement;
> - is followed immediately by `send()`, with no additional intervening operation of any kind
>   permitted between the read and the call.

This qualification applies only to step 11 and only to the extent stated. It does not reopen, edit,
or alter a single byte of signed §D.5's own text — exactly as this document's other corrections
operate by supersession, not by editing the signed original.

### 3.6 Recovery-evidence capture at the new step

Because the directed placement (§3.3) places the fresh observation after the marker write, a
qualifying failure there is governed by the existing FROZEN → AVAILABLE recovery protocol
(`docs/m7_operator_go_checklist.md:370–411`), whose qualifying-evidence standard already names, as
one non-exhaustive example, "an exception raised by... `eligibility.check_write()`... which... can
only raise... before the boundary" (`checklist:377–381`).

**This amendment directs, procedurally, that:**

> Where either the new step-3 `check_eligibility()` call, or `eligibility.check_write()` inside
> `send()` enforcing its result, fails or raises, the operator (or the session's own tooling)
> contemporaneously captures and preserves the resulting exception, traceback, or other applicable
> control-flow evidence — the same category of evidence `checklist:377–381` already recognizes,
> applied at this call site.

This is a **procedural evidence-capture instruction only**. It does not:
- create any new recovery authority beyond what `checklist:370–411` already provides;
- weaken, narrow, or restate the existing qualifying-evidence standard (`checklist:377–385`
  remains fully controlling, unedited, exactly as signed);
- infer recovery automatically from the mere existence of captured evidence;
- transition GO-2 from FROZEN to AVAILABLE automatically, at this step or any other — recovery
  remains, exactly as signed, an explicit, evidence-gated operator disposition (`checklist:
  393–411`);
- characterize evidence capture, by itself, as sufficient to authorize recovery. Captured evidence
  is a precondition for a subsequent, separate, explicit operator recovery disposition to be
  possible — it is not that disposition.

If qualifying evidence cannot be established and preserved for a given FROZEN episode, the record
remains FROZEN, indefinitely if necessary, exactly as `checklist:390–391` already states. This
amendment changes nothing about that outcome.

### 3.7 What the directed placement is, and is not

**Recording that the placement above was incorporated per operator direction, 2026-09-24.** This is
a placement instruction, not operator acceptance, signature, or final disposition of this amendment.
It does not fill, and must not be read as filling, `Amended by (operator)`, `Amended at`, or the
acceptance statement at the foot of this document — those remain for a separate, later, operator
acceptance/sign-off act, which the cold review already performed against this document does not
itself constitute. §D.5 itself remains SIGNED/LOCKED and unedited; only this standalone, still-unsigned amendment
now reflects the directed placement as its operative content.

## 4. Failure semantics at the new step — verified against current implementation

**This section states only what current code supports, and does not claim a diagnostic precision
that code does not have.**

`check_eligibility()` (`moltbook/transport.py:1418–1427`) has exactly two failure modes, verified
directly against `3b40fbd`, not assumed:

1. **The `GET` completes at the transport level, its body parses successfully as JSON, and that
   JSON value has the object/mapping shape `check_eligibility()` requires** — any HTTP status,
   including a 401 or other error response, whose body `real_request()` (`moltbook/transport.py:
   1289–1320`) successfully decodes as UTF-8, parses via `json.loads(raw)` on either its success
   path (lines 1310–1315) or its `except urllib.error.HTTPError` path (lines 1316–1320), **and
   yields a JSON object** (a dict, on which `.get("status")` — `moltbook/transport.py:1423` —
   can be called) — **and that object's `status` field is anything other than `"claimed"`.** This
   collapses into a single `EligibilityState.PENDING_CLAIM` result — indistinguishably, by design of
   the current code, not by this document's characterization. This is the same collapsing already
   recorded on the signed record at Checklist §C's C3 row (`docs/m7_operator_go_checklist.md:142`):
   "a dead credential and a live unclaimed one are the same value on the transport's own return."
   This document adds no new instance of the gap; it inherits the existing, already-disclosed one at
   a new call site. Under the placement at §3.3, this result is enforced by
   `eligibility.check_write()` inside `send()`, post-marker — see §3.3 and §3.6.
2. **The `GET` does not reach a returned `EligibilityState` at all.** Verified by direct re-read of
   `moltbook/transport.py:1289–1320` and `:1418–1427`, four distinct uncaught paths exist, none
   caught anywhere in `real_request()` or `check_eligibility()`: (a) any exception
   `urllib.request.urlopen` itself can raise that is not `urllib.error.HTTPError` (timeout,
   connection failure, etc.); (b) a failure decoding or parsing the response body —
   `.decode("utf-8")` or `json.loads(raw)` — on the success path (`transport.py:1311–1314`); (c) the
   identical decode/parse failure occurring **inside the `except urllib.error.HTTPError` handler
   itself** (`transport.py:1317–1320`) against a malformed or non-JSON error body — e.g. a
   500/502/503 response whose body is an HTML error page rather than JSON; and **(d) syntactically
   valid JSON that successfully parses via `json.loads(raw)` but is not an object/mapping** — a
   bare array, string, number, boolean, or `null` (e.g. a platform response body of `true`,
   `null`, `"ok"`, or `[]`). `HTTPResponse.body` (`moltbook/transport.py:277`) is annotated `dict`
   but that annotation is not runtime-enforced — nothing in `real_request()` or `HTTPResponse.
   __post_init__` (`transport.py:280–283`, which normalizes only `headers`) validates the parsed
   value's shape. `check_eligibility()`'s own `response.body.get("status")` call
   (`moltbook/transport.py:1423`) then raises `AttributeError` on any such non-dict value, since
   none of list, str, int, float, bool, or `NoneType` defines `.get()`. (a)–(c) occur inside
   `real_request()` and prevent it from ever returning; (d) occurs one call later, inside
   `check_eligibility()` itself, against a `real_request()` call that *did* return successfully.
   Malformed/non-JSON bodies (b, c) and structurally-incompatible-but-valid JSON (d) are therefore
   distinct implementation cases — one fails during parsing, the other fails during subsequent
   shape access — though `check_eligibility()` wraps neither its own call to `self._request_fn(...)`
   nor its own `.get()` access in any `try`/`except`, unlike `send()`'s write-path call, which
   explicitly catches `(TimeoutError, ConnectionError, OSError)` (`moltbook/transport.py:1493`) and
   which in any case would not catch either a body-parsing failure or a shape-access failure.
   **Any exception from (a), (b), (c), or (d) propagates uncaught out of `check_eligibility()`.**
   This is a plain code fact, not part of Finding A's own scope (Finding A concerns response
   *classification*, not transport-level, parsing, or shape failure), verified this pass, not
   previously documented at this call site. Under the placement at §3.3, all four sub-cases occur
   after the marker write and before the outbound-write boundary — per `checklist:362–366`, each is
   a FROZEN-path event, subject to the same evidence-gated recovery protocol and the same §3.6
   evidence-capture direction as failure mode 1. This amendment does not invent any new diagnostic
   category or recovery authority for any of (a)–(d) beyond what §3.6 already directs.

**Governance consequence stated — cause left undetermined:** per Implementation Note A's existing,
unamended invariant (`moltbook/transport.py:1191–1195`, "`claimed` -> writes proceed normally.
`pending_claim` -> writes rejected"), **failure to establish a qualifying `CLAIMED` observation
by either path above means the governed write must not proceed.** This document states that
consequence and no more. It does not attempt to distinguish, at this step, whether a `PENDING_
CLAIM` result reflects a genuinely unclaimed agent, an invalid or dead credential, a malformed or
unexpected response body, or any other condition the current response-classification code cannot
tell apart — that remains exactly the scope of the already-parked Finding A. **Finding A is not
resolved, narrowed, or otherwise touched by this document.** Nor does this document classify a raw
transport-level exception (failure mode 2 above) under Finding A's own terms — it is a distinct,
newly-surfaced-at-this-callsite fact, left as a plain observation, not a governance ruling of its
own.

## 5. What this amendment does not decide

Restating, for the avoidance of doubt beyond §1's list: this document does not accept, sign, or
lock itself, or constitute operator acceptance, merely by incorporating the operator's §3
placement direction, nor merely by having been cold-reviewed — acceptance remains a separate,
later act (§3.7); does not resolve Finding A; does
not touch `governance_config_version` in any respect; does not touch Checklist §D's requires-table;
does not touch DRAFT C4 Amendment 1 in any respect (a separate, later conformity revision of that
document will be required once this instrument is itself accepted — not undertaken here); does not
create, weaken, or auto-invoke any FROZEN → AVAILABLE recovery authority beyond §3.6's procedural
evidence-capture direction; does not authorize any code, test, GO-2, envelope, Dry Run, or
transmission activity; and does not itself become effective by its own existence.

**Remaining unresolved matters this document does not settle, preserved for the record:**
- The exact timing of transport-instance construction relative to gate step 1 is not explicitly
  staged anywhere in signed §D.5 or in this amendment — inferred only from existing Amd §4 step 1's
  "session that will hold the `KillSwitch` instance" language. Same-instance continuity for the
  placement at §3.3 depends on that inference holding; it is not independently re-established here.
- Whether "at a different validation step" (`spec:759–760`) means any earlier position within the
  same live gate, or only a categorically separate validation exercise (as its own given example,
  the §C3-style check, is) remains a genuinely open interpretive question about §16 Amendment 1's
  text in the abstract. It does not materially affect §3.3's placement, which independently
  satisfies §1.2's more specific "immediately before send" candidacy language regardless of how
  that separate phrase is read — but the interpretive question itself is not resolved by this
  document.
- Finding A's diagnostic limitations (§4 above) remain exactly as previously disclosed, at this new
  call site as much as at every existing one.

---

```
Status: DRAFT — unsigned, cold-reviewed. Placement (§3.3) incorporated per operator direction,
        2026-09-24; full acceptance of this amendment remains a separate, later, operator
        acceptance/sign-off act, not itself accomplished by the cold review already performed.
Amended by (operator):
Amended at:
Statement: "I have reviewed the correction to §D.5's external-contact description (§2),
            the placement incorporated at §3.3 per my own prior direction, the express
            qualification of step 11 (§3.5), the recovery-evidence capture direction
            (§3.6), and the eligibility-check failure semantics as verified against
            current implementation (§4). I accept this amendment as standing governance
            integrating Transport §16 Amendment 1's eligibility-freshness requirement
            into Checklist §D.5's gate. This acceptance does not itself authorize any
            transmission, sign any GO-2, or make DRAFT C4 Amendment 1 operative or
            conforming to this change — those remain separate acts, including C4
            Amendment 1's own required conformity revision once this amendment is
            accepted."
```
