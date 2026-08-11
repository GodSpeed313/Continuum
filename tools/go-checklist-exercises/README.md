# GO checklist exercises

Reproducible exercises backing individual rows of `docs/m7_operator_go_checklist.md`.

> Structural checking of the checklist tables themselves lives one level up, in
> `tools/verify_go_checklist.py` — it asserts every row is `OPEN`, `DRAFTED`, or
> `COMPLETE` and never signed over blank evidence. The two are complements: the
> verifier checks that a row is *well-formed*, these scripts produce what a row
> claims was *reviewed*. Neither judges whether the evidence is true, and neither
> authorizes anything.

Some checklist rows are satisfied by the pytest suite alone — the row names an invariant,
and a test proves it. Others say a mechanism was **exercised** and an artifact **produced
and reviewed**. For those, a passing test is necessary but is not the thing the row asks
for: the row asks for something a reviewer can look at.

These scripts produce that artifact, and commit the expected output alongside so an
independent reviewer can inspect the script, run it, and compare — without relying on a
session transcript or on anyone's recollection.

## Scripts

| Script | Checklist rows |
|---|---|
| `a2_dry_run_and_kill_switch.py` | §A2 row 4 (Dry Run §11 + structural isolation), §A2 row 5 (kill switch §10 manual activation, re-enablement, and the `KillSwitchActivation` audit record) |
| `a4_first_post_rehearsal.py` | §A4 (Dry Run against a payload representative of the intended first post — `action_type` POST, ruled 2026-08-08 — producing detector results, resolver decision, approval trace, Approved Action Envelope, and simulated transport outcome) |

## Running

From the repository root:

```
python tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py
python tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py --check

python tools/go-checklist-exercises/a4_first_post_rehearsal.py
python tools/go-checklist-exercises/a4_first_post_rehearsal.py --check
```

`--check` compares the live run against the committed `.expected.txt` and exits non-zero
on any difference. A difference is not automatically a defect — it means the recorded
evidence no longer describes the code, and something has to be re-reviewed before the
affected rows can still be treated as satisfied.

Volatile values (wall-clock timestamps, generated UUIDs) are redacted to fixed
placeholders so the transcript is stable across runs. Everything else is real output from
the shipped classes. The comparison is line-by-line rather than byte-for-byte because
`.gitattributes` sets `* text=auto`, so committed line endings depend on the reviewer's
platform; the content comparison is exact.

## Constraints these scripts observe

- **No network call.** The kill-switch exercise injects a recording stub into the
  `request_fn` seam and reports how many calls each step attempted; `DryRunTransport` has
  no seam to inject.
- **No production state.** Observation stores are created inside a temporary directory
  that is removed on exit. Nothing writes to a repository state file.
- **No new assertions.** These scripts do not replace or duplicate the test suite. Where
  an exercise demonstrates a behavior, `tests/test_moltbook_transport.py` is what proves
  it (`TestKillSwitch`, `TestDryRunIsolation`).
- **Harness-local steps are labeled as such, in the transcript itself.** These scripts
  exercise shipped code. Where one must supply something shipped code does not — as
  `a4_first_post_rehearsal.py` must, performing the trace-to-envelope binding locally
  because no shipped path joins the resolver's output to an `approval_trace_id` — the
  step is named in the transcript at the point it happens, and states that it does not
  assert the shipped client performs that join. An exercise may fill a gap in order to
  produce the artifact a row asks for; it may never let the filling read as evidence
  that the gap is closed.

- **They authorize nothing.** Exercising the kill switch and the dry-run path is
  preparation evidence. The first live transmission is a separate governed action
  requiring its own envelope and its own operator authorization (GO-2, §D).
