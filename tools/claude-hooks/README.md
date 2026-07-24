# Claude Code Hooks — Tracked Canonical Source

This directory is the version-controlled source of truth for Continuum's Claude Code hooks.
The live runtime state under `.claude/` is **generated and gitignored** (`.gitignore` keeps
`.claude/*` private except `.claude/skills/`) — never edit installed copies directly; edit the
sources here and re-run the installer. This boundary is deliberate: hook *design* is reviewable
project infrastructure, hook *installation* is local machine state.

Why tracked: the original PR #30 scaffold hooks lived only as local files and were nearly lost
(see `docs/scaffold_hooks_reconstruction_note.md` — the 2026-07-23 laptop crash is exactly the
failure mode that erases local-only process controls). Anything that shapes how Continuum is
developed must survive a dead workstation.

## Layout

```
tools/claude-hooks/
  README.md                  this file
  hooks/                     canonical hook scripts + settings template
    pre_bash_guard.py        PreToolUse(Bash): blocks rm -rf / git push --force, exit 2
    post_edit_tests.py       PostToolUse(Write|Edit): pytest -k <stem> for pi_script/rift/moltbook edits
    stop_suite_notify.py     Stop: full suite + Discord PASS/FAIL notify (notify-only, never blocks)
    settings.template.json   the .claude/settings.json wiring for the three hooks
  schemas/                   stdin JSON contract each hook consumes (documentation schemas)
  install-hooks.ps1          copies hooks + settings into .claude/ (Windows PowerShell 5.1)
  verify-hooks.ps1           proves installed state matches source and hooks actually fire
```

## Install

```powershell
powershell -ExecutionPolicy Bypass -File tools\claude-hooks\install-hooks.ps1
```

Re-run any time the tracked sources change. If your `.claude/settings.json` has local
customizations the installer refuses to clobber them — merge the `hooks` block manually or
re-run with `-Force` (a timestamped backup is kept).

## Verify

```powershell
powershell -ExecutionPolicy Bypass -File tools\claude-hooks\verify-hooks.ps1        # fast
powershell -ExecutionPolicy Bypass -File tools\claude-hooks\verify-hooks.ps1 -Full  # + real full-suite Stop-hook run
```

## Hook interface notes

- Hooks receive a JSON payload on **stdin** (current Claude Code interface — the old
  `CLAUDE_FILE_PATH`/`CLAUDE_TOOL_INPUT` env vars from the PR #30-era scaffold no longer exist).
  `schemas/` documents exactly which fields each hook consumes.
- Exit code 2 blocks (PreToolUse) or feeds stderr back to the model (PostToolUse). The Stop
  hook is notify-only and always exits 0 by design.
- `DISCORD_WEBHOOK_URL` (optional, never committed): enables the Stop hook's Discord
  notification. Unset, the suite still runs and the result is printed to the transcript.
- Scripts are invoked as `python .claude/hooks/<name>.py` with the project directory as cwd —
  shell-agnostic (works under both cmd and POSIX-shell hook execution), no jq/bash dependency.
