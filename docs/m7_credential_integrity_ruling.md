# M7 Constraint Ruling — CredentialIntegrity

**Status:** LOCKED / binding for implementation (signed off 2026-07-15, including §5.1 key isolation).
All §9 design decisions are resolved. This is the canonical spec-first ruling required by `CLAUDE.md`
and the `pi-script-constraint` skill for the CredentialIntegrity constraint in the M7 (Moltbook)
deployment. Build order: `moltbook/moltbook.pi` (entity + constraint) → key isolation + pre-send gate
in the client → test set including the §7 `xfail` known-gap tests.

**Numbering note:** Pi Script *grammar* rulings use the 9.x series (Section IX of the Pi Script
spec). This ruling introduces **no grammar change** — CredentialIntegrity is expressible with the
existing Form 2 `equality_rule` (`state_ref "must" "equal" pi_value`). It is therefore an
*application-level constraint ruling* scoped to M7, not a 9.x grammar ruling. If review finds the
six existing rule forms cannot express the required check, that becomes a grammar conversation
(a real 9.x ruling) *before* any code — do not invent syntax to close the gap.

---

## 1. Problem

M7 deploys a Continuum-governed agent into Moltbook, a live social platform for autonomous agents,
holding a per-agent API key (`moltbook_sk_...`; app-verification keys are `moltdev_...`). Every
outbound action the agent takes — post, comment, DM — is a channel through which that key, or any
other secret the agent holds, could be emitted into a public or semi-public space.

This is not a hypothetical. Two independent signals define the threat:

1. **Documented platform breach.** A misconfigured Moltbook database exposed ~1.5M agent API tokens
   and private DMs, some containing plaintext third-party keys agents had shared with each other
   (Wiz, *"Exposed Moltbook Database Reveals Millions of API Keys"*). Credential leakage between
   agents is the platform's demonstrated failure mode, not an edge case.
2. **Adversarial environment (our own recon).** The M7 scoping notes classify Moltbook as adversarial
   and record coordinated manipulation patterns. A measurable share of platform content carries
   prompt-injection payloads specifically crafted to extract keys and secrets from other agents.

So the governed agent must never emit its own API key (or any held secret) through a Moltbook action,
**including when adversarially provoked into doing so.**

## 2. What "violation" looks like (concrete)

A violation is: the content of any outbound Moltbook action (post body, comment body, DM body, or
profile/bio field) contains the agent's own API key, or any string matching a known secret pattern.

Concrete positive cases (must fire):
- A DM reply that pastes `moltbook_sk_<own-key>` because another agent asked "share your token to sync."
- A post that echoes an injection payload's requested "debug dump" including the key.
- A comment relaying *another* agent's `moltbook_sk_`/`moltdev_` key (defends the ecosystem, and
  proves the agent isn't a leak vector for keys shared with it).

Concrete negative cases (must NOT fire — false-positive guards):
- A post that merely mentions the string "API key" or discusses credential hygiene in the abstract.
- A comment containing a random 64-char hex hash that is not key-shaped and not the known own-key.
- The agent referencing its own *agent name* or public profile URL (not a secret).

## 3. Constraint definition

CredentialIntegrity is a boolean-latch constraint over a session entity field that a detector sets.
Pi Script remains **detection-only** (per `CLAUDE.md`): it observes the snapshot and rules on it.

```
// In moltbook/moltbook.pi (M7 policy). Only the CredentialIntegrity-relevant
// entity field is shown here; the full MoltbookSession entity is defined by the
// M7 policy alongside IdentityIntegrity / ManipulationFlag / LinkRestriction.

entity MoltbookSession {
    credential_exposed:  boolean      // set true by the outbound-content detector (§4)
    // ... other M7 fields ...
}

constraint CredentialIntegrity {
    priority:     critical
    rule:         MoltbookSession.credential_exposed must equal false
    on_violation: freeze + escalate
}
```

- **`priority: critical`** — same tier as SpecAlignment/ScopeGuard in the M5 policy; a leaked key is
  unrecoverable, so this is the most severe class.
- **`freeze + escalate`** — freeze halts all further agent action in the session (no further posts
  can compound the exposure); escalate raises it for human/out-of-band handling (rotate the key).
  This is the maximum two-action form the grammar allows (`violation_action: simple_action ("+"
  simple_action)?`), and it is the correct pair here.
- **No `decay_check`.** Exposure is a latch, not a time-decaying measure; periodic re-evaluation
  adds nothing. Once `credential_exposed` is true, it stays a violation until the key is rotated and
  the session is explicitly reset.

This is grammar-valid Form 2 (`equality_rule`) with a boolean value — identical shape to the M5
`ScopeGuard` (`scope_flag must equal false`).

## 4. Detection specification (what sets `credential_exposed`)

The boolean is computed by the Moltbook adapter/client, **not** by Pi Script (Pi Script does not
inspect raw content — it evaluates state). The detector scans each outbound action's content, in
this priority order:

1. **Exact own-key match (primary, zero false positives).** The client knows its own API key. Any
   outbound content containing that exact string ⇒ `credential_exposed = true`. This is the
   highest-confidence signal and directly targets the stated threat ("never posts its OWN key").
2. **Key-prefix pattern match (secondary, ecosystem defense).** Content matching
   `moltbook_sk_[A-Za-z0-9]+` or `moltdev_[A-Za-z0-9]+` ⇒ true. Catches relaying of any agent's key,
   including keys shared *to* this agent via DM.
3. **(Deferred) generic high-entropy secret patterns.** Broad secret regexes (AWS, generic
   `sk-...`, etc.) are a later extension — high false-positive risk, out of scope for the first pass.
   Flag as a candidate, do not implement now.

The known own-key used for step 1 must be supplied to the detector **from the same secret source as
the client's auth** (see §6), never hard-coded and never read back out of any tracked file.

**What this detector does NOT catch (accepted first-pass limit).** Exact-match + prefix regex is
defeated by any content transformation — a key emitted base64-encoded, reversed, spaced out, or
split across two actions ("first half now, second half next comment") passes the scan. This is
tolerable for the *own* key because §5.1 removes the own key from the model's reach entirely (you
cannot transform-and-leak a string the model never had). It remains a real limit for **foreign/
relayed** keys, which do enter context. That gap is documented, not closed in the first pass, and is
pinned by the adversarial known-gap tests in §7 — do not silently assume the gate is robust against
a determined obfuscating adversary. Broadening detection to defeat encoding is a later extension,
weighed against the false-positive cost noted in step 3.

## 5. Layer boundary and an honest limitation (READ THIS)

Pi Script detects and the resolver freezes — but **freeze cannot un-send a message.** If the detector
only records `credential_exposed = true` *after* the content is transmitted, the key is already
public and the breach has already happened; `freeze + escalate` then only prevents *further*
compounding and triggers rotation. That is valuable (it stops the bleeding and creates the audit
trace) but it is **not prevention.**

True prevention requires a **pre-send gate in the Moltbook client**: the detector (§4) runs on
candidate content *before* transmission; if it fires, the client refuses to send, sets
`credential_exposed = true`, and lets the Pi Script constraint formalize the freeze + escalate +
trace. Prevention lives in the adapter's send path; governance, enforcement (session freeze), and
audit live in Pi Script. This split is consistent with the architecture: Pi Script is detection-only,
the Layer-1→Pi Script adapter owns I/O.

**Companion requirement (BINDING for M7):** the M7 Moltbook client MUST implement the §4 detector as
a pre-send gate — this is not optional and not deferrable. A leaked platform key is immediately and
irreversibly exploitable (that is the entire reason this constraint exists), so a detect-after-the-
fact version would be an audit trail for a breach that already happened, not integrity. This is
*unlike* the ManipulationFlag v1/v2 split, where deferring the harder case still leaves a working
v1; here, deferring the gate leaves logging, not protection. The gate ships with M7.

**Prevention is two mechanisms, not one:** §5.1 key isolation (removes the own key from reach) plus
the §4 pre-send gate (nets foreign/relayed keys and client-code bugs). The gate alone never
protected the own key against a determined adversary — isolation does.

**Framing discipline (for write-ups and traces):** the pre-send gate is a single-output filter that
lives in the *client*, not in Pi Script. Continuum's thesis is state-over-time, not single-output
filtering — so a public trace must not imply Pi Script "caught" the key. Prevention is isolation +
client gate; Pi Script's role is the enforcement latch (freeze + escalate + violation count) and the
redacted audit trace. A gate-*prevented* attempt still sets `credential_exposed = true` and freezes:
a blocked exfiltration attempt is itself proof the agent was successfully manipulated and must stop.

## 5.1 Key isolation (BINDING) — the own key never enters model context

The strongest protection for the own API key is that the model never possesses it. The key lives
**only in the client's transport/auth layer**: it sets the `Authorization: Bearer` header and is
never placed into the prompt, system message, tool output, or any context the model composes content
from. The model generates every post/comment/DM without the key in scope, so no injection payload —
however encoded, split, or socially engineered — can make it emit a string it has never seen.

- The §4 exact-own-key detector still runs as defense-in-depth against a **client-code** bug that
  templates the key into content (a code path the model isn't even involved in). Isolation is the
  primary defense; the detector catches the implementation mistake.
- Isolation does not cover **foreign** keys — a key another agent DMs you *does* enter context when
  the agent reads that DM. That path is exactly what the §4 pre-send gate exists to net, and why
  relaying a foreign key is the same `critical` violation (§8, decision #4).

## 6. Secret-storage requirement (binding)

The API key is a long-lived credential in a platform with a documented mass-key-exposure incident.
Storage rules for M7:

- **Never in a tracked file.** Not in `CLAUDE.md`, not in `moltbook/moltbook.pi`, not in
  `moltbook/state.json` (which *is* committed under the `m5/` dogfood pattern), not in any trace
  written to `moltbook/traces/`, not in `.claude/settings.json`.
- Note the current `.gitignore`: `.claude/*` with `!.claude/skills/` means `.claude/settings.json`
  stays private — but relying on that for a secret is fragile. Prefer an **environment variable
  (`MOLTBOOK_API_KEY`)** or a secrets manager, resolved at runtime.
- The detector's known-own-key (§4 step 1) reads from that same runtime source — the key exists in
  process memory only, never written back to disk in the repo tree.
- A trace that records a CredentialIntegrity violation MUST redact the offending string (record that
  a key-shaped secret was detected and where, never the secret itself) — otherwise the audit log
  becomes a second copy of the leak. This extends the `resolution-trace` skill's "strip anything
  that reveals a bypass map" rule to secrets.

## 7. Required test pair (per CLAUDE.md)

Both added to `tests/test_moltbook_*.py` (new file, matching suite convention — not a `.test` file):

- **Deliberate-violation test:** a MoltbookSession snapshot where outbound content contains the
  known own-key (and a second case: a `moltbook_sk_`-shaped foreign key) ⇒ `credential_exposed` set
  true by the detector ⇒ CredentialIntegrity fires ⇒ resolver state `frozen`, escalation recorded.
- **Clean-pass test:** superficially similar content — a post discussing "API keys" in the abstract,
  and a non-key 64-char hex string ⇒ `credential_exposed` stays false ⇒ constraint SATISFIED, no
  action. Guards the §2 negative cases against false positives.
- **Key-isolation test (§5.1):** assert the own key is never present in the model-facing context
  object the client builds for generation — i.e. the string does not appear in the assembled
  prompt/system/tool-output payload. This is the test that makes isolation a checked property, not
  an aspiration.
- **Adversarial known-gap tests (`xfail`, tracked):** foreign-key exfiltration in transformed form —
  a `moltbook_sk_` key base64-encoded, reversed, and split across two actions. These are expected to
  *pass the detector* (i.e. NOT be caught) in the first pass; marking them `xfail` documents the
  boundary explicitly and turns any future detection improvement into a visible `xpass`. Mirrors how
  Rift 3.1 pinned its documented dormant/closed paraphrase limitation instead of hiding it.

## 8. Relationship to the other M7 constraints

- **LinkRestriction** governs *external links/references* the agent surfaces. CredentialIntegrity
  governs *secret exfiltration*. Overlapping intent (don't emit dangerous strings) but distinct
  detectors and distinct failure modes — keep them separate constraints, do not fold one into the
  other.
- **IdentityIntegrity** (identity claims stay consistent) and **ManipulationFlag** (manipulative
  patterns toward others) are orthogonal. CredentialIntegrity is the fourth M7 constraint, added
  because the API-key threat is specific to holding a platform credential in an adversarial space.
- **Not** the coordinated cross-agent manipulation case — that remains an explicit v1.1/v2
  `ManipulationFlag` extension per the recon notes, out of scope here.

## 9. Decisions log (resolved)

1. **Constraint name — `CredentialIntegrity`.** Kept. PascalCase, behavior-first, consistent with
   the `IdentityIntegrity` sibling. No collision in the M7 set.
2. **Detection scope — narrow first pass.** Exact own-key match + `moltbook_sk_`/`moltdev_` prefixes
   only (§4 steps 1–2). Generic secret-shaped regex deferred: it is a false-positive minefield
   (flags legitimate discussion of what a credential looks like, code snippets, hypotheticals).
   Broaden later only if observed necessary.
3. **Pre-send gate — BINDING for M7, not deferred.** A detect-after-the-fact version of *this*
   constraint protects nothing, because a leaked key is irreversibly exploitable the instant it is
   public. Prevention is §5.1 key isolation + §4 pre-send gate, both shipping with M7 (§5).
4. **Foreign-key relaying — same `critical` tier.** A relayed key is a live credential becoming
   public through the agent's output; harm is identical regardless of whose key it was. Treating it
   as lower severity would create an incentive gap (careful with own key, careless echoing others').

**Added during sign-off — §5.1 key isolation (awaiting explicit nod).** Output-scanning is a soft
boundary for the own key (defeated by encoding). Isolating the own key out of model context makes it
unleakable by any injection and closes the gap the narrow detection scope (#2) would otherwise leave.
This is a new binding architectural requirement on the M7 client; it is the one item still needing a
yes before implementation begins.
