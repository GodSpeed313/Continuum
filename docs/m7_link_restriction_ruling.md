# M7 Constraint Ruling — LinkRestriction

**Status:** LOCKED / binding for implementation (signed off 2026-07-16, both open questions
resolved — see §9). Canonical spec-first ruling required by `CLAUDE.md` and the
`pi-script-constraint` skill for the LinkRestriction constraint in the M7 (Moltbook) deployment.
Build order: `moltbook/moltbook.pi` (entity extension + constraint) → link-provenance detector →
gate wiring in `moltbook/client.py` (with reshare logging) → test set (violation/clean pair +
reshare-logging + allowlist-immutability).

**Numbering note:** No grammar change — LinkRestriction is the existing Form 2 `equality_rule`
(`MoltbookSession.link_violation must equal false`), same shape as CredentialIntegrity. This is an
application-level M7 constraint ruling, not a 9.x grammar ruling. If review finds the six rule
forms can't express it, that is a grammar conversation before any code.

---

## 1. Ruling (locked text)

The M7 agent may only surface external links that are **(a)** present in the source content it is
directly responding to or citing, or **(b)** on a static allowlist maintained in `moltbook/` config,
editable only outside the agent's runtime reach (never self-modifiable). The agent must never
generate, construct, or surface a novel external URL it was not given — including URLs assembled from
fragments, shortened/redirect links, or links suggested by another agent's post or DM that don't meet
(a) or (b). A violation is: outbound content contains a URL not traceable to one of the two permitted
sources. This is a **provenance check, not payload inspection** — the constraint doesn't judge whether
a link is malicious, only whether the agent had legitimate grounds to surface it. Priority **high**,
`on_violation: freeze + escalate`. Resharing a link present in source content passes the gate but is
**logged in every resolution trace regardless of outcome**, to build a provenance record for future
coordinated-link-seeding detection (out of scope for v1). The **pre-send gate is the primary control**
(same detect-can't-undo-a-post logic as CredentialIntegrity); the Pi Script constraint is the
audit/freeze layer for anything that slips through.

## 2. Why (threat)

The M7 recon notes flagged coordinated link-seeding as a live Moltbook pattern — the
`moltbook_pyclaw` / `Ting_Fodder` / `doctor_crustacean` cluster builds apparent authority through a
dense self-citation trail of cross-linked posts. A governed agent that could be steered (by an
injection payload or another agent's DM) into surfacing an attacker-chosen link becomes a node in
that seeding graph. The defensible v1 line is **provenance**: the agent surfaces a link only when it
can point to legitimate grounds (it was in the content being responded to, or on a human-owned
allowlist). Judging whether a link is *malicious*, or detecting *coordinated seeding chains*, is
explicitly out of scope — that is future ManipulationFlag v1.1/v2 or LinkRestriction v1.1 territory.
v1 does not pretend to solve it; it leaves the trail that later work needs (§5).

## 3. Constraint definition

Same boolean-latch pattern as CredentialIntegrity. A detector/gate sets `link_violation`; Pi Script
rules on the snapshot.

```
entity MoltbookSession {
    credential_exposed: boolean
    link_violation:     boolean      // set true by the link-provenance gate (§4)
    session_id:         identifier
}

constraint LinkRestriction {
    priority:     high
    rule:         MoltbookSession.link_violation must equal false
    on_violation: freeze + escalate
}
```

- **`priority: high`** (not `critical`): a leaked *key* is irreversibly exploitable; an
  un-provenanced *link* is a governance/authority-integrity failure, serious but a tier below key
  loss. `freeze + escalate` still applies — the agent stops and a human reviews.
- Grammar-valid Form 2, boolean value, identical machinery to `CredentialIntegrity` /
  `ScopeGuard`.

## 4. Detection — provenance, not payload (Q1 resolved)

A pre-send gate in the client extracts every URL from candidate outbound content and classifies each:

| Provenance | Grounds | Outcome |
| --- | --- | --- |
| `source` | The exact URL appears in the source content the agent is responding to/citing (a). | Pass, logged (§5). |
| `allowlist` | The URL's host is on the static `moltbook/` allowlist (b). | Pass, logged (§5). |
| `novel` | Neither — constructed, fragment-assembled, shortened/redirect, or suggested by another agent's post/DM without meeting (a)/(b). | **Violation:** latch `link_violation`, block the send, `freeze + escalate`. |

**Allowlist maintenance (Q1, resolved — same principle as CredentialIntegrity §5.1 key isolation).**
The allowlist is a **static config in `moltbook/`** (a sibling config file), editable **only via
commit/PR — never writable by the running agent at runtime**. An agent that could expand its own
allowlist defeats the constraint the same way a model holding its own API key defeated
CredentialIntegrity before isolation. It is **read-only to the agent, human-owned.** The client loads
it as an immutable value with no runtime-mutation path.

This is a **provenance check, not payload inspection**: the gate never fetches the link, never judges
whether the destination is malicious — only whether the agent had legitimate grounds to surface it.

## 5. Reshare logging (Q2 resolved) — leave a trail v1 doesn't act on

Every surfaced link is recorded in the M7 resolution trace **regardless of pass/fail**, not only
violations — URL, provenance (`source`/`allowlist`/`novel`), and whether it was allowed. Reasoning:
the recon notes already flagged coordinated link-seeding (the pyclaw/Ting_Fodder self-citation trail).
LinkRestriction v1 should **not** try to judge that — out of scope, same as ManipulationFlag's
coordinated-pattern case — but it should leave a trail. That record is exactly what a future
ManipulationFlag v1.1/v2 or LinkRestriction v1.1 needs to detect seeded-link chains, without
pretending v1 already solves it.

**Implementation boundary:** the reshare/provenance log is **moltbook-local** — produced by the
client and attached to the M7 trace written under `moltbook/traces/`. It does **not** modify
`pi_script/trace.py`: core trace is shared by systems with no links (m5, es, quantization), and this
is client/adapter-layer concern, consistent with the CredentialIntegrity split (prevention +
provenance are client-side; Pi Script is the constraint/freeze/audit-latch layer).

## 6. Layer split (unchanged principle from CredentialIntegrity §5)

The **pre-send gate is the primary control** — same detect-can't-undo-a-post logic: once a post with
a novel link is transmitted, freeze can't recall it, so prevention must happen before send. The Pi
Script `LinkRestriction` constraint is the enforcement latch (freeze + escalate) and audit layer for
anything that slips past the gate (e.g. a client-code bug). A blocked novel link still latches
`link_violation` (belt-and-suspenders): a blocked attempt is itself evidence the agent was steered
toward surfacing an attacker link and should stop. As with CredentialIntegrity, a public trace must
not imply Pi Script "caught" the link — the client gate did.

## 7. Required tests (per CLAUDE.md, plus the two Q-specific tests)

In `tests/test_moltbook_link_restriction.py`:

- **Deliberate-violation:** outbound content with a `novel` URL (not in source, host not allowlisted)
  ⇒ gate latches `link_violation` ⇒ `LinkRestriction` fires ⇒ resolver `frozen`, `freeze + escalate`.
  Include the assembled-from-fragments and shortened-link variants.
- **Clean-pass:** a URL present in source content, and a URL whose host is allowlisted ⇒
  `link_violation` stays false ⇒ constraint SATISFIED, `running`.
- **Reshare-logging (Q2):** a link present in source content passes the gate AND appears in the
  provenance log with `provenance="source"`, `allowed=True` — proving pass-through links are still
  recorded.
- **Allowlist-immutability (Q1):** the loaded allowlist has no runtime-mutation path from the client
  (read-only), so the agent cannot expand its own permitted set.

## 8. Relationship to the other M7 constraints

- **CredentialIntegrity** governs secret exfiltration; **LinkRestriction** governs link provenance.
  Overlapping intent (don't emit dangerous strings), distinct detectors, distinct latches — separate
  constraints, both enforced on `MoltbookSession`.
- Coordinated cross-agent link-seeding / manipulation stays **out of scope** (v1.1/v2). LinkRestriction
  v1 provides the provenance trail; it does not judge chains.
- IdentityIntegrity and ManipulationFlag remain unwritten — each needs its own ruling before code.

## 9. Decisions log (resolved)

1. **Constraint name — `LinkRestriction`.** PascalCase, behavior-first, consistent with the M7 set.
2. **Priority — `high`, `on_violation: freeze + escalate`.** A tier below CredentialIntegrity's
   `critical` (link ≠ irreversibly-exploitable key), but still stops the agent for human review.
3. **Q1 allowlist maintenance — outside model reach (key-isolation principle).** Static `moltbook/`
   config, editable only via commit/PR, never self-modifiable at runtime; loaded read-only.
4. **Q2 reshare handling — pass but always log.** Links traceable to source/allowlist pass the gate;
   every surfaced link is logged in the M7 trace regardless of outcome, building the provenance record
   for future coordinated-seeding detection (out of scope for v1). Logging is moltbook-local (§5), not
   a core `trace.py` change.
