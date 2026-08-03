# Ruling Amendment 2: CadenceIntegrity — specification durability correction

**Status:** LOCKED — signed off 2026-08-03. Amends
`m7_cadence_integrity_ruling_amendment_1.md` (LOCKED 2026-07-19) under
`m7_cadence_integrity_ruling.md`'s (LOCKED 2026-07-17) §10 amendment rule.

**Trigger:** Amendment 1 A1.6 item 3's standing falsification check, executed against the T3
cohort re-sample.

**Grounding source:** fourth longitudinal cohort re-sample, 2026-08-02 (T0+17d; due ~07-30,
captured three days late and recorded as such), 8 profiles, timing data and analysis in
`Downloads/Moltbook_Longitudinal_Cohort_T3__2026-08-02.md` §2. Timestamps carry 1-second
display resolution (±1–2s quantization noise per interval).

**Scope, stated up front because it is unusually narrow:** this amendment corrects
**specification language only**. It changes no parameter, no detector behavior, no code, and no
test. It is a correction to how Amendment 1 was *written*, not to what the detector *does*.
Every account-name reference this amendment touches lives in Amendment 1; the base ruling
contains none and is untouched.

---

## A2.1 What T3 showed

1. **The detector was not found defective. A1.6 check (a) passed with margin.** The motivating
   flagship metronome (`neo_konsi_s2bw`) produced the cleanest window observed across all four
   reads: 19 intervals, **no detector-visible gaps anywhere in the 20-post feed**, values 180–188s,
   whole-run spread 8s ≤ 2J. Tightest 5-windows have spread 3s. It fires at N=5/±5s with room to
   spare, and would fire at ±3s in this particular window.

2. **A committed normative sentence became false.** Amendment 1 A1.2 states verbatim that
   N=5/±5s "stays silent on burst posting (`bytes`)". At T3, `bytes` produced a **gap-free run of
   11 intervals** (174–185s) in which **six of the seven** available 5-windows qualify; the
   tightest has spread 5s at P = 176.5. The sentence is now contradicted by observation.

3. **The account changed; the detector did not.** `bytes` no longer exhibits the burst shape
   A1.1 item 4 described (short bursts of 3–4 posts minutes apart bounded by long gaps). At T3 it
   is running a genuine ~178s metronome. The detector correctly identified real periodicity in an
   account whose posting behavior changed between T1 and T3.

4. **J is not the variable in play.** Two Stratum A accounts (`vina`, `bytes`) fire at T3, and
   **both fire at ±3s as well as ±5s** (tightest spreads 3s and 5s respectively; both ≤ 2×3s).
   Tightening J would not have prevented either firing. J does not separate the populations, so
   no evidence here bears on whether J is correctly set.

5. **Per-account classification is unstable across reads.** `vina` fired / did not / fired.
   `bytes` did not / did not / fired. `Starfish` fired / did not / did not, under **three
   different periods** across the four reads (30-minute cron at T1, hourly :40–:41 slot at T2,
   ~90-minute cadence at T3). A1.2's positive list has therefore gone stale in the same way its
   negative list did, in the opposite direction.

## A2.2 Root cause

The defect is not a wrong parameter. It is that **an empirical assumption was embedded inside a
normative rule.**

"Stays silent on burst posting (`bytes`)" parses as a claim about the detector, but its truth
value is controlled by a third party's future behavior. When the account evolved, the sentence
became false without anything about the detector changing. A normative clause whose truth is
controlled by an external party is not a durable specification.

This is a documentation-integrity problem with an audit consequence, and that consequence — not
the detector's behavior — is what makes an amendment necessary rather than optional. A reviewer
reading A1.2 alongside the T3 record finds the repository internally inconsistent on its face,
and can only be reconciled by being told that the committed text is not what was meant.
Requiring that explanation is precisely the ambiguity this project exists to eliminate. Leaving
the text uncorrected on the grounds that everyone currently understands the intent trades a
permanent, discoverable inconsistency for a temporary, undocumented convenience.

**Precision worth recording, because it explains why two competent readings diverged:** A1.6's
criterion (b) is written as *"a burst-shaped account accumulating a qualifying run of 5"* — it is
**already shape-based**. A1.2's verification sentence is **account-based**. Read on its own,
criterion (b) was arguably not met at T3, since `bytes` was no longer burst-shaped. Read together
with A1.2, which fixes `bytes` as the definition of burst shape, it plainly was. The two clauses
disagreed with each other about what the negative example *is*. This amendment resolves that
disagreement in favor of the shape-based form.

## A2.3 Drafting principle (normative, applies to all future amendments)

> Normative clauses SHALL be written against posting **shapes**, defined by their structural
> properties. Specific accounts MAY appear only as **dated historical grounding** for why a shape
> mattered — never as the living definition of the shape itself.

A named account in a specification is an observation with a timestamp, not a fixture. Cohort
accounts are third parties under no obligation to remain the example they were sampled as.

## A2.4 Corrections to Amendment 1's text

Amendment 1 is corrected as follows. Wording is normative; the surrounding structure, headings,
and all other content are unchanged.

**(1) A1.2 verification sentence — the falsified clause.** Replace:

> Verified against the cohort dataset, N=5/±5s fires on the sustained metronomes
> (`neo_konsi_s2bw`, `vina`, `Starfish`) and stays silent on burst posting (`bytes`), paired
> posts (`diviner`), irregular heartbeats (`primefoxai`), and varying-multiple hourly slots
> (`lyralink`).

with:

> N=5/±5s fires on **sustained metronomic shape** — a fitted period held across at least five
> consecutive gap-free intervals within tolerance — and remains silent on **burst shape**
> (clustered emission bounded by run-breaking gaps), **paired-post shape**, **irregular
> heartbeat shape**, and **varying-multiple slot shape** (a stable phase slot at differing period
> multiples, so no single fitted P accumulates).
>
> *Historical grounding (2026-07-19, T1 cohort):* these shapes were observed respectively in
> `neo_konsi_s2bw`/`vina`/`Starfish`; `bytes`; `diviner`; `primefoxai`; `lyralink`. These
> attributions are provenance for why each shape was specified and are **not** continuing tests
> of the parameters. Subsequent reads confirm they must not be so used: at T3 (2026-08-02)
> `bytes` had adopted metronomic shape and qualified, and `Starfish` had left metronomic shape
> and did not qualify, in both cases through a change in the account rather than the detector.

**(2) A1.1 item 4 — decouple the shape from the name.** In the clause reading "the most
organic-plausible pattern for the governed agent (short bursts of 3–4 posts minutes apart,
bounded by long gaps — the `bytes` shape)", replace "— the `bytes` shape" with "— burst shape, as
observed in `bytes` at T1 (2026-07-19)". The structural claim that burst shape never accumulates
five consecutive qualifying intervals at any tolerance, because gaps break runs at ≤4, is
**retained unchanged**: it remains true of the shape, and T3 does not contradict it. What T3
contradicts is only the permanent identification of that shape with that account.

**(3) A1.2 N-row rationale.** Replace "lowering N to 4 would fire on the bytes-shaped burst
pattern" with "lowering N to 4 would fire on burst shape".

**(4) A1.1 items 1 and 2 — retained, dated.** These are past-tense records of what the T1
re-sample showed and are already correctly framed as historical observation. Append "(observed
2026-07-19)" to each account reference for consistency with the principle. No substantive change.

**(5) A1.5 slot-phase note.** Append "(observed 2026-07-19; the same phase behavior was still
present at T2 and T3)" to the `lyralink` reference. This one is out of scope for the parameters
and is strengthened rather than weakened by later reads.

## A2.5 What this amendment explicitly does NOT change

Stated affirmatively so no future reader infers a detector fault from the existence of an
amendment:

| Item | Status |
|---|---|
| Jitter tolerance J (±5s) | **Unchanged.** A2.1 item 4 establishes that no T3 evidence bears on J's correctness — both firings occur at ±3s as well, so J is not producing the contradiction. Changing a parameter because the examples changed, rather than because the detector failed, would not be evidence-based. |
| Consecutive intervals N (5) | Unchanged |
| Per-agent fitted period P (midrange) | Unchanged |
| Rolling window (7 days) | Unchanged |
| Readiness minimum (4 intervals) | Unchanged |
| Gap-reset semantics | Unchanged |
| `moltbook/cadence.py` | **No change.** Detector behavior is not amended. |
| Tests / fixtures | **No change.** No fixture encodes the corrected prose. |
| Base ruling `m7_cadence_integrity_ruling.md` | **Untouched.** It contains no account-name references. |
| A1.3 self-governance framing | Unchanged, and reinforced — see A2.6 |

## A2.6 A1.3 reinforced by T3

A1.3 holds that a CadenceIntegrity firing must never be read — in any trace, README, or public
claim — as evidence of manipulation. T3 supplies the strongest quantitative support yet: **three
of the eight cohort accounts (`neo_konsi_s2bw`, `vina`, `bytes`) would fire this constraint
today, and only one of them is the coordinated-manipulation exemplar.** Cadence continues to have
approximately zero power to distinguish legitimate from manipulative accounts on this platform.
The constraint is self-governance about the governed agent's own posting shape, and nothing else.

## A2.7 Standing falsification check — status going forward

A1.6 item 3 designated the T2 and T3 re-samples as the falsification checks on the ±5s grounding.
**Both have now been executed and the standing check is discharged:** T2 (2026-07-22) produced no
contradiction; T3 (2026-08-02) produced the specification contradiction corrected here and no
detector contradiction. No further cohort read is scheduled.

Any future falsification check requires its own designation in its own amendment; this one does
not create a standing obligation. Note also that once the governed agent is live, the
operationally relevant cadence data is the agent's **own** observation store, not the cohort —
consistent with §1's self-governance scope.

## A2.8 Code impact once signed off

**None.** No source file, parameter, fixture, or test changes. The suite is expected to remain at
589 passed + 7 xfailed, unchanged, because nothing executable is touched. The deliverable is the
corrected text of `m7_cadence_integrity_ruling_amendment_1.md` plus this amendment as its record.

Once signed off and locked, Amendment 1 gains an "Amended: A1.1 item 4, A1.2, A1.5 superseded by
Amendment 2" pointer, following the pattern the base ruling used for Amendment 1.
