"""compile_pi.py — Compile a .pi file to ir.json.

Usage:
    python compile_pi.py <file.pi> [output_ir.json]

If no output path is given, writes ir.json alongside the .pi file.
Bypasses PowerShell encoding issues that corrupt ir.json when piping
validator output directly from the shell.
"""

import json
import sys
from pathlib import Path

from pi_script.validator import validate_file


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python compile_pi.py <file.pi> [output_ir.json]", file=sys.stderr)
        sys.exit(1)

    pi_path = Path(sys.argv[1])
    if not pi_path.exists():
        print(f"ERROR: {pi_path} not found", file=sys.stderr)
        sys.exit(1)

    out_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else pi_path.with_name("ir.json")

    ok, errors, ir = validate_file(str(pi_path))
    if not ok:
        print("Validation errors:", file=sys.stderr)
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(1)

    out_path.write_text(json.dumps(ir, indent=2), encoding="utf-8")
    print(f"OK  {pi_path} -> {out_path}  ({len(ir['constraints'])} constraints, {len(ir['entities'])} entities)")


if __name__ == "__main__":
    main()
