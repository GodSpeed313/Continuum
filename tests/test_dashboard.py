import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from dashboard import build_app, discover_systems


@pytest.fixture
def governed_root(tmp_path):
    """A fake repo root with two governed systems: one with violations and
    trace files, one clean with no traces dir at all."""
    m5 = tmp_path / "m5"
    m5.mkdir()
    (m5 / "state.json").write_text(json.dumps({
        "trigger_type": "event",
        "entity": "ContinuumSession",
        "entity_state": {"scope_flag": False},
        "violation_counts": {"ScopeGuard": 2},
    }), encoding="utf-8")
    traces = m5 / "traces"
    traces.mkdir()
    (traces / "2026-05-17_221511.txt").write_text("RESOLUTION TRACE\nScopeGuard violated", encoding="utf-8")
    (traces / "2026-05-29_163949.txt").write_text("RESOLUTION TRACE\n<script>alert(1)</script>", encoding="utf-8")

    es = tmp_path / "es"
    es.mkdir()
    (es / "state.json").write_text(json.dumps({
        "trigger_type": "event",
        "entity": "ElasticsearchIndex",
        "entity_state": {"schema_intact": True},
    }), encoding="utf-8")

    # A subdirectory with no state.json at all shouldn't show up as a system.
    (tmp_path / "docs").mkdir()

    return tmp_path


class TestDiscoverSystems:
    def test_finds_systems_with_state_json_only(self, governed_root):
        systems = discover_systems(governed_root)
        assert set(systems) == {"m5", "es"}

    def test_violation_counts_and_trace_files(self, governed_root):
        systems = discover_systems(governed_root)
        assert systems["m5"]["violation_counts"] == {"ScopeGuard": 2}
        assert len(systems["m5"]["trace_files"]) == 2
        # es has no traces/ dir at all — should degrade to an empty list, not error
        assert systems["es"]["trace_files"] == []
        assert systems["es"]["violation_counts"] == {}

    def test_ignores_dirs_without_state_json(self, governed_root):
        systems = discover_systems(governed_root)
        assert "docs" not in systems


class TestDashboardRoutes:
    def test_index_lists_both_systems(self, governed_root):
        client = TestClient(build_app(governed_root))
        resp = client.get("/")
        assert resp.status_code == 200
        assert "m5" in resp.text
        assert "es" in resp.text
        assert "ContinuumSession" in resp.text

    def test_system_detail_lists_trace_files(self, governed_root):
        client = TestClient(build_app(governed_root))
        resp = client.get("/system/m5")
        assert resp.status_code == 200
        assert "2026-05-17_221511.txt" in resp.text
        assert "ScopeGuard" in resp.text

    def test_system_detail_unknown_system_404s(self, governed_root):
        client = TestClient(build_app(governed_root))
        resp = client.get("/system/nonexistent")
        assert resp.status_code == 404

    def test_trace_detail_renders_and_escapes_content(self, governed_root):
        client = TestClient(build_app(governed_root))
        resp = client.get("/system/m5/trace/2026-05-29_163949.txt")
        assert resp.status_code == 200
        # the raw trace contains a <script> tag as *content* — must be escaped,
        # not rendered, or this becomes a stored-XSS vector against a local tool
        assert "<script>" not in resp.text
        assert "&lt;script&gt;" in resp.text

    def test_trace_detail_unknown_filename_404s_not_arbitrary_read(self, governed_root):
        # only filenames actually discovered via discover_systems are servable —
        # this proves an unrelated file can't be read through this route
        secret = governed_root / "not_a_trace.txt"
        secret.write_text("should not be reachable", encoding="utf-8")
        client = TestClient(build_app(governed_root))
        resp = client.get("/system/m5/trace/not_a_trace.txt")
        assert resp.status_code == 404

    def test_trace_detail_path_traversal_rejected(self, governed_root):
        client = TestClient(build_app(governed_root))
        resp = client.get("/system/m5/trace/..%2F..%2Fstate.json")
        assert resp.status_code == 404
