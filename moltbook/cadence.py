"""
moltbook/cadence.py — CadenceIntegrity observation store, detector, and governance gate.

Implements docs/m7_cadence_integrity_ruling.md (LOCKED 2026-07-17), the first of the two
Longitudinal Constraints. Everything here is SELF-governance: the store holds the governed
agent's OWN post timestamps and nothing else — no content, no other accounts (ruling §1).

Three responsibilities, kept in ruling order:

  §4/§6 Observation store (persistent, deterministic)
        `CadenceObservationStore` persists post-ID → UTC-timestamp observations plus
        explicit gap records. Ingestion is idempotent by post ID; timestamps are
        normalized to UTC once, at ingestion. Profile state is a pure function of the
        stored history, so restarts — including restarts interleaved between every
        observation — cannot change the resulting MoltbookAgentProfile state (§6).

  §3/§4 Readiness gate + periodicity fit (application-level, NOT a Pi Script constraint)
        Below 4 valid intervals in the rolling window the constraint is NOT EVALUABLE:
        cadence_anomaly stays None (never defaulted to false — insufficient data ≠
        compliant) and the resolver is never invoked. The fit itself is mechanical:
        N consecutive intervals each within ±J seconds of a common period P (§4), with
        recorded gaps resetting the consecutive run rather than being bridged.

  §7   Enforcement plumbing
        `run_cadence_governance` submits the profile snapshot to the resolver only when
        ready, and on a CadenceIntegrity violation applies the client-side pause
        (`autonomous_posting_paused = true`) in the same step. Emitting escalate without
        applying the required client-side pause does not satisfy §7 (post-lock grammar
        correction) — which is why resolution and pause application live in one function
        rather than leaving the pause to a separate caller that could be skipped.
        The pause governs only FUTURE autonomous behavior; nothing here suppresses or
        retracts content already posted (§1/§9).
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from pi_script.resolver import resolve

# ── §5 parameters — ALL PROVISIONAL pending the 2026-07-19 cohort re-sample ──────
# Changing any of these values is a ruling amendment (§10), not a code change.
MIN_READY_INTERVALS = 4            # §3: ready at 5 posts = 4 valid intervals in-window
REQUIRED_CONSECUTIVE_INTERVALS = 5  # §5: N
JITTER_TOLERANCE_SECONDS = 5.0      # §5 as amended (Amendment 1, 2026-07-19): ±J; run spread
                                    # must fit within 2J. Widened ±3→±5 from the 7/19 cohort
                                    # grounding — real schedulers slip 6-17s, and ±3 sat at the
                                    # timestamp quantization floor (false-negative on the
                                    # flagship fixture). See
                                    # docs/m7_cadence_integrity_ruling_amendment_1.md A1.2.
ROLLING_WINDOW = timedelta(days=7)  # §5: matches the cohort re-sample cadence

PAUSE_REASON_CADENCE = "CadenceIntegrity violation: near-periodic posting pattern (ruling §7)"


def normalize_utc(ts: datetime | str) -> datetime:
    """
    §4/§6: normalize a post timestamp to UTC once, at ingestion. Accepts an ISO-8601
    string or datetime; a naive value is taken as already-UTC. Downstream code never
    re-normalizes — it only ever sees the aware-UTC value stored here.
    """
    if isinstance(ts, str):
        ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    if ts.tzinfo is None:
        return ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(timezone.utc)


@dataclass(frozen=True)
class CadenceGovernanceResult:
    """Outcome of one governance pass over the agent's cadence profile."""
    evaluated: bool          # False == NOT EVALUABLE (readiness gate, ruling §2/§3)
    trace: dict | None       # resolver trace when evaluated, else None
    rendered: str            # resolver rendering, or the §3 NOT EVALUABLE block
    exit_code: int           # resolver exit code when evaluated, else 0
    pause_applied: bool      # True when this pass applied the §7 client-side pause


class CadenceObservationStore:
    """
    Persistent, deterministic store of the governed agent's own post timestamps.

    File layout (JSON, ISO-8601 UTC throughout):
        observations       {post_id: timestamp}   — first write wins (idempotent, §4/§6)
        gaps               [timestamp, ...]       — explicit detector-recorded gaps (§4)
        paused             bool                   — §7 pause latch, survives restarts
        pause_reason       str | null
        anomaly_cleared_through  timestamp | null — set by human_reset(); §6/§7: clearing
                                                    cadence_anomaly never erases history,
                                                    so recompute honors this watermark
                                                    instead of re-latching the same run

    Profile state is recomputed from this file on every read — never cached across
    mutations — which is what makes A,B,C and A,restart,B,restart,C indistinguishable (§6).
    """

    def __init__(self, path: str | Path, agent_id: str) -> None:
        # Fail closed on a missing agent identity, mirroring the client's A1 stance:
        # a profile store either knows which agent it governs or does not construct.
        if not agent_id.strip():
            raise ValueError("agent_id is required: CadenceIntegrity governs a named agent only")
        self._path = Path(path)
        if self._path.exists():
            data = json.loads(self._path.read_text(encoding="utf-8"))
            if data.get("agent_id") != agent_id:
                raise ValueError(
                    f"store at {self._path} belongs to agent "
                    f"'{data.get('agent_id')}', not '{agent_id}'"
                )
            self._data = data
        else:
            self._data = {
                "agent_id": agent_id,
                "observations": {},
                "gaps": [],
                "paused": False,
                "pause_reason": None,
                "anomaly_cleared_through": None,
            }
            self._save()

    # ── Persistence ──────────────────────────────────────────────────────────────
    def _save(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    # ── Ingestion (§4/§6) ────────────────────────────────────────────────────────
    def ingest(self, post_id: str, timestamp: datetime | str) -> bool:
        """
        Record one of the agent's own posts. Idempotent by post ID: the first write
        wins and a re-ingest (same or different timestamp) changes nothing (§4/§6).
        Returns True if the observation was new.
        """
        if post_id in self._data["observations"]:
            return False
        self._data["observations"][post_id] = normalize_utc(timestamp).isoformat()
        self._save()
        return True

    def record_gap(self, timestamp: datetime | str) -> None:
        """
        Explicitly record a known observation gap (§4/§6: gaps are recorded, not
        inferred). Intervals spanning a recorded gap are not constructed — the gap
        resets the consecutive-interval count rather than counting for or against.
        """
        iso = normalize_utc(timestamp).isoformat()
        if iso not in self._data["gaps"]:
            self._data["gaps"].append(iso)
            self._save()

    # ── §7 pause latch (client-side state, distinct from frozen) ─────────────────
    @property
    def paused(self) -> bool:
        return bool(self._data["paused"])

    @property
    def pause_reason(self) -> str | None:
        return self._data["pause_reason"]

    def apply_pause(self, reason: str = PAUSE_REASON_CADENCE) -> None:
        self._data["paused"] = True
        self._data["pause_reason"] = reason
        self._save()

    def human_reset(self) -> None:
        """
        Explicit human review/reset (§7): clears the pause and cadence_anomaly, but
        never the observation history. The clearance watermark stops the recompute
        from immediately re-latching the exact run a human just reviewed, while any
        NEW post extending or restarting the pattern is still caught.
        """
        self._data["paused"] = False
        self._data["pause_reason"] = None
        obs = self._observations()
        self._data["anomaly_cleared_through"] = obs[-1][1].isoformat() if obs else None
        self._save()

    # ── Deterministic recompute (§3/§4/§6) ───────────────────────────────────────
    def _observations(self) -> list[tuple[str, datetime]]:
        """All observations, ordered by (timestamp, post_id) — a total order, so the
        result is independent of ingestion/restart interleaving (§6)."""
        parsed = [(pid, datetime.fromisoformat(iso)) for pid, iso in self._data["observations"].items()]
        return sorted(parsed, key=lambda p: (p[1], p[0]))

    def observation_count(self) -> int:
        return len(self._data["observations"])

    def _window_intervals(self) -> tuple[list[dict], datetime | None, datetime | None]:
        """
        Build consecutive-post intervals inside the current rolling window (§4).

        The window is anchored to the newest observation (end = max timestamp,
        start = end − 7 days) rather than the wall clock, so recompute is a pure
        function of stored history (§6). Older observations age out of the interval
        calculation here but are never deleted from the store.

        Returns (intervals, window_start, window_end); each interval carries its
        length in seconds and the timestamp of the post that ends it. A recorded gap
        between two posts suppresses that interval entirely (§4: never bridged).
        """
        obs = self._observations()
        if not obs:
            return [], None, None
        window_end = obs[-1][1]
        window_start = window_end - ROLLING_WINDOW
        in_window = [(pid, ts) for pid, ts in obs if ts >= window_start]
        gaps = [datetime.fromisoformat(g) for g in self._data["gaps"]]

        intervals: list[dict] = []
        for (_, a), (_, b) in zip(in_window, in_window[1:]):
            gap_between = any(a < g <= b for g in gaps)
            intervals.append({
                "seconds": (b - a).total_seconds(),
                "end_ts": b,
                "after_gap": gap_between,   # marks a break in consecutiveness
                "valid": not gap_between,
            })
        return intervals, window_start, window_end

    def _find_periodic_run(self, intervals: list[dict]) -> dict | None:
        """
        §4 periodicity fit: N consecutive valid intervals each within ±J seconds of a
        common period P. Implemented as the equivalent mechanical test that the run's
        spread (max − min) fits within 2J, with P fitted per run as the midrange —
        per-agent, never a fixed global period (§5). Runs whose final post is at or
        before the human-review clearance watermark are skipped (§7). Among matching
        runs the tightest spread wins (earliest on ties) — deterministic.
        """
        cleared_raw = self._data["anomaly_cleared_through"]
        cleared = datetime.fromisoformat(cleared_raw) if cleared_raw else None
        n = REQUIRED_CONSECUTIVE_INTERVALS

        # Split into consecutive segments: a recorded gap resets the run (§4).
        segments: list[list[dict]] = [[]]
        for iv in intervals:
            if iv["after_gap"]:
                segments.append([])
                continue
            segments[-1].append(iv)

        best: dict | None = None
        for seg in segments:
            for i in range(len(seg) - n + 1):
                run = seg[i:i + n]
                if cleared is not None and run[-1]["end_ts"] <= cleared:
                    continue
                lengths = [iv["seconds"] for iv in run]
                spread = max(lengths) - min(lengths)
                if spread > 2 * JITTER_TOLERANCE_SECONDS:
                    continue
                period = (max(lengths) + min(lengths)) / 2
                candidate = {
                    "period_seconds": period,
                    "max_jitter_seconds": max(abs(x - period) for x in lengths),
                    "spread": spread,
                }
                if best is None or candidate["spread"] < best["spread"]:
                    best = candidate
        return best

    def profile_state(self) -> dict[str, Any]:
        """
        The MoltbookAgentProfile entity state (ruling §2), recomputed deterministically
        from stored history (§6). While not ready, cadence_anomaly is None — an explicit
        unset state, never a default false (§3: insufficient data ≠ compliant).
        """
        intervals, w_start, w_end = self._window_intervals()
        valid = [iv for iv in intervals if iv["valid"]]
        ready = len(valid) >= MIN_READY_INTERVALS

        anomaly: bool | None = None
        period = jitter = 0
        if ready:
            # The full interval list goes in: gap-marked intervals act as segment
            # breaks inside the fit and never join a run themselves.
            match = self._find_periodic_run(intervals)
            anomaly = match is not None
            if match:
                period = int(round(match["period_seconds"]))
                jitter = int(round(match["max_jitter_seconds"]))

        return {
            "agent_id": self._data["agent_id"],
            "cadence_observation_ready": ready,
            "cadence_anomaly": anomaly,
            "observed_interval_count": len(valid),
            "common_period_seconds": period,     # whole seconds (post-lock correction)
            "max_jitter_seconds": jitter,        # whole seconds (post-lock correction)
            "rolling_window_start": w_start.isoformat() if w_start else "",
            "rolling_window_end": w_end.isoformat() if w_end else "",
        }


def render_not_evaluable(profile: dict[str, Any]) -> str:
    """The §3 NOT EVALUABLE trace block — rendered from the application-level gate,
    never from a Pi Script constraint reporting a non-violation (ruling §2)."""
    return (
        "CONSTRAINT: CadenceIntegrity\n"
        "Observation readiness : false\n"
        "Evaluation             : insufficient post history "
        f"({profile['observed_interval_count']}/{MIN_READY_INTERVALS} required intervals)\n"
        "Result                 : NOT EVALUABLE\n"
        "Action                 : none\n"
    )


def run_cadence_governance(
    ir: dict[str, Any],
    store: CadenceObservationStore,
    trigger_type: str = "event",
) -> CadenceGovernanceResult:
    """
    One full CadenceIntegrity governance pass (ruling §2/§3/§7):

      1. Recompute the profile. If not ready, stop at the application-level gate and
         render NOT EVALUABLE — the resolver never sees the rule (§2/§3).
      2. If ready, submit the MoltbookAgentProfile snapshot to the resolver.
      3. If CadenceIntegrity is violated, apply the client-side pause in the SAME
         step — emitting escalate without applying the required client-side pause
         does not satisfy §7.
    """
    profile = store.profile_state()
    if not profile["cadence_observation_ready"]:
        return CadenceGovernanceResult(
            evaluated=False,
            trace=None,
            rendered=render_not_evaluable(profile),
            exit_code=0,
            pause_applied=False,
        )

    snapshot = {
        "trigger_type": trigger_type,
        "entity": "MoltbookAgentProfile",
        "entity_state": dict(profile),
        "response_history": [],
    }
    trace, rendered, exit_code = resolve(ir, snapshot)

    pause_applied = False
    cadence = next(c for c in trace["constraints"] if c["name"] == "CadenceIntegrity")
    if cadence["status"] == "violated" and not store.paused:
        store.apply_pause()
        pause_applied = True

    return CadenceGovernanceResult(
        evaluated=True,
        trace=trace,
        rendered=rendered,
        exit_code=exit_code,
        pause_applied=pause_applied,
    )
