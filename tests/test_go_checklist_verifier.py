"""
Tests for tools/verify_go_checklist.py — the GO checklist structural verifier.

The verifier exists because a signature landed on a row with empty Status and
Evidence three separate times. Its own classification logic is therefore exactly
the kind of thing that must not be allowed to drift untested: the RESOLUTION TRACE
renderer drifted from its spec precisely because nothing asserted its format.

These tests pin the three permitted row states and every defect state, and assert
the real checklist is structurally sound.
"""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "verify_go_checklist", REPO_ROOT / "tools" / "verify_go_checklist.py"
)
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)

ITEM, STATUS, EV, BY, AT = "an item", "Complete", "evidence text", "Kevin Brown", "2026-08-08 21:17 EDT"


def row(item=ITEM, status="", evidence="", by="", at=""):
    return [item, status, evidence, by, at]


class TestPermittedStates(unittest.TestCase):
    """The three states the process actually allows."""

    def test_all_four_fields_empty_is_open(self):
        state, _ = verifier.classify(row())
        self.assertEqual(state, verifier.OPEN)

    def test_status_and_evidence_without_signature_is_drafted(self):
        """What a Claude drafting commit produces — legitimate, awaiting the operator."""
        state, _ = verifier.classify(row(status=STATUS, evidence=EV))
        self.assertEqual(state, verifier.DRAFTED)

    def test_all_four_fields_filled_is_complete(self):
        state, _ = verifier.classify(row(status=STATUS, evidence=EV, by=BY, at=AT))
        self.assertEqual(state, verifier.COMPLETE)

    def test_permitted_states_are_not_defects(self):
        for cells in (row(), row(status=STATUS, evidence=EV),
                      row(status=STATUS, evidence=EV, by=BY, at=AT)):
            state, _ = verifier.classify(cells)
            self.assertNotIn(state, verifier.DEFECTS)


class TestSignedOverBlank(unittest.TestCase):
    """The defect that actually occurred, three times. A blank row is visibly
    unfinished; a row signed over blank evidence looks finished."""

    def test_signature_with_both_status_and_evidence_empty(self):
        state, why = verifier.classify(row(by=BY, at=AT))
        self.assertEqual(state, verifier.SIGNED_OVER_BLANK)
        self.assertIn("asserts nothing", why)

    def test_signature_with_evidence_empty_but_status_filled(self):
        state, why = verifier.classify(row(status=STATUS, by=BY, at=AT))
        self.assertEqual(state, verifier.SIGNED_OVER_BLANK)
        self.assertIn("Evidence", why)

    def test_signature_with_status_empty_but_evidence_filled(self):
        state, why = verifier.classify(row(evidence=EV, by=BY, at=AT))
        self.assertEqual(state, verifier.SIGNED_OVER_BLANK)
        self.assertIn("Status", why)

    def test_signed_over_blank_is_a_defect(self):
        state, _ = verifier.classify(row(by=BY, at=AT))
        self.assertIn(state, verifier.DEFECTS)


class TestPartialStates(unittest.TestCase):

    def test_name_without_timestamp(self):
        state, why = verifier.classify(row(status=STATUS, evidence=EV, by=BY))
        self.assertEqual(state, verifier.PARTIAL_SIGNATURE)
        self.assertIn("Verified at", why)

    def test_timestamp_without_name(self):
        state, why = verifier.classify(row(status=STATUS, evidence=EV, at=AT))
        self.assertEqual(state, verifier.PARTIAL_SIGNATURE)
        self.assertIn("Verified by", why)

    def test_status_without_evidence(self):
        state, _ = verifier.classify(row(status=STATUS))
        self.assertEqual(state, verifier.PARTIAL_DRAFT)

    def test_evidence_without_status(self):
        state, _ = verifier.classify(row(evidence=EV))
        self.assertEqual(state, verifier.PARTIAL_DRAFT)


class TestMalformed(unittest.TestCase):
    """An unescaped pipe inside an Evidence cell reshapes the table silently."""

    def test_too_many_cells(self):
        state, why = verifier.classify([ITEM, STATUS, "ev | with pipe", BY, AT, "extra"])
        self.assertEqual(state, verifier.MALFORMED)
        self.assertIn("6 cells", why)

    def test_too_few_cells(self):
        state, _ = verifier.classify([ITEM, STATUS, EV])
        self.assertEqual(state, verifier.MALFORMED)


class TestParsing(unittest.TestCase):

    def test_header_and_separator_rows_are_skipped(self):
        text = (
            "### A9. Example\n"
            "| Item | Status | Evidence | Verified by | Verified at |\n"
            "|---|---|---|---|---|\n"
            f"| {ITEM} | {STATUS} | {EV} | {BY} | {AT} |\n"
        )
        rows = list(verifier.parse_rows(text))
        self.assertEqual(len(rows), 1)
        line_no, section, cells = rows[0]
        self.assertEqual(line_no, 4)
        self.assertEqual(section, "A9. Example")
        self.assertEqual(cells[3], BY)

    def test_section_key_extraction(self):
        self.assertEqual(verifier.section_key("A2. Engineering completeness"), "A")
        self.assertEqual(verifier.section_key("C. Preparation Work"), "C")
        self.assertEqual(verifier.section_key("Scaffold-hooks debt"), "")


class TestRealChecklist(unittest.TestCase):
    """The shipped checklist must always be structurally sound. This does not
    assert any row is signed — only that no row is in a defective state."""

    def test_live_checklist_has_no_defective_rows(self):
        text = verifier.CHECKLIST.read_text(encoding="utf-8-sig")
        rows = list(verifier.parse_rows(text))
        self.assertGreater(len(rows), 0, "no table rows parsed — parser or path is wrong")
        for line_no, section, cells in rows:
            state, why = verifier.classify(cells)
            self.assertNotIn(
                state, verifier.DEFECTS,
                f"{verifier.CHECKLIST.name} L{line_no} [{section}]: {state} — {why}",
            )

    def test_every_live_row_has_exactly_five_cells(self):
        text = verifier.CHECKLIST.read_text(encoding="utf-8-sig")
        for line_no, section, cells in verifier.parse_rows(text):
            self.assertEqual(len(cells), verifier.EXPECTED_CELLS,
                             f"L{line_no} [{section}] has {len(cells)} cells")


if __name__ == "__main__":
    unittest.main()
