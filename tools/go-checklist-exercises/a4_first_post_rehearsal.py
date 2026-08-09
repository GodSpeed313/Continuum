"""
§A4 — reproducible rehearsal for the M7 Operator GO Checklist.

    docs/m7_operator_go_checklist.md  §A4. Rehearsal

Row: "At least one Dry Run (§11) executed against a payload representative of the
      intended first post/reply — same shape, same `action_type` — producing detector
      results, Arbiter decision, approval trace, Approved Action Envelope, and
      simulated transport outcome, reviewed and free of surprises"

`action_type` is POST, by operator ruling on 2026-08-08.

WHAT THIS HARNESS DOES THAT THE SHIPPED CODE DOES NOT
─────────────────────────────────────────────────────
The row names five artifacts from one run. No shipped code path produces that chain,
for two structural reasons that are both deliberate:

  1. `as_client_transport` (moltbook/transport.py) is the only shipped bridge from
     MoltbookClient to an ActionEnvelope, and it is bound to MoltbookHTTPTransport —
     it reads `.outcome`, `.retry_category`, `.publication_status`. DryRunTransport
     returns a DryRunOutcome, which has `simulated_outcome` /
     `simulated_publication_status` and no `retry_category` at all: a deliberately
     separate type with "no shared base class and no implicit conversion"
     (transport.py). That is the §A2 structural-isolation property, working as
     designed. It also means the shipped adapter cannot be pointed at a dry run.
  2. `as_client_transport` builds envelopes with a plain uuid4 `action_id`, and
     DryRunTransport rejects any id outside the reserved `dryrun-` namespace.

So this script performs the trace-to-envelope binding ITSELF, locally, in
`bind_trace_to_envelope_id` below. **That binding is harness-local. It does not
assert, and must not be read as asserting, that the shipped Moltbook client
currently performs that join — it does not.** Everything else in this transcript is
real output from shipped classes: the detectors, the resolver, both longitudinal
governance passes, ActionEnvelope, and DryRunTransport are all called as shipped.

The separate matter of `approval_trace_id_fn` being an unwired seam in production is
filed as its own post-GO item (TODO.md, "M7 — post-GO engineering debt"), not left
as a footnote here.

WHAT IT DOES NOT DO
───────────────────
No network call: DryRunTransport has no request_fn seam, and the client's transport
seam is a recording stub. No production state: the longitudinal stores are created
in a temporary directory removed on exit. It asserts nothing the pytest suite does
not already assert; its purpose is to PRODUCE the five reviewable artifacts.

It authorizes nothing. A rehearsal on a representative payload is not a
pre-clearance of the eventual first post's content — detector results are
content-dependent, and the actual text is bound at GO-2 via `payload_hash` (§D).

Usage:
    python tools/go-checklist-exercises/a4_first_post_rehearsal.py
        Print the transcript.

    python tools/go-checklist-exercises/a4_first_post_rehearsal.py --check
        Print the transcript and compare it against the committed
        a4_first_post_rehearsal.expected.txt. Exit 0 on match, 1 on mismatch.

Volatile values (wall-clock timestamps, generated UUIDs) are redacted to fixed
placeholders so the transcript is reproducible.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from moltbook.cadence import CadenceObservationStore, run_cadence_governance  # noqa: E402
from moltbook.citation import CitationEdgeStore, run_citation_governance  # noqa: E402
from moltbook.client import LinkBlocked, MoltbookClient  # noqa: E402
from moltbook.detector import scan_content, scan_identity, scan_links  # noqa: E402
from moltbook.dryrun import DRY_RUN_ID_PREFIX, is_dry_run_id  # noqa: E402
from moltbook.transport import (  # noqa: E402
    ActionEnvelope,
    ActionType,
    DryRunTransport,
    canonical_payload_hash,
    make_dry_run_action_id,
)
from pi_script.parser import parse_file  # noqa: E402
from pi_script.resolver import resolve  # noqa: E402
from pi_script.validator import PiValidator  # noqa: E402

POLICY = REPO_ROOT / "moltbook" / "moltbook.pi"
CONFIG_V1 = "config-v1"
EXPECTED_PATH = Path(__file__).with_suffix("").with_name("a4_first_post_rehearsal.expected.txt")

# The governed account (CLAUDE.md: registered, verified, claimed).
HANDLE = "continuumagent"
DECLARED_NAME = "Continuum"
DECLARED_ROLES = ("governed agent",)

# ── The representative payload ───────────────────────────────────────────────────
# Representative in the two respects the row names: same SHAPE (a POST payload is
# {"content": ...} — no parent_post_id, which is what makes it a POST and not a
# REPLY) and same action_type (POST, ruled 2026-08-08).
#
# It is NOT the final text. The row's representativeness test is shape and
# action_type; it says nothing about content. Detector results are content-
# dependent, so a clean pass here is evidence about the PIPELINE, not a clearance
# of the eventual wording — that is bound at GO-2 via payload_hash.
REPRESENTATIVE_CONTENT = (
    "This account is governed by Continuum. Every outbound post is evaluated "
    "against a written policy before it is sent, and the resolution trace for "
    "that evaluation is recorded."
)

_UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_ISO = r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?"
_REDACTIONS = (
    (re.compile(rf"{re.escape(DRY_RUN_ID_PREFIX)}{_UUID}"), f"{DRY_RUN_ID_PREFIX}<uuid4>"),
    (re.compile(rf"datetime\.datetime\([^)]*\)"), "<utc-timestamp>"),
    (re.compile(_ISO), "<utc-timestamp>"),
    (re.compile(_UUID), "<uuid4>"),
)

_lines: list[str] = []


def emit(line: str = "") -> None:
    for pattern, replacement in _REDACTIONS:
        line = pattern.sub(replacement, line)
    _lines.append(line)


def rule(title: str) -> None:
    emit()
    emit("=" * 78)
    emit(title)
    emit("=" * 78)


def load_ir() -> dict:
    tree, err = parse_file(str(POLICY))
    assert err is None, err
    ok, errors, ir = PiValidator(tree).validate()
    assert ok, errors
    return ir


# ── The harness-local binding (see module docstring) ─────────────────────────────

_BOUND_TRACE_FIELDS = (
    "domain",
    "entity",
    "trigger_type",
    "triggered_by",
    "constraints",
    "conflict_resolution",
    "final_action",
    "system_state",
)


def bind_trace_to_envelope_id(trace: dict) -> str:
    """
    HARNESS-LOCAL trace-to-envelope binding. Not shipped behavior.

    A RESOLUTION TRACE carries no identifier of its own (pi_script/trace.py builds
    no id field), so an `approval_trace_id` has to come from somewhere. Rather than
    invent an opaque label, this derives a content-addressed id from the ruling
    itself, so the id is verifiably bound to that exact resolver output and changes
    if the ruling changes.

    `timestamp` and the derived `human_text` are excluded from the digest
    deliberately: the timestamp records WHEN the pass ran, not WHAT was ruled, and
    including it would make the id — and this transcript — irreproducible.
    """
    ruling = {field: trace[field] for field in _BOUND_TRACE_FIELDS}
    canonical = json.dumps(ruling, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"a4-rehearsal-trace-{digest[:16]}"


# ── Step 1 — detector results ────────────────────────────────────────────────────

def step_detectors(client: MoltbookClient, sent: list) -> None:
    rule("STEP 1 — DETECTOR RESULTS (shipped detectors, moltbook/detector.py)")

    emit()
    emit("Representative POST payload (shape and action_type, not final text):")
    emit(f"    {REPRESENTATIVE_CONTENT!r}")
    emit(f"    length: {len(REPRESENTATIVE_CONTENT)} chars")

    emit()
    emit("[1] scan_content — CredentialIntegrity")
    cred = scan_content(REPRESENTATIVE_CONTENT, own_key=client._api_key)
    emit(f"    is_leak             : {cred.is_leak}")
    emit(f"    detail              : {cred.detail!r}")

    emit()
    emit("[2] scan_links — LinkRestriction")
    links = scan_links(REPRESENTATIVE_CONTENT, source_content="", allowed_hosts=client.allowed_hosts)
    emit(f"    is_violation        : {links.is_violation}")
    emit(f"    findings            : {list(links.findings)}")
    emit(f"    novel (unsourced)   : {list(links.novel)}")
    emit(f"    allowlist in force  : {client.allowed_hosts}")

    emit()
    emit("[3] scan_identity — IdentityIntegrity")
    ident = scan_identity(
        REPRESENTATIVE_CONTENT,
        declared_handle=HANDLE,
        declared_name=DECLARED_NAME,
        declared_roles=DECLARED_ROLES,
    )
    emit(f"    is_contradiction    : {ident.is_contradiction}")
    emit(f"    kind                : {ident.kind!r}")
    emit(f"    detail              : {ident.detail!r}")

    emit()
    emit("[4] The full pre-send gate, via the shipped MoltbookClient.send() path.")
    emit("    Transport seam is a recording stub — this proves the gates PASSED and")
    emit("    the action reached the transport boundary; it makes no network call.")
    client.send(content=REPRESENTATIVE_CONTENT, action="post")
    emit(f"    reached transport   : {sent}")
    emit(f"    latches after send  : credential_exposed={client.credential_exposed} "
         f"link_violation={client.link_violation} identity_drift={client.identity_drift}")


# ── Step 2 — resolver decision and approval trace ────────────────────────────────

def step_resolver(ir: dict, client: MoltbookClient) -> dict:
    rule("STEP 2 — RESOLVER DECISION + APPROVAL TRACE (pi_script/resolver.py)")

    snapshot = client.snapshot(trigger_type="event")
    emit()
    emit("Snapshot submitted (MoltbookSession pass — the three session constraints):")
    for key, value in snapshot["entity_state"].items():
        emit(f"    {key:22} = {value!r}")
    emit(f"    (snapshot carries no API key: {not client._contains_key(snapshot)})")

    trace, rendered, exit_code = resolve(ir, snapshot)

    emit()
    emit(f"Resolver exit code    : {exit_code}   (0 = all satisfied)")
    emit(f"system_state          : {trace['system_state']!r}")
    emit(f"final_action          : {trace['final_action']!r}")
    emit(f"conflict_resolution   : {trace['conflict_resolution']!r}")
    emit()
    emit("Per-constraint rulings:")
    for c in trace["constraints"]:
        emit(f"    {c['name']:26} {c['status']:10} {c['evaluation']}")

    emit()
    emit("RESOLUTION TRACE as rendered by the shipped renderer:")
    for line in rendered.splitlines():
        emit(f"    {line}")

    return trace


# ── Step 3 — longitudinal passes ─────────────────────────────────────────────────

def step_longitudinal(ir: dict, scratch: Path) -> None:
    rule("STEP 3 — LONGITUDINAL CONSTRAINTS (separate governance passes, by ruling)")

    emit()
    emit("The two Longitudinal Constraints are NOT part of the MoltbookSession pass —")
    emit("each submits its own MoltbookAgentProfile snapshot behind its own readiness")
    emit("gate (rulings §2/§3). Shown here so this rehearsal accounts for all five")
    emit("enforced constraints rather than silently covering three.")
    emit()
    emit("For a FIRST post both are structurally NOT EVALUABLE — there is no posting")
    emit("history to compute from. That is the correct first-post state, not a gap.")

    cadence_store = CadenceObservationStore(scratch / "cadence.json", HANDLE)
    citation_store = CitationEdgeStore(scratch / "citation.json", HANDLE)

    emit()
    emit("[1] CadenceIntegrity — run_cadence_governance()")
    cadence = run_cadence_governance(ir, cadence_store)
    emit(f"    evaluated           : {cadence.evaluated}   (False = stopped at the readiness gate)")
    emit(f"    resolver saw the rule: {cadence.trace is not None}")
    emit(f"    exit_code           : {cadence.exit_code}")
    emit(f"    pause_applied       : {cadence.pause_applied}")
    emit("    rendered:")
    for line in cadence.rendered.splitlines():
        emit(f"      {line}")

    emit()
    emit("[2] CitationClusterIntegrity — run_citation_governance()")
    emit("    §5 thresholds are UNDEFINED until a grounding amendment, so this is")
    emit("    not-evaluable for two independent reasons (no history, no parameters).")
    citation = run_citation_governance(ir, citation_store)
    emit(f"    evaluated           : {citation.evaluated}")
    emit(f"    resolver saw the rule: {citation.trace is not None}")
    emit(f"    exit_code           : {citation.exit_code}")
    emit(f"    pause_applied       : {citation.pause_applied}")
    emit("    rendered:")
    for line in citation.rendered.splitlines():
        emit(f"      {line}")


# ── Step 4 — Approved Action Envelope ────────────────────────────────────────────

def step_envelope(trace: dict) -> ActionEnvelope:
    rule("STEP 4 — APPROVED ACTION ENVELOPE (shipped ActionEnvelope.approve)")

    approval_trace_id = bind_trace_to_envelope_id(trace)

    emit()
    emit("*** HARNESS-LOCAL BINDING — READ THIS BEFORE READING THE ENVELOPE ***")
    emit("The trace-to-envelope binding below is performed by THIS SCRIPT. It does")
    emit("not assert that the shipped Moltbook client performs that join; it does")
    emit("not. In shipped code `as_client_transport` defaults approval_trace_id to a")
    emit("fresh uuid4 unbound to any resolver trace (filed: TODO.md post-GO debt).")
    emit()
    emit(f"    bound over fields   : {list(_BOUND_TRACE_FIELDS)}")
    emit("    excluded            : ['timestamp', 'human_text'] — when it ran, not what was ruled")
    emit(f"    approval_trace_id   : {approval_trace_id!r}")

    payload = {"content": REPRESENTATIVE_CONTENT}
    emit()
    emit("Payload — POST shape: content only, no parent_post_id (that is what makes")
    emit("it a POST and not a REPLY).")
    emit(f"    payload keys        : {sorted(payload)}")
    emit(f"    canonical_payload_hash: {canonical_payload_hash(payload)}")

    action_id = make_dry_run_action_id()
    envelope = ActionEnvelope.approve(
        action_type=ActionType.POST,
        payload=payload,
        approval_trace_id=approval_trace_id,
        governance_config_version=CONFIG_V1,
        action_id=action_id,
    )

    emit()
    emit("Approved Action Envelope (all fields):")
    for key, value in asdict(envelope).items():
        emit(f"    {key:26} = {value!r}")
    emit()
    emit(f"    action_id is dry-run namespaced: {is_dry_run_id(envelope.action_id)}")
    emit(f"    payload_hash matches payload   : "
         f"{envelope.payload_hash == canonical_payload_hash(payload)}")

    return envelope


# ── Step 5 — simulated transport outcome ─────────────────────────────────────────

def step_dry_run(envelope: ActionEnvelope) -> None:
    rule("STEP 5 — SIMULATED TRANSPORT OUTCOME (shipped DryRunTransport, §11)")

    dry = DryRunTransport(live_config_version=CONFIG_V1)
    outcome = dry.send(envelope)

    emit()
    emit("DryRunTransport ran real envelope validation (§4 freshness checks) and made")
    emit("no network call — it has no request_fn parameter to inject one into.")
    emit()
    emit(f"    returned type                 : {type(outcome).__name__}  (NOT TransportResult)")
    emit(f"    simulated_outcome             : {outcome.simulated_outcome}")
    emit(f"    simulated_publication_status  : {outcome.simulated_publication_status}")
    emit(f"    simulated_verification_status : {outcome.simulated_verification_status}")
    emit(f"    detail                        : {outcome.detail!r}")
    emit(f"    envelope carried on outcome   : {outcome.envelope.action_id!r}")
    emit(f"    instance trace length         : {len(dry.trace)}  (recorded to this instance only)")


# ── Control ──────────────────────────────────────────────────────────────────────

def step_control(client_factory) -> None:
    rule("CONTROL — the clean pass above is a real pass, not an inert pipeline")

    emit()
    emit("A rehearsal that only shows a clean run cannot distinguish 'the detectors")
    emit("evaluated this payload and found nothing' from 'the detectors are not")
    emit("wired'. One deliberate violation, same pipeline, same client construction.")
    emit()
    emit("This control produces NO envelope and NO dry run: it is blocked at the")
    emit("pre-send gate, which is the point.")

    control = client_factory()
    tainted = REPRESENTATIVE_CONTENT + " Details: https://unknown-host.example/x"
    emit()
    emit(f"    payload           : ...{tainted[-46:]!r}")
    try:
        control.send(content=tainted, action="post")
        emit("    !! NOT BLOCKED — exercise FAILED")
    except LinkBlocked as exc:
        emit(f"    raised            : LinkBlocked({exc})")
    emit(f"    latches after block: credential_exposed={control.credential_exposed} "
         f"link_violation={control.link_violation} identity_drift={control.identity_drift}")
    emit("    (the latch is set even though the send was blocked — addendum A5)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare output against the committed expected transcript; exit 1 on mismatch",
    )
    args = parser.parse_args()

    ir = load_ir()
    sent: list = []

    def recording_transport(**kwargs):
        sent.append({k: v for k, v in kwargs.items() if k != "headers"})
        return {"outcome": "recorded-by-harness-stub"}

    def make_client(transport=None):
        return MoltbookClient(
            api_key="rehearsal-key-not-a-real-credential",
            transport=transport,
            session_id="a4-rehearsal",
            declared_handle=HANDLE,
            declared_name=DECLARED_NAME,
            declared_roles=DECLARED_ROLES,
        )

    emit("§A4 REHEARSAL — first governed POST, dry run")
    emit("docs/m7_operator_go_checklist.md §A4 · action_type POST ruled 2026-08-08")
    emit("Produces the five artifacts the row names. Authorizes nothing.")

    client = make_client(recording_transport)
    with tempfile.TemporaryDirectory(prefix="a4-rehearsal-") as tmp:
        step_detectors(client, sent)
        trace = step_resolver(ir, client)
        step_longitudinal(ir, Path(tmp))
        envelope = step_envelope(trace)
        step_dry_run(envelope)
        step_control(lambda: make_client(recording_transport))

    rule("REHEARSAL COMPLETE — no network call made, no production state touched.")
    transcript = "\n".join(_lines) + "\n"
    # The shipped trace renderer uses box-drawing characters, which a cp1252 console
    # cannot encode. Force UTF-8 so the transcript is identical on every platform.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:  # pragma: no cover - Python < 3.7 only
        pass
    sys.stdout.write(transcript)

    if not args.check:
        return 0

    if not EXPECTED_PATH.exists():
        sys.stderr.write(f"\n--check: expected transcript not found at {EXPECTED_PATH}\n")
        return 1
    # Line-by-line rather than byte-for-byte: `.gitattributes` sets `* text=auto`,
    # so committed line endings depend on the reviewer's platform. Content is exact.
    expected = EXPECTED_PATH.read_text(encoding="utf-8-sig")
    if transcript.splitlines() == expected.splitlines():
        sys.stderr.write("\n--check: transcript matches the committed expected output.\n")
        return 0
    sys.stderr.write(
        "\n--check: TRANSCRIPT DIFFERS from the committed expected output.\n"
        "         Investigate before treating §A4 as satisfied.\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
