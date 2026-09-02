# M7 — Eligibility Gate Freshness Ruling

**Status: DRAFT — pending operator review. Not signed, not accepted, not binding on anything.**
Drafted 2026-09-01 against `HEAD` at `12bcf4fd36294cb566ab5c54bed8b7a565640b49`, tree clean.
**Drafting this document is not acceptance of it, does not close any open item, and does not
authorize any code change, checklist edit, or transmission.** Everything in this document is a
proposed finding and a proposed invariant, awaiting the operator's own determination per §8 below.

**Raised by:** `docs/m7_c3_endpoint_connectivity_validation_2026-08-21.md` §6 item 2, in the
existing signed record — quoted in full at §2 below — which states plainly that the gate is
"fail-open until a real read moves it, which matters for §D and §E" and explicitly defers
resolution to "its own ruling." Independently re-derived here by direct inspection of
`moltbook/transport.py` and `docs/m7_c4_first_post_runbook_2026-08-21.md` §7 during preparation
for §D, rather than taken on C3's word.

**Not required by any of C1–C5.** All five are closed and signed; none of their rows names this
question, and this document does not reopen, amend, or relitigate any of them. It responds to a
finding those documents raised and left open, not to a gap in their own satisfaction.

This document **amends no numbered section** of `docs/m7_operator_go_checklist.md`, of
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md` (including its Implementation
Notes), of `docs/moltbook_api_spec.md`, of `TODO.md`, or of any ruling in `docs/`. It states a
finding and, contingent on operator acceptance, a governance requirement — it does not itself
enact that requirement anywhere.

**Nothing here authorizes transmission**, and nothing here authorizes engineering work.
GO-1 §5.1/§5.3 continue to govern; no governed post or reply may be sent, and no code cited below
may be changed on the strength of this document alone. **This document is read-only in effect
until and unless the operator signs a disposition on it.**

**Cross-reference convention.** A bare `§N` refers to this document. References to another
document's sections are always named — "checklist §D", "transport spec §16", "C3 §6", "C4 §7".

---

## 1. What this document decides, and what it does not

It decides, subject to operator acceptance: (a) that two defects discovered in and around the
eligibility gate are distinct in kind and consequence and must not be treated as one finding;
(b) whether the more serious of the two is a condition that must be satisfied before §D may be
sought; and (c) what class of governance instrument is required to carry that determination.

It does **not** decide: which code changes, if any, satisfy the requirement; whether the
requirement is satisfied by a transport change, a runbook change, a new checklist row, a changed
default, or some combination; or whether satisfying it requires a formal transport-spec §16
amendment as opposed to a non-binding implementation note. §6 states the requirement in the
abstract and §8 states why choosing among those instruments is deliberately left open here.

## 2. Grounding — the machinery, as it exists at `12bcf4f`

**The gate's default.** `EligibilityGate` (`moltbook/transport.py:1188-1214`) is a dataclass:

```python
state: EligibilityState = EligibilityState.CLAIMED
```

(`:1198`). No platform call is required to construct one in the `CLAIMED` state — it is the
field's default, not an observation.

**What moves it.** Only `EligibilityGate.update()` (`:1201-1203`) changes `state`, and the only
caller of `update()` is `MoltbookHTTPTransport.check_eligibility()` (`:1418-1427`):

```python
def check_eligibility(self) -> EligibilityState:
    response = self._request_fn("GET", "/agents/status", None, self._auth_headers())
    state = (
        EligibilityState.CLAIMED
        if response.body.get("status") == "claimed"
        else EligibilityState.PENDING_CLAIM
    )
    self.eligibility.update(state)
    return state
```

**What `send()` actually checks.** `send()` (`:1440-1474`) calls, in order:

```python
validate_envelope(envelope, live_config_version=self._live_config_version)
self.kill_switch.check_write()
self.eligibility.check_write()
```

`EligibilityGate.check_write()` (`:1209-1214`) reads `self.state` — a field already set (or left
at its default) before `send()` was ever called. **`send()` does not call `check_eligibility()`
and does not call `health_check()`.** It evaluates whatever the gate already holds.

**The kill switch does not establish this by analogy, and C4's own text should not be read as
claiming it does.** `KillSwitch._engaged` is set to `True` only inside `_engage()` (`:570`),
called only from four explicit local methods — `activate_manual` (`:480-483`),
`activate_ambiguous_write` (`:485-488`), `activate_reconciliation_contradiction` (`:490-493`),
`activate_captcha_suspension_risk` (`:495-538`) — and set to `False` only at construction
(`:464`) and by the operator-only `clear()` (`:557-564`); a full-text search of `moltbook/`
confirms these are the only writers of `_engaged` anywhere in the package. Every value
`KillSwitch.check_write()` (`:475-477`) can read was placed there by the transport's own code
acting on a fact it already knew. `EligibilityGate.state` (`:1198`) is different in exactly the
respect that matters: its only mutator anywhere in `moltbook/` is `update()` (`:1201-1203`),
called from exactly one call site in the entire package — `check_eligibility()` (`:1418-1427`) —
confirmed by the same full-text search. The default value was placed there by nobody's
observation of the platform at all.

C4 §7 step 7 (`docs/m7_c4_first_post_runbook_2026-08-21.md:236-241`) frames its claim — "the
guarantee is stronger than an unbroken recheck window" — around the kill switch specifically,
and its concluding sentence ties back to "Step 3's confirmation" (the kill-switch recheck) alone.
But the sentence supporting that claim names `kill_switch.check_write()` **and**
`eligibility.check_write()` together, in the same breath, as the calls `send()` makes "before any
network call" (`transport.py:1472-1474`), and backs the pair with one quoted guarantee — "called
immediately before the actual network write, not just once somewhere upstream" — drawn from
`KillSwitch`'s own docstring (`transport.py:445-461`, quoting `:448-450`). **Nowhere does §7 note
that this docstring is `KillSwitch`-specific, or that its guarantee does not, by its own terms,
extend to `eligibility.check_write()`.** A reader of this passage could reasonably conclude the
two gates carry the same freshness protection. They do not, for the reason given above: reading
`self.state` at the identical call site one line later (`:1474`) guarantees only that the read
happens at the last possible moment — it says nothing about whether the value being read was ever
informed by the platform, and for the unrefreshed default it was not. `_engaged`'s guarantee holds
because every value it can hold was already vetted by the transport's own logic before
`check_write()` runs; `EligibilityGate.state`'s does not, because its default was vetted by
nothing.

**The status/metadata discard.** `_status_result()` (`:1414-1416`):

```python
def _status_result(self, state: "EligibilityState") -> TransportResult:
    outcome = TransportOutcome.SUCCESS
    return TransportResult(outcome, RetryCategory.SAFE_READ, platform_response={"status": state.value})
```

`outcome` is hardcoded regardless of what `/agents/status` actually returned; `platform_headers`
and `rate_limit` are never populated on this path. Contrast `read_feed()` (`:1429-1437`), which
checks `response.status_code == 200` for its outcome and passes `headers`/`rate_limit` through
unconditionally — the discard in `_status_result()` is specific to the eligibility path, not a
transport-wide pattern.

**C4's own treatment of "immediately before send."** `docs/m7_c4_first_post_runbook_2026-08-21.md`
§7 sequences nine steps under GO-2. Step 2 is an explicit clean-tree recheck; step 3 is an
explicit `KillSwitch.engaged` recheck "in this same session, on the instance that will be passed
to the transport"; step 7's own text extends that guarantee into code by citing `:448-450` above.
**No step in §7 performs, or requires, a fresh `check_eligibility()` or `health_check()` call on
the send-executing instance.** The runbook demonstrates, for the kill switch, exactly the
discipline this document argues is missing for eligibility — which is evidence the omission is a
gap rather than a considered decision, since the authors solved this class of problem once and
did not carry it to the adjacent line.

**What C3 already attests, and does not.** `docs/m7_c3_endpoint_connectivity_validation_2026-08-21.md`,
signed `Kevin Brown, 2026-08-21 15:56 EDT`, recorded a live `CLAIMED` read at 2026-08-21 19:10 UTC
against transport `c1eb9ba`. Its own row (checklist §C, row for C3) states: **"It does not attest
that... the credential will still be valid at §E."** C3's read is not wired to the
`EligibilityGate` instance any future `send()` call will use, has no expiry, and — per the
finding above — nothing in the current corpus requires it to be repeated before §E regardless.

## 3. Two distinct findings, kept separate

### Finding A — Status/metadata loss (transport-level)

`check_eligibility()` maps every response body lacking the literal string `"claimed"` — a `401`
auth-failure envelope included — to `PENDING_CLAIM`, indistinguishable from a genuine unclaimed
agent; `_status_result()` discards `status_code`, `headers`, and `rate_limit` before any caller
can see them.

**Direction of failure: fail-closed.** `check_write()` blocks any state other than `CLAIMED`. A
dead or expired credential therefore still blocks the write — it does not leak through. The
defect is **diagnostic, not permissive**: `EligibilityBlocked` reports "platform eligibility is
`pending_claim`" for what may actually be an authentication failure, sending an operator toward
the claim lifecycle rather than the credential, inside a runbook (C4 §2) governed by a fixed,
non-extendable 300-second approval window where a wrong diagnosis has a real cost.

**This finding, by itself, creates no path for an unauthorized write to reach the network**, and
is treated below as non-blocking on that basis alone. It remains open and worth correcting on its
own merits, independent of Finding B.

### Finding B — Freshness / default-state (execution-boundary level)

`EligibilityGate.state` defaults to `CLAIMED`; `send()` reads that state via `check_write()` and
never itself refreshes it; no step in C4 §7 refreshes it either. C3 §6 item 2, already on the
signed record, states this directly: **"The gate is therefore fail-open until a real read moves
it, which matters for §D and §E... 'the eligibility gate is configured' and 'the eligibility gate
has been informed by the platform' are different states, and only the second one is worth
anything at execution time."**

**Direction of failure: fail-open.** This is not a diagnostic-quality problem. As C4 §7 is
currently written, a governed send under §E can execute against an `EligibilityGate` that has
never queried the platform in that session at all — permitted by a dataclass default, not by any
observation. This is the finding load-bearing to §D.

**A. and B. are independent.** Fixing A (propagating `status_code`/headers, distinguishing a
`401` from a genuine `pending_claim`) does not by itself force a fresh read before send — the
gate could still enter `send()` at its unread default with A fully fixed. Conversely, forcing a
fresh `check_eligibility()` call before every send would close B without touching A's
misdiagnosis exposure on failure. Treating them as one item, as TODO.md's tracker entry currently
does (see §4), risks a fix that addresses one and reports the other closed by association.

## 4. Precedent search

Every document below was checked. Documents ruled irrelevant are listed with the reason.

| Document | Checked | Relevant? | What it establishes |
|---|---|---|---|
| `TODO.md` | Full "M7 — §C / C3 parked items" section read | Partial | Tracks Findings A+B as one bullet ("item 1"), explicitly ties it to §D/§E, explicitly subordinates itself to the checklist: "Where the two appear to disagree, the checklist governs." A tracking record, not a governing instrument, and its merger of A+B is itself part of why a document that keeps them separate is needed. |
| `docs/m7_c1_live_captcha_wiring_plan_2026-08-13.md` (C1) | Section headers + relevant passages | No | Governs CAPTCHA response classification (§3.1–3.4, §9). No eligibility content. |
| `docs/m7_c1_wiring_plan_erratum_1_2026-08-17.md` | Read in full | Structural only | Not substantively relevant. Establishes the standalone-document convention (title, Status line, Subject/Raised lines, foot-of-document signature block) this ruling follows, since — like the erratum — it is not evidence for a pre-existing checklist row. |
| C2 (no dedicated artifact) | Checklist row 141 read | No | Evidence is row-only, citing `transport.py`/`test_moltbook_transport.py` at `ce84d22`. Concerns CAPTCHA verify wiring, not eligibility. Establishes only that row-only evidence is an accepted checklist shape — not the shape chosen here, since this finding needs a citable standalone record per the C1/C3/C4/C5 precedent for anything with its own reasoning to preserve. |
| `docs/m7_c3_endpoint_connectivity_validation_2026-08-21.md` (C3) | Read in full, including §6 | **Yes — controlling** | §6 items 1 and 2 are the origin of Findings A and B respectively. Item 2 names §D/§E and uses "fail-open" directly. The checklist row citing C3 (row for C3) elevates items 1 and 6 (rate-limit) to "material" in its own summary text but does not restate item 2's §D/§E relevance in that summary — the underlying artifact states it plainly, but a reader of the checklist row alone would not see it foregrounded. |
| `docs/m7_c4_first_post_runbook_2026-08-21.md` (C4) | Read in full, including §7 | **Yes** | §7's nine-step sequence is the exact location of the gap: explicit "immediately before send" rechecks exist for clean-tree (step 2) and kill switch (step 3, reinforced at step 7), none for eligibility. Shows the runbook's authors solved this problem class for one gate and did not extend it to the adjacent one. |
| `docs/m7_c5_published_outcome_correction_procedure_2026-08-27.md` (C5) | Read in full (from earlier session context) | No | Governs post-publication correction/withdrawal. No eligibility content. |
| `docs/m7_moltbook_transport_boundary_and_deployment_spec.md` | Full-text grep for "eligib"/"freshness"; Implementation Note A read in full (lines 731–777); §16 read in full (707–729) | **Yes** | Note A establishes the *semantic* meaning of `claimed`/`pending_claim` and explicitly disclaims constraint/kill-switch status ("not a governance violation... no Pi Script constraint evaluates it"). It states **no freshness or recency requirement anywhere** — confirmed by grep, zero hits for either term in the whole document. §16 lists eight categories requiring formal amendment; "execution boundaries" is a plausible candidate for whether this ruling's invariant, if accepted, must go through §16 rather than a non-binding note — addressed as an open question in §8, not resolved here. |
| `docs/m7_first_live_post_governed_envelope.md` (First-Post Rider) | Full-text grep for "eligib" | No hits | The rider's populated fields (`action_id`, `t3_grounding_reference`, `dry_run_rehearsal_reference`, `captcha_configuration_state`, `kill_switch_precheck`, `operator_go_reference`, `correction_procedure_reference`, `execution_commit_reference`) contain no eligibility-freshness field today. |
| `docs/m7_operator_go_checklist.md` | §D (160–225) read in full; preamble (1–46) read | **Yes — controlling for disposition** | §D's Requires table (5 rows) does not currently name eligibility in any form. The checklist's own status line is "DRAFT — pending operator review and sign-off" — unlike the transport spec, it has no §16-style formal-amendment lock of its own, so adding a row is not itself gated by a formal-amendment procedure. This is the eventual destination for a §D-scoped requirement, if accepted, but that edit is not made by this document. |
| `docs/m7_go1_decision_2026-08-10.md` | Read in full | Structural only | Confirms the standalone-decision-record convention and that such a record "is not a row in that checklist and does not add one" — the same posture this document takes. No eligibility content. |
| `docs/m7_identity_integrity_ruling.md` + addenda 1/2, `docs/m7_credential_integrity_ruling.md`, `docs/m7_cadence_integrity_ruling.md` + amendments 1/2, `docs/m7_citation_cluster_integrity_ruling.md`, `docs/m7_link_restriction_ruling.md` | Filenames enumerated; `credential_integrity_ruling.md` header read in full | No | These are Pi Script **constraint** rulings — required by `CLAUDE.md`'s spec-first rule for anything the resolver evaluates. Note A explicitly places the eligibility gate outside this category. Their naming convention (`m7_<topic>_ruling.md`, undated) is the wrong instrument class for this document, for the same reason — noted so the choice not to use it is visible, not silent. |
| `docs/moltbook_api_spec.md` | Grep for `/agents/status` | No (reference only) | Describes the actual API surface; not a governance document. Consistent with what C3 observed. Cited as supporting evidence only, never as a source of obligation. |
| `docs/pi_script_v01_draft3.md`, `docs/pi_script_v02_draft5.md`, `pi_script/pi_script.lark` | Full-text grep for "eligib"/"freshness" | No hits | Confirms this is not a grammar/9.x-series question — no Pi Script rule form is implicated. |
| GAP register | Grepped `docs/`, `TODO.md`, `README.md`, `CLAUDE.md` for "GAP", "GAP register", "GAP-\d" | **No instrument exists** | Continuum has no GAP register. (A `open_contract_gaps.md`-style instrument exists in a different project, WorldCraft Visuals — not part of this repository and not imported here.) The "GAP-register item" disposition named in the operator's request is therefore not an available option in this corpus, not merely unused. |
| `CLAUDE.md` | Read in full | Background only | Confirms "spec first, build second," the resolver-autonomy principle, and that the transport layer is explicitly "NOT a Pi Script constraint" — consistent with, and supporting, the ownership determination in §8. |

## 5. Does Finding B block GO-2?

**Determination: yes, pending operator acceptance of this document — Finding B is a GO-2-blocking
condition as the corpus currently stands.**

**Evidence supporting a blocking determination:**

- The corpus contains no step, anywhere, that requires a platform-informed eligibility
  observation before a governed send. `send()` does not obtain one; C4 §7 does not require one.
- C3 §6 item 2 already states, on the signed record, that this "matters for §D and §E" and uses
  the term "fail-open" — this is not a new characterization invented here, it is a restatement of
  an existing, if under-surfaced, finding.
- C3's own row explicitly disclaims standing for this purpose: it "does not attest that... the
  credential will still be valid at §E." No other document in the corpus makes that attestation
  either.
- The failure direction is permissive, not protective: the absence of a check does not block
  execution, it silently permits it. This is the opposite of the checklist's own stated design
  principle — "No item on this checklist may be marked complete from memory or general
  confidence" — applied here to a runtime state rather than a checklist row, but the same
  principle: an unread default is not evidence.

**Evidence that would make it non-blocking, and whether it exists:**

- A documented, enforced step — anywhere between GO-2 signature and network transmission — that
  performs a live `check_eligibility()` (or equivalent) on the exact instance executing `send()`,
  within a stated and operator-accepted freshness bound. **This does not exist in the current
  corpus.** C4 §7 was checked specifically for it and does not contain it.
- A documented argument that the gate's default-`CLAIMED` behavior is an intentional,
  operator-accepted design choice rather than an oversight (analogous to Note A's explicit
  "why no kill-switch trigger" reasoning for a different question). **No such argument exists
  anywhere in Note A or elsewhere** — Note A is silent on freshness in either direction; it
  neither requires it nor waives it.
- A standing argument that C3's single 2026-08-21 observation is sufficient because the interval
  to §E is short and claim status changes are rare. **This argument is not available on the
  record**: it would require exactly the kind of invented, unmeasured confidence threshold the
  checklist's own design forbids, and C3's row already forecloses it in its own words.

Because none of the three exists in the current corpus, the determination is that Finding B
blocks §D as things stand — not as an assumption carried in from the earlier chat triage, but as
the outcome of checking specifically for evidence against blocking and finding none.

**Finding A is not, by itself, GO-2-blocking**, per the fail-closed reasoning in §3. It remains
an open, recorded defect independent of this determination.

## 6. The invariant (stated, not implemented)

Contingent on operator acceptance, the governance requirement this document proposes is:

> **Before a governed send under checklist §E may proceed past `eligibility.check_write()` to a
> network write, the `EligibilityGate` instance that call reads MUST reflect a platform-informed
> observation — obtained by a live call to `check_eligibility()` or an equivalent platform read —
> taken on the same transport instance that will execute the send, within an operator-determined
> freshness bound of that send. A gate value that is merely the dataclass default, or that was
> set by an observation from a prior session or a different instance, does not satisfy this
> requirement, regardless of how recently that prior observation occurred.**

This invariant is scoped to **Finding B only**. It does not require Finding A's status/metadata
discard to be fixed as a precondition of satisfying it — a fresh `check_eligibility()` call made
immediately before send would satisfy this invariant even with Finding A unresolved, though
Finding A would remain open on its own separate track. The two findings' resolutions are not
sequenced against each other by this document.

**Deliberately not decided here:** the freshness bound's value; whether the observation is
obtained by a new explicit call, a changed default, a new C4 step, a new §D precondition, or a
transport-level change to `send()` itself; and whether any of those changes require a formal §16
amendment or fit within a non-binding implementation note. §8 states why these are left open.

## 7. The authorization boundary this document preserves

Three things are distinct, and no acceptance of this document collapses any of them into another:

1. **A fresh platform eligibility observation** — a fact, obtained by a network call, about
   whether the agent is currently claimed. This document proposes that one must exist,
   freshly, before §E. It is not itself permission for anything.
2. **A transport-level success/failure result** — `TransportResult`, `TransportOutcome`, the
   `EligibilityState` derived from (1). Even a `CLAIMED` result is a description of platform
   state, not an authorization.
3. **The authorization to execute the single-use GO-2 action** — the operator's own signed
   decision under checklist §D, binding one exact `action_id`/`payload_hash`/config/commit
   combination, expiring, single-use.

**A passing eligibility observation, and even a fully accepted and satisfied version of the
invariant at §6, does not authorize GO-2 transmission.** It would remove one obstacle to §D being
sought; it does not itself grant §D, and it does not touch §D's existing five Requires rows (full
suite green, rider population, payload/hash review, kill-switch confirmation, §C1–C5 complete),
none of which this document alters. GO-2 remains a separate, human, dated, signed decision under
the existing checklist process — this document does not shorten that process by one step.

## 8. Ownership / instrument determination

**This is a new, standalone ruling — not an amendment to C3, not a C-numbered artifact, not a
Pi Script constraint ruling, and not a GAP-register item (none exists in this repository).**

- **Not a C-artifact.** §C's five items are enumerated exhaustively in the checklist's own text
  ("all five must be complete before §D can be sought") and all five are closed and signed. This
  finding does not correspond to any of them; filing it as a sixth would silently expand a closed,
  signed list rather than add to the open one (§D), and this document does not do that.
- **Not an amendment to C3.** C3's header status is "EXECUTED... SIGNED," its own text states it
  "amends no numbered section" of anything, and the erratum precedent (§4 above) establishes that
  a signed document is corrected by a new standalone document, never reopened. C3 §6 item 2
  already explicitly deferred this to "its own ruling" — this document is that ruling, not an edit
  to C3.
- **Not a Pi Script constraint ruling.** Note A's own text places the eligibility gate outside
  Pi Script's evaluation entirely, and `CLAUDE.md`'s governance-boundary language is consistent
  with that. The undated `m7_<topic>_ruling.md` naming family belongs to that different
  instrument class; using it here would misclassify the finding.
- **Not a GAP-register item.** No such instrument exists anywhere in this repository's `docs/`,
  `TODO.md`, `README.md`, or `CLAUDE.md` (checked directly, §4). Nothing to file it under.
- **Open, and explicitly not resolved here:** whether accepting this ruling's invariant (§6)
  requires a **formal §16 amendment** to the transport spec. §16 requires formal amendment for
  changes affecting, among others, "execution authority," "transport responsibilities," and
  "execution boundaries." A requirement that `send()` must not proceed without a freshly-obtained
  platform fact is arguably a new necessary condition on the execution boundary — Note A
  established what the gate's states *mean*, not what must be true of the gate's *freshness*
  before it may be trusted, and the invariant at §6 would add exactly that. Equally arguably, it
  could be implemented as a non-binding clarification the way Note A itself was, if the operator
  judges it a refinement of an already-locked health-check responsibility (§5/§12) rather than a
  new category of restriction. **This document does not decide that question.** It is the
  operator's determination, and it is sequence-relevant: if §16 applies, the spec-track amendment
  would need to precede any checklist-track change citing it, mirroring how C1 had to settle
  semantics before C2 could implement them.
- **If accepted, the eventual checklist-track consequence** is a new row in §D's Requires table
  (which currently has none naming eligibility), citing this document or its accepted successor
  as Evidence — the same shape C1–C5 already established for §C. This document does not add that
  row.

## 9. Disposition

**This document is currently unsigned and has no governance effect.** Nothing in `moltbook/`,
`tests/`, the checklist, the transport spec, or `TODO.md` has been changed by drafting it, and
none should be until the operator records a disposition below.

If, and only if, the operator accepts §5's blocking determination and §6's invariant, the minimum
downstream actions — **none performed here** — would be:

1. An operator determination on §8's open question (whether §16 applies), made before any code or
   runbook change, since it determines which instrument governs the fix.
2. A resolution of Finding B satisfying §6's invariant, in whichever form the operator's §8
   determination permits — this document takes no position among the candidates it deliberately
   did not choose among in §6.
3. A new row added to checklist §D's Requires table citing whatever document records that
   resolution, following the C1–C5 evidentiary pattern.
4. Optionally, and separately, a resolution of Finding A (status/metadata propagation) on its own
   track — not sequenced against 1–3, since §6 established the two findings are independent.

None of 1–4 is authorized by this document. This document only establishes the finding, the
proposed invariant, and the instrument question — it does not perform, and should not be treated
as performing, any of them.

---

```
Status: DRAFT — awaiting operator disposition
Reviewed by (operator):
Reviewed at:
Disposition (select one, to be completed by operator, not by this document):
  [ ] Accepted as written — Finding B blocks §D; invariant at §6 stands; §8's §16 question
      remains open for a separate determination.
  [ ] Accepted with modification — operator states the modification.
  [ ] Rejected — operator states the reasoning; Finding B's blocking status reverts to
      undetermined, not to "non-blocking," absent a stated reason.
Statement:
```
