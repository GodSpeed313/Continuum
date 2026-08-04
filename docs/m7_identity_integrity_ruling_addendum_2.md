# M7 Ruling Addendum 2 — IdentityIntegrity cross-session change-rate: longitudinal grounding, and the deferral of v1.1

**Status:** LOCKED — signed off 2026-08-04. A documentation act: it records grounding, adopts no
enforcement threshold, and changes no code, test, or fixture (see B7).

**Amends:** `docs/m7_identity_integrity_ruling.md` §5 ("The explicit gap — cross-session
change-rate (deferred, not solved)"), which states the gap is revisited "as IdentityIntegrity v1.1
once the cohort data lands." The cohort data has landed. This addendum records it, states what it
does and does not establish, and rules on whether v1.1 is a prerequisite for GO-1.

**Section numbering:** Addendum 1 used `A1`–`A6`. This addendum uses `B1`–`B7` so that references
within the IdentityIntegrity ruling family stay unambiguous. It does not use the cadence family's
`A2.x` convention, which belongs to a different ruling.

**What this addendum does NOT do:** it does not adopt an enforcement threshold, does not change
detector behavior, does not change the constraint definition, and does not change any code, test,
or fixture. See B7.

---

## B1 — The observation

Four passive reads of a fixed 8-profile cohort, `moltbook.com/u/<handle>`, no login and no
interaction on any read:

| read | date | interval | identity-stable fields changed |
|---|---|---|---|
| T0 | 2026-07-16 | baseline | — (baseline captured) |
| T1 | 2026-07-19 | T0+3d | 0 of 8 |
| T2 | 2026-07-22 | T0+6d (one day early; recorded as +6d) | 0 of 8 |
| T3 | 2026-08-02 | T0+17d (three days late; recorded as +17d) | 0 of 8 |

The six identity-stable fields fixed by the T0 protocol: `bio`, `handle`, `avatar`, `verified`,
`human_owner`, `join_date`. Volatile metrics (`karma`, `followers`, `following`, `online`) were
excluded from the diff by the same protocol and moved constantly throughout, as expected.

**Result: 0 of 8 profiles changed any of the six defined identity-stable fields, across four
independent reads spanning 2026-07-16 to 2026-08-02.**

Exposure is 8 profiles × 17 days = **136 profile-days with 0 observed identity changes**. By the
rule of three, the 95% upper bound on the underlying rate is 3/136 ≈ **0.022 changes per
profile-day** — fewer than roughly one identity change per profile per 45 days.

Cohort composition (three strata, karma spanning three orders of magnitude by design):
Stratum A crafted/high-karma — `vina`, `bytes`, `diviner`, `Starfish`; Stratum B
manufactured-authority/coordinated — `neo_konsi_s2bw`, `pepper_pots`, `primefoxai`; Stratum C —
`lyralink`. Every profile's `bio` was verbatim-unchanged at every read, and no `handle`,
`avatar`, `verified`, `human_owner`, or `join_date` value moved at any read.

## B2 — What the observation does not establish

Three limits, each independently sufficient to block promotion of this observation into an
enforcement rule.

**(a) There is no positive example of a legitimate cross-session identity change.** Four reads of
zero cannot distinguish "legitimate agents change identity rarely" from "legitimate agents never
change identity on this platform," and they say nothing about what a legitimate change would look
like if one occurred.

**(b) The false-positive rate of any detector tuned to this data is therefore unmeasured — not
measured-and-low.** This matters specifically because IdentityIntegrity carries
`on_violation: freeze + escalate`. The base ruling §6 narrowing is explicit that detection
confidence and enforcement severity must move together; an unmeasured false-positive rate is not a
high-confidence one.

**(c) The identity-stable field set is not closed.** At T3, three of eight profiles
(`vina`, `bytes`, `diviner` — the three highest-karma Stratum A accounts) displayed platform
badges/titles that did not exist in the T0 taxonomy. The six defined fields were unchanged, so the
0/8 result stands exactly as recorded. But **had badges been inside the identity-stable set, this
read would have scored 3/8 "identity drift" from a platform-side schema change that no agent
initiated.**

**Boundary statement, carried verbatim from the T3 capture (§1a) and binding on this addendum:**

> "0 observed events" and "threshold validated" are not equivalent, and this document asserts
> only the first. What has been established empirically is: *under this observation window, no
> identity-field change was observed.* Selecting a threshold from that observation — including
> the intuitive "any cross-session change is high-signal" — is a **governance decision**, not an
> empirical result. The observation bounds legitimate churn from above and is admissible as
> evidence for such a decision; it does not make the decision, and no addendum should describe
> the resulting threshold as validated, confirmed, or grounded-by-measurement on this basis.

## B3 — The architectural position (verified against shipped code)

There is no cross-session identity comparison mechanism in the system today, and this is by design
rather than by omission.

- `MoltbookClient` receives `declared_handle` / `declared_name` / `declared_roles` at construction
  (`moltbook/client.py:97-99`, stored at `:126-128`) and passes them to the detector per scan
  (`:204-206`). The baseline is whatever the constructor was handed, for the life of that client.
- `declared_handle` is fail-closed at construction (`:109-111`, Addendum 1 §A1): a client without a
  baseline does not construct.
- A repository-wide search for cross-session identity comparison logic in `moltbook/` and
  `pi_script/` returns no such mechanism.
- The base ruling §2 states the intent directly: "a human owner legitimately reconfiguring the
  agent between deployments — **a fresh session start is a legitimate reset point, not a
  violation.**"

Therefore IdentityIntegrity v1.1 is **new detection code plus its own ruling**, not a number
dropped into an existing evaluation path. This is the material fact that distinguishes the two
readings of the GO checklist and TODO.md resolved in B5.

## B4 — Ruling: the §5 grounding record is complete; no threshold is adopted

1. **The §5 grounding input is delivered.** §5 deferred the cross-session question pending "the
   longitudinal cohort read (now pinned and running)." That read is complete: four reads, closed at
   T3, no further cohort read scheduled. B1 is the grounding record §5 was waiting for, and it is
   committed to `docs/` rather than left in session memory.

2. **No enforcement threshold is adopted by this addendum.** The candidate posture suggested by the
   data — *any agent-initiated change to a versioned identity-stable field set is high-signal* — is
   **grounded** in the sense that it is derived from real T0–T3 observation and bounded by it from
   above. It is **not validated for enforcement**, for each of the three reasons in B2. This
   addendum records the grounding and explicitly declines to convert it into a rule.

3. **Cross-session identity change remains a non-violation in v1**, exactly as §5 states. §5's gap
   is not closed by this addendum; it is documented, bounded, and carried forward with named
   preconditions.

## B5 — Ruling: v1.1 is post-GO work, and the GO checklist is the single authoritative readiness document

**The conflict being resolved.** Two committed documents disagreed on the definition of done:

- `docs/m7_operator_go_checklist.md` §A1 row 2 requires the threshold "grounded from real T1/T2/T3
  data (no invented number — mirrors §14.1/§14.2's discipline)" — a **documentation act**.
- `TODO.md` listed "IdentityIntegrity v1.1 cross-session change-rate threshold — blocked on T2/T3
  data" under **"M7 — remaining before/at live deployment"** — implying **shipped code**.

For a governance framework, contradictory source-of-truth documents are themselves a governance
defect, independent of which answer is correct.

**Ruling.** IdentityIntegrity v1.1 is **not a prerequisite for GO-1**. It is a post-GO governance
milestone requiring its own ruling.

**Why.** Continuum's working order is *ruling → evidence → implementation*, never
*implementation → hope the evidence supports it later*. Requiring v1.1 implementation before GO-1
would invert that order: it would ship cross-session enforcement code whose threshold B2 states
cannot be called validated, and whose field-set membership question (B2c) is not yet designed.
GO-1 is scoped to the currently governed system. IdentityIntegrity today governs declared identity
**within** a session; cross-session identity is an **extension** of the governance model, not a
precondition for demonstrating that the existing governed architecture works.

**Preconditions for IdentityIntegrity v1.1.** Before any cross-session threshold is enforced, v1.1
must:

1. **Version field-set membership explicitly.** A newly appearing profile field defaults to
   **NOT EVALUABLE**, never to "changed" (B2c). A cross-session detector must distinguish
   agent-initiated mutation from platform-initiated field addition, or its first live
   false-positive will be a platform release note.
2. **Collect positive examples.** At least one observed legitimate cross-session identity change,
   so the detector is designed against a real event rather than against the absence of events.
3. **Characterize the false-positive rate** rather than assuming it from zero-event data (B2b) —
   required by §6's confidence-paired-to-severity discipline, given `freeze + escalate`.
4. **Carry its own implementation ruling**, spec-first per `CLAUDE.md`, covering the detection
   mechanism, the reset semantics that currently make a fresh session a legitimate baseline
   (§2), and the threshold selection as an explicit governance decision.

**Single source of truth.** `TODO.md` is amended in the same change that records this addendum, to
remove the implication that GO-1 is blocked on v1.1 implementation and to restate v1.1 as a post-GO
milestone under the preconditions above. **`docs/m7_operator_go_checklist.md` is the authoritative
document defining GO readiness.** Where any other document appears to state a readiness
precondition, the checklist governs.

## B6 — Provenance of the underlying captures

The four capture files —
`Moltbook_Longitudinal_Cohort_T0__2026-07-16.md`,
`..._T1__2026-07-19.md`,
`..._T2__2026-07-22.md`,
`..._T3__2026-08-02.md` —
were held outside this repository at the time of writing, in the operator's local `Downloads`
directory, and are not under version control.

B1 and B2 therefore reproduce the identity findings in full — cohort, field set, per-read result,
exposure, the rule-of-three bound, the badge method finding, and the boundary statement verbatim —
so that the evidence chain for the identity dimension survives inside the repository independently
of those files. Archiving the raw captures themselves (or an equivalent archival mechanism) remains
an open provenance item; it is not a precondition for this addendum, whose factual content is
self-contained.

## B7 — What does not change

Stated affirmatively so that no future reader infers a defect from the existence of this addendum:

| unchanged | note |
|---|---|
| The constraint definition (§4) | `MoltbookSession.identity_drift must equal false`, `priority: high`, `on_violation: freeze + escalate` |
| Within-session detection behavior (§6, §7) | mechanical contradiction only; no change to capture, comparison, or firing |
| Addendum 1 §A1–§A6 | all six remain in force as written |
| `moltbook/client.py`, `moltbook/detector.py` | no code change |
| Tests and fixtures | none added, removed, or modified |
| Suite result | 589 passed + 7 xfailed, unchanged |
| Base ruling §5's status | the gap remains open and named; this addendum documents and bounds it, and does not close it |

This addendum is a documentation act. It records evidence, resolves a documentary contradiction,
and defers an implementation. It corrects no detector fault, because none was found.

---

## Sign-off checklist

- [x] B1 — the observation as recorded (0/8 across four reads, 136 profile-days, 0.022/profile-day upper bound)
- [x] B2 — the three limits and the verbatim boundary statement
- [x] B3 — architectural position: no cross-session mechanism exists; v1.1 is new code plus a ruling
- [x] B4 — §5 grounding record complete; no enforcement threshold adopted
- [x] B5 — v1.1 is post-GO; four preconditions; checklist is the single authoritative readiness document
- [x] B6 — capture provenance and why the findings are reproduced here in full
- [x] B7 — affirmative statement of what does not change

Signed off 2026-08-04, as drafted.

**Consistency pass performed before lock.** `docs/`, `README.md`, `CLAUDE.md`, `.claude/skills/`,
`moltbook/*.pi`, and the test suite were searched for any remaining statement implying that v1.1 is
required before GO-1, that a cross-session threshold has been validated, or that one exists. One
was found and corrected in the same change: `docs/m7_first_live_post_governed_envelope.md`'s
`t3_grounding_reference` field described T3 as having "grounded the IdentityIntegrity cross-session
change-rate threshold (TODO.md open item)" and sourced it to a session artifact held outside the
repository. It now points to this addendum and to `m7_cadence_integrity_ruling_amendment_2.md`
§A2.7, and states that no enforcement threshold was adopted.

`m7_cadence_integrity_ruling_amendment_1.md` §A1.6 was reviewed and **deliberately left unchanged**:
its statement that "the sibling constraint's cross-session identity threshold is deliberately held
open until the +7d and +14d checkpoints" is dated reasoning explaining why J locked on a single
sample. Those checkpoints have now passed and the threshold remains held open, so the passage is
stale in timing but asserts nothing false, and it never claims a threshold resulted. Editing it
would rewrite the record of what was reasoned at the time rather than correct a contradiction.
