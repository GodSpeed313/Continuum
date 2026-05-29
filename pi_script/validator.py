"""
Pi Script v0.2 — Semantic Validator
Walks the Lark AST produced by parser.py and runs semantic checks.
Supports multi-domain files (Ruling 9.5 — cross-domain imports).
Returns: (is_valid: bool, errors: list[str], ir: dict)
"""

from __future__ import annotations

import copy
from typing import Any

from lark import Tree, Token


# ── Helpers ───────────────────────────────────────────────────────────────────

def _leaf_value(node) -> str:
    """Extract string value from a terminal-like node.
    Handles Token, Tree with children, and empty Tree (value in .data).
    """
    if isinstance(node, Token):
        return str(node)
    if isinstance(node, Tree):
        if node.children:
            return _leaf_value(node.children[0])
        return str(node.data)
    return str(node)


def _tok(node: Tree, index: int) -> str:
    """Return children[index] as a plain string."""
    return str(node.children[index])


def _subtrees(tree: Tree, data: str) -> list[Tree]:
    return [n for n in tree.iter_subtrees() if n.data == data]


def _first_child_tree(node: Tree, data: str) -> Tree | None:
    for c in node.children:
        if isinstance(c, Tree) and c.data == data:
            return c
    return None


def _state_ref_str(node: Tree) -> str:
    """state_ref node → 'Entity.state_name'"""
    return f"{node.children[0]}.{node.children[1]}"


def _extract_duration(node: Tree) -> dict[str, Any]:
    """duration node → {value: float, unit: str}"""
    unit_node = node.children[1]
    if isinstance(unit_node, Token):
        unit = str(unit_node)
    elif isinstance(unit_node, Tree):
        if unit_node.children:
            unit = str(unit_node.children[0])
        else:
            # Empty tree — unit is encoded in the rule name, e.g. "time_unit__minutes"
            unit = str(unit_node.data)
    else:
        unit = str(unit_node)
    return {
        "value": float(_tok(node, 0)),
        "unit": unit,
    }


def _extract_state_type(node) -> str:
    """state_type node → human-readable type string."""
    if isinstance(node, Token):
        return str(node)
    if not node.children:
        return node.data
    ch = node.children[0]
    if isinstance(ch, Token):
        # Two PI_NUMBER children → range(lo..hi); one STATE_TYPE_KW → keyword type
        if len(node.children) == 2:
            return f"range({ch}..{node.children[1]})"
        return str(ch)
    if isinstance(ch, Tree):
        return f"sequence({_extract_state_type(ch)})"
    return "unknown"


def _extract_pi_value(node: Tree) -> Any:
    """pi_value alias node → Python scalar."""
    alias = node.data
    if alias == "pv_number":
        raw = str(node.children[0])
        return float(raw) if "." in raw else int(raw)
    if alias == "pv_true":
        return True
    if alias == "pv_false":
        return False
    if alias == "pv_string":
        return str(node.children[0]).strip('"')
    if alias == "pv_state_ref":
        return _state_ref_str(node.children[0])
    return None


def _extract_rule(rule_expr_node: Tree) -> dict[str, Any]:
    """rule_expr node → flat dict the evaluator can act on."""
    inner = rule_expr_node.children[0]
    kind = inner.data

    if kind == "range_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        return {
            "kind":   "range_rule",
            "ref":    _state_ref_str(ref),
            "lo":     float(_tok(inner, 1)),
            "hi":     float(_tok(inner, 2)),
        }

    if kind == "threshold_rule":
        ref = _first_child_tree(inner, "state_ref")
        dur = _first_child_tree(inner, "duration")
        if ref is None or dur is None:
            return {"kind": "unknown"}
        return {
            "kind":      "threshold_rule",
            "ref":       _state_ref_str(ref),
            "below":     float(str(inner.children[1])),
            "within":    _extract_duration(dur),
        }

    if kind == "equality_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        val_node = inner.children[1]
        return {
            "kind":  "equality_rule",
            "ref":   _state_ref_str(ref),
            "value": _extract_pi_value(val_node),
        }

    if kind == "membership_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        return {
            "kind": "membership_rule",
            "ref":  _state_ref_str(ref),
        }

    if kind == "if_rule":
        ref = _first_child_tree(inner, "state_ref")
        if ref is None:
            return {"kind": "unknown"}
        cond = inner.children[1]          # if_condition alias node
        require = str(inner.children[2])  # SNAKE_ID action
        before  = str(inner.children[3])  # SNAKE_ID outcome

        if cond.data == "cond_compare":
            return {
                "kind":      "conditional_rule",
                "ref":       _state_ref_str(ref),
                "op":        str(cond.children[0]),
                "value":     _extract_pi_value(cond.children[1]),
                "require":   require,
                "before":    before,
            }
        if cond.data in ("cond_bool_true", "cond_bool_false"):
            return {
                "kind":    "conditional_rule",
                "ref":     _state_ref_str(ref),
                "op":      "==",
                "value":   cond.data == "cond_bool_true",
                "require": require,
                "before":  before,
            }
        if cond.data == "cond_contradiction":
            return {
                "kind":    "contradiction_rule",
                "ref":     _state_ref_str(ref),
                "require": require,
                "before":  before,
            }

    return {"kind": "unknown"}


def _extract_violation_action(va_node: Tree) -> list[str]:
    """violation_action node → list of action strings, e.g. ['freeze','rollback']"""
    actions = []
    for c in va_node.children:
        if isinstance(c, Tree) and c.data == "simple_action":
            actions.append(_leaf_value(c))
    return actions


# ── IR factory & per-node processors (module-level, reused by PiValidator) ───

def _empty_ir() -> dict[str, Any]:
    return {
        "domain":         None,
        "audit_interval": None,
        "tiebreaker":     "timestamp_asc",
        "entities":       {},
        "constraints":    {},
        "maps":           {},
        "enforce":        {},
        "arbiter":        None,
    }


def _process_entity(node: Tree, ir: dict) -> None:
    name = _tok(node, 0)
    states: dict[str, str] = {}
    for ch in node.children:
        if isinstance(ch, Tree) and ch.data == "state_field":
            states[_tok(ch, 0)] = _extract_state_type(ch.children[1])
    ir["entities"][name] = states


def _process_constraint(node: Tree, ir: dict) -> None:
    name = _tok(node, 0)
    rec: dict[str, Any] = {
        "priority":     None,
        "rule":         None,
        "on_violation": [],
        "escalation":   [],
        "decay_check":  None,
    }
    for ch in node.children:
        if not isinstance(ch, Tree):
            continue
        if ch.data == "c_priority":
            rec["priority"] = _leaf_value(ch.children[0])
        elif ch.data == "c_rule":
            rec["rule"] = _extract_rule(ch.children[0])
        elif ch.data == "c_on_violation":
            rec["on_violation"] = _extract_violation_action(ch.children[0])
        elif ch.data == "c_decay_check":
            rec["decay_check"] = _extract_duration(ch.children[0])
        elif ch.data == "c_escalation":
            steps = []
            for step in ch.children[0].children:
                if isinstance(step, Tree) and step.data == "escalation_step":
                    steps.append({
                        "at":     float(_tok(step, 0)),
                        "action": _leaf_value(step.children[1]),
                    })
            rec["escalation"] = steps
    ir["constraints"][name] = rec


def _process_map(node: Tree, ir: dict, errors: list) -> None:
    target_ref  = None
    maps_to_val = None
    triggers: list[str] = []
    label: str | None = None

    for ch in node.children:
        if not isinstance(ch, Tree):
            continue
        if ch.data == "mi_target":
            target_ref = _state_ref_str(ch.children[0])
        elif ch.data == "mi_maps_to":
            maps_to_val = _extract_pi_value(ch.children[0])
        elif ch.data == "mi_triggers":
            for entry in ch.children[0].children:
                if isinstance(entry, Tree) and entry.data == "trigger_entry":
                    triggers.append(str(entry.children[0]).strip('"'))
                elif isinstance(entry, Tree) and entry.data == "regex_trigger":
                    triggers.append(f"regex:{str(entry.children[0]).strip(chr(34))}")
        elif ch.data == "mi_label":
            raw = str(ch.children[0]).strip('"')
            if not raw:
                errors.append("Map block label must be a non-empty string.")
            else:
                label = raw

    if target_ref is not None:
        ir["maps"].setdefault(target_ref, [])
        map_entry: dict = {"maps_to": maps_to_val, "triggers": triggers}
        if label is not None:
            map_entry["label"] = label
        ir["maps"][target_ref].append(map_entry)


def _process_enforce(node: Tree, ir: dict) -> None:
    entity_name: str | None = None
    constraint_names: list[str] = []
    for ch in node.children:
        if not isinstance(ch, Tree):
            continue
        if ch.data == "ei_entity":
            entity_name = str(ch.children[0])
        elif ch.data == "ei_constraints":
            for tok in ch.children[0].children:
                if isinstance(tok, Token):
                    constraint_names.append(str(tok))
    if entity_name:
        ir["enforce"][entity_name] = constraint_names


def _process_arbiter(node: Tree, ir: dict) -> None:
    rec: dict[str, Any] = {
        "name":                  _tok(node, 0),
        "acceptable_evolution":  [],
        "never_acceptable":      [],
        "requires_human_review": [],
        "acceptance_monitor":    None,
    }
    for ch in node.children:
        if not isinstance(ch, Tree):
            continue
        if ch.data == "ai_acceptable":
            rec["acceptable_evolution"] = _str_list(ch.children[0])
        elif ch.data == "ai_never":
            rec["never_acceptable"] = _str_list(ch.children[0])
        elif ch.data == "ai_human_review":
            rec["requires_human_review"] = _str_list(ch.children[0])
        elif ch.data == "ai_monitor":
            mon: dict[str, Any] = {}
            for item in ch.children:
                if isinstance(item, Tree) and item.data == "mi_threshold":
                    mon["threshold"] = float(_tok(item, 0))
                elif isinstance(item, Tree) and item.data == "mi_window":
                    mon["window"] = _extract_duration(item.children[0])
            rec["acceptance_monitor"] = mon
    ir["arbiter"] = rec


# ── Validator ─────────────────────────────────────────────────────────────────

class PiValidator:

    def __init__(self, tree: Tree):
        self.tree   = tree
        self.errors: list[str] = []
        self.ir: dict[str, Any] = _empty_ir()

    def validate(self) -> tuple[bool, list[str], dict[str, Any]]:
        sections = [c for c in self.tree.children
                    if isinstance(c, Tree) and c.data == "domain_section"]
        if not sections:
            self.errors.append("Missing required 'domain' declaration.")
            return False, self.errors, self.ir

        domain_irs: dict[str, dict] = {}
        domain_order: list[str] = []

        for section in sections:
            d_ir = self._build_domain_ir(section)
            name = d_ir["domain"]
            if name in domain_irs:
                self.errors.append(f"Duplicate domain name '{name}'.")
            else:
                domain_irs[name] = d_ir
                domain_order.append(name)

        if not domain_order:
            return False, self.errors, self.ir

        primary_name = domain_order[-1]
        self.ir = self._resolve_imports(domain_irs, primary_name)

        self._check_entity_state_refs_exist()
        self._check_membership_rules_have_maps()
        self._check_enforce_refs_declared()

        return (len(self.errors) == 0), self.errors, self.ir

    # ── Per-section build ─────────────────────────────────────────────────────

    def _build_domain_ir(self, section: Tree) -> dict[str, Any]:
        ir = _empty_ir()
        ir["_import_refs"] = []  # [(src_domain, constraint_name), ...]

        domain_node = section.children[0]
        ir["domain"] = _tok(domain_node, 0)

        audit_count = 0
        for item in domain_node.children:
            if not isinstance(item, Tree):
                continue
            if item.data == "domain_item":
                ch = item.children[0]
                if isinstance(ch, Tree) and ch.data == "duration":
                    ir["audit_interval"] = _extract_duration(ch)
                    audit_count += 1
                elif isinstance(ch, Tree) and ch.data == "tiebreaker_mode":
                    ir["tiebreaker"] = _leaf_value(ch)
            elif item.data == "di_imports":
                imports_item_node = item.children[0]
                for ref in imports_item_node.children:
                    if isinstance(ref, Tree) and ref.data == "import_ref":
                        ir["_import_refs"].append(
                            (str(ref.children[0]), str(ref.children[1]))
                        )

        if audit_count == 0:
            self.errors.append(
                "audit_interval is required and must appear exactly once in the domain block."
            )
        elif audit_count > 1:
            self.errors.append(
                f"audit_interval must appear exactly once (found {audit_count})."
            )

        for stmt in section.children[1:]:
            if not isinstance(stmt, Tree) or stmt.data != "top_level_stmt":
                continue
            decl = stmt.children[0]
            if not isinstance(decl, Tree):
                continue
            if decl.data == "entity_decl":
                _process_entity(decl, ir)
            elif decl.data == "constraint_decl":
                _process_constraint(decl, ir)
            elif decl.data == "map_decl":
                _process_map(decl, ir, self.errors)
            elif decl.data == "enforce_decl":
                _process_enforce(decl, ir)
            elif decl.data == "arbiter_decl":
                _process_arbiter(decl, ir)

        return ir

    # ── Import resolution ─────────────────────────────────────────────────────

    def _resolve_imports(self, domain_irs: dict, primary_name: str) -> dict:
        primary = domain_irs[primary_name]
        import_refs = primary.pop("_import_refs", [])

        # Clear _import_refs from library domains too
        for d in domain_irs.values():
            d.pop("_import_refs", None)

        # Detect circular imports: primary imports from source that imports back
        for src_domain, _ in import_refs:
            if src_domain not in domain_irs:
                continue
            src_refs = domain_irs[src_domain].get("_import_refs_snapshot", [])
            for back_domain, _ in src_refs:
                if back_domain == primary_name:
                    self.errors.append(
                        f"Circular import: '{primary_name}' ↔ '{src_domain}'."
                    )

        for src_domain, constraint_name in import_refs:
            if src_domain not in domain_irs:
                self.errors.append(
                    f"Import '{src_domain}.{constraint_name}': "
                    f"domain '{src_domain}' not found in this file."
                )
                continue

            src_ir = domain_irs[src_domain]

            if constraint_name not in src_ir["constraints"]:
                self.errors.append(
                    f"Import '{src_domain}.{constraint_name}': constraint "
                    f"'{constraint_name}' not found in domain '{src_domain}'."
                )
                continue

            if constraint_name in primary["constraints"]:
                self.errors.append(
                    f"Import '{src_domain}.{constraint_name}': domain "
                    f"'{primary_name}' already declares a constraint named "
                    f"'{constraint_name}'. Remove the local declaration or rename it."
                )
                continue

            src_constraint = src_ir["constraints"][constraint_name]
            rule = src_constraint.get("rule") or {}
            ref  = rule.get("ref", "")
            if ref:
                entity_name, field_name = ref.split(".", 1)
                if entity_name not in primary["entities"]:
                    self.errors.append(
                        f"Import '{src_domain}.{constraint_name}' targets '{ref}' "
                        f"but entity '{entity_name}' is not declared in domain "
                        f"'{primary_name}'."
                    )
                    continue
                if field_name not in primary["entities"][entity_name]:
                    self.errors.append(
                        f"Import '{src_domain}.{constraint_name}' targets '{ref}' "
                        f"but entity '{entity_name}' has no field '{field_name}' "
                        f"in domain '{primary_name}'."
                    )
                    continue

            entry = copy.deepcopy(src_constraint)
            entry["imported_from"] = src_domain
            primary["constraints"][constraint_name] = entry

        return primary

    # ── Semantic checks (operate on self.ir after merge) ─────────────────────

    def _check_entity_state_refs_exist(self):
        entities = self.ir["entities"]
        for cname, cdata in self.ir["constraints"].items():
            rule = cdata.get("rule") or {}
            ref  = rule.get("ref")
            if not ref:
                continue
            entity_name, field_name = ref.split(".", 1)
            if entity_name not in entities:
                self.errors.append(
                    f"Reference to undeclared entity '{entity_name}' in '{ref}'."
                )
            elif field_name not in entities[entity_name]:
                self.errors.append(
                    f"Entity '{entity_name}' has no state '{field_name}' "
                    f"(referenced in '{ref}')."
                )
        for map_ref in self.ir["maps"]:
            entity_name, field_name = map_ref.split(".", 1)
            if entity_name not in entities:
                self.errors.append(
                    f"Reference to undeclared entity '{entity_name}' in map "
                    f"target '{map_ref}'."
                )
            elif field_name not in entities[entity_name]:
                self.errors.append(
                    f"Entity '{entity_name}' has no state '{field_name}' "
                    f"(referenced in map target '{map_ref}')."
                )

    def _check_membership_rules_have_maps(self):
        for cname, cdata in self.ir["constraints"].items():
            rule = cdata.get("rule")
            if not rule or rule["kind"] != "membership_rule":
                continue
            ref = rule["ref"]
            if ref not in self.ir["maps"] or not self.ir["maps"][ref]:
                self.errors.append(
                    f"Constraint '{cname}': membership rule targets '{ref}' "
                    f"but no map block declares that as its target. "
                    f"Add at least one 'map' block with 'target: {ref}'."
                )

    def _check_enforce_refs_declared(self):
        declared = set(self.ir["constraints"])
        for entity, names in self.ir["enforce"].items():
            for name in names:
                if name not in declared:
                    self.errors.append(
                        f"enforce block for '{entity}' references "
                        f"undeclared constraint '{name}'."
                    )


# ── Private helper ────────────────────────────────────────────────────────────

def _str_list(node: Tree) -> list[str]:
    return [str(c).strip('"') for c in node.children if isinstance(c, Token)]


# ── CLI ───────────────────────────────────────────────────────────────────────

def validate_file(path: str) -> tuple[bool, list[str], dict[str, Any]]:
    from pi_script.parser import parse_file
    tree, err = parse_file(path)
    if err:
        return False, [err], {}
    return PiValidator(tree).validate()


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python validator.py <file.pi>", file=sys.stderr)
        sys.exit(1)
    ok, errors, ir = validate_file(sys.argv[1])
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
    if ok:
        print(json.dumps(ir, indent=2))
        print(f"OK  {sys.argv[1]}", file=sys.stderr)
    sys.exit(0 if ok else 1)
