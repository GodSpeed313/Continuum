from pathlib import Path

from mcp_server import check_governance

FIXTURES = Path(__file__).parent.parent / "rift"


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
