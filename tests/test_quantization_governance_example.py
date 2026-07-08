from pathlib import Path

from pi_script.resolver import resolve
from pi_script.validator import validate_file

SPEC = Path(__file__).parent.parent / "examples" / "quantization_governance.pi"


def _resolve(memory_latency_ratio, signal_quality, outlier_intensity):
    ok, errors, ir = validate_file(str(SPEC))
    assert ok, errors
    state = {
        "trigger_type": "event",
        "entity": "QuantizationEngine",
        "entity_state": {
            "memory_latency_ratio": memory_latency_ratio,
            "signal_quality": signal_quality,
            "outlier_intensity": outlier_intensity,
        },
    }
    return resolve(ir, state)


class TestQuantizationGovernanceSpec:
    def test_validates_clean(self):
        ok, errors, ir = validate_file(str(SPEC))
        assert ok, errors
        assert set(ir["constraints"]) == {"HardwareIntegrity", "SignalStability", "GranularityShift"}

    def test_all_constraints_satisfied_within_bounds(self):
        trace, rendered, exit_code = _resolve(0.5, "nominal", 3)
        assert exit_code == 0
        statuses = {c["name"]: c["status"] for c in trace["constraints"]}
        assert statuses == {
            "HardwareIntegrity": "satisfied",
            "SignalStability": "satisfied",
            "GranularityShift": "satisfied",
        }

    def test_hardware_integrity_bound_rule_fires_at_threshold(self):
        # Ruling 9.9 bound_rule: "must remain < 0.8" — this is the exact
        # constraint that used the invalid "must remain below 0.8" syntax
        # before Ruling 9.9 introduced Form 7.
        trace, rendered, exit_code = _resolve(0.85, "nominal", 3)
        assert exit_code == 1
        statuses = {c["name"]: c["status"] for c in trace["constraints"]}
        assert statuses["HardwareIntegrity"] == "violated"

    def test_hardware_integrity_satisfied_just_under_threshold(self):
        trace, rendered, exit_code = _resolve(0.79, "nominal", 3)
        statuses = {c["name"]: c["status"] for c in trace["constraints"]}
        assert statuses["HardwareIntegrity"] == "satisfied"

    def test_signal_stability_and_granularity_shift_violate_together(self):
        trace, rendered, exit_code = _resolve(0.5, "unstable", 15)
        assert exit_code == 1
        statuses = {c["name"]: c["status"] for c in trace["constraints"]}
        assert statuses["SignalStability"] == "violated"
        assert statuses["GranularityShift"] == "violated"
        assert statuses["HardwareIntegrity"] == "satisfied"
