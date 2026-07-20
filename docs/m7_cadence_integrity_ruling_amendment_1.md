# Ruling Amendment 1: CadenceIntegrity — §5 grounding from the 7/19 cohort re-sample

**Status:** LOCKED — signed off 2026-07-19 (review round folded in: A1.6 single-sample
justification + T2/T3 falsification check; A1.4 documentation-only confirmation). Amends
`m7_cadence_integrity_ruling.md` (LOCKED 2026-07-17) under its §10 amendment rule.

**Grounding source:** first longitudinal cohort re-sample, 2026-07-19 (T0+3d), 8 profiles,
timing data and analysis recorded in
`Downloads/Moltbook_Longitudinal_Cohort_T1__2026-07-19.md` §2. Timestamps carry 1-second
display resolution (±1–2s quantization noise per interval).

---

## A1.1 What the re-sample showed

1. **The provisional parameters false-negative on the motivating fixture.** The observed
   flagship metronome (`neo_konsi_s2bw`, ~180s base period) exhibits occasional scheduler
   slips of 6–17 seconds (intervals of 187s, 192s, 197s between clean 180±2s stretches).
   Under N=5 consecutive / ±3s jitter with gap-reset, its longest qualifying run is 4 —
   the constraint as provisionally parameterized never fires on the exact pattern that
   motivated it.
2. **±3s is simultaneously not tight enough to be exclusive.** A Stratum-A account (`vina`)
   held 7 consecutive intervals within ±1.5s of a 180.5s period. Tightness does not buy
   discrimination.
3. **Scheduler-driven cadence is platform-universal.** Every cohort account across all three
   strata shows second-precision cron signatures (180s metronomes, a 30-min cron with ±5s
   slip, hourly slot alignment at :07:0x). Near-periodic timing therefore has ~zero power to
   distinguish legitimate from manipulative accounts on Moltbook.
4. **Burst-shaped posting is protected by N and gap-reset, not by jitter tightness.** The
   most organic-plausible pattern for the governed agent (short bursts of 3–4 posts minutes
   apart, bounded by long gaps — the `bytes` shape) never accumulates 5 consecutive
   qualifying intervals at ANY tolerance, because gaps break runs at ≤4.

## A1.2 Amended parameter values

| Parameter | Was (provisional) | Now | Status |
|---|---|---|---|
| Minimum posts before ready | 5 (4 intervals) | **unchanged** | Grounded (nothing contradicted it) |
| Consecutive intervals required (N) | 5 | **unchanged — 5** | Grounded (N, with gap-reset, is what protects burst posting; lowering N to 4 would fire on the bytes-shaped burst pattern) |
| Common period (P) | per-agent fitted | **unchanged** | Grounded (cohort periods span 180s to hour-multiples; a global P is untenable) |
| Jitter tolerance (±J) | ±3 seconds | **±5 seconds** | Grounded per §5's designated trigger (must sit above the ±1–2s timestamp quantization floor and absorb observed real-scheduler slip — max in-run deviation seen: 4.5s; catches the flagship's 7-interval run at fitted-P deviation 3.5s). Standing falsification check at T2/T3 — see A1.6 |
| Rolling window duration | 7 days | **unchanged** | Grounded (no cross-window pattern observed that a different window would have caught) |

Semantics reminder (unchanged): a run qualifies when the maximum deviation of each of N
consecutive intervals from the per-agent best-fit period P is ≤ J; a detector-recorded gap
resets the run.

Verified against the cohort dataset, N=5/±5s fires on the sustained metronomes
(`neo_konsi_s2bw`, `vina`, `Starfish`) and stays silent on burst posting (`bytes`), paired
posts (`diviner`), irregular heartbeats (`primefoxai`), and varying-multiple hourly slots
(`lyralink`).

## A1.3 Scope clarification (restating §1, sharpened by finding 3)

Because scheduler-driven cadence is the Moltbook norm, a CadenceIntegrity firing must never
be read — in any trace, README, or public claim — as evidence of manipulation. It is a
self-governance policy: the governed agent does not emit metronomic autonomous posting,
because that posting shape is the substrate coordinated manipulation rides on
(cadence + duplication + cross-citation together, per the T0/T1 cohort notes). Detection of
OTHER accounts' coordination remains v1.1/v2 scope.

## A1.4 Correction: §5 table false-positive / false-negative column contents

The locked §5 table's last two content columns were swapped in four of five rows: text
describing evasion (missed detection — a false-NEGATIVE surface) sat in the
"False-positive surface" column and vice versa. **This correction is documentation-only.**
The swapped columns are rationale prose; detection semantics live entirely in the parameter
values and §4 (N, J, per-agent P fit, gap-reset), none of which this correction touches. The
A1.2 verification claim (fires on 3 sustained metronomes, silent on the other 5 cohort
accounts) was computed directly from the T1 interval dataset, independent of this table, so
the correction changes no trigger outcome. This amendment's A1.2 supersedes the table; for
the record, the corrected assignments of the original text are:

| Parameter | False-positive surface (fires wrongly) | False-negative surface (fails to fire) |
|---|---|---|
| Minimum posts before ready | None (floor only delays detection) | A mechanical actor could operate briefly under the floor undetected |
| Consecutive intervals (N) | Legitimate bursty posters could theoretically hit N by chance — mitigated by jitter tolerance | An agent reverting to irregular posting every (N−1)th interval evades detection |
| Common period (P) | N/A | An adversary aware of the fit tolerance could deliberately jitter within it |
| Jitter tolerance (±J) | Too loose and a coincidentally regular poster could false-positive | Too tight and a slightly noisier scheduler evades detection *(this is finding 1, observed live)* |
| Rolling window duration | Reuse of the operational interval carries no firing risk | A pattern resetting exactly every 7 days could evade cross-window detection; slow, deliberately spaced manipulation is outside the window's reach (named non-goal) |

## A1.5 Noted for v1.1 (out of scope here)

Slot-phase alignment detection: `lyralink` posts at :07:07–:07:11 of the hour with varying
hour-multiple intervals — invisible to single-period fitting, trivially visible to a
phase-alignment check. Recorded as a candidate v1.1 detector extension, not part of this
amendment.

## A1.6 Why J locks on one sample while IdentityIntegrity's threshold waits for T2/T3

The sibling constraint's cross-session identity threshold is deliberately held open until the
+7d and +14d checkpoints; this amendment locks off the single 7/19 sample. The asymmetry is
principled, not an oversight:

1. **Each constraint follows its own locked spec.** CadenceIntegrity §5 states verbatim that
   every value is "provisional pending the 7/19 cohort re-sample" — the locked ruling
   designated this single re-sample as the grounding event. IdentityIntegrity's ruling (§5)
   equally explicitly deferred its cross-session threshold to the multi-checkpoint
   longitudinal read. Both sign-offs already chose their evidence bar; this amendment honors
   CadenceIntegrity's, and re-deciding it here would itself be a silent spec change.
2. **The measured quantities differ in kind.** Identity change-frequency is a rate per unit
   time: one 3-day diff yields a numerator over a single interval and is structurally
   insufficient regardless of cohort size. Cadence periodicity is a within-feed structural
   property: a single profile read yields ~19 interval measurements per account (~150 across
   the cohort) — a full per-account interval distribution captured in one visit. The
   longitudinal axis is what identity needs and cadence does not.
3. **Corroboration is free, so "grounded" carries a falsification check rather than blind
   confidence.** The T2 (~7/23) and T3 (~7/30) identity re-samples read the same profile
   pages; cadence intervals will be recaptured at zero marginal cost. Standing check: if
   either shows (a) a sustained metronome whose in-run slip exceeds ±5s such that the
   flagship pattern again escapes N=5, or (b) a burst-shaped account accumulating a
   qualifying run of 5, the grounding is contradicted and an Amendment 2 is triggered.
   Grounded means evidence-backed, not immune to revision.

## A1.7 Code impact once signed off

`moltbook/cadence.py` jitter constant ±3 → ±5 (one value; §8 test fixtures that encode ±3
update alongside). No entity, grammar, enforcement, or store changes. Suite must stay green.
