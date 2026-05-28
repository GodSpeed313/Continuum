"""Rift v0.1 — Semantic Validator.
Walks the Lark AST produced by parser.py and runs five semantic checks.
Returns: (is_valid: bool, errors: list[str], ir: dict)
"""

from __future__ import annotations

import re
from typing import Any

from lark import Tree, Token


# ── Helpers ───────────────────────────────────────────────────────────────────

def _tok(node: Tree, index: int) -> str:
    return str(node.children[index])


def _subtrees(tree: Tree, data: str) -> list[Tree]:
    return [n for n in tree.iter_subtrees() if n.data == data]


def _first_child_tree(node: Tree, data: str) -> Tree | None:
    for c in node.children:
        if isinstance(c, Tree) and c.data == data:
            return c
    return None


def _strip_quotes(s: str) -> str:
    return s.strip('"')


def _captures_in_pattern(pattern: str) -> set[str]:
    """Return all [capture_name] names found in a quoted pattern string."""
    return set(re.findall(r'\[(\w+)\]', pattern))


def _extract_violation_action(va_node: Tree) -> list[str]:
    actions = []
    for c in va_node.children:
        if isinstance(c, Tree) and c.data == "simple_action":
            if c.children:
                actions.append(str(c.children[0]))
    return actions


# ── Validator ─────────────────────────────────────────────────────────────────

class RiftValidator:

    def __init__(self, tree: Tree):
        self.tree = tree
        self.errors: list[str] = []
        self.ir: dict[str, Any] = {
            "intents":     {},   # intent_name -> intent_ir
            "maps":        [],   # list of map_ir dicts
            "constraints": {},   # constraint_name -> constraint_ir
        }

    def validate(self) -> tuple[bool, list[str], dict[str, Any]]:
        self._extract_maps()
        self._extract_constraints()
        self._extract_intents()

        self._check_no_duplicate_intent_names()
        self._check_treat_capture_in_when_pattern()
        self._check_releases_refs_declared()
        self._check_generates_names_unique()
        self._check_required_intent_fields()

        return (len(self.errors) == 0), self.errors, self.ir

    # ── Extraction ────────────────────────────────────────────────────────────

    def _extract_maps(self):
        for node in _subtrees(self.tree, "map_decl"):
            # children: ESCAPED_STRING, MAP_ARROW, map_target, SNAKE_ID
            pattern = _strip_quotes(_tok(node, 0))
            target_node = _first_child_tree(node, "target_pascal") \
                       or _first_child_tree(node, "target_snake")
            if target_node is None:
                # fallback: find any map_target child
                for c in node.children:
                    if isinstance(c, Tree) and c.data == "map_target":
                        target_node = c.children[0] if c.children else None
                        break

            target_entity = str(target_node.children[0]) if target_node else None
            target_field  = str(target_node.children[1]) if target_node else None
            state_value   = _tok(node, -1)  # last child is SNAKE_ID state value

            self.ir["maps"].append({
                "pattern":      pattern,
                "target_entity": target_entity,
                "target_field":  target_field,
                "state_value":   state_value,
            })

    def _extract_constraints(self):
        for node in _subtrees(self.tree, "constraint_decl"):
            name = _tok(node, 0)
            rec: dict[str, Any] = {
                "priority":     None,
                "rule":         None,
                "on_violation": [],
            }
            for ch in node.children:
                if not isinstance(ch, Tree):
                    continue
                if ch.data == "c_priority":
                    pri = ch.children[0]
                    rec["priority"] = str(pri.children[0]) if isinstance(pri, Tree) and pri.children else str(pri)
                elif ch.data == "c_rule":
                    rec["rule"] = _strip_quotes(str(ch.children[0]))
                elif ch.data == "c_on_violation":
                    rec["on_violation"] = _extract_violation_action(ch.children[0])
            self.ir["constraints"][name] = rec

    def _extract_intents(self):
        for node in _subtrees(self.tree, "intent_decl"):
            name = _tok(node, 0)
            rec: dict[str, Any] = {
                "when":      None,   # pattern string
                "treat":     None,   # {"capture": str, "as": str}
                "until":     None,   # {"kind": "user_declares"|"condition", "value": str}
                "enforce":   None,   # directive string
                "releases":  None,   # {"intent": str, "capture": str}
                "generates": None,   # constraint name string
                "priority":  None,
            }
            for ch in node.children:
                if not isinstance(ch, Tree) or ch.data != "intent_item":
                    continue
                clause = ch.children[0] if ch.children else None
                if clause is None or not isinstance(clause, Tree):
                    continue
                self._extract_intent_clause(rec, clause)
            self.ir["intents"][name] = rec

    def _extract_intent_clause(self, rec: dict, clause: Tree):
        kind = clause.data

        if kind == "when_clause":
            rec["when"] = _strip_quotes(str(clause.children[0]))

        elif kind == "treat_clause":
            cap_node = _first_child_tree(clause, "capture_ref")
            capture  = str(cap_node.children[0]) if cap_node else None
            state    = str(clause.children[-1])
            rec["treat"] = {"capture": capture, "as": state}

        elif kind == "until_clause":
            until_expr = _first_child_tree(clause, "until_user_declares") \
                      or _first_child_tree(clause, "until_condition_name")
            if until_expr is None and clause.children:
                until_expr = clause.children[0] if isinstance(clause.children[0], Tree) else None
            if until_expr is not None:
                if until_expr.data == "until_user_declares":
                    rec["until"] = {
                        "kind":  "user_declares",
                        "value": _strip_quotes(str(until_expr.children[0])),
                    }
                elif until_expr.data == "until_condition_name":
                    rec["until"] = {
                        "kind":  "condition",
                        "value": str(until_expr.children[0]),
                    }

        elif kind == "enforce_clause":
            rec["enforce"] = _strip_quotes(str(clause.children[0]))

        elif kind == "releases_clause":
            intent_name = str(clause.children[0])
            cap_node    = _first_child_tree(clause, "capture_ref")
            capture     = str(cap_node.children[0]) if cap_node else None
            rec["releases"] = {"intent": intent_name, "capture": capture}

        elif kind == "generates_clause":
            rec["generates"] = str(clause.children[0])

        elif kind == "priority_annotation":
            pri = clause.children[0]
            rec["priority"] = str(pri.children[0]) if isinstance(pri, Tree) and pri.children else str(pri)

    # ── Semantic checks ───────────────────────────────────────────────────────

    def _check_no_duplicate_intent_names(self):
        seen: set[str] = set()
        for node in _subtrees(self.tree, "intent_decl"):
            name = _tok(node, 0)
            if name in seen:
                self.errors.append(f"Duplicate intent name '{name}'.")
            seen.add(name)

    def _check_treat_capture_in_when_pattern(self):
        for name, rec in self.ir["intents"].items():
            when    = rec.get("when")
            treat   = rec.get("treat")
            if when is None or treat is None:
                continue
            captures = _captures_in_pattern(when)
            capture  = treat.get("capture")
            if capture and capture not in captures:
                self.errors.append(
                    f"Intent '{name}': treat references capture '[{capture}]' "
                    f"but it is not declared in the when pattern \"{when}\"."
                )

    def _check_releases_refs_declared(self):
        declared = set(self.ir["intents"])
        for name, rec in self.ir["intents"].items():
            releases = rec.get("releases")
            if not releases:
                continue
            ref = releases["intent"]
            if ref not in declared:
                self.errors.append(
                    f"Intent '{name}': releases references undeclared intent '{ref}'."
                )

    def _check_generates_names_unique(self):
        seen: dict[str, str] = {}  # constraint_name -> intent_name
        for name, rec in self.ir["intents"].items():
            gen = rec.get("generates")
            if not gen:
                continue
            if gen in seen:
                self.errors.append(
                    f"Constraint name '{gen}' generated by both "
                    f"'{seen[gen]}' and '{name}'. Constraint names must be unique."
                )
            seen[gen] = name

    def _check_required_intent_fields(self):
        for name, rec in self.ir["intents"].items():
            missing = []
            if rec.get("when") is None:
                missing.append("when")
            if rec.get("treat") is None:
                missing.append("treat")
            if missing:
                self.errors.append(
                    f"Intent '{name}' is missing required field(s): "
                    + ", ".join(missing) + "."
                )


# ── CLI ───────────────────────────────────────────────────────────────────────

def validate_file(path: str) -> tuple[bool, list[str], dict[str, Any]]:
    from rift.parser import parse_file
    tree, err = parse_file(path)
    if err:
        return False, [err], {}
    return RiftValidator(tree).validate()


if __name__ == "__main__":
    import json
    import sys
    if len(sys.argv) < 2:
        print("Usage: python validator.py <file.rift>", file=sys.stderr)
        sys.exit(1)
    ok, errors, ir = validate_file(sys.argv[1])
    if errors:
        for e in errors:
            print(f"ERROR  {e}", file=sys.stderr)
    if ok:
        print(json.dumps(ir, indent=2))
        print(f"OK  {sys.argv[1]}", file=sys.stderr)
    sys.exit(0 if ok else 1)
