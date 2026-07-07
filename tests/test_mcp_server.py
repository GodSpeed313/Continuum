import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from mcp_server import check_governance

FIXTURES = Path(__file__).parent.parent / "rift"


def _run_one_persisted_call(args: tuple[str, str]) -> dict:
    """Module-level so it's picklable for ProcessPoolExecutor (Windows spawn)."""
    source, state_path = args
    state = {
        "trigger_type": "event",
        "entity": "Project",
        "entity_state": {"state": "active"},
    }
    return check_governance(source, state, source_type="pi", persist=True, state_path=state_path)


def _state(entity_state: dict) -> dict:
    return {
        "trigger_type": "event",
        "entity": "Project",
        "entity_state": entity_state,
    }


class TestCheckGovernancePi:
    def test_pi_source_dormant_satisfies_shelved_guard(self):
        # shelved_projects.pi enforces both ShelvedProjectGuard (state == "dormant")
        # and ActiveProjectGuard (state == "active") on Project simultaneously, so
        # no single state value satisfies both — check the specific constraint.
        source = (FIXTURES / "shelved_projects.pi").read_text(encoding="utf-8")
        result = check_governance(source, _state({"state": "dormant"}), source_type="pi")
        assert result["passed"] is False
        constraints = {c["name"]: c["status"] for c in result["trace"]["constraints"]}
        assert constraints["ShelvedProjectGuard"] == "satisfied"
        assert constraints["ActiveProjectGuard"] == "violated"

    def test_pi_source_violated(self):
        source = (FIXTURES / "shelved_projects.pi").read_text(encoding="utf-8")
        result = check_governance(source, _state({"state": "active"}), source_type="pi")
        assert result["passed"] is False
        assert "VIOLATION DETECTED" in result["rendered_trace"]

    def test_pi_source_invalid_returns_errors(self):
        result = check_governance("not a valid policy", _state({"state": "dormant"}), source_type="pi")
        assert result["passed"] is False
        assert "errors" in result


class TestCheckGovernanceRift:
    def test_rift_source_compiles_and_evaluates(self):
        source = (FIXTURES / "shelved_projects.rift").read_text(encoding="utf-8")
        result = check_governance(source, _state({"state": "active"}), source_type="rift")
        assert result["passed"] is False
        assert "rendered_trace" in result

    def test_rift_source_dormant_satisfies_shelved_guard(self):
        source = (FIXTURES / "shelved_projects.rift").read_text(encoding="utf-8")
        result = check_governance(source, _state({"state": "dormant"}), source_type="rift")
        constraints = {c["name"]: c["status"] for c in result["trace"]["constraints"]}
        assert constraints["ShelvedProjectGuard"] == "satisfied"


class TestCheckGovernanceSourceType:
    def test_invalid_source_type_rejected(self):
        result = check_governance("anything", _state({"state": "dormant"}), source_type="bogus")
        assert result["passed"] is False
        assert "errors" in result


class TestCheckGovernancePersist:
    def test_persist_requires_state_path(self):
        source = (FIXTURES / "shelved_projects.pi").read_text(encoding="utf-8")
        result = check_governance(source, _state({"state": "active"}), source_type="pi", persist=True)
        assert result["passed"] is False
        assert "errors" in result

    def test_persist_writes_state_and_trace_on_violation(self, tmp_path):
        source = (FIXTURES / "shelved_projects.pi").read_text(encoding="utf-8")
        state_path = tmp_path / "state.json"

        result = check_governance(
            source, _state({"state": "active"}), source_type="pi",
            persist=True, state_path=str(state_path),
        )

        assert result["passed"] is False
        assert result["persisted"] is True
        assert "trace_file" in result
        assert Path(result["trace_file"]).exists()

        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["violation_counts"]["ShelvedProjectGuard"] == 1

    def test_persist_carries_violation_counts_forward_across_calls(self, tmp_path):
        source = (FIXTURES / "shelved_projects.pi").read_text(encoding="utf-8")
        state_path = tmp_path / "state.json"

        for expected_count in (1, 2, 3):
            result = check_governance(
                source, _state({"state": "active"}), source_type="pi",
                persist=True, state_path=str(state_path),
            )
            assert result["trace"]["updated_violation_counts"]["ShelvedProjectGuard"] == expected_count

    def test_persist_is_safe_under_concurrent_processes(self, tmp_path):
        # The whole point of the file lock: N processes hitting the same
        # state_path concurrently must not lose any violation-count increments
        # or collide on trace filenames.
        source = (FIXTURES / "shelved_projects.pi").read_text(encoding="utf-8")
        state_path = tmp_path / "state.json"
        n_calls = 8

        with ProcessPoolExecutor(max_workers=n_calls) as pool:
            results = list(pool.map(_run_one_persisted_call, [(source, str(state_path))] * n_calls))

        assert all(r["persisted"] for r in results)

        saved = json.loads(state_path.read_text(encoding="utf-8"))
        assert saved["violation_counts"]["ShelvedProjectGuard"] == n_calls

        trace_files = list((tmp_path / "traces").glob("*.txt"))
        assert len(trace_files) == n_calls
