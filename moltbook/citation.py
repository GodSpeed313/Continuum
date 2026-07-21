"""
moltbook/citation.py — CitationClusterIntegrity edge store, detector, and governance gate.

Implements docs/m7_citation_cluster_integrity_ruling.md (LOCKED 2026-07-18), the second of
the two Longitudinal Constraints. Everything here is SELF-governance: only the governed
agent's OWN outbound citations can establish a violation. Incoming citations to the agent
are context — usable to compute reciprocity, never sufficient alone to set the flag (§1/§4).

Three responsibilities, kept in ruling order:

  §4/§6 Edge store (persistent, deterministic, DIRECTIONAL)
        `CitationEdgeStore` persists post-ID → {source, targets, timestamp} records plus
        explicit gap records, built from the same post ingestion pipeline as the cadence
        store — extracting edges instead of timestamps (§4). Edges are directional and are
        never collapsed to undirected before attribution. Ingestion is idempotent by post
        ID; profile state is a pure function of the stored history (§6).

  §3/§4/§5 Readiness gate + cluster-shape fit (application-level, NOT a Pi Script constraint)
        §5: every normative threshold is UNDEFINED until a ruling amendment grounds it in
        real M7 citation history. There is deliberately no grounded default in this module —
        parameters must be injected (`CitationClusterParameters`), and with none injected
        `citation_observation_ready` can never become true, so the constraint renders
        NOT EVALUABLE and cannot fire. That is the ruling's safe default, not a gap.
        Tests inject synthetic parameters to prove the MECHANISM (§8's required positive
        fixture); those values assert nothing about Moltbook.

  §7   Enforcement plumbing
        `run_citation_governance` submits the profile snapshot to the resolver only when
        ready, and on a CitationClusterIntegrity violation applies the client-side pause
        (`autonomous_posting_paused = true`) in the same step — emitting escalate without
        applying the required pause does not satisfy §7. The pause governs only FUTURE
        autonomous behavior; nothing here suppresses or retracts content already posted.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from pi_script.resolver import resolve
from moltbook.cadence import normalize_utc
from moltbook.dryrun import is_dry_run_id

# §5: the rolling window is the ONE grounded parameter — inherited directly from
# CadenceIntegrity §5 (same cohort-cadence rationale), not independently re-derived.
ROLLING_WINDOW = timedelta(days=7)

PAUSE_REASON_CITATION = (
    "CitationClusterIntegrity violation: outbound citations sustaining a closed "
    "reciprocal cluster (ruling §7)"
)


@dataclass(frozen=True)
class CitationClusterParameters:
    """
    The §5 normative thresholds. NO defaults, by design: production code has no grounded
    values to offer until the first real M7 citation activity triggers the §5/§10
    amendment. Constructing this object is a claim that grounded values exist — which is
    why the module ships no instance of it.
    """
    min_outbound_edges: int          # §3 readiness floor AND §4 causal-attribution minimum
    min_cluster_size: int            # §4: "small" has a lower bound before it's a cluster
    min_reciprocal_edges: int        # §4: how many mutual pairs make "tightly reciprocal"
    max_external_degree_ratio: float  # §4: how isolated "low-external-degree" means


@dataclass(frozen=True)
class CitationGovernanceResult:
    """Outcome of one governance pass over the agent's citation profile."""
    evaluated: bool          # False == NOT EVALUABLE (readiness gate, ruling §3/§5)
    trace: dict | None       # resolver trace when evaluated, else None
    rendered: str            # resolver rendering, or the §3 NOT EVALUABLE block
    exit_code: int           # resolver exit code when evaluated, else 0
    pause_applied: bool      # True when this pass applied the §7 client-side pause


class CitationEdgeStore:
    """
    Persistent, deterministic store of directional citation edges.

    One record per post, from the same ingestion pipeline as the cadence store (§4):
    the governed agent's own posts contribute OUTBOUND edges (attributable conduct);
    observed external posts contribute context edges (reciprocity evidence only).

    File layout (JSON, ISO-8601 UTC throughout):
        posts              {post_id: {source, targets, timestamp}}  — first write wins (§4/§6)
        gaps               [timestamp, ...]   — explicit detector-recorded gaps (§4)
        paused             bool               — §7 pause latch, survives restarts
        pause_reason       str | null
        cluster_cleared_through  timestamp | null — set by human_reset(); §6/§7: clearing
                                                    the flag never erases edge history, so
                                                    recompute honors this watermark instead
                                                    of re-latching the reviewed cluster

    Profile state is recomputed from this file on every read — never cached across
    mutations — so A,B,C and A,restart,B,restart,C are indistinguishable (§6).
    """

    def __init__(self, path: str | Path, agent_id: str) -> None:
        # Fail closed on a missing agent identity (same stance as the cadence store /
        # addendum A1): the store either knows which agent it governs or does not construct.
        if not agent_id.strip():
            raise ValueError(
                "agent_id is required: CitationClusterIntegrity governs a named agent only"
            )
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
                "posts": {},
                "gaps": [],
                "paused": False,
                "pause_reason": None,
                "cluster_cleared_through": None,
            }
            self._save()

    # ── Persistence ──────────────────────────────────────────────────────────────
    def _save(self) -> None:
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(json.dumps(self._data, indent=2), encoding="utf-8")
        os.replace(tmp, self._path)

    # ── Ingestion (§4/§6) ────────────────────────────────────────────────────────
    @staticmethod
    def _clean_handle(handle: str) -> str:
        return handle.strip().lstrip("@")

    def ingest(
        self,
        post_id: str,
        source: str,
        cited: Iterable[str],
        timestamp: datetime | str,
    ) -> bool:
        """
        Record one post's citation edges: `source` → each handle in `cited`, directional.
        Self-citations are dropped (a self-loop is not a relationship between accounts).
        Idempotent by post ID: the first write wins and a re-ingest (same or different
        edges) changes nothing (§4/§6). Returns True if the record was new.

        Structural dry-run isolation (transport spec §11): an ID in the reserved
        dry-run namespace is rejected here, at the store boundary, regardless of what
        called ingest() — a dry-run action must never enter the citation graph.
        """
        if is_dry_run_id(post_id):
            return False
        if post_id in self._data["posts"]:
            return False
        src = self._clean_handle(source)
        targets = sorted({
            t for t in (self._clean_handle(c) for c in cited) if t and t != src
        })
        self._data["posts"][post_id] = {
            "source": src,
            "targets": targets,
            "timestamp": normalize_utc(timestamp).isoformat(),
        }
        self._save()
        return True

    def record_gap(self, timestamp: datetime | str) -> None:
        """
        Explicitly record a known observation gap (§4/§6: gaps are recorded, not
        inferred). For a graph there is no run to reset; the record marks the edge
        history as known-incomplete around that time and is preserved for audit.
        """
        iso = normalize_utc(timestamp).isoformat()
        if iso not in self._data["gaps"]:
            self._data["gaps"].append(iso)
            self._save()

    def post_count(self) -> int:
        return len(self._data["posts"])

    # ── §7 pause latch (client-side state, distinct from frozen) ─────────────────
    @property
    def paused(self) -> bool:
        return bool(self._data["paused"])

    @property
    def pause_reason(self) -> str | None:
        return self._data["pause_reason"]

    def apply_pause(self, reason: str = PAUSE_REASON_CITATION) -> None:
        self._data["paused"] = True
        self._data["pause_reason"] = reason
        self._save()

    def human_reset(self) -> None:
        """
        Explicit human review/reset (§7): clears the pause and citation_cluster_flag,
        never the edge history. The clearance watermark forgives the cluster as
        reviewed — a NEW outbound citation from the governed agent into that cluster
        is sustaining it afresh and re-fires.
        """
        self._data["paused"] = False
        self._data["pause_reason"] = None
        newest = self._records()
        self._data["cluster_cleared_through"] = (
            newest[-1][2].isoformat() if newest else None
        )
        self._save()

    # ── Deterministic recompute (§3/§4/§6) ───────────────────────────────────────
    def _records(self) -> list[tuple[str, dict, datetime]]:
        """All post records ordered by (timestamp, post_id) — a total order, so the
        result is independent of ingestion/restart interleaving (§6)."""
        parsed = [
            (pid, rec, datetime.fromisoformat(rec["timestamp"]))
            for pid, rec in self._data["posts"].items()
        ]
        return sorted(parsed, key=lambda r: (r[2], r[0]))

    def _window_edges(self) -> tuple[list[dict], datetime | None, datetime | None]:
        """
        Directional edge instances inside the current rolling window (§4).

        The window is anchored to the newest ingested post (end = max timestamp,
        start = end − 7 days) rather than the wall clock, so recompute is a pure
        function of stored history (§6) — the same anchoring rule as the cadence
        store, which is what lets the two constraints share the entity's
        rolling-window fields (§2). Older records age out of the calculation here
        but are never deleted from the store.
        """
        records = self._records()
        if not records:
            return [], None, None
        window_end = records[-1][2]
        window_start = window_end - ROLLING_WINDOW
        edges: list[dict] = []
        for pid, rec, ts in records:
            if ts < window_start:
                continue
            for target in rec["targets"]:
                edges.append({
                    "post_id": pid,
                    "source": rec["source"],
                    "target": target,
                    "ts": ts,
                })
        return edges, window_start, window_end

    def profile_state(
        self, params: CitationClusterParameters | None = None
    ) -> dict[str, Any]:
        """
        The MoltbookAgentProfile citation state (ruling §2), recomputed
        deterministically from stored history (§6).

        The graph metrics are parameter-free and always computed; only readiness and
        the flag need §5 thresholds. With `params=None` (the production state until
        the grounding amendment) readiness is structurally false and
        `citation_cluster_flag` stays None — an explicit unset, never a default
        false (§3: insufficient data ≠ compliant; §5: no enforcement without grounding).

        Mechanical definitions (§4, directional throughout):
          - outbound edge: instance with source == the governed agent
          - mutual partner: X where agent→X and X→agent both exist in-window
          - cluster: the agent plus its mutual partners (the closed structure the
            agent is a PARTICIPANT in — accounts merely citing the agent never
            enter it, which is the §1/§4 guilt-by-association boundary)
          - reciprocal_edge_count: unordered pairs within the cluster with BOTH
            directions present
          - external_edge_count: instances from a cluster member to a non-member;
            the external-degree ratio is external / (internal + external)
        """
        edges, w_start, w_end = self._window_edges()
        agent = self._data["agent_id"]

        pairs = {(e["source"], e["target"]) for e in edges}
        outbound = [e for e in edges if e["source"] == agent]

        partners = {
            t for (s, t) in pairs
            if s == agent and (t, agent) in pairs
        }
        cluster = {agent} | partners
        members = sorted(cluster)
        reciprocal_pairs = {
            (u, v)
            for i, u in enumerate(members)
            for v in members[i + 1:]
            if (u, v) in pairs and (v, u) in pairs
        }
        internal = [e for e in edges if e["source"] in cluster and e["target"] in cluster]
        external = [e for e in edges if e["source"] in cluster and e["target"] not in cluster]
        outbound_in_cluster = [e for e in outbound if e["target"] in partners]

        ready = params is not None and len(outbound) >= params.min_outbound_edges

        flag: bool | None = None
        if ready:
            assert params is not None
            total = len(internal) + len(external)
            ratio = (len(external) / total) if total else 0.0
            cleared_raw = self._data["cluster_cleared_through"]
            cleared = datetime.fromisoformat(cleared_raw) if cleared_raw else None
            newest_contribution = max(
                (e["ts"] for e in outbound_in_cluster), default=None
            )
            flag = (
                # §4 causal attribution: the agent's own outbound edges into the
                # cluster meet the minimum — incoming citations never suffice.
                len(outbound_in_cluster) >= params.min_outbound_edges
                # §4 shape, not magnitude:
                and len(cluster) >= params.min_cluster_size
                and len(reciprocal_pairs) >= params.min_reciprocal_edges
                and ratio <= params.max_external_degree_ratio
                # §7 watermark: the reviewed cluster is forgiven; a new outbound
                # contribution after review is sustaining it afresh.
                and newest_contribution is not None
                and (cleared is None or newest_contribution > cleared)
            )

        return {
            "agent_id": agent,
            "citation_observation_ready": ready,
            "citation_cluster_flag": flag,
            "cluster_size": len(cluster) if partners else 0,
            "m7_outbound_edge_count": len(outbound),
            "reciprocal_edge_count": len(reciprocal_pairs),
            "external_edge_count": len(external),
            "rolling_window_start": w_start.isoformat() if w_start else "",
            "rolling_window_end": w_end.isoformat() if w_end else "",
        }


def render_not_evaluable(
    profile: dict[str, Any], params: CitationClusterParameters | None
) -> str:
    """The §3 NOT EVALUABLE trace block — rendered from the application-level gate,
    never from a Pi Script constraint reporting a non-violation (ruling §2). The two
    not-ready causes are kept distinct: ungrounded parameters (§5, the production
    state until the amendment) vs. insufficient outbound history (§3)."""
    if params is None:
        reason = "parameters ungrounded (ruling §5 — no amendment has set thresholds yet)"
    else:
        reason = (
            "insufficient outbound citation history "
            f"({profile['m7_outbound_edge_count']}/{params.min_outbound_edges} required edges)"
        )
    return (
        "CONSTRAINT: CitationClusterIntegrity\n"
        "Observation readiness : false\n"
        f"Evaluation             : {reason}\n"
        "Result                 : NOT EVALUABLE\n"
        "Action                 : none\n"
    )


def run_citation_governance(
    ir: dict[str, Any],
    store: CitationEdgeStore,
    params: CitationClusterParameters | None = None,
    trigger_type: str = "event",
) -> CitationGovernanceResult:
    """
    One full CitationClusterIntegrity governance pass (ruling §2/§3/§5/§7):

      1. Recompute the profile. If not ready — including the production state where no
         grounded parameters exist (§5) — stop at the application-level gate and render
         NOT EVALUABLE; the resolver never sees the rule.
      2. If ready, submit the MoltbookAgentProfile snapshot to the resolver. (The
         cadence fields are absent from this snapshot, so CadenceIntegrity reports
         suspended in this pass — each longitudinal constraint is evaluated by its own
         governance pass against its own store.)
      3. If CitationClusterIntegrity is violated, apply the client-side pause in the
         SAME step — emitting escalate without applying the required pause does not
         satisfy §7.
    """
    profile = store.profile_state(params)
    if not profile["citation_observation_ready"]:
        return CitationGovernanceResult(
            evaluated=False,
            trace=None,
            rendered=render_not_evaluable(profile, params),
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
    result = next(c for c in trace["constraints"] if c["name"] == "CitationClusterIntegrity")
    if result["status"] == "violated" and not store.paused:
        store.apply_pause()
        pause_applied = True

    return CitationGovernanceResult(
        evaluated=True,
        trace=trace,
        rendered=rendered,
        exit_code=exit_code,
        pause_applied=pause_applied,
    )
