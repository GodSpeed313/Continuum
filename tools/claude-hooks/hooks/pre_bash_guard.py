"""PreToolUse guard for Bash: block destructive commands deterministically.

Port of the scaffold's v2 hook (settings.example.json, PR #30 era) to the
current Claude Code hook interface: input arrives as JSON on stdin, exit
code 2 blocks the tool call and feeds stderr back to the model.
"""
import json
import re
import sys

BLOCKED = re.compile(r"rm -rf|git push --force|git push -f\b")


def main() -> int:
    try:
        # utf-8-sig: PowerShell 5.1 pipes prepend a BOM, which json.load rejects —
        # and a guard that fails open on that is silently not guarding.
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except (json.JSONDecodeError, ValueError):
        return 0  # malformed input: never block on our own parse failure
    command = (payload.get("tool_input") or {}).get("command", "")
    match = BLOCKED.search(command)
    if match:
        print(
            f"Blocked by .claude/hooks/pre_bash_guard.py: command contains "
            f"'{match.group(0)}'. Destructive commands require the operator "
            f"to run them manually.",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
