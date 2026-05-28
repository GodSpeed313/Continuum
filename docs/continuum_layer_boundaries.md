# Continuum Layer Boundaries

**What belongs in each layer — and what does not.**

This document exists because the Continuum stack has three distinct layers, and
mixing constructs across layers produces documents that are hard to implement,
hard to review, and hard to publish. Any governance spec, design note, or
implementation blueprint should fit cleanly into one layer.

---

## The Three Layers

| Layer | Name | Owns | Does Not Own |
|---|---|---|---|
| Layer 3 | **Rift** | User intent declarations, natural language → machine state mapping, intent lifecycle | Constraint evaluation, system execution, hardware behavior |
| Layer 2 | **Pi Script** | Constraint declarations, entity state monitoring, violation detection, RESOLUTION TRACEs | How the system executes, how data is stored, kernel-level behavior |
| Layer 1 | **Execution** | GPU/CPU kernels, quantization math, hardware latency, memory hierarchy | What constraints mean, what violations imply, what humans should review |

---

## Boundary Rules

**Pi Script does not specify execution.**
A Pi Script constraint says `memory_latency_ratio must remain below 0.8`. It does
not say how the latency is measured, which GPU architecture is in use, or how
dequantization is implemented. That is Layer 1. Pi Script only governs the
*observable state value* — whatever the execution layer reports.

**Layer 1 does not declare governance.**
A Triton or CUDA kernel does not contain Pi Script constraints. It may emit state
values (e.g., stall probability, latency ratio) that a Pi Script adapter reads.
The kernel is a data source. Pi Script is the monitor.

**Rift does not evaluate constraints.**
Rift produces Pi Script. It does not run the resolver, does not produce RESOLUTION
TRACEs, and does not make violation decisions. Those belong to Layer 2.

---

## What This Means for Documents

Any document that mixes layers should be split before publication or implementation.

| Mixed Document Type | How to Split |
|---|---|
| Quantization governance + Pi Script constraints + Triton kernels | Three documents: (1) Layer 1 kernel spec, (2) Pi Script `.pi` governance file, (3) adapter script that bridges L1 output to L2 input |
| Rift design + Pi Script constraint examples | Two documents: Rift design note (Layer 3), Pi Script `.pi` file (Layer 2) |
| Application architecture + governance policy | Two documents: application design doc, Pi Script `.pi` policy file |

---

## The Adapter Pattern

When Layer 1 execution needs to feed state into Layer 2 governance, the bridge
is an **adapter script** — not a mixed-layer document. The adapter:

1. Reads Layer 1 output (kernel metrics, hardware state, application data)
2. Computes the observable state values Pi Script cares about
3. Writes `state.json` for the Pi Script resolver

The `es/es_adapter.py` is the canonical example of this pattern.
The adapter owns the translation. Pi Script owns the governance. Neither reaches
into the other's domain.

---

*This boundary holds for all v0.1 work. Cross-layer integration is a v0.4+ feature (Rift full-stack integration per Section VII of the Pi Script spec).*
