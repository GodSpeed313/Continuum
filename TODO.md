# Continuum — TODO

## test_validator_unit.py — NEEDS RECREATION

**File:** `tests/test_validator_unit.py`
**Status:** Never committed to source. Original lost. Must be recreated.

**Scope:** Hand-built Lark Tree unit test harness. Constructs AST nodes directly and
feeds them to `PiValidator` — no parser required. Tests validator internals in isolation.

| Group | Count | Coverage |
|---|---|---|
| `TestPiValidatorHappyPath` | 11 | Full IR extraction: domain, audit_interval, entities, all 5 rule types, maps, enforce, arbiter, escalation steps |
| `TestSemanticErrors` | 7 | Missing domain, missing audit_interval, duplicate audit_interval, bad entity ref, bad state ref, membership without map, enforce with undeclared constraint |
| `TestMalformedAst` | 5 | Rules missing state_ref child — verifies None guards return `{"kind": "unknown"}` instead of crashing |
| `TestConditionalRules` | 3 | if_rule variants: cond_compare, cond_bool_true, cond_contradiction |

**Why it matters:** The 12 tests in `tests/test_validator.py` cover end-to-end behavior
via the parser. `test_validator_unit.py` tests validator internals directly — faster
feedback loop and better isolation for debugging. Not a blocker for M4 but important
for long-term robustness.

---

## Milestone tracker

- [x] M1 — Grammar finalized
- [x] M2 — Semantic validator, 12/12 tests passing
- [ ] M3 — Parser hardening (next)
- [ ] M4 — Resolver core
- [ ] M5 — Dogfood (30 days)
- [ ] M6 — Publish
