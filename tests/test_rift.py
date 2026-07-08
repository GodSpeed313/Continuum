"""Rift v0.1 tests — parser, validator, compiler.
Rift v0.2 tests — declaration matcher (Rift Ruling 3.1)."""

from pathlib import Path

import pytest

from rift.parser import parse_string, parse_file
from rift.validator import RiftValidator, validate_file
from rift.compiler import RiftCompiler
from rift.matcher import MatchResult, match_declaration, render_match

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
