# Ruling: CitationClusterIntegrity

**Status:** LOCKED, signed off 2026-07-18. Second of the two Longitudinal Constraints —
inherits the persistent-state model, observation-sufficiency invariant, and pause_autonomy
enforcement mechanism established by CadenceIntegrity. The genuinely new idea here is graph
relationships with directional causal attribution.

**Numbering note:** No grammar change. One Form-2 equality_rule evaluation, gated by an
application-level readiness check — same shape as CadenceIntegrity.

## 1. Ruling

CitationClusterIntegrity is a self-governance constraint: it governs only the M7 agent's own
citation behavior, never another account's. It evaluates whether the governed agent's own
outbound citations materially contribute to closing or sustaining a small, tightly reciprocal,
low-external-degree cluster of accounts. Incoming citations to M7 — other accounts citing M7 —
are context only and can never independently establish a violation. It does not evaluate
content, does not evaluate intent, and does not classify or restrict any account other than
the governed agent.

## 2. Governed entity and state

```
entity MoltbookAgentProfile {
    // ... existing CadenceIntegrity fields unchanged ...

    citation_observation_ready:   boolean
    citation_cluster_flag:        boolean

    cluster_size:                 integer
    m7_outbound_edge_count:       integer
    reciprocal_edge_count:        integer
    external_edge_count:          integer
    rolling_window_start:         text   // shared window fields with CadenceIntegrity
    rolling_window_end:           text
}

constraint CitationClusterIntegrity {
    priority:     high
    rule:         MoltbookAgentProfile.citation_cluster_flag must equal false
    on_violation: escalate
}
```

Same grammar mapping as CadenceIntegrity: escalate is the Pi Script action. The required pause
is client-side profile state (`autonomous_posting_paused = true`), applied by the client when
an escalate originates from CitationClusterIntegrity. Emitting escalate without applying that
pause does not satisfy §7.

## 3. Observation sufficiency

Same invariant as CadenceIntegrity §3: insufficient data ≠ compliant.
`citation_observation_ready` becomes true only once the governed agent has a minimum number of
outbound citation edges recorded in the current rolling window (value in §5). While not ready,
`citation_cluster_flag` stays unset, not defaulted false — trace renders NOT EVALUABLE,
identical shape to CadenceIntegrity's trace.

## 4. Detection definition

- **Directional edges only.** The citation graph must never be collapsed to undirected edges
  before attribution is calculated. M7 → external account is attributable outbound conduct;
  external account → M7 is contextual evidence only, usable to compute reciprocity but never
  sufficient alone to set the flag.
- **Causal attribution requirement.** `citation_cluster_flag` may be set only when the
  governed agent has produced at least the minimum required outbound edges (§5) contributing
  to a detected closed structure. A cluster of external accounts citing each other, with M7
  merely mentioned by one of them, does not qualify — M7 must be a participant in closing or
  sustaining the loop, not a target of it.
- **Cluster shape, not magnitude.** This detects a small, tightly reciprocal,
  low-external-degree structure — a shape property — not a raw citation-count threshold.
  Citing other agents' work is common and legitimate.
- **Missing/duplicate observations.** Same idempotency-by-post-ID and gap-recording rules as
  CadenceIntegrity §4 — the citation store is built from the same underlying post ingestion
  pipeline, just extracting edges instead of timestamps.

## 5. Parameter grounding

Normative parameters require empirical grounding. Until representative observations exist,
parameter values remain undefined rather than estimated. This is a general Continuum
principle, not specific to this constraint — it will apply to every future longitudinal or
relational parameter the same way.

Applied here: M7 has not yet operated on Moltbook, so there is no fixture of M7's own outbound
citation behavior. The recon's pepper_pots/corra/pyclaw-successor cluster was observed
qualitatively from the outside, not measured with exact edge counts — it can motivate the
shape of detection (§4) but cannot ground a number.

| Parameter | Value | Status |
|---|---|---|
| Minimum outbound edges before ready | Undefined | No fixture of M7's own citation history exists yet |
| Minimum cluster size | Undefined (recon fixture suggests ~3, not precisely counted) | Requires actual observed edge counts, not estimation |
| Minimum reciprocal edges | Undefined | Requires the fixture's edges to be counted, not estimated |
| Maximum external-degree ratio | Undefined | Not yet grounded in any observation |
| Rolling window duration | 7 days | Locked — inherited directly from CadenceIntegrity §5, same cohort-cadence rationale, not independently re-derived |

Until the undefined parameters are grounded, `citation_observation_ready` cannot become true,
and CitationClusterIntegrity cannot fire — this is a safe default (no enforcement without
grounding), not a missing implementation. First real M7 citation activity on Moltbook is the
trigger for the ruling amendment that fills in these values.

## 6. Persistence requirements

Identical to CadenceIntegrity §6, applied to the citation edge store instead of the timestamp
store: survives restarts, idempotent by post ID, deterministically recomputable from stored
history, gaps recorded not inferred, clearing the flag doesn't erase the edge history, and the
same restart-interleave determinism guarantee (A,B,C ≡ A,restart,B,restart,C).

## 7. Enforcement

Identical to CadenceIntegrity §7: `on_violation: escalate` in-grammar.
`autonomous_posting_paused = true` is the client-side consequence, applied when escalate
originates from CitationClusterIntegrity. Applies to all outbound channels (posts, comments,
DMs). Does not block read-only observation. Explicit human-authorized sends remain possible
while paused. Persists across process restarts. Cleared only through explicit human
review/reset. Reset clears the pause and `citation_cluster_flag` but never the underlying edge
history. Never suppresses or retracts previously emitted content — governs only future
autonomous behavior.

## 8. Required tests

Same base shape as CadenceIntegrity §8: positive fixture, negative fixture, insufficient-data
case (NOT EVALUABLE), restart persistence, duplicate ingestion, expired-window behavior, pause
persistence and explicit clearing, restart-interleave determinism.

Plus two tests specific to the directional-graph logic:

- **Guilt-by-association test** (the most important test in this set): external accounts
  forming a tight reciprocal cluster that cites M7 repeatedly, with zero M7-outbound edges →
  must stay clean, `citation_cluster_flag` never sets.
- **One-directional evasion test** (documents a known gap, does not fix it): M7 repeatedly
  cited by a cluster it never reciprocates toward → confirm this correctly stays clean per the
  ruling's own scope, not a bug.

## 9. Known gaps and non-goals

- No detection of one-directional citation-seeding (M7 citing others without reciprocation) —
  the causal-attribution requirement means this cannot trigger the flag even if it's part of a
  coordinated pattern. Real, named gap.
- No engagement-metric correlation. No content-based manipulation detection. No cross-window
  pattern detection (inherited non-goals from CadenceIntegrity).
- This is the reusable foundation for LinkRestriction's deferred coordinated-link-seeding
  piece, if and when that gets built — not built now.
- Graph infrastructure (a shared store across multiple graph-based constraints) is explicitly
  not built here. CitationClusterIntegrity owns its own edge list. Generalizing to shared
  graph infrastructure is deferred until a second real graph-based constraint has its own
  locked ruling — not built speculatively for hypothetical future constraints.

## 10. Amendment rule

Identical to CadenceIntegrity §10: any parameter change requires a ruling amendment. Given
§5's parameters are largely undefined rather than provisional, this ruling requires at least
one substantive amendment before `citation_observation_ready` can ever become true — that's
expected, not a drafting gap.
