"""dashboard.py — read-only web UI for browsing Continuum governance state and traces.

Scans ROOT itself plus its immediate subdirectories for a state.json file
(and an optional sibling traces/ directory of RESOLUTION TRACE .txt files),
and serves a simple browsable view of each governed system's current state
and violation history.

This exists for the v0.2 Gate Condition ("non-expert must understand the
system's actions") — traces are technically legible as flat files, but not
actually browsable. This makes them browsable without changing where or how
they're stored: no migration, reads the same state.json / traces/*.txt
convention log_session.py and check_governance(persist=True) already write.

Usage:
    python dashboard.py [--root PATH] [--host HOST] [--port PORT]
"""

import argparse
import html
import json
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, PlainTextResponse, Response
from starlette.routing import Route

STYLE = """
<style>
  body { font-family: -apple-system, Segoe UI, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1, h2 { font-weight: 600; }
  table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
  th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #ddd; }
  th { color: #666; font-weight: 500; font-size: 0.85rem; text-transform: uppercase; }
  a { color: #0645ad; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .count-zero { color: #888; }
  .count-nonzero { color: #b3261e; font-weight: 600; }
  pre { background: #f5f5f5; padding: 1rem; border-radius: 6px; overflow-x: auto; white-space: pre-wrap; }
  .back { display: inline-block; margin-bottom: 1rem; }
  .muted { color: #888; font-size: 0.9rem; }
</style>
"""


def _load_state(path: Path) -> dict:
    for encoding in ("utf-8-sig", "utf-16", "utf-8"):
        try:
            return json.loads(path.read_text(encoding=encoding))
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return {}


def discover_systems(root: Path) -> dict[str, dict]:
    """Return {key: {dir, entity, violation_counts, trace_files}} for every
    directory (root included) that has a state.json."""
    systems: dict[str, dict] = {}
    candidates = [("root", root)]
    for d in sorted(root.iterdir()):
        if d.is_dir() and not d.name.startswith(".") and d.name != "__pycache__":
            candidates.append((d.name, d))

    for key, d in candidates:
        state_file = d / "state.json"
        if not state_file.exists():
            continue
        state = _load_state(state_file)
        traces_dir = d / "traces"
        trace_files = sorted(
            (p for p in traces_dir.glob("*.txt")), reverse=True
        ) if traces_dir.is_dir() else []
        systems[key] = {
            "dir": d,
            "entity": state.get("entity", "unknown"),
            "violation_counts": state.get("violation_counts", {}),
            "trace_files": trace_files,
        }
    return systems


def _page(body: str) -> str:
    return f"<!doctype html><html><head><meta charset='utf-8'><title>Continuum Governance Dashboard</title>{STYLE}</head><body>{body}</body></html>"


async def index(request):
    root = request.app.state.root
    systems = discover_systems(root)

    rows = []
    for key, info in sorted(systems.items()):
        total_violations = sum(info["violation_counts"].values())
        count_class = "count-nonzero" if total_violations else "count-zero"
        rows.append(
            f"<tr><td><a href='/system/{html.escape(key)}'>{html.escape(key)}</a></td>"
            f"<td>{html.escape(info['entity'])}</td>"
            f"<td class='{count_class}'>{total_violations}</td>"
            f"<td>{len(info['trace_files'])}</td></tr>"
        )

    body = f"""
    <h1>Continuum Governance Dashboard</h1>
    <p class="muted">Scanning: {html.escape(str(root.resolve()))}</p>
    <table>
      <tr><th>System</th><th>Entity</th><th>Total violations</th><th>Trace files</th></tr>
      {''.join(rows) if rows else '<tr><td colspan="4" class="muted">No governed systems found (no state.json in this root or its subdirectories).</td></tr>'}
    </table>
    """
    return HTMLResponse(_page(body))


async def system_detail(request):
    root = request.app.state.root
    key = request.path_params["key"]
    systems = discover_systems(root)
    info = systems.get(key)
    if info is None:
        return PlainTextResponse("System not found", status_code=404)

    rows = []
    for f in info["trace_files"]:
        rows.append(
            f"<tr><td><a href='/system/{html.escape(key)}/trace/{html.escape(f.name)}'>{html.escape(f.name)}</a></td></tr>"
        )

    counts_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count}</td></tr>"
        for name, count in info["violation_counts"].items()
    ) or "<tr><td colspan='2' class='muted'>No violations recorded</td></tr>"

    body = f"""
    <a class="back" href="/">&larr; All systems</a>
    <h1>{html.escape(key)}</h1>
    <p class="muted">Entity: {html.escape(info['entity'])} &middot; {html.escape(str(info['dir']))}</p>

    <h2>Violation counts</h2>
    <table><tr><th>Constraint</th><th>Count</th></tr>{counts_rows}</table>

    <h2>Trace files ({len(info['trace_files'])})</h2>
    <table>{''.join(rows) if rows else "<tr><td class='muted'>No trace files</td></tr>"}</table>
    """
    return HTMLResponse(_page(body))


async def trace_detail(request):
    root = request.app.state.root
    key = request.path_params["key"]
    filename = request.path_params["filename"]
    systems = discover_systems(root)
    info = systems.get(key)
    if info is None:
        return PlainTextResponse("System not found", status_code=404)

    match = next((f for f in info["trace_files"] if f.name == filename), None)
    if match is None:
        return PlainTextResponse("Trace file not found", status_code=404)

    text = match.read_text(encoding="utf-8")
    body = f"""
    <a class="back" href="/system/{html.escape(key)}">&larr; {html.escape(key)}</a>
    <h1>{html.escape(filename)}</h1>
    <pre>{html.escape(text)}</pre>
    """
    return HTMLResponse(_page(body))


def build_app(root: Path) -> Starlette:
    app = Starlette(routes=[
        Route("/", index),
        Route("/system/{key}", system_detail),
        Route("/system/{key}/trace/{filename}", trace_detail),
    ])
    app.state.root = root
    return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Continuum governance dashboard")
    parser.add_argument("--root", default=".", help="Root directory to scan for governed systems (default: cwd)")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8899)
    args = parser.parse_args()

    app = build_app(Path(args.root))
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
