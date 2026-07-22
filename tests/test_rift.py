"""Rift v0.1 tests — parser, validator, compiler.
Rift v0.2 tests — declaration matcher (Rift Ruling 3.1),
declaration-resolution session (Rift Ruling 3.2)."""

from pathlib import Path

import pytest

from rift.parser import parse_string, parse_file
from rift.validator import RiftValidator, validate_file
from rift.compiler import RiftCompiler
from rift.matcher import (
    MatchResult,
    match_declaration,
    render_match,
    validate_match_result,
)
from rift.session import Resolution, RiftSession

RIFT_DIR          = Path(__file__).parent.parent / "rift"
SHELVED_RIFT      = RIFT_DIR / "shelved_projects.rift"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse(source: str):
    tree, err = parse_string(source, source_name="<test>")
    assert err is None, f"Parse error (fix test source): {err}"
    return tree


def _validate(source: str):
    tree = _parse(source)
    return RiftValidator(tree).validate()


def _compile(source: str) -> str:
    ok, errors, ir = _validate(source)
    assert ok, "Validation failed (fix test source): " + "\n".join(errors)
    return RiftCompiler(ir, source_name="<test>").compile()


# ─────────────────────────────────────────────────────────────────────────────
# Parser tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRiftParser:
    def test_shelved_projects_parses(self):
        """Canonical test file parses without error."""
        tree, err = parse_file(SHELVED_RIFT)
        assert err is None, f"Parse failed:\n{err}"
        assert tree is not None

    def test_minimal_valid_program(self):
        """One map + one intent is the minimum valid Rift program."""
        source = """\
map "I shelved [project]" -> project.state: dormant

intent RespectShelfedProjects {
    when user declares: "I shelved [project]"
    treat: [project] as dormant
    generates: Pi Script constraint ShelvedProjectGuard
}
"""
        tree, err = parse_string(source)
        assert err is None, f"Parse failed:\n{err}"
        assert tree is not None

    def test_ascii_arrow_accepted(self):
        source = 'map "archive [item]" -> item.status: archived\n'
        tree, err = parse_string(source)
        assert err is None

    def test_unicode_arrow_accepted(self):
        source = 'map "archive [item]" → item.status: archived\n'
        tree, err = parse_string(source)
        assert err is None

    def test_bad_syntax_returns_error_string(self):
        tree, err = parse_string("intent {}", source_name="<test>")
        assert tree is None
        assert isinstance(err, str) and len(err) > 0

    def test_empty_source_returns_error(self):
        tree, err = parse_string("", source_name="<test>")
        assert tree is None
        assert err is not None

    def test_all_optional_clauses_accepted(self):
        source = """\
map "freeze [project]" -> project.status: frozen

intent HardFreeze {
    when user declares: "freeze [project]"
    treat: [project] as frozen
    until: user declares "unfreeze [project]"
    enforce: "do not modify [project] under any circumstances"
    generates: Pi Script constraint HardFreezeGuard
    @priority: critical
}
"""
        tree, err = parse_string(source)
        assert err is None, f"Parse failed:\n{err}"

    def test_releases_clause_accepted(self):
        source = """\
map "revisit [project]" -> project.state: active

intent Reactivate {
    when user declares: "revisit [project]"
    treat: [project] as active
    releases: RespectShelfed for [project]
    generates: Pi Script constraint ActiveGuard
}
"""
        tree, err = parse_string(source)
        assert err is None

    def test_hand_written_constraint_accepted(self):
        source = """\
constraint ManualGuard {
    priority: high
    rule: "project.state must equal dormant"
    on_violation: flag
}
"""
        tree, err = parse_string(source)
        assert err is None

    def test_comment_lines_ignored(self):
        source = """\
// This is a comment
map "shelve [item]" -> item.state: dormant  // inline comment
"""
        tree, err = parse_string(source)
        assert err is None

    def test_block_comment_ignored(self):
        source = """\
/* block comment */
map "shelve [item]" -> item.state: dormant
"""
        tree, err = parse_string(source)
        assert err is None


# ─────────────────────────────────────────────────────────────────────────────
# Validator tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRiftValidator:
    def test_shelved_projects_validates_clean(self):
        """Canonical file passes all semantic checks."""
        ok, errors, ir = validate_file(str(SHELVED_RIFT))
        assert ok, "Validation errors:\n" + "\n".join(errors)

    def test_ir_intents_extracted(self):
        ok, errors, ir = validate_file(str(SHELVED_RIFT))
        assert ok
        assert "RespectShelfedProjects" in ir["intents"]
        assert "ReactivateProject" in ir["intents"]

    def test_ir_intent_when_field(self):
        _, _, ir = validate_file(str(SHELVED_RIFT))
        rec = ir["intents"]["RespectShelfedProjects"]
        assert rec["when"] == "I shelved [project]"

    def test_ir_intent_treat_field(self):
        _, _, ir = validate_file(str(SHELVED_RIFT))
        rec = ir["intents"]["RespectShelfedProjects"]
        assert rec["treat"] == {"capture": "project", "as": "dormant"}

    def test_ir_intent_generates_field(self):
        _, _, ir = validate_file(str(SHELVED_RIFT))
        rec = ir["intents"]["RespectShelfedProjects"]
        assert rec["generates"] == "ShelvedProjectGuard"

    def test_ir_maps_extracted(self):
        _, _, ir = validate_file(str(SHELVED_RIFT))
        patterns = [m["pattern"] for m in ir["maps"]]
        assert "I shelved [project]" in patterns
        assert "let's revisit [project]" in patterns

    def test_ir_releases_extracted(self):
        _, _, ir = validate_file(str(SHELVED_RIFT))
        rec = ir["intents"]["ReactivateProject"]
        assert rec["releases"] == {"intent": "RespectShelfedProjects", "capture": "project"}

    def test_duplicate_intent_name_rejected(self):
        source = """\
map "do [x]" -> x.state: done

intent A {
    when user declares: "do [x]"
    treat: [x] as done
    generates: Pi Script constraint G1
}

intent A {
    when user declares: "do [x]"
    treat: [x] as done
    generates: Pi Script constraint G2
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("Duplicate intent" in e and "A" in e for e in errors)

    def test_treat_capture_not_in_when_rejected(self):
        source = """\
map "do [x]" -> x.state: done

intent BadCapture {
    when user declares: "do [x]"
    treat: [y] as done
    generates: Pi Script constraint G
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("y" in e for e in errors)

    def test_releases_undeclared_intent_rejected(self):
        source = """\
map "do [x]" -> x.state: done

intent DoThing {
    when user declares: "do [x]"
    treat: [x] as done
    releases: NonExistent for [x]
    generates: Pi Script constraint G
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("NonExistent" in e for e in errors)

    def test_duplicate_generates_names_rejected(self):
        source = """\
map "do [x]" -> x.state: done
map "undo [x]" -> x.state: undone

intent A {
    when user declares: "do [x]"
    treat: [x] as done
    generates: Pi Script constraint SameName
}

intent B {
    when user declares: "undo [x]"
    treat: [x] as undone
    generates: Pi Script constraint SameName
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("SameName" in e for e in errors)

    def test_missing_when_clause_rejected(self):
        source = """\
map "do [x]" -> x.state: done

intent NoWhen {
    treat: [x] as done
    generates: Pi Script constraint G
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("when" in e for e in errors)

    def test_missing_treat_clause_rejected(self):
        source = """\
map "do [x]" -> x.state: done

intent NoTreat {
    when user declares: "do [x]"
    generates: Pi Script constraint G
}
"""
        ok, errors, _ = _validate(source)
        assert not ok
        assert any("treat" in e for e in errors)


# ─────────────────────────────────────────────────────────────────────────────
# Compiler tests
# ─────────────────────────────────────────────────────────────────────────────

class TestRiftCompiler:
    def test_shelved_projects_compiles(self):
        """Canonical file compiles without error."""
        from rift.compiler import compile_file
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pi", delete=False) as f:
            out = f.name
        try:
            success, result = compile_file(str(SHELVED_RIFT), out)
            assert success, f"Compile failed: {result}"
            assert Path(out).exists()
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_output_is_valid_pi_script(self):
        """Compiled output passes the Pi Script validator."""
        from rift.compiler import compile_file
        from pi_script.validator import validate_file as pi_validate_file
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix=".pi", delete=False) as f:
            out = f.name
        try:
            success, _ = compile_file(str(SHELVED_RIFT), out)
            assert success
            ok, errors, _ = pi_validate_file(out)
            assert ok, "Generated Pi Script failed validation:\n" + "\n".join(errors)
        finally:
            if os.path.exists(out):
                os.unlink(out)

    def test_domain_block_emitted(self):
        pi_src = _compile("""\
map "shelve [p]" -> p.state: dormant
intent A {
    when user declares: "shelve [p]"
    treat: [p] as dormant
    generates: Pi Script constraint G
}
""")
        assert "domain rift_generated" in pi_src
        assert "audit_interval: 1 hour" in pi_src

    def test_entity_emitted_in_pascal_case(self):
        pi_src = _compile("""\
map "shelve [p]" -> p.state: dormant
intent A {
    when user declares: "shelve [p]"
    treat: [p] as dormant
    generates: Pi Script constraint G
}
""")
        assert "entity P {" in pi_src

    def test_map_blocks_emitted(self):
        pi_src = _compile("""\
map "shelve [p]" -> p.state: dormant
intent A {
    when user declares: "shelve [p]"
    treat: [p] as dormant
    generates: Pi Script constraint G
}
""")
        assert "map DormantMap" in pi_src
        assert 'maps_to:  "dormant"' in pi_src

    def test_constraint_rule_emitted(self):
        pi_src = _compile("""\
map "shelve [p]" -> p.state: dormant
intent A {
    when user declares: "shelve [p]"
    treat: [p] as dormant
    generates: Pi Script constraint ShelvedGuard
}
""")
        assert "constraint ShelvedGuard" in pi_src
        assert 'P.state must equal "dormant"' in pi_src

    def test_enforce_block_emitted(self):
        pi_src = _compile("""\
map "shelve [p]" -> p.state: dormant
intent A {
    when user declares: "shelve [p]"
    treat: [p] as dormant
    generates: Pi Script constraint G
}
""")
        assert "enforce {" in pi_src
        assert "entity:      P" in pi_src
        assert "[G]" in pi_src

    def test_priority_annotation_propagates(self):
        pi_src = _compile("""\
map "freeze [p]" -> p.state: frozen
intent FreezeIt {
    when user declares: "freeze [p]"
    treat: [p] as frozen
    generates: Pi Script constraint FreezeGuard
    @priority: critical
}
""")
        assert "priority:     critical" in pi_src

    def test_multiple_intents_emit_multiple_constraints(self):
        pi_src = _compile("""\
map "shelve [p]" -> p.state: dormant
map "revisit [p]" -> p.state: active

intent Shelve {
    when user declares: "shelve [p]"
    treat: [p] as dormant
    generates: Pi Script constraint ShelvedGuard
}

intent Revisit {
    when user declares: "revisit [p]"
    treat: [p] as active
    releases: Shelve for [p]
    generates: Pi Script constraint ActiveGuard
}
""")
        assert "constraint ShelvedGuard" in pi_src
        assert "constraint ActiveGuard" in pi_src
        assert "ShelvedGuard, ActiveGuard" in pi_src


# ─────────────────────────────────────────────────────────────────────────────
# Matcher tests — Rift Ruling 3.1 (Semantic Declaration Matching)
# ─────────────────────────────────────────────────────────────────────────────

MATCHER_MAPS = [
    {"pattern": "I shelved [project]",     "target_entity": "project",
     "target_field": "state", "state_value": "dormant"},
    {"pattern": "let's revisit [project]", "target_entity": "project",
     "target_field": "state", "state_value": "active"},
    {"pattern": "I'm done with [project]", "target_entity": "project",
     "target_field": "state", "state_value": "closed"},
]


class _Vec(tuple):
    """Minimal embedding stand-in supporting the @ (dot product) operator."""
    def __matmul__(self, other):
        return sum(a * b for a, b in zip(self, other))


def _fake_encode(scores: dict, calls: list | None = None):
    """Build a fake rift.matcher._encode.

    Texts found in `scores` embed as (score, 0); all other texts (the
    declaration probe) embed as (1, 0) — so probe @ comparison == score.
    """
    def encode(texts):
        if calls is not None:
            calls.append(list(texts))
        return [
            _Vec((scores[t], 0.0)) if t in scores else _Vec((1.0, 0.0))
            for t in texts
        ]
    return encode


class TestRiftMatcherExact:
    def test_exact_match_extracts_capture(self):
        r = match_declaration("I shelved Veritas", MATCHER_MAPS)
        assert r.matched and r.tier == "exact"
        assert r.map_index == 0
        assert r.captures == {"project": "Veritas"}

    def test_exact_match_case_insensitive(self):
        r = match_declaration("i SHELVED veritas", MATCHER_MAPS)
        assert r.matched and r.tier == "exact"
        assert r.captures == {"project": "veritas"}

    def test_exact_whitespace_normalized(self):
        r = match_declaration("  I   shelved   the old prototype ", MATCHER_MAPS)
        assert r.matched and r.tier == "exact"
        assert r.captures == {"project": "the old prototype"}

    def test_exact_source_order_precedence(self):
        maps = [
            {"pattern": "do [x]",       "target_entity": "x",
             "target_field": "state", "state_value": "done"},
            {"pattern": "do [x] twice", "target_entity": "x",
             "target_field": "state", "state_value": "doubled"},
        ]
        r = match_declaration("do it twice", maps)
        assert r.matched and r.tier == "exact"
        assert r.map_index == 0

    def test_literal_pattern_no_captures(self):
        maps = [{"pattern": "freeze everything", "target_entity": "system",
                 "target_field": "state", "state_value": "frozen"}]
        r = match_declaration("freeze everything", maps)
        assert r.matched and r.tier == "exact"
        assert r.captures == {}

    def test_no_match_returns_tier_none(self, monkeypatch):
        low = {"I shelved project": 0.05, "let's revisit project": 0.02,
               "I'm done with project": 0.01}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(low))
        r = match_declaration("what's the weather like", MATCHER_MAPS)
        assert not r.matched
        assert r.tier == "none"
        assert r.map is None


class TestRiftMatcherSemantic:
    def test_semantic_match_above_threshold(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.4,
                  "I'm done with project": 0.2}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("I put it on ice", MATCHER_MAPS)
        assert r.matched and r.tier == "semantic"
        assert r.map_index == 0
        assert r.map["state_value"] == "dormant"
        assert r.score == 0.9

    def test_semantic_below_threshold_no_match(self, monkeypatch):
        scores = {"I shelved project": 0.2, "let's revisit project": 0.1,
                  "I'm done with project": 0.05}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("unrelated text", MATCHER_MAPS)
        assert not r.matched and r.tier == "none"
        assert "below threshold" in r.explanation

    def test_semantic_ambiguous_no_match(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.88,
                  "I'm done with project": 0.1}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("wrap up the thing", MATCHER_MAPS)
        assert not r.matched and r.tier == "none"
        assert "ambiguous" in r.explanation

    def test_semantic_captures_empty(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.1,
                  "I'm done with project": 0.1}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("I put Veritas on ice", MATCHER_MAPS)
        assert r.matched and r.tier == "semantic"
        assert r.captures == {}

    def test_semantic_result_has_candidates(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.5,
                  "I'm done with project": 0.3}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("I put it on ice", MATCHER_MAPS)
        assert len(r.candidates) == 3
        got = [c["score"] for c in r.candidates]
        assert got == sorted(got, reverse=True)
        assert r.candidates[0]["comparison_text"] == "I shelved project"

    def test_exact_short_circuits_semantic(self, monkeypatch):
        calls = []
        monkeypatch.setattr("rift.matcher._encode", _fake_encode({}, calls))
        r = match_declaration("I shelved Veritas", MATCHER_MAPS)
        assert r.matched and r.tier == "exact"
        assert calls == []

    def test_degraded_flag_when_model_unavailable(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", lambda texts: None)
        r = match_declaration("I put it on ice", MATCHER_MAPS)
        assert not r.matched and r.tier == "none"
        assert r.degraded is True
        assert "DEGRADED" in r.explanation

    def test_threshold_zero_rejected(self):
        with pytest.raises(ValueError):
            match_declaration("anything", MATCHER_MAPS, threshold=0.0)

    def test_threshold_one_accepted(self, monkeypatch):
        scores = {"I shelved project": 1.0, "let's revisit project": 0.1,
                  "I'm done with project": 0.1}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("I put it on ice", MATCHER_MAPS, threshold=1.0)
        assert r.matched and r.score == 1.0

    def test_threshold_above_one_rejected(self):
        with pytest.raises(ValueError):
            match_declaration("anything", MATCHER_MAPS, threshold=1.1)

    def test_known_values_masked_in_probe(self, monkeypatch):
        calls = []
        scores = {"I shelved project": 0.9, "let's revisit project": 0.1,
                  "I'm done with project": 0.1}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores, calls))
        match_declaration(
            "I mothballed Veritas", MATCHER_MAPS, known_values=["Veritas"]
        )
        assert len(calls) == 1
        assert "I mothballed project" in calls[0]
        assert all("Veritas" not in t for t in calls[0])

    def test_render_match_shows_scores(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.4,
                  "I'm done with project": 0.2}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("I put it on ice", MATCHER_MAPS)
        out = render_match(r, "I put it on ice")
        assert "RIFT MATCH TRACE" in out
        assert "semantic" in out
        assert "0.9" in out
        assert "selected" in out
        assert "MATCHED" in out
        assert "project.state: dormant" in out


class TestRiftMatcherIndependence:
    """Rift Ruling 3.1 §3.1.3 — hard layer boundary: no cross-layer reuse."""

    def test_no_pi_script_reference_in_source(self):
        source = (RIFT_DIR / "matcher.py").read_text(encoding="utf-8")
        assert "pi_script" not in source

    def test_import_does_not_load_pi_script(self):
        import subprocess, sys
        code = (
            "import rift.matcher, sys; "
            "loaded = [m for m in sys.modules if m.startswith('pi_script')]; "
            "assert loaded == [], f'pi_script modules loaded: {loaded}'; "
            "print('clean')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(RIFT_DIR.parent), capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "clean" in proc.stdout


# ─────────────────────────────────────────────────────────────────────────────
# Session tests — Rift Ruling 3.2 (Known-Values Accumulation)
# ─────────────────────────────────────────────────────────────────────────────

SEMANTIC_SHELVE = {"I shelved project": 0.9, "let's revisit project": 0.4,
                   "I'm done with project": 0.2}


class TestRiftSession:
    def test_tier1_captures_accumulate(self):
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("I shelved Veritas")
        assert isinstance(r, Resolution)
        assert r.result.matched and r.result.tier == "exact"
        assert r.newly_accumulated == ("Veritas",)
        assert s.known_values == ("Veritas",)

    def test_accumulated_values_mask_later_calls(self, monkeypatch):
        s = RiftSession(MATCHER_MAPS)
        s.resolve("I shelved Veritas")
        calls = []
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE, calls))
        r = s.resolve("I mothballed Veritas")
        assert r.result.matched and r.result.tier == "semantic"
        assert len(calls) == 1
        assert "I mothballed project" in calls[0]
        assert all("Veritas" not in t for t in calls[0])
        assert r.known_values_used == ("Veritas",)

    def test_semantic_match_does_not_accumulate(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE))
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("I put it on ice")
        assert r.result.matched and r.result.tier == "semantic"
        assert r.newly_accumulated == ()
        assert s.known_values == ()

    def test_no_match_does_not_accumulate(self, monkeypatch):
        low = {"I shelved project": 0.05, "let's revisit project": 0.02,
               "I'm done with project": 0.01}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(low))
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("what's the weather like")
        assert not r.result.matched
        assert r.newly_accumulated == ()
        assert s.known_values == ()

    def test_caller_values_used_for_call(self, monkeypatch):
        calls = []
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE, calls))
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("I mothballed Veritas", known_values=["Veritas"])
        assert r.known_values_used == ("Veritas",)
        assert "I mothballed project" in calls[0]
        assert all("Veritas" not in t for t in calls[0])

    def test_caller_values_not_persisted(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE))
        s = RiftSession(MATCHER_MAPS)
        s.resolve("I mothballed Veritas", known_values=["Veritas"])
        assert s.known_values == ()

    def test_dedup_case_insensitive(self):
        s = RiftSession(MATCHER_MAPS)
        s.resolve("I shelved Veritas")
        r = s.resolve("let's revisit VERITAS")
        assert r.result.tier == "exact"
        assert r.newly_accumulated == ()
        assert s.known_values == ("Veritas",)

    def test_union_accumulated_form_wins(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE))
        s = RiftSession(MATCHER_MAPS)
        s.resolve("I shelved Veritas")
        r = s.resolve("I mothballed it", known_values=["VERITAS"])
        assert r.known_values_used == ("Veritas",)

    def test_masking_order_longest_first(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE))
        s = RiftSession(MATCHER_MAPS)
        s.resolve("I shelved Veritas")
        r = s.resolve("I mothballed it", known_values=["Veritas 2"])
        assert r.known_values_used == ("Veritas 2", "Veritas")

    def test_empty_accumulation_baseline(self, monkeypatch):
        calls = []
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(SEMANTIC_SHELVE, calls))
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("I mothballed Veritas")
        # probe is the raw declaration — no masking without known values
        assert "I mothballed Veritas" in calls[0]
        assert r.known_values_used == ()
        assert r.result == match_declaration("I mothballed Veritas", MATCHER_MAPS)

    def test_degraded_model_visible_not_crash(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", lambda texts: None)
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("I put it on ice")
        assert not r.result.matched
        assert r.result.degraded is True
        assert "DEGRADED" in r.trace
        assert r.newly_accumulated == ()
        assert s.known_values == ()

    def test_known_values_property_readonly(self):
        s = RiftSession(MATCHER_MAPS)
        s.resolve("I shelved Veritas")
        kv = s.known_values
        assert isinstance(kv, tuple)
        kv += ("Intruder",)
        assert s.known_values == ("Veritas",)
        with pytest.raises(AttributeError):
            s.known_values = ("Intruder",)

    def test_trace_shows_session_block(self):
        s = RiftSession(MATCHER_MAPS)
        r = s.resolve("I shelved Veritas")
        assert "RIFT MATCH TRACE" in r.trace
        assert "RIFT SESSION" in r.trace
        assert "Known values : (none)" in r.trace
        assert '[project] = "Veritas"' in r.trace

    def test_from_rift_file_constructor(self):
        s = RiftSession.from_rift_file(str(SHELVED_RIFT))
        r = s.resolve("I shelved Veritas")
        assert r.result.matched and r.result.tier == "exact"
        assert s.known_values == ("Veritas",)

    def test_from_rift_file_invalid_raises(self, tmp_path):
        bad = tmp_path / "invalid.rift"
        bad.write_text("this is not a rift program {{{", encoding="utf-8")
        with pytest.raises(ValueError, match="failed validation"):
            RiftSession.from_rift_file(str(bad))

    def test_end_to_end_accumulation_flow(self, monkeypatch):
        s = RiftSession(MATCHER_MAPS)

        # 1. Tier 1 exact match populates the known-values set
        r1 = s.resolve("I shelved Veritas")
        assert r1.result.tier == "exact"
        assert r1.newly_accumulated == ("Veritas",)
        assert "RIFT MATCH TRACE" in r1.trace
        assert '[project] = "Veritas"' in r1.trace

        # 2. Tier 2 semantic match benefits from the accumulated masking
        calls = []
        scores = {"let's revisit project": 0.9, "I shelved project": 0.4,
                  "I'm done with project": 0.2}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores, calls))
        r2 = s.resolve("time to pick Veritas back up")
        assert r2.result.matched and r2.result.tier == "semantic"
        assert r2.result.map["state_value"] == "active"
        assert "time to pick project back up" in calls[0]
        assert all("Veritas" not in t for t in calls[0])
        assert r2.known_values_used == ("Veritas",)
        assert r2.newly_accumulated == ()
        assert 'Known values : "Veritas"' in r2.trace
        assert "semantic" in r2.trace


class TestRiftSessionIndependence:
    """Rift Ruling 3.2 §3.2.4 — hard layer boundary: no cross-layer sourcing."""

    def test_no_pi_script_reference_in_source(self):
        source = (RIFT_DIR / "session.py").read_text(encoding="utf-8")
        assert "pi_script" not in source

    def test_import_does_not_load_pi_script(self):
        import subprocess, sys
        code = (
            "import rift.session, sys; "
            "loaded = [m for m in sys.modules if m.startswith('pi_script')]; "
            "assert loaded == [], f'pi_script modules loaded: {loaded}'; "
            "print('clean')"
        )
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(RIFT_DIR.parent), capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stderr
        assert "clean" in proc.stdout


class TestMatchResultContract:
    """MatchResult contract validation (matched × tier × degraded × explanation).

    render_match validates every result before rendering; internally invalid
    field combinations fail loudly instead of falling through to a generic
    rendering path. The distinct no-match reasons the matcher already computes
    (empty declaration, no maps, degraded, below threshold, ambiguous) must
    each stay visible in the trace — never flattened into one generic no-match.
    """

    # ── Valid emitted combinations render correctly ──────────────────────────

    def test_render_exact_match(self):
        r = match_declaration("I shelved Veritas", MATCHER_MAPS)
        out = render_match(r, "I shelved Veritas")
        assert "Tier        : exact" in out
        assert "Captures" in out and "Veritas" in out
        assert "✓ MATCHED" in out

    def test_render_semantic_match_shows_score_threshold_margin(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.4,
                  "I'm done with project": 0.2}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("I put it on ice", MATCHER_MAPS)
        out = render_match(r, "I put it on ice")
        assert "Tier        : semantic" in out
        assert "Threshold" in out and "Margin" in out
        assert "0.9" in out and "← selected" in out
        assert "✓ MATCHED" in out

    def test_render_below_threshold_keeps_distinct_reason(self, monkeypatch):
        scores = {"I shelved project": 0.2, "let's revisit project": 0.1,
                  "I'm done with project": 0.05}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("unrelated text", MATCHER_MAPS)
        out = render_match(r, "unrelated text")
        assert "✗ NO MATCH" in out
        assert "below threshold" in out
        assert "score: 0.2" in out  # candidates stay visible

    def test_render_ambiguous_keeps_distinct_reason(self, monkeypatch):
        scores = {"I shelved project": 0.9, "let's revisit project": 0.88,
                  "I'm done with project": 0.1}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(scores))
        r = match_declaration("wrap up the thing", MATCHER_MAPS)
        out = render_match(r, "wrap up the thing")
        assert "✗ NO MATCH" in out
        assert "ambiguous" in out
        assert "within margin" in out

    def test_render_degraded_keeps_distinct_reason(self, monkeypatch):
        monkeypatch.setattr("rift.matcher._encode", lambda texts: None)
        r = match_declaration("I put it on ice", MATCHER_MAPS)
        out = render_match(r, "I put it on ice")
        assert "⚠ DEGRADED" in out
        assert "✗ NO MATCH" in out
        assert "unavailable" in out

    def test_render_empty_declaration_reason(self):
        r = match_declaration("   ", MATCHER_MAPS)
        out = render_match(r, "   ")
        assert "✗ NO MATCH" in out and "empty declaration" in out

    def test_render_no_maps_reason(self):
        r = match_declaration("I shelved Veritas", [])
        out = render_match(r, "I shelved Veritas")
        assert "✗ NO MATCH" in out and "no maps declared" in out

    def test_no_match_reasons_are_not_flattened(self, monkeypatch):
        """The three semantic-tier no-match paths carry distinct explanations."""
        monkeypatch.setattr("rift.matcher._encode", lambda texts: None)
        degraded = match_declaration("x y z", MATCHER_MAPS).explanation
        low = {"I shelved project": 0.2, "let's revisit project": 0.1,
               "I'm done with project": 0.05}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(low))
        below = match_declaration("x y z", MATCHER_MAPS).explanation
        close = {"I shelved project": 0.9, "let's revisit project": 0.88,
                 "I'm done with project": 0.1}
        monkeypatch.setattr("rift.matcher._encode", _fake_encode(close))
        ambiguous = match_declaration("x y z", MATCHER_MAPS).explanation
        assert len({degraded, below, ambiguous}) == 3
        assert "DEGRADED" in degraded
        assert "below threshold" in below
        assert "ambiguous" in ambiguous

    # ── Required explanations ────────────────────────────────────────────────

    def test_unmatched_requires_explanation(self):
        r = MatchResult(matched=False, tier="none", explanation="")
        with pytest.raises(ValueError, match="non-empty"):
            render_match(r)

    def test_degraded_requires_explanation(self):
        r = MatchResult(matched=False, tier="none", degraded=True, explanation=" ")
        with pytest.raises(ValueError, match="non-empty"):
            render_match(r)

    # ── Invalid combinations fail loudly ─────────────────────────────────────

    def test_unknown_tier_fails_loudly(self):
        r = MatchResult(matched=True, tier="fuzzy", map={}, map_index=0)
        with pytest.raises(ValueError, match="tier"):
            render_match(r)

    def test_matched_with_tier_none_fails_loudly(self):
        r = MatchResult(matched=True, tier="none", explanation="x")
        with pytest.raises(ValueError):
            validate_match_result(r)

    def test_matched_without_map_fails_loudly(self):
        r = MatchResult(matched=True, tier="exact", map=None, explanation="x")
        with pytest.raises(ValueError, match="map"):
            render_match(r)

    def test_matched_degraded_fails_loudly(self):
        r = MatchResult(matched=True, tier="exact", map={}, map_index=0,
                        degraded=True, explanation="x")
        with pytest.raises(ValueError, match="degraded"):
            validate_match_result(r)

    def test_semantic_match_without_score_fails_loudly(self):
        r = MatchResult(matched=True, tier="semantic", map={}, map_index=0,
                        score=None, explanation="x")
        with pytest.raises(ValueError, match="score"):
            validate_match_result(r)

    def test_semantic_match_with_captures_fails_loudly(self):
        r = MatchResult(matched=True, tier="semantic", map={}, map_index=0,
                        score=0.5, captures={"project": "Veritas"},
                        explanation="x")
        with pytest.raises(ValueError, match="captures"):
            validate_match_result(r)

    def test_unmatched_with_exact_tier_fails_loudly(self):
        r = MatchResult(matched=False, tier="exact", explanation="x")
        with pytest.raises(ValueError):
            validate_match_result(r)

    def test_unmatched_with_map_fails_loudly(self):
        r = MatchResult(matched=False, tier="none", map={}, map_index=0,
                        explanation="x")
        with pytest.raises(ValueError):
            validate_match_result(r)

    def test_unmatched_with_captures_fails_loudly(self):
        r = MatchResult(matched=False, tier="none",
                        captures={"project": "Veritas"}, explanation="x")
        with pytest.raises(ValueError):
            validate_match_result(r)

    def test_degraded_with_candidates_fails_loudly(self):
        r = MatchResult(matched=False, tier="none", degraded=True,
                        candidates=[{"score": 0.5}], explanation="x")
        with pytest.raises(ValueError):
            validate_match_result(r)
