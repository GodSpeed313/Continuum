"""
quickstart.py — Clone and run in 60 seconds.

    python quickstart.py

What this does:
    1. Validates examples/tasks.pi — confirms the grammar and produces an IR
    2. Runs the resolver against state.json — evaluates all constraints
    3. Prints a RESOLUTION TRACE to the terminal

No arguments. No setup beyond: pip install -r requirements.txt
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent


def step(n: int, msg: str) -> None:
    print(f"\n[{n}/3] {msg}")


def fail(msg: str) -> None:
    print(f"\n  ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    print("=" * 56)
    print("  Continuum — Pi Script quickstart")
    print("=" * 56)

    # ── Step 1: Validate examples/tasks.pi ───────────────────
    step(1, "Validating examples/tasks.pi ...")

    tasks_pi = ROOT / "examples" / "tasks.pi"
    if not tasks_pi.exists():
        fail(f"examples/tasks.pi not found at {tasks_pi}")

    try:
        from pi_script.validator import validate_file
    except ImportError as e:
        fail(f"Import failed: {e}\n  Run: pip install -r requirements.txt")

    ok, errors, ir = validate_file(str(tasks_pi))

    if not ok:
        print("  Validation errors:")
        for err in errors:
            print(f"    {err}")
        fail("Validation failed — fix the errors above before continuing.")

    print(f"  ✓ Valid — {len(ir['constraints'])} constraints, "
          f"{len(ir['entities'])} entities, "
          f"{len(ir['maps'])} map entries")

    # ── Step 2: Write ir.json ─────────────────────────────────
    ir_path = ROOT / "ir.json"
    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(ir, f, indent=2)
    print(f"  ✓ IR written to {ir_path.name}")

    # ── Step 3: Run the resolver ──────────────────────────────
    step(2, "Loading state snapshot (state.json) ...")

    state_path = ROOT / "state.json"
    if not state_path.exists():
        fail(
            "state.json not found.\n"
            "  It should be in the repo root — check your clone is complete."
        )

    with open(state_path, encoding="utf-8") as f:
        state = json.load(f)

    entity = state.get("entity", "unknown")
    trigger = state.get("trigger_type", "unknown")
    print(f"  ✓ Entity: {entity}  |  Trigger: {trigger}")

    step(3, "Running resolver ...")
    print()

    try:
        from pi_script.resolver import resolve
    except ImportError as e:
        fail(f"Import failed: {e}")

    trace, rendered, exit_code = resolve(ir, state)

    print(rendered)

    # ── Summary ───────────────────────────────────────────────
    print("=" * 56)
    violations = [c for c in trace["constraints"] if c["status"] == "violated"]
    suspended  = [c for c in trace["constraints"] if c["status"] == "suspended"]

    if exit_code == 0:
        print(f"  RESULT: SATISFIED — {len(trace['constraints'])} constraints passed")
    else:
        print(f"  RESULT: VIOLATION — {len(violations)} violation(s) detected")

    if suspended:
        print(f"  NOTE:   {len(suspended)} constraint(s) suspended (missing state fields)")

    print(f"  System state: {trace['system_state'].upper()}")
    print("=" * 56)
    print()
    print("  Next steps:")
    print("  - Edit state.json to trigger a violation and re-run")
    print("  - Read the grammar spec: docs/pi_script_v01_draft3.md")
    print("  - Write your own .pi file and validate it:")
    print("      python -m pi_script.validator your_file.pi")
    print()

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
