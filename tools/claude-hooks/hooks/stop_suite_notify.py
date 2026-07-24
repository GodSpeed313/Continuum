"""Stop hook: run the full suite and notify Discord of the result.

Port of the scaffold's v2 hook, with its one real bug fixed: the original
`pytest && curl PASS || curl FAIL` sent FAIL whenever the PASS webhook call
itself failed. Here the suite result and the notification result are
independent. Notify-only by design — this hook never blocks the stop
(always exits 0), matching the original's behavior.

DISCORD_WEBHOOK_URL must be set in the environment (never committed); when
unset, the suite still runs and the result is printed to the transcript.
"""
import json
import os
import subprocess
import sys
import urllib.request


def notify(webhook_url: str, content: str) -> None:
    req = urllib.request.Request(
        webhook_url,
        data=json.dumps({"content": content}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except OSError as exc:
        print(f"Discord notify failed (suite result unaffected): {exc}")


def main() -> int:
    try:
        # utf-8-sig tolerates the BOM PowerShell 5.1 pipes prepend
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except (json.JSONDecodeError, ValueError):
        payload = {}
    project_dir = payload.get("cwd") or "."
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=280,
    )
    passed = result.returncode == 0
    summary = (result.stdout or "").strip().splitlines()
    last_line = summary[-1] if summary else "(no pytest output)"
    status = "PASS" if passed else "FAIL — check before shipping"
    print(f"Continuum suite: {status} ({last_line})")
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if webhook_url:
        notify(webhook_url, f"Continuum suite: {status}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
