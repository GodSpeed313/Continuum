"""
§A2 rows 4 and 5 — reproducible exercise for the M7 Operator GO Checklist.

    docs/m7_operator_go_checklist.md  §A2. Engineering completeness

Row 4: "Dry Run mode (§11) exercised; structural isolation confirmed (production
        ingestion rejects the reserved Dry Run identifier namespace)"
Row 5: "Kill switch (§10) manual activation (`KillSwitch.activate_manual(operator=...)`)
        and re-enablement (`KillSwitch.clear(operator=...)`) both exercised outside Dry
        Run isolation testing, with a `KillSwitchActivation` audit record produced and
        reviewed"

This script exists so those two rows cite something an independent reviewer can execute
and compare, rather than a session transcript. It asserts nothing that the pytest suite
does not already assert; its purpose is to PRODUCE the reviewable artifact — in
particular the `KillSwitchActivation` audit record, which row 5 requires be produced and
reviewed, not merely covered by a test.

What it does NOT do: no network call is made (the kill-switch half injects a recording
stub into the `request_fn` seam; the dry-run half has no seam to inject), and no
production state file is touched (the stores are created inside a temporary directory
that is removed on exit).

Usage:
    python tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py
        Print the transcript.

    python tools/go-checklist-exercises/a2_dry_run_and_kill_switch.py --check
        Print the transcript and compare it byte-for-byte against the committed
        a2_dry_run_and_kill_switch.expected.txt. Exit 0 on match, 1 on mismatch.

Volatile values (wall-clock timestamps, the generated dry-run UUID) are redacted to
fixed placeholders so the transcript is byte-reproducible. Everything else is real
output from the shipped classes.
"""

from __future__ import annotations

import argparse
import re
import sys
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from moltbook.cadence import CadenceObservationStore  # noqa: E402
from moltbook.citation import CitationEdgeStore  # noqa: E402
from moltbook.dryrun import DRY_RUN_ID_PREFIX, is_dry_run_id  # noqa: E402
from moltbook.transport import (  # noqa: E402
    ActionEnvelope,
    ActionType,
    DryRunTransport,
    HTTPResponse,
    KillSwitchEngaged,
    MoltbookHTTPTransport,
    make_dry_run_action_id,
)

CONFIG_V1 = "config-v1"
INGEST_AT = datetime(2026, 8, 5, 12, 0, 0, tzinfo=timezone.utc)
EXPECTED_PATH = Path(__file__).with_suffix("").with_name("a2_dry_run_and_kill_switch.expected.txt")

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_REDACTIONS = (
    (re.compile(r"datetime\.datetime\([^)]*tzinfo=datetime\.timezone\.utc\)"), "<utc-timestamp>"),
    (re.compile(rf"{re.escape(DRY_RUN_ID_PREFIX)}{_UUID}"), f"{DRY_RUN_ID_PREFIX}<uuid4>"),
)

_lines: list[str] = []


def emit(line: str = "") -> None:
    for pattern, replacement in _REDACTIONS:
        line = pattern.sub(replacement, line)
    _lines.append(line)


def rule(title: str) -> None:
    emit()
    emit("=" * 78)
    emit(title)
    emit("=" * 78)


def envelope(**overrides) -> ActionEnvelope:
    defaults = dict(
        action_type=ActionType.POST,
        payload={"content": "hello moltbook"},
        approval_trace_id="a2-exercise",
        governance_config_version=CONFIG_V1,
    )
    defaults.update(overrides)
    return ActionEnvelope.approve(**defaults)


def exercise_kill_switch(operator: str) -> None:
    """Row 5. Deliberately on MoltbookHTTPTransport — the live transport class — because
    the row requires this be exercised OUTSIDE Dry Run isolation testing."""
    rule("ROW 5 — Kill switch (§10) on MoltbookHTTPTransport (live class, stubbed seam)")

    network_calls: list[tuple[str, str]] = []

    def recording_request(method, path, body, headers):
        network_calls.append((method, path))
        return HTTPResponse(200, {"id": "stub-1"}, {})

    transport = MoltbookHTTPTransport(
        "stub-key", request_fn=recording_request, live_config_version=CONFIG_V1
    )

    emit()
    emit("[1] Baseline — switch disengaged, a governed write transmits.")
    result = transport.send(envelope())
    emit(f"    engaged             : {transport.kill_switch.engaged}")
    emit(f"    write outcome       : {result.outcome}")
    emit(f"    network calls so far: {network_calls}")

    emit()
    emit("[2] MANUAL ACTIVATION — KillSwitch.activate_manual(operator=...)")
    transport.kill_switch.activate_manual(
        operator=operator, detail="GO checklist §A2 row 5 exercise — no incident"
    )
    emit(f"    engaged             : {transport.kill_switch.engaged}")
    emit()
    emit("    KillSwitchActivation audit record produced (all fields):")
    for key, value in asdict(transport.kill_switch.activation_log[-1]).items():
        emit(f"      {key:22} = {value!r}")

    emit()
    emit("[3] While engaged — writes blocked, reads unaffected (fail-closed, §10).")
    calls_before = len(network_calls)
    try:
        transport.send(envelope())
        emit("    !! WRITE WAS NOT BLOCKED — exercise FAILED")
    except KillSwitchEngaged as exc:
        emit(f"    write raised        : KillSwitchEngaged({exc})")
    emit(f"    network calls attempted by the blocked write: {len(network_calls) - calls_before}")
    read = transport.read_feed()
    emit(f"    read outcome        : {read.outcome}  (reads continue while engaged)")
    emit(f"    engaged after a successful read: {transport.kill_switch.engaged}"
         "  (no automatic recovery)")

    emit()
    emit("[4] RE-ENABLEMENT — KillSwitch.clear(operator=...)")
    transport.kill_switch.clear(operator=operator, detail="exercise complete")
    emit(f"    engaged             : {transport.kill_switch.engaged}")
    emit()
    emit("    Clearance audit record (the log records the clear, not only the engage):")
    for key, value in asdict(transport.kill_switch.activation_log[-1]).items():
        emit(f"      {key:22} = {value!r}")

    emit()
    emit("[5] Post-clear — a governed write transmits again.")
    result = transport.send(envelope())
    emit(f"    write outcome       : {result.outcome}")
    emit(f"    total network calls : {len(network_calls)}  {network_calls}")
    emit()
    emit(f"    Full activation log ({len(transport.kill_switch.activation_log)} entries):")
    for i, entry in enumerate(transport.kill_switch.activation_log, 1):
        emit(f"      {i}. mode={entry.mode!r} trigger={entry.trigger!r} "
             f"class={entry.affected_action_class!r} detail={entry.detail!r}")


def exercise_dry_run(scratch: Path) -> None:
    """Row 4."""
    rule("ROW 4 — Dry Run mode (§11) and structural isolation")

    emit()
    emit("[1] Dry run runs real envelope validation and makes no network call.")
    emit("    DryRunTransport has no request_fn parameter at all — the absence of a")
    emit("    network seam is structural, not a runtime flag that could be flipped.")
    dry = DryRunTransport(live_config_version=CONFIG_V1)
    dry_id = make_dry_run_action_id()
    outcome = dry.send(envelope(action_id=dry_id))
    emit(f"    dry-run action_id   : {dry_id!r}")
    emit(f"    reserved prefix     : {DRY_RUN_ID_PREFIX!r}  is_dry_run_id -> {is_dry_run_id(dry_id)}")
    emit(f"    returned type       : {type(outcome).__name__}  (NOT TransportResult)")
    emit(f"    simulated_outcome   : {outcome.simulated_outcome}")
    emit(f"    simulated_publication_status  : {outcome.simulated_publication_status}")
    emit(f"    simulated_verification_status : {outcome.simulated_verification_status}")
    emit(f"    detail              : {outcome.detail!r}")
    emit(f"    instance trace len  : {len(dry.trace)}  (recorded only to this instance)")

    emit()
    emit("[2] The dry-run transport refuses a non-namespaced (production) action_id.")
    try:
        dry.send(envelope(action_id="real-post-1"))
        emit("    !! ACCEPTED — exercise FAILED")
    except ValueError as exc:
        emit(f"    raised ValueError   : {exc}")

    emit()
    emit("[3] STRUCTURAL ISOLATION — production ingestion rejects the reserved namespace")
    emit("    even under DIRECT attempted ingestion, bypassing the transport entirely.")
    cadence = CadenceObservationStore(scratch / "cadence_probe.json", "continuumagent")
    was_new = cadence.ingest(dry_id, INGEST_AT)
    emit(f"    CadenceObservationStore.ingest(dry_run_id)    -> was_new={was_new}, "
         f"observation_count={cadence.observation_count()}")
    citation = CitationEdgeStore(scratch / "citation_probe.json", "continuumagent")
    was_new = citation.ingest(dry_id, "continuumagent", ["someone_else"], INGEST_AT)
    emit(f"    CitationEdgeStore.ingest(dry_run_id)          -> was_new={was_new}, "
         f"post_count={citation.post_count()}")

    emit()
    emit("[4] Contrast — a REAL id DOES mutate, proving the rejection is")
    emit("    namespace-specific and not a store that silently drops everything.")
    was_new = cadence.ingest("real-post-1", INGEST_AT)
    emit(f"    CadenceObservationStore.ingest('real-post-1') -> was_new={was_new}, "
         f"observation_count={cadence.observation_count()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--operator",
        default="operator",
        help="operator string recorded in the audit records (default: %(default)r — "
             "deliberately generic so the committed transcript makes no claim about who ran it)",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare output against the committed expected transcript; exit 1 on mismatch",
    )
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="a2-exercise-") as tmp:
        exercise_kill_switch(args.operator)
        exercise_dry_run(Path(tmp))

    rule("EXERCISE COMPLETE — no network call made, no production state touched.")
    transcript = "\n".join(_lines) + "\n"
    sys.stdout.write(transcript)

    if not args.check:
        return 0

    if not EXPECTED_PATH.exists():
        sys.stderr.write(f"\n--check: expected transcript not found at {EXPECTED_PATH}\n")
        return 1
    # Compared line-by-line rather than byte-for-byte: `.gitattributes` sets
    # `* text=auto`, so the committed transcript's line endings are whatever the
    # reviewer's platform checks out. The content comparison is still exact.
    expected = EXPECTED_PATH.read_text(encoding="utf-8-sig")
    if transcript.splitlines() == expected.splitlines():
        sys.stderr.write("\n--check: transcript matches the committed expected output.\n")
        return 0
    sys.stderr.write(
        "\n--check: TRANSCRIPT DIFFERS from the committed expected output.\n"
        "         Investigate before treating §A2 rows 4-5 as satisfied.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
