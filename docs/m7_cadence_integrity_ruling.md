# Ruling: CadenceIntegrity

**Status:** LOCKED, signed off 2026-07-17. First of the two Longitudinal Constraints —
establishes the persistent-state governance model that CitationClusterIntegrity will inherit.
**Amended:** §5 is superseded by Amendment 1 (LOCKED 2026-07-19,
`m7_cadence_integrity_ruling_amendment_1.md`) — J widened ±3s→±5s, other values grounded
unchanged, FP/FN column contents corrected. Read §5 below through that amendment.

**Numbering note:** No grammar change. One Form-2 equality_rule evaluation, gated by an
application-level readiness check (not a separate Pi Script constraint) — application-level
M7 ruling, same as the other four.

## 1. Ruling

CadenceIntegrity is a self-governance constraint: it governs only the M7 agent's own posting
behavior, never another account's. It evaluates whether the governed agent's observed posting
cadence satisfies one mechanically defined structural pattern — near-exact periodic post
timing. It does not evaluate content, does not evaluate intent, and does not evaluate any
account other than the governed agent. It never suppresses or retracts previously emitted
content; it governs only future autonomous behavior.

## 2. Governed entity and state

```
entity MoltbookAgentProfile {
    agent_id:                    identifier   // the governed M7 agent only

    cadence_observation_ready:   boolean
    cadence_anomaly:             boolean

    observed_interval_count:     integer
    common_period_seconds:       number
    max_jitter_seconds:          number
    rolling_window_start:        timestamp
    rolling_window_end:          timestamp
}

constraint CadenceIntegrity {
    priority:     high
    rule:         MoltbookAgentProfile.cadence_anomaly must equal false
    on_violation: pause_autonomy + escalate
}
```

There is no CadenceObservationGate constraint. Readiness is an application-level gate: the
resolver evaluates CadenceIntegrity's rule only when `cadence_observation_ready = true`. When
not ready, the trace renders NOT EVALUABLE directly from that gate, not from a Pi Script
constraint reporting a non-violation. This keeps "can this be evaluated" and "was this
violated" as categorically separate questions.

## 3. Observation sufficiency

- **Minimum observations:** `cadence_observation_ready` becomes true only once at least
  5 posts (4 intervals) from the governed agent have been recorded in the current rolling
  window.
- **Warm-up behavior:** while `cadence_observation_ready = false`, `cadence_anomaly` is not
  evaluated and must not be set to either value — it stays in an explicit unset/null state,
  not defaulted to false. Insufficient data ≠ compliant.
- **Trace semantics:**

```
CONSTRAINT: CadenceIntegrity
Observation readiness : false
Evaluation             : insufficient post history (2/4 required intervals)
Result                 : NOT EVALUABLE
Action                 : none
```

## 4. Detection definition

- **Timestamp normalization:** all post timestamps normalized to UTC at ingestion.
- **Interval construction:** consecutive-post intervals only, within the current rolling
  window. Gaps from missing/undetected posts are not silently bridged.
- **Periodicity calculation:** a definitional tolerance — "N consecutive intervals each
  within ±J seconds of a common period P constitutes the near-periodic pattern" (a mechanical
  fit, not a population-normality claim).
- **Missing observations:** a detector-recorded gap resets the consecutive-interval count
  rather than counting for or against the pattern.
- **Duplicate observations:** ingestion is idempotent by post ID.

## 5. Parameter-provenance table

| Parameter | Value | Grounding | Rationale | False-positive surface | False-negative surface | Status |
|---|---|---|---|---|---|---|
| Minimum posts before ready | 5 (4 intervals) | Baseline pass observed the pattern across many more than 4 posts | Below 4 intervals, "regular" and "coincidental" aren't distinguishable | A mechanical actor could operate briefly under the floor undetected | None (floor only delays detection) | Provisional |
| Consecutive intervals required (N) | 5 | Matches depth of the fixture observed in the baseline pass | Requires a sustained pattern, not a coincidental run | An agent reverting to irregular posting every 4th interval evades detection | Legitimate bursty posters could theoretically hit 5 by chance — mitigated by jitter tolerance | Provisional — confirm against 7/19 cohort re-sample |
| Common period (P) | Not fixed — detector fits best-matching period per agent | Observed ~3-minute spacing is one instance, not a universal constant | A fixed global period would miss other cadence-based actors; per-agent fit generalizes the pattern shape | N/A | An adversary aware of the fit tolerance could deliberately jitter within it | Provisional |
| Jitter tolerance (±J seconds) | ±3 seconds | Matches "near-exact" language from the baseline pass | Tight enough that organic human-paced posting won't false-positive | Too tight and a slightly noisier scheduler evades detection | Too loose and a coincidentally regular poster could false-positive | Provisional — needs real second observation |
| Rolling window duration | 7 days | Matches the cohort re-sample cadence already established | Reuses an interval already operationally committed to | A pattern resetting exactly every 7 days could evade cross-window detection | Slow, deliberately spaced manipulation is outside this window's reach — named non-goal | Provisional |

Every value above is provisional pending the 7/19 cohort re-sample. Locking any of them is a
ruling amendment (§10), not a code change.

## 6. Persistence requirements

- Observations survive process and session restarts.
- Ingestion is idempotent by post ID.
- Timestamps normalized to UTC at ingestion, never re-normalized differently downstream.
- Rolling window expiration: observations age out of the interval calculation but are not
  deleted from the underlying observation store.
- Gaps in observation are explicitly recorded, not inferred.
- MoltbookAgentProfile state is deterministically recomputable from stored observation
  history.
- Clearing `cadence_anomaly` via human review does not erase the observation history that
  produced it.
- Detector execution order under interleaved restarts must not change resulting profile
  state — A,B,C and A,restart,B,restart,C must produce identical MoltbookAgentProfile state.

## 7. Enforcement

- `on_violation: pause_autonomy + escalate` — a new action distinct from freeze.
- `autonomous_posting_paused = true` semantics: applies to posts, comments, and DMs initiated
  autonomously; does not block read-only observation; explicit human-authorized sends remain
  possible while paused; persists across process restarts; cleared only through explicit
  human review/reset; reset clears the pause and `cadence_anomaly` but never the underlying
  observation history.
- CadenceIntegrity never suppresses or retracts previously emitted content — it governs only
  future autonomous behavior (repeated from §1 as a binding enforcement boundary, not just
  descriptive framing).

## 8. Required tests

- Positive fixture: synthetic sequence matching the observed near-periodic pattern →
  `cadence_anomaly = true`, pause_autonomy + escalate fires.
- Negative fixture, irregular spacing → stays clean.
- Negative fixture, frequent-but-irregular → stays clean (frequency and regularity
  decoupled).
- Insufficient-data case → `cadence_observation_ready = false`, trace renders NOT EVALUABLE,
  never silently clean.
- Restart persistence: observation history and profile state survive a simulated restart.
- Duplicate ingestion: re-ingesting the same post ID does not alter interval count.
- Expired-window behavior: an old near-periodic run aged out of the rolling window no longer
  contributes.
- Pause persistence and explicit clearing: survives restart, only clears via reset,
  read-only/human-authorized-send behavior verified during pause.
- Restart-interleave determinism: interleave restarts between every observation in the
  positive fixture; assert identical final profile state to the non-interleaved run.

## 9. Known gaps and non-goals

- No detection of manipulation via content, only timing.
- No cross-window pattern detection (an actor regular within each 7-day window but varying
  window-to-window evades this).
- No engagement-metric correlation.
- Parameter values fixture-grounded from a single observed account, pending broader cohort
  validation.
- Explicit boundary: this constraint governs only future autonomous posting behavior — it
  has no mechanism for, and must never be extended to, suppressing or retracting content
  already posted.

## 10. Amendment rule

Any change to a §5 parameter value — minimum posts, consecutive-interval count, jitter
tolerance, or window duration — requires a ruling amendment, not a silent code change. The
cohort re-sample data is expected to trigger at least one such amendment.

---

## Post-lock grammar correction (2026-07-17)

**Classification:** post-lock grammar correction — fixes an invalid representation of the
approved design. It does not reopen §3–§9 substance and does not require a new sign-off
cycle.

The §2 block as originally locked does not parse under the shipped Pi Script v0.2 grammar:
`pause_autonomy` is not in the closed action set (`pi_script.lark` `ACTION_KW: flag | warn |
escalate | freeze | rollback`), and `timestamp` / `number` are not state types
(`STATE_TYPE_KW: integer | boolean | text | identifier`). Consistent with this ruling's own
numbering note ("No grammar change"), the approved design is represented in the existing
grammar as follows:

- **Action:** the shipped constraint declares `on_violation: escalate`. `pause_autonomy` is
  implemented as client-side profile state (`autonomous_posting_paused = true`), applied by
  the moltbook client when the resolver reports a CadenceIntegrity violation — the same
  prevention-is-client-side pattern as the M7 pre-send gates. The resolver trace renders
  `system_state: escalated`, which remains distinct from `frozen` as §7 requires. Emitting
  escalate without applying the required client-side pause does not satisfy §7.
- **Field types:** `rolling_window_start` / `rolling_window_end` → `text` (ISO-8601 UTC);
  `common_period_seconds` / `max_jitter_seconds` → `integer` (whole seconds).

All §7 pause semantics (persistence, human-only clearing, autonomous-send scope, the
non-suppression boundary) are unchanged.
