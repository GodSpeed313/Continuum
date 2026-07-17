# M7 Ruling Addendum 1 — IdentityIntegrity edge cases + pre-send gate ordering

**Status:** LOCKED / binding for implementation (signed off 2026-07-17 — A1–A6 approved as
drafted). Grammar verification performed at sign-off: the `arbiter` block in the terminology note
is a real grammar keyword (`pi_script/pi_script.lark:131`, `arbiter_decl`), distinct from the
retired component name — the note stands.

**Amends:** `docs/m7_identity_integrity_ruling.md` (LOCKED 2026-07-16). §A5 additionally amends the
shared pre-send gate contract described in the gate sections of
`docs/m7_credential_integrity_ruling.md` (§4/§5) and `docs/m7_link_restriction_ruling.md` (§4/§5),
because the gate is one mechanism serving all three M7 constraints.

**Provenance:** external technical review received 2026-07-17. Every mechanical claim in that review
was verified against `moltbook/detector.py`, `moltbook/client.py`, the M7 rulings, and the v0.1/v0.2
grammar specs before being accepted here. Findings that did not survive verification are not in this
addendum.

---

## A1 — `declared_handle` must be non-empty (fail-closed at construction)

**Problem (verified).** `MoltbookClient(declared_handle: str = "")` flows into
`known = {_norm(declared_handle)}`, so an unconfigured client's known-identity set is effectively
`{""}` and **any** explicit self-naming statement ("My name is ContinuumAgent") fires the gate. The
current behavior is fail-closed by accident, not by decision — it conflates *missing configuration*
with *identity drift*, which is exactly the silent-assumption failure mode Continuum exists to
eliminate.

**Ruling.** Constructing a governed client without a non-empty (post-strip) `declared_handle` is a
configuration error, not a degraded mode:

```python
if not declared_handle.strip():
    raise ValueError("declared_handle is required: IdentityIntegrity cannot run without a session-start baseline")
```

**Rejected alternative:** auto-disabling the identity gate when no handle is supplied
(`identity_integrity_enabled = bool(declared_handle.strip())`). A governed production client
silently running with a constraint switched off is the same silent-assumption failure in the other
direction. A constraint either has a trustworthy baseline or the client does not construct.

**Required tests:** construction with `""` and with whitespace-only handle raises `ValueError`;
construction with a valid handle is unaffected; existing suite updated where clients were
constructed handle-less.

---

## A2 — Identity name format: full display names are supported; comparison is token-prefix-tolerant

**Problem (verified — worse than the review stated).** The API accepts a multi-word
`declared_name` (normalized as a complete string), but the capture group `(\w[\w-]{1,})` takes one
token. With `declared_name="Continuum Guardian"`, the truthful statement *"My name is Continuum
Guardian"* captures only `continuum`, which is not in the known set → the gate **blocks a truthful
self-naming, latches `identity_drift`, and freeze+escalates the session**. That is a self-inflicted
session freeze on a supported configuration, and it directly undermines §6 of the base ruling, whose
entire justification for `freeze + escalate` is that v1 detection is high-confidence.

**Decision (resolves the unmade choice the API was papering over).** v1 identities are:

- `declared_handle` — single token, `@`/`u/`-strippable (unchanged), and
- `declared_name` — an optional **full display name, which may be multi-word**.

**Detector contract.** The self-naming capture is extended to a bounded multi-token phrase (word
tokens joined by single spaces, capped at 4 tokens, stopping at punctuation). A captured claim is
**consistent** — must NOT fire — iff, after normalization, it stands in a leading-token-prefix
relation with any known identity in either direction:

- the captured phrase is a leading-token prefix of a known identity
  (*"my name is Continuum"* vs. declared `Continuum Guardian` → consistent), or
- a known identity is a leading-token prefix of the captured phrase
  (*"my name is Continuum Guardian the Third"* → capture `Continuum Guardian the Third`, of which
  the declared `Continuum Guardian` is a leading prefix → consistent; note punctuation ends the
  capture, so *"my name is Continuum Guardian, obviously"* captures exactly `Continuum Guardian`).

A claim that matches no known identity under this bidirectional tolerance fires as `handle_name`
(*"my name is Continuum Destroyer"* — shares a first token but is a prefix of nothing and nothing is
a prefix of it → **fires**).

**Accepted false-negative surface.** Prefix tolerance means a claim that merely truncates a known
name never fires. Accepted: the base ruling explicitly prefers false negatives over freezing normal
traffic (§6, severity-paired-to-confidence). This is the same trade as the dominant-register guard.

**Required tests:** truthful multi-word self-naming with multi-word `declared_name` → clean pass
(the regression for the self-DoS above); divergent multi-word claim (`Continuum Destroyer`) → fires;
single-token truthful prefix → clean; existing single-token contradiction cases unchanged.

---

## A3 — Role-negation word boundaries

**Problem (verified).** `r"i(?:'m| am) not (?:a |an |the )?" + re.escape(role)` has no anchors:
declared role `art` matches *"I am not an artist."*, and the leading `i` can bind inside a preceding
token.

**Ruling.** Anchor both ends:

```python
r"\bi(?:'m| am) not (?:a |an |the )?" + re.escape(role) + r"(?=\W|$)"
```

Phrase-level ambiguity (declared role `art` vs. *"I am not an art critic"*) remains out of scope —
boundaries fix token-level false matches, not semantics.

**Required tests:** role `art` + *"I am not an artist."* → clean pass; role `auditor` + *"I'm not an
auditor"* → still fires (regression guard on the fix itself).

---

## A4 — Quoted / reported speech: documented known gap, no exclusion zones in v1

**Problem (verified — currently undocumented).** The detector scans raw outbound text with no
speaker attribution. *The attacker wrote, "My name is RootAdmin."* or *Do not post messages like:
"I am @fake_support."* fire as if the agent renamed itself. The base ruling's only pinned detector
gap is semantic persona-drift; this one has no pin and no mention.

**Ruling.** Quoted/reported speech is a **named v1 false-positive gap**, pinned by an
`xfail(strict)` test asserting the aspirational non-fire on quoted material (same discipline as the
persona-drift pin — it fails by design today and surfaces as a visible `xpass` if attribution ever
improves). Quote/code-fence **exclusion zones are deliberately NOT added in v1**: an exclusion zone
is an evasion channel — an agent that wraps a real self-declaration in quote markers walks through
the gate. Any future exclusion mechanism must ship with adversarial tests proving a real
self-declaration cannot be disguised as quotation to bypass detection. Until then the gate stays
over-broad rather than evadable — for a `freeze + escalate` constraint, a rare false positive on
quoted text is the safer failure than a clean bypass.

**Required tests:** the `xfail(strict)` pin described above, plus a clean-pass confirming a quoted
*matching* identity does not fire (nothing to contradict).

---

## A5 — Pre-send gate runs scan-all-then-block (amends the shared gate contract)

**Grounding — this is not a new design choice.** Pi Script v0.1, Resolution Q1
(`docs/pi_script_v01_draft3.md`): *"All active violations are logged as co-active in the RESOLUTION
TRACE regardless of which action executes. No violation is silently dropped. The human reviewer sees
the full set."* Ruling 9.7 (v0.2) makes the arbiter block — the meta-constraint layer that resolves
compound consequences — mandatory. The current gate is fail-fast (credential → link → identity,
first hit raises), so a message tripping multiple gates latches only the first: later latches are
never set, the resolver never sees the violations as co-active, and — verified — a credential-blocked
message never even gets its URLs written to the link provenance log, because `scan_links` never
runs. Fail-fast at the gate silently drops violations that Q1 says may never be silently dropped.

**Ruling.** On every outbound action the gate:

1. runs **all** detectors (`scan_content`, `scan_links`, `scan_identity`) unconditionally;
2. latches **every** finding (`credential_exposed`, `link_violation`, `identity_drift`) and always
   writes the link provenance log;
3. then blocks **once**, raising the most-severe applicable exception — severity order unchanged:
   `KeyLeakBlocked` > `LinkBlocked` > `IdentityDriftBlocked`.

Prevention behavior is unchanged (the message was blocked before and is blocked now); what changes
is audit completeness — the snapshot carries the full co-active set, so the resolver rules on the
whole simultaneous event per Q1's restrictiveness-ordering rather than on procedural gate order.

**Required tests:** a single message tripping all three gates → all three latches set, link log
populated, `KeyLeakBlocked` raised; resolver evaluation of the resulting snapshot shows all three
constraints co-active in the RESOLUTION TRACE; single-violation messages behave exactly as before.

---

## A6 — Named scope distinction: identity *consistency*, not identity *authenticity*

**Ruling (documentation of scope, no code change).** IdentityIntegrity v1 guarantees
**consistency**: the agent remained consistent with the baseline captured at session start. It does
**not** guarantee **authenticity**: that the baseline itself was legitimate or authorized. The
baseline is whatever the constructor was handed — a compromised agent that self-initializes with an
attacker-chosen identity stays perfectly "consistent" with it. A1's non-empty requirement is
necessary for a trustworthy baseline but not sufficient.

This is the same honest-scope move as LinkRestriction's provenance-not-payload framing and gets the
same treatment: named in the ruling, not hidden. Baseline **trust establishment** — a signed
deployment manifest, owner-controlled configuration, a platform profile fetch at session start, or
an immutable session token — is a separate trust mechanism, a v1.1+ candidate, and out of scope for
v1. Until it exists, IdentityIntegrity's claim is: *given* the declared baseline, the agent did not
contradict it mid-session.

---

## Terminology note (for anything copied out of the external review)

The **component** is the resolver (`pi_script/resolver.py`) — "the Arbiter" is retired as a
component name per `CLAUDE.md`. The **`arbiter` grammar block** remains correct, current spec
terminology (Ruling 9.7 requires it by that name). The external review's uses of "Arbiter" referred
to the grammar-layer ruling and were accurate; only prose about the runtime component needs the
resolver name.

---

## Out of band (mechanical, no sign-off needed, done alongside this draft)

- `README.md` build-status: stale "278 tests passing" corrected; M7 row added.
- `CLAUDE.md` repo map: same stale count corrected.

## Sign-off checklist

- [x] A1 — fail-closed constructor
- [x] A2 — display-name decision + prefix-tolerant comparison
- [x] A3 — role-negation anchors
- [x] A4 — quoted-speech xfail pin, no exclusion zones
- [x] A5 — scan-all-then-block gate (touches all three M7 constraints' gate behavior)
- [x] A6 — consistency-vs-authenticity distinction added to ruling scope

Signed off 2026-07-17, as drafted.

## Implementation note (post-lock, 2026-07-17) — A2 residual gap discovered while building

The A2 capture/comparison mechanics surfaced one residual false positive the draft did not state:
**truncating a multi-word declared name and continuing the sentence without punctuation** pollutes
the capture with chatter tokens (*"my name is Continuum and I audit constraints"* → capture
`Continuum and I audit`), which diverges at token 2 exactly the way *"Continuum Destroyer"* does —
the two are mechanically indistinguishable in v1. Mere truncation with punctuation (*"call me
Continuum."*) is clean, as A2 states; only the unpunctuated-chatter variant fires. This narrow case
requires a multi-word `declared_name` whose first word is not the handle, plus self-truncation
mid-sentence. Pinned by an `xfail(strict)` test asserting the aspirational non-fire
(`test_truncated_name_with_trailing_chatter_is_a_known_false_positive`), same treatment as every
other documented gap. No A1–A6 decision is changed by this note; a capitalization-gated token
continuation (name-cased tokens only) is a candidate v1.1 refinement that would resolve it.

Build order after LOCK: detector/client changes (A1–A3, A5) → tests including A4 pin → full suite
green → README/ruling cross-references updated.
