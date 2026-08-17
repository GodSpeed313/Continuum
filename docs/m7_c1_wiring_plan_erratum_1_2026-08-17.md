# C1 Live CAPTCHA Wiring Plan — Erratum 1

**Status:** DRAFT — awaiting operator signature. Corrects nothing until signed.
**Subject document:** `docs/m7_c1_live_captcha_wiring_plan_2026-08-13.md` (LOCKED, signed
`Kevin Brown` / 2026-08-13 18:28 EDT)
**Raised:** 2026-08-17, during C2 implementation of §3.2/§3.3.

---

## 1. What this erratum is, and what it is not

This erratum corrects **one scope word in one internal cross-reference**. It is filed as its own
dated artifact rather than as an edit to the locked plan, following the precedent that a locked
document is not reopened to record a correction.

**It corrects:** the row range cited by §3.2 rule 1 when it points at §3.3.

**It does not:**

- change any row's **outcome**. Every outcome in §3.3 is exactly as signed.
- change §3.3 in any respect — not its rows, its detection column, its outcomes, or its evidence
  provenance.
- decide anything that was undecided. No response condition acquires a classification it did not
  already have under §3.3 as signed.
- reopen, revisit, or re-weigh §3.4 (the HTTP 409 reasoning), §4, §5, §6, §7, or §9.
- alter the plan's version binding to the 2026-07-21 `moltbook.com/skill.md` capture.

**The distinction this erratum depends on:** §3.3 assigns outcomes; §3.2 describes the order in
which rows are *reached*. The defect is in the second, and correcting it changes which rule reaches
a row — never what the row says when reached.

## 2. The defect

§3.2 rule 1 reads:

> **An enumerated non-2xx HTTP status (§3.3 rows 3–7) is authoritative** and classifies the
> response regardless of body content.

Rows 3–7 are C1-3 (410), C1-4 (404), C1-5 (409), C1-6 (429), and C1-7 (401).

§3.3 also enumerates two further non-2xx statuses: **C1-8 (HTTP 400)** and **C1-9 (HTTP 500)**.
Rule 1 does not reach them, because its cited range stops at row 7.

§3.2 rule 4 does not reach them either. It reads:

> **A non-2xx status not enumerated in §3.3** matches none of the rules above and falls to §4 below.

400 and 500 *are* enumerated in §3.3, so rule 4 excludes them by its own terms. Rules 2 and 3 are
both conditioned on 2xx.

**Consequence as written:** HTTP 400 and HTTP 500 are matched by no rule of §3.2. Rule 4 was added
precisely so that "rules 1–3 are not a complete decision procedure on their own" would not leave a
response without a verdict; the same incompleteness remains for these two statuses, and it is not
closed by rule 4 because rule 4's condition excludes them.

## 3. Why this is a citation slip and not an unstated decision

Four features of the plan as signed establish that rows 8 and 9 were intended to be reached. The
first three bear on both rows; the fourth is direct evidence for row 9 only, and is noted as such:

1. **§3.3 assigns them outcomes.** C1-8 and C1-9 each carry a Detection column (HTTP 400 / HTTP
   500), an Outcome column (`AMBIGUOUS` for both), and an evidence-provenance entry. A row that
   could never be reached would not carry a detection rule.
2. **§8 item 1 requires all of them to be reachable.** §8 states that C2 is complete when all of
   its items are evidenced, and item 1 is "`submit_captcha_fn` implements §3.3 exactly — every
   enumerated condition classified as specified, with the §3.2 precedence order applied in that
   order." (Quoted without the source's bold; no emphasis added.) Under the uncorrected reading,
   C1-8 and C1-9 are classified as `C1-R` and never as themselves, so item 1 could not be satisfied
   for two rows the plan enumerates.
3. **Rule 4's own examples exclude them.** Rule 4 illustrates its scope with "a response such as
   `403` or `503`" — two statuses §3.3 does *not* enumerate. Neither example is an enumerated row,
   which is consistent with rule 4 being aimed at unenumerated statuses only.
4. **§7's own example list treats C1-9 as reachable.** Setting out why the recording requirement
   exists, §7 contrasts "a documented-ambiguous response (C1-6, C1-9, C1-10)" with "a response C1
   never enumerated (C1-R)". C1-9 appears there as a documented-ambiguous condition *distinct from*
   the residual case — so a section of the plan written after §3.2 already assumes row 9 is
   recorded as itself rather than folded into C1-R. **That list does not name C1-8**, so this point
   is direct evidence for row 9 only; row 8's reachability rests on points 1–3 and on its identical
   structural position in §3.3 (an enumerated non-2xx status with its own detection rule and
   outcome).

## 4. The correction

§3.2 rule 1's parenthetical should read, correcting the citation to the enumerated non-2xx rows of
§3.3 as a whole rather than the sub-range "rows 3–7":

> **An enumerated non-2xx HTTP status (§3.3 rows 3–9) is authoritative** and classifies the
> response regardless of body content.

Rows 3–9 are C1-3 (410), C1-4 (404), C1-5 (409), C1-6 (429), C1-7 (401), C1-8 (400), and C1-9
(500) — that is, every non-2xx status §3.3 enumerates. Rows 1 and 2 are the 2xx rows governed by
rules 2 and 3; rows 10 and 11 (C1-10, C1-R) are not statuses and are governed by §3.3's own
detection column and by §4 respectively.

No other text of §3.2 changes. Rule 4 is unamended and continues to cover non-2xx statuses that
§3.3 does not enumerate, `403` and `503` among them.

## 5. Outcome neutrality

**This correction changes no outcome, at runtime or on the record's `outcome` field.** C1-8 and
C1-9 are `AMBIGUOUS` in §3.3 as signed, and `C1-R` is `AMBIGUOUS` under §4. A response classified
either way produces the same `CaptchaOutcome`, the same `publication_status`, and the same
`verification_status`, and moves no counter.

What the correction changes is **which condition identifier is recorded**, and that is the reason it
is worth correcting rather than tolerating. §7 requires the record to distinguish a
documented-ambiguous outcome from a response the plan never enumerated, because "those two facts
carry opposite weight. The first confirms the documented model held. The second falsifies it."
Under the uncorrected reading, a documented HTTP 400 or 500 would be recorded as a falsification of
the model rather than a confirmation of it, and §E's question would be answered wrongly from a
correctly-classified response.

## 6. Effect on the implementation, stated plainly

The C2 implementation committed at `55fd620` treats all seven enumerated non-2xx statuses as
authoritative under §3.2 rule 1 — the corrected reading. It was written that way because §8 item 1
admits no other reading, and the divergence from §3.2's literal text was recorded in the code at the
mapping and in the commit message at the time, not discovered afterwards.

**This erratum does not authorize that implementation retroactively, and signing it does not
constitute review of the C2 code.** It records what the plan means. Whether C2 correctly implements
the plan is the C2 checklist row's question, answered by its own evidence and its own signature.

## 7. Scope and limits of this document

This erratum is bound to `docs/m7_c1_live_captcha_wiring_plan_2026-08-13.md` as signed on
2026-08-13, and inherits that document's version binding to the 2026-07-21 capture without widening
it. It asserts nothing about the platform's behaviour, and nothing about whether any §3.3
classification is empirically correct — §2 of the plan states that none has been confirmed against a
live write, and this erratum leaves that statement exactly as it stands.

---

```
Status:
Corrected by (operator): Kevin Brown
Corrected at: 2026-08-17 00:42 EDT
Statement: "I have reviewed the defect described in §2 and the correction in §4,
            and confirm this erratum corrects the scope of a cross-reference in
            §3.2 rule 1 only. It changes no row's outcome, amends no other
            section, and decides nothing that was undecided."
```
