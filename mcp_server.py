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

import tempfile
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from pi_script.validator import validate_file as validate_pi_file
from pi_script.resolver import resolve
from rift.compiler import compile_file as compile_rift_file

mcp = FastMCP("continuum-governance")


@mcp.tool()
def check_governance(
    source: str, state: dict[str, Any], source_type: str = "pi"
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
              "violation_counts": {...}         # optional, prior counts to carry forward
            }
        source_type: "pi" for native Pi Script, or "rift" for a Rift program
            (compiled to Pi Script automatically before evaluation).

    Returns:
        A dict with `passed` (bool), `rendered_trace` (human-readable
        RESOLUTION TRACE text), and `trace` (the structured trace dict).
        On a compile/validation error, returns `passed: False` and an
        `errors` list instead.
    """
    if source_type not in ("pi", "rift"):
        return {"passed": False, "errors": [f"source_type must be 'pi' or 'rift', got {source_type!r}"]}

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


if __name__ == "__main__":
    mcp.run(transport="stdio")
