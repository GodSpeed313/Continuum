"""
C3 connectivity probe — docs/m7_c3_endpoint_connectivity_validation_2026-08-21.md §4.

READ-ONLY. Issues at most three GETs. Never imports, constructs, or calls anything
on the write path. Never prints key material.

Run from the repo root:  python tools/c3_connectivity_probe.py [log_output_dir]

PROVENANCE: this is the script that produced the observations recorded at §5 of that
artifact, executed once at 2026-08-21 19:10:41-42 UTC with the transport at c1eb9ba.
It is committed verbatim as it ran, with exactly one deviation, made when it moved
into the repo: the log destination. In the scratchpad it wrote beside itself; from
tools/ that would drop an untracked log into the governed tree on every run, so the
default is now the system temp directory and an explicit directory may be passed as
argv[1]. Nothing else changed — no request, no classification, no recorded field.

RE-RUNNING THIS IS A LIVE ACT, NOT A TEST. It sends the real credential to the real
platform. §C3's binding wording permits only the two documented non-publishing reads
it performs; it is not a test-suite fixture and nothing in tests/ imports it.
"""

from __future__ import annotations

import json

import pathlib
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

SCRIPT = pathlib.Path(__file__).resolve()
sys.path.insert(0, str(pathlib.Path.cwd()))

from moltbook.transport import (  # noqa: E402
    MOLTBOOK_BASE_URL,
    MoltbookHTTPTransport,
    real_request,
)

EXPECTED_BASE_URL = "https://www.moltbook.com/api/v1"
log: list[dict] = []


def record(step: str, **fields) -> None:
    entry = {"step": step, "at": datetime.now(timezone.utc).isoformat(), **fields}
    log.append(entry)
    print(json.dumps(entry, indent=2, default=str))


# ── §4.1 pre-flight, offline — no network ────────────────────────────────────────
def load_key() -> str:
    env = pathlib.Path.cwd() / ".env"
    for line in env.read_text(encoding="utf-8").splitlines():
        if line.startswith("MOLTBOOK_API_KEY="):
            return line.split("=", 1)[1].strip()
    raise SystemExit("PRE-FLIGHT FAIL: MOLTBOOK_API_KEY not found in .env — stopping, no request made")


if MOLTBOOK_BASE_URL != EXPECTED_BASE_URL:
    raise SystemExit(f"PRE-FLIGHT FAIL: base URL is {MOLTBOOK_BASE_URL!r}, expected {EXPECTED_BASE_URL!r}")

api_key = load_key()
if not api_key:
    raise SystemExit("PRE-FLIGHT FAIL: MOLTBOOK_API_KEY is empty — stopping, no request made")

record(
    "4.1 pre-flight (offline)",
    base_url=MOLTBOOK_BASE_URL,
    base_url_matches_expected=True,
    key_present=True,
    key_length=len(api_key),          # length only — never the value
    network_touched=False,
)


# ── §4.2 unauthenticated redirect check — NO Authorization header ────────────────
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # do not follow — we want to SEE the redirect, not chase it


try:
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(f"{EXPECTED_BASE_URL}/agents/status", method="GET")
    t0 = time.monotonic()
    try:
        with opener.open(req, timeout=10) as resp:
            status, hdrs = resp.status, dict(resp.headers)
    except urllib.error.HTTPError as exc:
        status, hdrs = exc.code, dict(exc.headers)
    record(
        "4.2 redirect check (unauthenticated)",
        url=f"{EXPECTED_BASE_URL}/agents/status",
        authorization_header_sent=False,
        status_code=status,
        location=hdrs.get("Location"),
        redirected=300 <= status < 400,
        elapsed_s=round(time.monotonic() - t0, 3),
    )
except Exception as exc:  # URLError / timeout / DNS — recorded, not raised (§4.5)
    record("4.2 redirect check (unauthenticated)", error_type=type(exc).__name__, error=str(exc))


# ── the probe object: captcha-unconfigured, so no verify call is possible (§3) ───
#
# request_fn is a PASS-THROUGH RECORDER, not a substitute: it calls the production
# `real_request` with the production base_url and returns its HTTPResponse unchanged.
# Same urllib call, same timeout, same headers, same redirect posture. It exists only
# because health_check() discards the HTTPResponse — it records no status code and no
# headers — so without this seam the probe could not observe the raw HTTP status of
# GET /agents/status at all, which is the one thing C3 most needs to see (§6 item 1).
observed: list[dict] = []


def recording_request_fn(method: str, path: str, body: dict | None, headers: dict):
    response = real_request(EXPECTED_BASE_URL, method, path, body, headers)
    observed.append({
        "method": method,
        "path": path,
        "status_code": response.status_code,
        "headers": dict(response.headers),
        "body_sent": body,  # always None on this run — every call here is a GET
    })
    return response


transport = MoltbookHTTPTransport(
    api_key=api_key,
    request_fn=recording_request_fn,
    captcha_verifier=None,      # both None: Note E fail-closed invariant satisfied,
    submit_captcha_fn=None,     # and no CAPTCHA submission capability exists at all
)

# ── §4.3 health check / claim status — ONE call to GET /agents/status ────────────
try:
    t0 = time.monotonic()
    result = transport.health_check()
    raw = observed[-1] if observed else {}
    record(
        "4.3 health check + claim status (authenticated)",
        endpoint="GET /api/v1/agents/status",
        http_status_code=raw.get("status_code"),          # from the recorder — the
        rate_limit_headers={                              # TransportResult has neither
            k: v for k, v in raw.get("headers", {}).items()
            if k.startswith("x-ratelimit") or k == "retry-after"
        },
        transport_outcome=result.outcome.value,           # always SUCCESS — see §6 item 1
        retry_category=result.retry_category.value,
        eligibility_state=transport.eligibility.state.value,
        platform_response=result.platform_response,
        elapsed_s=round(time.monotonic() - t0, 3),
    )
except Exception as exc:
    record("4.3 health check + claim status (authenticated)", error_type=type(exc).__name__, error=str(exc))


# ── §4.4 feed read — GET /posts, shape only, no content ──────────────────────────
try:
    t0 = time.monotonic()
    feed = transport.read_feed()
    body = feed.platform_response or {}
    items = body.get("posts") or body.get("data") or []
    raw = observed[-1] if observed else {}
    record(
        "4.4 feed read (authenticated)",
        endpoint="GET /api/v1/posts",
        http_status_code=raw.get("status_code"),
        transport_outcome=feed.outcome.value,
        top_level_keys=sorted(body.keys()) if isinstance(body, dict) else type(body).__name__,
        item_count=len(items) if isinstance(items, list) else None,
        has_next_cursor="next_cursor" in body if isinstance(body, dict) else None,
        has_more=body.get("has_more") if isinstance(body, dict) else None,
        rate_limit={
            "limit": feed.rate_limit.limit,
            "remaining": feed.rate_limit.remaining,
            "reset": feed.rate_limit.reset,
            "retry_after_delay_seconds": feed.rate_limit.retry_after_delay_seconds,
        } if feed.rate_limit else None,
        elapsed_s=round(time.monotonic() - t0, 3),
        # deliberately NOT recorded: post titles, bodies, authors, ids
    )
except Exception as exc:
    record("4.4 feed read (authenticated)", error_type=type(exc).__name__, error=str(exc))


# ── write the log OUTSIDE the repo — argv[1] if given, else the system temp dir ──
out_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path(tempfile.gettempdir())
out = out_dir / "c3_probe_log.json"
redacted = json.dumps(log, indent=2, default=str)
assert api_key not in redacted, "ABORT: key material present in log — not written"
out.write_text(redacted, encoding="utf-8")
print(f"\nlog written to {out}")
