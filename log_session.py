from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from pi_script.resolver import resolve

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
M5   = ROOT / "m5"

DEFAULT_STATE_REF = "ContinuumSession.session_topic"


def _load(path: Path) -> dict:
    for enc in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return json.loads(path.read_bytes().decode(enc))
        except (UnicodeDecodeError, ValueError):
            continue
    print(f"ERROR: cannot decode '{path}'", file=sys.stderr)
    sys.exit(2)


def _append_response(state: dict, text: str, state_ref: str) -> None:
    history = state.setdefault("response_history", [])
    history.append({
        "text":      text,
        "state_ref": state_ref,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


def _save_state(state: dict) -> None:
    (M5 / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="M5 daily runner — resolves dogfood.pi against current state"
    )
    parser.add_argument(
        "--response",
        metavar="TEXT",
        help="Log a response entry for this session (appended to response_history)",
    )
    parser.add_argument(
        "--state-ref",
        metavar="REF",
        default=DEFAULT_STATE_REF,
        help=f"State ref (topic) for the response entry (default: {DEFAULT_STATE_REF})",
    )
    parser.add_argument(
        "--clear-history",
        action="store_true",
        help="Clear response_history from state.json and exit",
    )
    parser.add_argument(
        "--reset-violations",
        metavar="CONSTRAINT",
        nargs="?",
        const="__all__",
        help="Reset violation counter(s) in state.json and exit. "
             "With no argument resets all counters; with a name resets only that constraint.",
    )
    args = parser.parse_args()

    state = _load(M5 / "state.json")

    if args.clear_history:
        state["response_history"] = []
        _save_state(state)
        print("[log_session] response_history cleared.")
        return

    if args.reset_violations is not None:
        counts = state.setdefault("violation_counts", {})
        if args.reset_violations == "__all__":
            state["violation_counts"] = {}
            print("[log_session] All violation counters reset.")
        else:
            counts.pop(args.reset_violations, None)
            print(f"[log_session] Violation counter reset: {args.reset_violations}")
        _save_state(state)
        return

    if args.response:
        _append_response(state, args.response, args.state_ref)
        _save_state(state)
        history = state.get("response_history", [])
        print(f"[log_session] Response logged (history depth: {len(history)})")

    ir = _load(M5 / "ir.json")
    trace, rendered, exit_code = resolve(ir, state)
    print(rendered)

    # Persist any violation count increments back to state
    new_counts = trace.get("updated_violation_counts", {})
    if new_counts:
        counts = state.setdefault("violation_counts", {})
        counts.update(new_counts)
        _save_state(state)

    if exit_code == 1:
        ts   = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
        dest = M5 / "traces" / f"{ts}.txt"
        dest.write_text(rendered, encoding="utf-8")
        print(f"\nTrace saved → {dest}")
    elif exit_code == 0:
        print("\nNo violations — trace not saved.")


if __name__ == "__main__":
    main()
