# M7 Constraint Ruling — IdentityIntegrity

**Status:** LOCKED / binding for implementation (signed off 2026-07-16). Canonical spec-first ruling
required by `CLAUDE.md` and the `pi-script-constraint` skill for the IdentityIntegrity constraint in
the M7 (Moltbook) deployment. Build order: `moltbook/moltbook.pi` (entity + constraint) →
mechanical-contradiction detector → gate wiring in `moltbook/client.py` → tests including the
gap-documenting `xfail` for deferred semantic drift.

**Numbering note:** No grammar change — Form 2 `equality_rule`
(`MoltbookSession.identity_drift must equal false`), same shape as CredentialIntegrity /
LinkRestriction. Application-level M7 ruling, not a 9.x grammar ruling.

---

## 1. Scope note (read this first)

This ruling is deliberately **partial**. The M7 baseline sampling pass
(`Moltbook_Baseline_Sampling__M7_IdentityIntegrity.md`) found that cross-session identity
change-rate — "how often do legitimate agents change bios/names vs. how static they are" — is **not
observable from a single snapshot**: Moltbook's profile UI has no edit history, and answering it
properly needs longitudinal cohort data (pinned at T0 2026-07-16, re-sampling in progress). This
ruling covers only what's grounded today: **within-session identity consistency**. The cross-session
change-rate threshold is an explicit, named gap (§5) — not something this ruling pretends to solve,
same discipline as CredentialIntegrity's encoding-gap `xfail` pins.

## 2. Ruling (locked text, scoped to within-session)

The M7 agent's declared identity — its stated name/handle, bio/persona claims, and any role it
asserts for itself — must remain consistent for the duration of a session once declared. A violation
is: the agent's own outbound content asserts an identity claim (name, role, persona, "I am / I do X")
that contradicts the identity it declared at session start, within the same session, with no
session-boundary reset in between.

This does **not** cover: the platform-level profile fields (bio text, avatar, verified badge)
changing **between** sessions — the deferred cross-session piece (§5); or a human owner legitimately
reconfiguring the agent between deployments — **a fresh session start is a legitimate reset point,
not a violation.**

## 3. Why (grounded in the baseline pass)

The baseline sampling found `✓ Verified` is near-universal and does **not** discriminate legitimate
agents from low-effort or manufactured accounts — a verified content-farm account (`lyralink`)
carries the same badge as serious participants. So IdentityIntegrity **can't lean on platform trust
signals**; it has to be **self-referential** — does the agent stay consistent with what *it itself*
declared, independent of what the platform badges it as. That is a narrower, more defensible claim
than "detect fake identities," and it is the part actually supported by what was observed.

## 4. Constraint definition

```
entity MoltbookSession {
    credential_exposed: boolean
    link_violation:     boolean
    identity_drift:     boolean      // set true by the within-session consistency gate (§6)
    session_id:         identifier
}

constraint IdentityIntegrity {
    priority:     high
    rule:         MoltbookSession.identity_drift must equal false
    on_violation: freeze + escalate
}
```

`priority: high` — same tier as LinkRestriction: a self-contradiction is an authority/trust-integrity
failure, serious and freeze-worthy, but not irreversibly-exploitable the way a leaked key is.

## 5. The explicit gap — cross-session change-rate (deferred, not solved)

This ruling does **not** define, and IdentityIntegrity v1 does **not** enforce, any threshold on how
often bio/name/persona changes **between** sessions. That requires the longitudinal cohort read (now
pinned and running) to establish what "normal" static-vs-mutable actually looks like for legitimate
agents before any number gets written into a rule. Until that data exists, cross-session identity
change is **not** a v1 violation — flagging it now would be exactly the "identity_consistency > 0.85
because it feels right" mistake the recon notes warned against. Revisit as IdentityIntegrity v1.1
once the cohort data lands.

## 6. Detection — mechanical contradiction only (v1)

**This section was deliberately narrowed at sign-off, and the narrowing is load-bearing.** The
baseline pass found that first-person "I am / I do X" declarative claims are the **dominant normal
posting register** on Moltbook. A detector that fires on "identity claims" in general would collide
with the single most common sentence structure on the platform — a false-positive machine aimed at
normal traffic. So v1 detection is restricted to **mechanically-checkable contradictions** of the
identity captured at session start:

1. **Handle/name contradiction.** At session start the client captures the agent's declared handle
   (and optional display name), held immutable for the session. The detector flags outbound content
   only when it asserts a *different* self-identity through an **explicit self-naming construct** —
   `"my name/handle/username is X"`, `"call me X"`, `"I go by X"`, `"posting/signing as X"`, or a
   handle-prefixed self-claim `"I am @X"` / `"this is u/X"` — where X does not match the declared
   handle or name. Bare `"I am <phrase>"` **without** a `@`/`u/` prefix or a naming verb is NOT an
   identity claim (this is the guard against the dominant-register collision — "I am confident",
   "I am the senior engineer who read the paper" must not fire). A `@X`/`u/X` reference to *another*
   agent (e.g. `"@bytes nailed it"`) is not a self-claim and must not fire.
2. **Direct role negation.** The detector flags outbound content that explicitly negates a declared
   role string — `"I am not <declared_role>"` / `"I'm not <declared_role>"` — for a role captured at
   session start. Only direct negation of a captured role, not open-ended role inference.

**Deferred as a named gap (v1.1+): semantic persona-drift.** Detecting a subtle voice/persona shift
that contradicts the declared identity *without* an explicit handle/name/role construct is an
open-ended semantic-NLU problem and a false-positive minefield against Moltbook's confident,
declarative baseline tone. It is deferred exactly the way CredentialIntegrity deferred generic
secret-shaped regexes and LinkRestriction deferred malicious-link judgment. It is pinned by an
`xfail(strict)` test (§8) so nobody "fixes" it into enforcing something unmeasured, and so a future
improvement surfaces as a visible `xpass`.

**Severity is paired to detection confidence (the reason the narrowing matters).** `freeze +
escalate` freezes the whole session; that is only honest when a violation is high-confidence. Broad
semantic detection + freeze would be a false-positive machine aimed at normal traffic. The mechanical
scope above **is what justifies keeping `freeze + escalate`** — it is kept *because* v1 detection is
high-confidence, not kept by default and hoped to hold up. If detection were ever broadened to fuzzy
semantic drift, the action would have to soften to `flag`/`warn` until that detector proved out.

## 7. Detection mechanics + layer split (unchanged pattern)

A pre-send gate in the client captures declared identity once at session start and compares every
outbound action against it per §6. On a mechanical contradiction: latch `identity_drift`, block the
send (pre-send-gate-is-primary-control, same as CredentialIntegrity/LinkRestriction), raise
`IdentityDriftBlocked`, `freeze + escalate`. A blocked attempt still latches (belt-and-suspenders).
Prevention is client-side; Pi Script is the enforcement latch + audit. A fresh client / fresh session
is a legitimate reset — the declared identity is re-captured, so a between-session change is not a
within-session violation (§2).

## 8. Relationship to the other M7 constraints

Automation-cadence signals (e.g. the metronomic ~3-min posting pattern the baseline pass flagged in
`neo_konsi_s2bw`, and the coordinated cross-citation machine in `pepper_pots`) are **explicitly not**
part of IdentityIntegrity — those are behavioral/structural signals, ManipulationFlag v1.1/v2
territory. IdentityIntegrity stays scoped to **self-consistency of declared identity**, not detecting
bots by behavior. CredentialIntegrity (secret exfiltration) and LinkRestriction (link provenance)
remain distinct sibling constraints; all three enforce on `MoltbookSession`.

## 9. Required tests (per CLAUDE.md)

In `tests/test_moltbook_identity_integrity.py`:

- **Deliberate-violation:** agent declares identity X at session start; later same-session outbound
  content asserts a contradicting handle/name via an explicit self-naming construct → gate latches
  `identity_drift`, blocks, resolver `frozen` / `freeze + escalate`. Include a role-negation case.
- **Clean-pass:** consistent identity throughout a session (including bare first-person "I am /
  I do X" claims that are the normal register, and `@other-agent` references) → `identity_drift`
  stays false, `running`. Plus a fresh-session-boundary case: re-declaring a different identity in a
  *new* session is NOT a violation (models §2 reset).
- **Dominant-register guard:** normal declarative first-person content ("I am confident this parses",
  "I processed the document") does NOT fire — the explicit test that §6's narrowing holds.
- **Gap-documenting `xfail(strict)`:** a semantic persona-drift case with no explicit handle/name/
  role construct asserts the *aspirational* catch (`is_contradiction is True`); it currently fails by
  design (mechanical detection can't see it), documenting the deferred §6 gap exactly as
  CredentialIntegrity's encoding pins do, and flipping to a visible `xpass` if detection improves.

## 10. Decisions log (resolved)

1. **Name — `IdentityIntegrity`.** Consistent with the M7 set.
2. **Scope — within-session only for v1.** Cross-session change-rate deferred to v1.1 pending the
   longitudinal cohort (§5). Shipped now because within-session is a self-contained mechanism with no
   data dependency, and holding it hostage to a 2+-week-out data collection is the weaker trade.
3. **Detection — mechanical contradiction only (§6).** Handle/name via explicit self-naming
   constructs + direct role negation. Semantic persona-drift deferred as an `xfail`-pinned gap.
   Chosen because the baseline pass measured "I am / I do X" as the dominant normal register; a broad
   detector would fire on normal traffic.
4. **`priority: high`, `freeze + escalate` — kept, justified by the narrowed detection.** Severity is
   paired to confidence; the mechanical scope is what makes freezing the session defensible.
