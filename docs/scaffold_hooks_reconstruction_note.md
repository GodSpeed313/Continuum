# Scaffold Hooks — Reconstruction Note

**Status:** informational finding, not gating on M7 deployment (see
`docs/m7_operator_go_checklist.md` §A2 for the one-line non-gating statement). This note carries
the fuller finding and the architectural question it raises, kept out of the operational GO
checklist so that document stays narrowly executable.

## What was actually found

TODO.md's "Infrastructure / process debt" entry describes the item as: "Claude Code scaffold
hooks (PR #30) never installed — bash/`CLAUDE_*`-env-var shaped, need Windows + current-JSON-
interface rework before enabling." That phrasing implies the hook source files exist in the repo,
waiting for a rework pass.

They don't. PR #30 (`3172e5a`, "chore: add Claude Code scaffold (CLAUDE.md + skills)") added
`CLAUDE.md` and the three `.claude/skills/*/SKILL.md` files, and its own commit message states
"Un-ignore `.claude/skills/` so the skills are tracked while local settings/hooks stay private."
The repo's `.gitignore` confirms this: `.claude/*` is ignored except `!.claude/skills/`. Hooks
were therefore always local-only and were never committed at any point in this repo's history.

The debt is consequently not "repo code waiting for a Windows rework." It is:

> Unrecoverable local scaffold-hook examples from PR #30 must either be located from an existing
> workstation copy or reconstructed from the intended behavior and interface.

## The architectural question this raises

Before doing either recovery or reconstruction, one decision needs to be made explicitly, because
it changes what "done" looks like:

- **Are hooks intentionally user-local tooling** — personal workflow conveniences that
  legitimately differ per contributor/workstation and have no business being tracked? If so, the
  existing `.gitignore` boundary is correct as-is, and "closing this debt" just means Kevin
  personally reconstructing or re-authoring his own local hooks, with no repo change required.

- **Or are hooks project infrastructure** that every contributor should be able to install
  reproducibly? If so, committing live `.claude` runtime state directly would be the wrong fix —
  it would blur the local/tracked boundary PR #30 deliberately drew. The better shape is a tracked
  canonical source that *generates* the local files, e.g.:

  ```
  tools/claude-hooks/          (or examples/claude-hooks/)
  scripts/install-claude-hooks.ps1
  ```

  An installer script creates the actual `.claude/...` runtime files from the tracked template —
  preserving the local-config boundary while making the hook design itself version-controlled,
  reviewable, and testable.

This is Kevin's call, not something to resolve by default in either direction. It has no bearing
on M7 go-decision readiness and is out of scope for the deployment packet regardless of which way
it's resolved.

## Update 2026-07-24 — recovery half resolved (workstation session)

The "locate from an existing workstation copy" branch succeeded: the original scaffold hook
source was found in `Downloads/continuum-scaffold-v2.zip`
(`.claude/hooks/settings.example.json`, three hooks: post-edit targeted pytest, Stop-time full
suite + Discord notify, pre-Bash destructive-command guard). All three were reworked from the
dead bash/`CLAUDE_*`-env-var shape to the current stdin-JSON hook interface as Python scripts
(`.claude/hooks/pre_bash_guard.py`, `post_edit_tests.py`, `stop_suite_notify.py`) wired via
`.claude/settings.json`, and verified live: guard blocks `git push --force` (exit 2) and passes
benign commands; post-edit hook ran `pytest -k cadence` to green on an in-scope file and skipped
an out-of-scope one; Stop hook ran the full suite green (589 passed + 7 xfail, 6.6s) with the
original's PASS-webhook-failure-sends-FAIL bug fixed. `DISCORD_WEBHOOK_URL` unset = suite still
runs, result printed only. TODO.md's debt entry is updated accordingly.

The architectural question above (user-local tooling vs. tracked canonical source + installer)
remains open and is still Kevin's call. One new data point for it: the 2026-07-23 laptop crash is
exactly the failure mode that destroys local-only files — the current install exists only in
this workstation's `.claude/`, so the tracked-canonical-source option now has a concrete
survivability argument, with this note's file list serving as the reconstruction reference in
the meantime.

## Resolution 2026-07-24 — tracked infrastructure shipped, this note is CLOSED

The operator decided: tracked. "A laptop crash should not be able to erase process controls that
matter to how Continuum is developed." Implemented as `tools/claude-hooks/` (canonical hook
sources + settings template + stdin-schema docs + `install-hooks.ps1` / `verify-hooks.ps1`,
Windows PowerShell 5.1 compatible), with `.claude/` remaining local and generated — the
local/tracked boundary PR #30 drew is preserved; the hook *design* is now version-controlled,
reviewable, and reproducible on another machine.

The verify script's first run on this workstation immediately paid for itself: PowerShell 5.1
pipes prepend a UTF-8 BOM to native-command stdin, which `json.load` rejects — so
`pre_bash_guard.py` failed **open** (a guard silently not guarding). All three hooks now decode
stdin as `utf-8-sig`; the smoke test that caught it is part of `verify-hooks.ps1`, so any host
with BOM-emitting pipes re-tests the case on every verification run.
