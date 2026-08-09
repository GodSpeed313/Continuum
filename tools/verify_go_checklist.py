"""
Structural verifier for the M7 Operator GO Checklist.

    docs/m7_operator_go_checklist.md

This does NOT judge whether a row's evidence is true — that is the operator's job
and cannot be automated. It checks that the table is structurally sound and that
every row is in one of the three states the process actually permits, so a row can
never end up asserting something nobody meant it to assert.

WHY IT EXISTS
─────────────
The checklist's four-field rule says an item is satisfied only when Item, Status,
Evidence, `Verified by`, and `Verified at` are all filled. Three separate times a
signature landed on a row whose Status and Evidence were empty — twice because the
web editor was pointed at the wrong branch, once because a 5,450-character Evidence
paste silently failed while the two short cells beside it succeeded. Each time the
result was an operator name recorded against an attestation that asserted nothing,
and each time it was caught by hand.

A blank row is visibly unfinished. A row signed over blank evidence looks finished.
That asymmetry is the whole reason this runs before a merge.

THE THREE PERMITTED ROW STATES
──────────────────────────────
    OPEN      all four fields empty — not yet worked
    DRAFTED   Status + Evidence filled, both signature fields empty — awaiting the
              operator; this is what a Claude drafting commit produces
    COMPLETE  all four fields filled — signed

Anything else is a defect. The one that matters most:

    SIGNED-OVER-BLANK   `Verified by` or `Verified at` filled while Status or
                        Evidence is empty — a signature attesting to nothing

That state is not a weaker satisfaction of the four-field rule; it is outside it.
The rule exists so that drafting and attesting are distinct acts, and a signature
that precedes its own evidence inverts them.

Structural damage (a row that does not split into exactly five cells) is also a
defect: an unescaped pipe inside an Evidence cell silently reshapes the table.

Usage:
    python tools/verify_go_checklist.py
        Report every row's state. Exit 0 if all rows are in a permitted state.

    python tools/verify_go_checklist.py --require-complete A
        Additionally require every row in section A to be COMPLETE. Use this to
        check a section's gate before relying on it — §B's GO-1 authorization
        requires all of §A complete, and this is how that claim gets verified
        rather than eyeballed.

    python tools/verify_go_checklist.py --quiet
        Print only defects and the summary.

Exit codes: 0 = all rows in a permitted state (and any --require-complete satisfied);
1 = at least one defect; 2 = the checklist could not be read or contains no tables.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
CHECKLIST = REPO_ROOT / "docs" / "m7_operator_go_checklist.md"

FIELDS = ("Item", "Status", "Evidence", "Verified by", "Verified at")
EXPECTED_CELLS = len(FIELDS)

OPEN, DRAFTED, COMPLETE = "OPEN", "DRAFTED", "COMPLETE"
SIGNED_OVER_BLANK = "SIGNED-OVER-BLANK"
PARTIAL_SIGNATURE = "PARTIAL-SIGNATURE"
PARTIAL_DRAFT = "PARTIAL-DRAFT"
MALFORMED = "MALFORMED"

DEFECTS = {SIGNED_OVER_BLANK, PARTIAL_SIGNATURE, PARTIAL_DRAFT, MALFORMED}

_SEPARATOR = re.compile(r"^\|[\s:|-]+\|$")


def classify(cells: list[str]) -> tuple[str, str]:
    """Return (state, explanation). `cells` excludes nothing — all five, stripped."""
    if len(cells) != EXPECTED_CELLS:
        return MALFORMED, (
            f"row splits into {len(cells)} cells, expected {EXPECTED_CELLS} — an "
            f"unescaped '|' inside a cell reshapes the table silently"
        )

    _, status, evidence, by, at = cells
    drafted = bool(status) and bool(evidence)
    draft_blank = not status and not evidence
    signed = bool(by) and bool(at)
    sig_blank = not by and not at

    if draft_blank and sig_blank:
        return OPEN, "not yet worked"
    if drafted and sig_blank:
        return DRAFTED, "awaiting operator signature"
    if drafted and signed:
        return COMPLETE, "signed"

    # Everything below is a defect. Report the most serious reading first.
    if (by or at) and (not status or not evidence):
        missing = [n for n, v in zip(("Status", "Evidence"), (status, evidence)) if not v]
        return SIGNED_OVER_BLANK, (
            f"signature present but {' and '.join(missing)} empty — this records an "
            f"operator against an attestation that asserts nothing"
        )
    if by and not at:
        return PARTIAL_SIGNATURE, "`Verified by` filled but `Verified at` empty"
    if at and not by:
        return PARTIAL_SIGNATURE, "`Verified at` filled but `Verified by` empty"
    if status and not evidence:
        return PARTIAL_DRAFT, "Status filled but Evidence empty"
    if evidence and not status:
        return PARTIAL_DRAFT, "Evidence filled but Status empty"
    return MALFORMED, "unclassifiable field combination"


def parse_rows(text: str):
    """Yield (line_no, section, cells). Skips table headers and separator rules."""
    section = "(before any section)"
    for i, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        if stripped.startswith("## ") or stripped.startswith("### "):
            section = stripped.lstrip("#").strip()
            continue
        if not stripped.startswith("|"):
            continue
        if _SEPARATOR.match(stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if cells and cells[0] == "Item":  # table header
            continue
        yield i, section, cells


def section_key(section: str) -> str:
    """'A2. Engineering completeness' -> 'A'. Used by --require-complete."""
    m = re.match(r"([A-Z])\d*\.", section)
    return m.group(1) if m else ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--path", default=str(CHECKLIST),
                        help="checklist to verify (default: %(default)s)")
    parser.add_argument("--require-complete", metavar="SECTION", action="append", default=[],
                        help="require every row in this section (e.g. A) to be COMPLETE; "
                             "repeatable")
    parser.add_argument("--quiet", action="store_true",
                        help="print only defects and the summary")
    args = parser.parse_args()

    # This report contains em-dashes and section signs, and the checklist it reads is
    # full of them. A cp1252 console would raise UnicodeEncodeError mid-report and
    # exit non-zero for a reason that has nothing to do with the checklist.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - Python < 3.7 only
        pass

    path = pathlib.Path(args.path)
    if not path.exists():
        sys.stderr.write(f"checklist not found: {path}\n")
        return 2
    text = path.read_text(encoding="utf-8-sig")

    rows = list(parse_rows(text))
    if not rows:
        sys.stderr.write(f"no table rows found in {path} — refusing to report success\n")
        return 2

    counts = {OPEN: 0, DRAFTED: 0, COMPLETE: 0}
    defects: list[str] = []
    by_section: dict[str, list[str]] = {}
    current = None

    for line_no, section, cells in rows:
        state, why = classify(cells)
        by_section.setdefault(section, []).append(state)
        if state in DEFECTS:
            defects.append(f"  L{line_no}  [{section}]  {state}: {why}")
        else:
            counts[state] += 1

        if not args.quiet:
            if section != current:
                print(f"\n{section}")
                current = section
            if state == MALFORMED:
                print(f"  L{line_no:<4} {state}")
            else:
                _, status, evidence, by, at = cells
                flag = "  <-- DEFECT" if state in DEFECTS else ""
                print(f"  L{line_no:<4} {state:<17} {len(evidence):>5} ev-chars  "
                      f"{(by or '—'):<13} {(at or '—'):<21}{flag}")

    print("\n" + "=" * 74)
    total = len(rows)
    print(f"{total} rows: {counts[COMPLETE]} complete, {counts[DRAFTED]} drafted, "
          f"{counts[OPEN]} open, {len(defects)} defective")

    if defects:
        print("\nDEFECTS — these must be resolved before the affected rows can be "
              "treated as meaningful:")
        for d in defects:
            print(d)

    failed = bool(defects)

    for want in args.require_complete:
        want = want.strip().upper()
        matching = {s: st for s, st in by_section.items() if section_key(s) == want}
        if not matching:
            print(f"\n--require-complete {want}: no section {want} found")
            failed = True
            continue
        incomplete = {s: [x for x in st if x != COMPLETE] for s, st in matching.items()}
        incomplete = {s: v for s, v in incomplete.items() if v}
        n = sum(len(v) for v in matching.values())
        if incomplete:
            print(f"\n--require-complete {want}: NOT SATISFIED — "
                  f"{sum(len(v) for v in incomplete.values())} of {n} rows not COMPLETE")
            for s, v in incomplete.items():
                print(f"    {s}: {', '.join(v)}")
            failed = True
        else:
            print(f"\n--require-complete {want}: SATISFIED — all {n} rows COMPLETE")

    if failed:
        return 1
    print("\nAll rows are in a permitted state (OPEN, DRAFTED, or COMPLETE).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
