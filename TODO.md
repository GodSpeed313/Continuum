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
- [x] M3 — Parser — 9/9 tests passing
- [x] M4 — Resolver core — 89/89 tests passing
- [x] M5 — Dogfood — gate met (6+ violations across two independent systems: 2 Continuum session + 4+ Melody Maestro automated, 23-day active run)
- [x] M6 — Publish — ConsistencyGuard activated, Rift v0.1 shipped, Jupyter playground live (paper at docs/m6_paper_draft1.md)

## v0.2 ruling tracker

- [x] Ruling 9.4 — bidirectional map blocks (PR #10)
- [x] Ruling 9.5 — cross-domain constraint inheritance (PR #11)
- [x] Ruling 9.6 — persistent violation counters (PR #12)
- [x] Ruling 9.7 — arbiter mandatory + flag-as-always-additive (PR #13)
- [x] Ruling 9.8 — semantic similarity map matching (PR #14, #15)
- [x] Ruling 9.9 — standing bound rule / Form 7 (PR #16)

Pending rulings: none. Spec doc (`docs/pi_script_v02_draft5.md`, Draft 10) confirms.

## Tooling / integration (post-9.9)

- [x] MCP server exposing governance checks as a tool (PR #18)
- [x] Persistence + cross-process write-queue for `check_governance` (PR #19)
- [x] Read-only governance dashboard (PR #20)
- [x] Quantization-governance domain example — corrected to valid v0.2 syntax, proves grammar is domain-general (PR #21)

240/240 tests passing.
