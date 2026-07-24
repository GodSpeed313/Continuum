"""PostToolUse hook for Write|Edit: run targeted tests for core-package edits.

Port of the scaffold's v2 hook: when a .py file under pi_script/, rift/, or
moltbook/ is written or edited, run `pytest -k <stem> -q` (the scaffold's
deliberate approximation of "run related tests" — README_SETUP.md notes it
is blunt by design). Exit 2 on test failure so the failures are fed back to
the model; exit 0 when no tests match (pytest exit 5) or the file is out of
scope.
"""
import json
import pathlib
import subprocess
import sys

WATCHED = ("pi_script", "rift", "moltbook")


def main() -> int:
    try:
        # utf-8-sig tolerates the BOM PowerShell 5.1 pipes prepend
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8-sig"))
    except (json.JSONDecodeError, ValueError):
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path", "")
    if not file_path or not file_path.endswith(".py"):
        return 0
    project_dir = pathlib.Path(payload.get("cwd") or ".").resolve()
    try:
        rel = pathlib.Path(file_path).resolve().relative_to(project_dir)
    except ValueError:
        return 0  # edited file lives outside the project
    if rel.parts[0] not in WATCHED:
        return 0
    stem = pathlib.Path(file_path).stem
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-k", stem, "-q"],
        cwd=project_dir,
        capture_output=True,
        text=True,
        timeout=110,
    )
    if result.returncode in (0, 5):  # 5 = no tests matched the -k expression
        return 0
    tail = "\n".join((result.stdout or "").splitlines()[-30:])
    print(
        f"pytest -k {stem} failed (exit {result.returncode}) after editing "
        f"{rel}:\n{tail}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
