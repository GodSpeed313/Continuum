from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pi_script.resolver import resolve

ROOT = Path(__file__).parent
M5   = ROOT / "m5"


def _load(path: Path) -> dict:
    for enc in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return json.loads(path.read_bytes().decode(enc))
        except (UnicodeDecodeError, ValueError):
            continue
    print(f"ERROR: cannot decode '{path}'", file=sys.stderr)
    sys.exit(2)


def main() -> None:
    ir    = _load(M5 / "ir.json")
    state = _load(M5 / "state.json")

    _trace, rendered, exit_code = resolve(ir, state)
    print(rendered)

    if exit_code == 1:
        ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        dest = M5 / "traces" / f"{ts}.txt"
        dest.write_text(rendered, encoding="utf-8")
        print(f"\nTrace saved → {dest}")
    elif exit_code == 0:
        print("\nNo violations — trace not saved.")


if __name__ == "__main__":
    main()
