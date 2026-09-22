# M7 — GO-2 Decision Record (First Governed Transmission Authorization)

**Status: DRAFT — NOT SIGNED. GO-2 is NOT granted.** This record stages the objective,
independently-verifiable portions of the GO-2 package required by
`docs/m7_operator_go_checklist.md` §D. It is produced for operator review and does not authorize
anything by its own existence. Several fields required by §D and by the First-Post Rider
(`docs/m7_first_live_post_governed_envelope.md` §2) cannot be populated yet — see §3 below — and
this record does not paper over that gap. `Authorized by (operator)` and `Authorized at` are left
blank and are not to be filled by anyone other than the accountable human, per the checklist
header's rule that `Verified by`/authorization fields may never be filled by an automated agent.

This record amends no numbered section of `docs/m7_operator_go_checklist.md`, of
`docs/m7_moltbook_transport_boundary_and_deployment_spec.md`, or of any ruling in `docs/`. It
stages one decision's supporting evidence; it does not make the decision.

---

## 1. Execution candidate — fixed, subject to §D's own conditions

```
execution_candidate_commit:      71910459a03cf5b7baf9b94e6063222a6c8a840e (7191045)
                                  — postdates C1 (8a...13...), C2 (ce84d22), C3 (2026-08-21
                                  artifact), C4 (52a8c9c / c36161b), and C5 (b559882), all
                                  Complete per docs/m7_operator_go_checklist.md §C rows.

test_result:
  passed:                        647
  xfailed:                       7
  failed:                        0
  errors:                        0
  xpass:                         0
  xfail_census_reference:        TODO.md, "### xfail census (7 — deliberate known-gap pins, not
                                  failures)" (lines 275–279) — all 7 observed xfails match this
                                  census by name and category; none added, removed, or changed.

tree_state:                      clean before and after the run — `git status --short` empty at
                                  both checkpoints; `git clean -ndx` shows only gitignored
                                  artifacts (__pycache__/, .pytest_cache/, .env, .claude/,
                                  .letta/), none inside a governed execution path.

Command:                         python -m pytest -q -rx (base form matches the CI-authoritative
                                  command at .github/workflows/tests.yml:17)
Environment:                     Python 3.12.10, pytest 9.0.3, Windows — see §4 for the CI
                                  Python-version discrepancy and its disposition.
Run performed:                   2026-09-18, this session, directly on the named commit.
```

This section fixes `7191045` as the execution candidate **for the purpose of this draft package
only**. Per §D's own text, `execution_candidate_commit` must postdate C1–C5 (satisfied) and the
full suite must be green with a clean tree (satisfied, verified directly). Fixing it here does not
authorize execution; per §3 below, several other §D preconditions remain unmet regardless of this
commit being sound.

**Note on `main`'s advancement since this fixation.** `main` has since advanced from `7191045` to
`3d71fa5` via PR #87 ("Adopt M7 D.5 single-use transmission gate"). PR #87 changed only
`.gitignore` and `docs/m7_operator_go_checklist.md` — no governed code (`moltbook/transport.py` or
any other implementation file) was modified. `7191045`'s fixation above is therefore not being
silently represented as the current `main` tip; it remains the execution candidate this record was
drafted and verified against, and its code is unchanged relative to `main` today. This note does
not re-authorize, re-test, or replace the execution candidate — any such change remains a separate
act.

---

## 2. §D requires-table — objective status, not a signature

This section reports the status of each of §D's five requirement rows as objectively observable
today. It is evidence for operator review, not a completion of those rows in
`docs/m7_operator_go_checklist.md` — no edit has been made to that file's §D table by this record.

| Item | Objectively observed status |
|---|---|
| §C1–C5 all complete, each with recorded evidence | **Satisfied.** All five rows read `Complete` in `docs/m7_operator_go_checklist.md` (lines 140–144), each with a dated evidence artifact. |
| Full suite green at `execution_candidate_commit`; clean tree | **Satisfied at `7191045`.** See §1. |
| First-Post Rider fully populated | **Not satisfied.** Three of eight required fields cannot be populated today: `dry_run_rehearsal_reference` (no exact payload exists to rehearse — §3.1), `execution_commit_reference` (points to this record's own `execution_candidate_commit`, fixable once this record is otherwise complete), and `operator_go_reference` (points to this record itself, which is unsigned). `captcha_configuration_state` and `kill_switch_precheck` are runtime-only facts that cannot be honestly attested before a live send session exists (§3.2, §3.3). See §5 for the full field-by-field matrix. |
| Exact payload and its `payload_hash` reviewed and approved by the operator | **Not satisfied — blocking.** No exact first-live-post payload exists anywhere in this repository. See §3.1. |
| `KillSwitch.engaged` confirmed `False` at review time | **Not meaningfully observable today.** `moltbook.transport.KillSwitch` has no persisted or global instance in this repository — every instantiation (production and test) is a fresh in-memory object defaulting to `engaged = False`. There is no standing live-session `KillSwitch` object to query "at review time" because no live-deployment runner has been built yet. See §3.3. |

---

## 3. Blocking dependencies

### 3.1 No exact payload exists

Searched `docs/`, `moltbook/`, and this repository generally for a drafted or approved literal
first-post payload. None exists. `docs/m7_go1_decision_2026-08-10.md` §5 item 4 states this
plainly: "§A4's representativeness test was shape and `action_type` only. The actual wording is
bound at GO-2 via `payload_hash`" — i.e., GO-2 was always the point where real content would first
appear, and it has not yet.

This blocks, directly or indirectly:
- `authorized_payload_hash` (§D template) — `canonical_payload_hash()` (`moltbook/transport.py:49–53`)
  hashes the actual payload dict; there is nothing to hash.
- `authorized_action_id` — per `ActionEnvelope.approve()` (`moltbook/transport.py:66–93`), an
  `action_id` is generated by the approval side at the moment a real envelope is approved over a
  real payload; generating one now, over no payload, would not identify anything real.
- The First-Post Rider's `dry_run_rehearsal_reference` (§3.2 below).
- The First-Post Rider's `execution_commit_reference`, which points at the execution candidate
  bound to a specific `action_id`/`payload_hash` pair that doesn't yet exist.

**This is the root blocker.** Nothing downstream of it can be honestly finalized.

### 3.2 Exact-payload Dry Run cannot be performed — and was not attempted

The rider requires a `DryRunTransport` run against "this exact payload — same `payload_hash`, same
`action_type`" (`docs/m7_first_live_post_governed_envelope.md` line 40).

`DryRunTransport.send()` (`moltbook/transport.py:1243–1268`) requires a real `ActionEnvelope` whose
`action_id` carries the reserved dry-run prefix and whose `payload` is the actual content under
test — it calls `validate_envelope()` against that real envelope. Because no exact payload exists
(§3.1), there is no envelope to construct, and therefore **no rehearsal that could even be run**,
authorized or not. This is stronger than "not yet authorized" — it is structurally impossible until
§3.1 is resolved.

The GO-1 rehearsal cited at `docs/m7_go1_decision_2026-08-10.md` §4 (artifact `cfd6897`) does
**not** qualify: it tested shape and `action_type` only, by GO-1's own admission, and predates any
possible payload for this action.

**No Dry Run was run during this pass.** Per your instruction, this population pass does not
self-authorize or attempt to manufacture this evidence. Once an exact payload exists and is
reviewed, the sequence would be: (1) build the real `ActionEnvelope` via `ActionEnvelope.approve()`
with the reviewed payload and a `governance_config_version`; (2) substitute a dry-run-namespaced
`action_id` via `make_dry_run_action_id()` (`moltbook/transport.py:1219–1221`); (3) construct
`DryRunTransport(live_config_version=...)` and call `.send(envelope)`; (4) record the resulting
`DryRunOutcome` and its `payload_hash`/`action_type` match against the real envelope as the rider's
`dry_run_rehearsal_reference`. This performs no network call (`DryRunTransport` is structurally
isolated per transport spec §11) and writes only to the `DryRunTransport` instance's own `trace`,
never to the cadence/citation stores. That structural non-publishing property is what would make
the rehearsal safe to run once authorized — it is not, by itself, authorization to run it, and this
pass does not run it.

### 3.3 Captcha configuration state and kill-switch precheck are runtime-only facts

Both `captcha_configuration_state` and `kill_switch_precheck` are documented in the rider (§2's
Source column) as facts about "constructor state at send time" / "runtime check... immediately
before this send." No live-deployment runner or session object exists in this repository today
(`grep` for non-test `MoltbookHTTPTransport(` construction finds only
`tools/c3_connectivity_probe.py` and `tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py` —
both preparation/exercise tooling, not a live-send runner), and `KillSwitch` has no persisted
global instance (§2 table, last row). Attesting either field's *value* today, against no real send
session, would be reporting on an object that does not yet exist rather than on the actual send.
These two fields can only become final immediately before the live send, under §E — which is
correctly where the checklist places the kill-switch reconfirmation (line 219) as a check
independent of, and later than, this §D review-time observation.

### 3.4 `governance_config_version` has no fixed repository convention

`ActionEnvelope.governance_config_version` and `MoltbookHTTPTransport`'s `live_config_version` are
both constructor parameters (`moltbook/transport.py:93`, `:1255`, `:1366`) with no committed
constant, version file, or naming convention anywhere in `docs/`, `moltbook/`, or the policy file
`moltbook/moltbook.pi`. This is an operator/engineering determination still to be made when the
live construction is built, not a value this pass can derive or should guess at.

### 3.5 `authorization_expires_at` has no governing duration

Searched all of `docs/` for an existing rule fixing how long a GO-2 authorization should remain
valid before voiding unused. None exists — the only related figure found is the standard
`ActionEnvelope`'s own 300-second `execution_window_seconds` default
(`moltbook/transport.py:74`), which is a different thing (the envelope's own freshness window
between approval and transmission), not GO-2's authorization-record expiry. This is an explicit
operator determination, left pending rather than invented.

---

## 4. Verification-environment note

Local verification (this pass and the prior pass): Python 3.12.10, pytest 9.0.3, Windows.
CI (`.github/workflows/tests.yml:13`) declares Python 3.11.

No governing document in this repository requires environment parity between local verification
and CI as a GO-2 precondition. `docs/m7_operator_go_checklist.md`'s own A2 precedent row (line 85)
recorded its passing preparation-baseline run under this same local environment (Python 3.12.10 /
pytest 9.0.3 / Windows) as sufficient evidence, without CI parity being raised as a condition.
**Disposition: observed, non-blocking, per existing repository precedent — not silently dropped.**
If the operator wants CI-environment parity established before GO-2, that is a new requirement to
adopt, not one already in force.

---

## 5. First-Post Rider — field-by-field status

The First-Post Rider (`docs/m7_first_live_post_governed_envelope.md` §2) defines eight required
fields. Their status, as established by §1–§3 above:

| Field | Status | Basis |
|---|---|---|
| `action_id` | Blocked | No real `ActionEnvelope` exists — depends on a real payload (§3.1) |
| `t3_grounding_reference` | **Satisfied** | Points to committed longitudinal grounding (§2 above) |
| `dry_run_rehearsal_reference` | Blocked | No payload to rehearse against (§3.1, §3.2) |
| `captcha_configuration_state` | Blocked | Runtime-only fact; no live-send session exists yet (§3.3) |
| `kill_switch_precheck` | Blocked | Runtime-only fact; no live-send session exists yet (§3.3) |
| `operator_go_reference` | Blocked | Circular — points to this record's own signature, which does not yet exist |
| `correction_procedure_reference` | **Satisfied** | Points to the finalized C5 procedure (§2 above) |
| `execution_commit_reference` | Blocked | Points to this record's own `execution_candidate_commit`; fixable only once this record is otherwise complete (§2 above) |

Summary: 2 of 8 fields satisfied (`t3_grounding_reference`, `correction_procedure_reference`), 6
blocked — 3 on the missing payload directly or indirectly (`action_id`, `dry_run_rehearsal_
reference`, `execution_commit_reference`), 2 on there being no live-send runtime yet
(`captcha_configuration_state`, `kill_switch_precheck`), and 1 (`operator_go_reference`)
circularly on this very record being signed.

---

## 6. What this record does not do

1. It does not authorize the live transmission, or any preparation not already authorized under
   GO-1.
2. It does not assert that the First-Post Rider is complete. It is not.
3. It does not assert that `KillSwitch.engaged` has been checked for the actual live send session.
   It has not, because that session does not yet exist.
4. It does not fix `authorized_action_id`, `authorized_payload_hash`,
   `authorized_config_version`, or `authorization_expires_at`. All four remain blank pending §3.
5. It does not populate `consumed_at`. That field belongs to §E, after execution, and this record
   has not been signed, let alone executed under.
6. It confers no authority over the future contents of any document it cites.

---

## 7. Authorization block — unsigned

```
Status:      DRAFT — blocked. See §3 for the specific unresolved dependencies. Not ready for
             signature.

Evidence (pointer to completed §C + rider record):
             §C: docs/m7_operator_go_checklist.md lines 140–144, all five rows Complete.
             Rider: docs/m7_first_live_post_governed_envelope.md §2 — NOT fully populated;
             see §5 above for the full field-by-field status.

Authorized by (operator):  [BLANK — operator only]

Authorized at:              [BLANK — operator only]

Statement: "I have reviewed the completed wiring, runbook, and
            correction/withdrawal procedure, the exact payload, envelope,
            and execution_candidate_commit for this action, and authorize
            exactly one live governed transmission bound to the identifiers
            above. Any payload, configuration, envelope, governed-code,
            credential, or target-action change invalidates this
            authorization and requires a new GO-2 record."

            [Preserved verbatim from docs/m7_operator_go_checklist.md §D for operator review.
            Its truth has not been affirmed by anyone — the exact payload and envelope it refers
            to do not yet exist.]
```

---

Nothing has been transmitted. No §E row has been marked. `consumed_at` is blank. This record does
not become effective by its own existence — only an operator signature under §7, and only once §3's
dependencies are resolved, can do that.
