"""mcp_server.py — MCP server exposing Continuum's governance pipeline as a tool.

Lets an agent check whether a state would violate a Pi Script policy — either
a native .pi policy, or a .rift program that gets compiled to Pi Script first —
before acting, instead of only being checked after the fact by the cron
governance watcher.

Usage:
    python mcp_server.py

Wire up in an MCP client (e.g. Claude Code) with a stdio transport pointing
at this file.
"""

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from filelock import FileLock
from mcp.server.fastmcp import FastMCP

from pi_script.validator import validate_file as validate_pi_file
from pi_script.resolver import resolve
from rift.compiler import compile_file as compile_rift_file

mcp = FastMCP("continuum-governance")


def _load_state_file(path: Path) -> dict:
    """Tolerantly decode a state JSON file (UTF-8, UTF-8-BOM, or UTF-16)."""
    for encoding in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Cannot decode '{path}' as UTF-8 or UTF-16 JSON")


def _atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _evaluate(source: str, state: dict[str, Any], source_type: str) -> dict[str, Any]:
    is_rift = source_type == "rift"
    suffix = ".rift" if is_rift else ".pi"

    with tempfile.TemporaryDirectory() as tmp:
        src_path = Path(tmp) / f"policy{suffix}"
        src_path.write_text(source, encoding="utf-8")

        pi_path = src_path
        if is_rift:
            ok, result = compile_rift_file(str(src_path))
            if not ok:
                return {"passed": False, "errors": result.splitlines()}
            pi_path = Path(result)

        ok, errors, ir = validate_pi_file(str(pi_path))
        if not ok:
            return {"passed": False, "errors": errors}

        trace, rendered, exit_code = resolve(ir, state)
        return {
            "passed": exit_code == 0,
            "rendered_trace": rendered,
            "trace": trace,
        }


@mcp.tool()
def check_governance(
    source: str,
    state: dict[str, Any],
    source_type: str = "pi",
    persist: bool = False,
    state_path: str | None = None,
) -> dict[str, Any]:
    """Check a state snapshot against a governance policy.

    Args:
        source: Policy text, in the format named by `source_type`.
        state: The state snapshot to evaluate the policy against:
            {
              "trigger_type": "event" | "heartbeat",
              "entity": "<EntityName from the policy's enforce block>",
              "entity_state": {"<field>": <value>, ...},
              "response_history": [...],       # optional, for contradiction_rule
              "violation_counts": {...}         # optional; ignored if persist=True,
                                                 # since persisted counts take over
            }
        source_type: "pi" for native Pi Script, or "rift" for a Rift program
            (compiled to Pi Script automatically before evaluation).
        persist: If True, `state_path` is treated as the durable state file for
            this governed system: its prior `violation_counts` are loaded and
            carried forward, the updated state is written back, and a trace
            file is saved to a sibling `traces/` directory on violation — the
            same behavior `log_session.py` has for the M5 dogfood loop.
            Locked cross-process (via `<state_path>.lock`) so two concurrent
            callers can't race on the same file.
        state_path: Path to the durable state JSON file. Required when
            persist=True; ignored otherwise.

    Returns:
        A dict with `passed` (bool), `rendered_trace` (human-readable
        RESOLUTION TRACE text), and `trace` (the structured trace dict).
        When persist=True, also includes `persisted: True` and, on violation,
        `trace_file` (the path the trace was saved to).
        On a compile/validation/input error, returns `passed: False` and an
        `errors` list instead.
    """
    if source_type not in ("pi", "rift"):
        return {"passed": False, "errors": [f"source_type must be 'pi' or 'rift', got {source_type!r}"]}

    if not persist:
        return _evaluate(source, state, source_type)

    if not state_path:
        return {"passed": False, "errors": ["state_path is required when persist=True"]}

    path = Path(state_path)
    lock = FileLock(str(path) + ".lock")
    with lock:
        persisted = _load_state_file(path) if path.exists() else {}

        merged_state = dict(state)
        merged_state["violation_counts"] = persisted.get("violation_counts", {})

        result = _evaluate(source, merged_state, source_type)
        if "errors" in result:
            return result

        trace = result["trace"]
        new_counts = trace.get("updated_violation_counts") or {}
        if new_counts:
            persisted.setdefault("violation_counts", {}).update(new_counts)

        persisted["trigger_type"] = state.get("trigger_type")
        persisted["entity"] = state.get("entity")
        persisted["entity_state"] = state.get("entity_state", {})
        if "response_history" in state:
            persisted["response_history"] = state["response_history"]

        _atomic_write_json(path, persisted)
        result["persisted"] = True

        if not result["passed"]:
            traces_dir = path.parent / "traces"
            traces_dir.mkdir(exist_ok=True)
            ts = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S_%f")
            trace_file = traces_dir / f"{ts}.txt"
            trace_file.write_text(result["rendered_trace"], encoding="utf-8")
            result["trace_file"] = str(trace_file)

        return result


if __name__ == "__main__":
    mcp.run(transport="stdio")
