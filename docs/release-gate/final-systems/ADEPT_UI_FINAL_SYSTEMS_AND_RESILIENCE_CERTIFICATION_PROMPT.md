# Adept UI — Final Systems & Resilience Certification Prompt

**Status:** LOCKED REQUIREMENTS  
**Audience:** Primary agents, implementers, and independent verifiers  
**Binary program verdicts only:** GO | NO-GO (no Conditional GO)

This document is the authoritative prompt and locked-requirements set for the **Final Systems & Resilience Certification**. Later sections may expand coverage, but they **must not** weaken, omit, or reinterpret the Product Law or the MiniMax Timeline Re-take gate below.

```text
Highest-priority rules in this certification (in order):
1. Product Law — Adept UI End-to-End Product Certification
   (+ Creator Illusion Rule)
2. MiniMax Timeline Re-take Certification
   (+ Timeline Integrity Rule)
3. Remaining final systems & resilience coverage
4. Release Freeze Rule (after AUTOMATED BETA GATE COMPLETE)
```

After independent verification of the full suite:

```text
AUTOMATED BETA GATE COMPLETE — READY FOR HUMAN BETA
```

Overall program GO may only be issued as:

```text
GO — ADEPT UI FINAL SYSTEMS AND RESILIENCE CERTIFICATION PASSED
```

and only when **both** locked addenda pass alongside remaining final systems coverage.

---

# Final Addendum — Adept UI End-to-End Product Certification

## Product Law (Highest Priority)

> **Standing Build Law #29 (Product Abstraction):** This Product Law is the certification expression of permanent Build Law #29 in [`docs/ADEPT_UI_BUILD_MEMORY_LAYER.md`](../../ADEPT_UI_BUILD_MEMORY_LAYER.md). Adept UI is the product; underlying runtimes are implementation details managed behind Adept UI.

This entire certification must be performed **inside Adept UI**.

The objective is to certify the **creator experience**, not the underlying engines.

Every action a creator performs must originate from the Adept UI interface and its product APIs.

The certification must never become a test of ComfyUI, MiniMax, Ollama, Babylon, or any other underlying subsystem independently.

## Creator Illusion Rule

At no point during normal product operation should the creator feel they are operating multiple independent AI applications.

The creator experiences one cohesive filmmaking platform.

Model selection, runtime orchestration, recovery, and routing are internal implementation details managed by Adept UI.

---

## Allowed Runtime Behavior

Underlying runtimes may be:

* automatically started;
* automatically stopped;
* automatically recovered;
* automatically health-checked;
* automatically reused.

These operations must occur **behind Adept UI**.

The creator must never be required to:

* launch ComfyUI manually;
* launch MiniMax manually;
* launch Ollama manually;
* open ComfyUI;
* interact with `:8188`;
* interact with `:8192`;
* access runtime dashboards;
* submit `/prompt` payloads;
* manipulate workflow JSON;
* browse model folders;
* inspect checkpoint filenames.

If a runtime is unavailable, Adept UI is responsible for detecting, reporting, and (where appropriate) recovering it.

---

## Automatic Runtime Management

Adept UI owns the complete runtime lifecycle:

```text
Detect → Launch → Health Check → Recover → Reconnect → Reuse → Graceful Shutdown
```

If required services are not running, Adept UI should:

1. **Detect** the missing runtime;
2. **Launch** the approved runtime automatically;
3. **Health Check** wait for readiness and verify GPU availability;
4. **Recover** / **Reconnect** when a runtime drops mid-session;
5. **Reuse** healthy processes instead of spawning duplicates;
6. **Graceful Shutdown** when stopping or refreshing Beta / product services;
7. continue the creator workflow without manual intervention.

The creator should experience:

```text
Generate Image
```

—not—

```text
Please open ComfyUI.
Please start Ollama.
Please launch MiniMax.
```

Automatic recovery is part of the product.

---

## Creator Perspective Rule

Every Playwright scenario must behave exactly as though a filmmaker has never heard of:

* ComfyUI;
* Ollama;
* MiniMax runtime;
* Babylon;
* workflow JSON;
* node graphs;
* GPU launch scripts.

The filmmaker only knows Adept UI.

Every interaction must therefore begin from:

* Home;
* Production workspace;
* Co-Director;
* Character Creator;
* Scriptwriter;
* PoseCraft;
* Storyboard;
* Image Generation;
* Voice Studio;
* Timeline;
* MAGI;
* Audio Studio;
* Library.

---

## Runtime Transparency

The UI may honestly display information such as:

```text
Local Runtime Ready

MiniMax H3 Ready

Image Runtime Ready

Voice Runtime Ready
```

or

```text
Recovering Image Runtime...
```

It must not expose implementation details that belong to engineering rather than creators.

---

## No External Operations

The certification must never require Playwright to:

* open ComfyUI in a browser;
* manipulate ComfyUI directly;
* POST directly to `:8188`;
* POST directly to `:8192`;
* call MiniMax runtime endpoints directly;
* invoke Ollama directly;
* import workflow JSON manually;
* manipulate Timeline data outside Adept UI.

Verification through product APIs is permitted.

Creator actions must originate exclusively from Adept UI.

---

## End-to-End Requirement

The complete certification—from project creation to final rendered media—must occur inside Adept UI.

This includes:

* project creation;
* planning;
* scriptwriting;
* Character Creator;
* PoseCraft;
* Image Generation;
* Storyboard;
* Voice Studio;
* Timeline;
* MiniMax Re-take;
* MAGI;
* Audio Studio;
* Library;
* export;
* cleanup.

No creator-facing step may require leaving Adept UI.

**One project law:** Use **only one** disposable Adept UI project for the end-to-end path. Do not spawn multiple projects to complete certification steps. All assets, takes, and provenance must live in that single project.

---

## Product Identity Rule

This certification validates **Adept UI as a complete filmmaking platform**.

The underlying runtimes are implementation details.

Passing certification means a filmmaker can complete an end-to-end production workflow without leaving Adept UI or interacting directly with any supporting runtime.

---

## Final Certification Requirement (Product Law)

The Final Systems & Resilience Certification may only issue:

```text
GO — ADEPT UI FINAL SYSTEMS AND RESILIENCE CERTIFICATION PASSED
```

if **100% of creator actions were successfully completed inside Adept UI**, with all runtime interactions managed transparently by the platform.

If any creator-facing step requires leaving Adept UI or manually operating an external runtime, the certification must instead issue:

```text
NO-GO — ADEPT UI END-TO-END PRODUCT EXPERIENCE INCOMPLETE
```

This establishes the final certification as a validation of **Adept UI as a cohesive production application**, ensuring that all underlying technologies remain invisible to the end user while the platform delivers the complete filmmaking workflow.

---

# Mandatory Addendum — MiniMax Timeline Re-take Certification

**Priority:** Highest gate among engine/workflow certifications (second only to Product Law).  
**Overall Final Systems GO is blocked until this gate passes.**

## Purpose

The final Playwright certification must prove that Adept UI can use **MiniMax H3 through Timeline** to perform a real, creator-initiated **Re-take** on an existing generated shot.

This must test the actual Timeline Re-take workflow—not merely generate a second unrelated clip.

The required path is:

```text
Existing Timeline shot
→ Select shot or segment
→ Open Re-take
→ Preserve approved shot context
→ Modify one bounded creative instruction
→ Generate through private MiniMax H3 Route A
→ Review result
→ Replace or add as alternate take
→ Preserve provenance and prior take
```

**One project:** Use only **1** project in Adept UI to complete this. Everything must be stored in a single project.

## Locked runtime policy

MiniMax remains:

```text
Private Local
Owner Only
Experimental
Route A
```

The test must not enable:

* public Creator access;
* Best Match;
* general automatic routing;
* silent H3-to-LTX fallback;
* direct browser access to `:8192`;
* direct `/prompt` submission.

All generation must originate through the Adept UI creator interface and product API.

## Test setup

Use one generated product-ad shot already placed in Timeline.

Recommended shot:

```text
A glowing glass bottle on a dark studio table,
slow cinematic push-in,
subtle condensation,
controlled rim lighting.
```

The original shot becomes:

```text
Take 1 — Approved Baseline
```

## Re-take instruction

Through Timeline, request one bounded variation such as:

```text
Keep the bottle, framing, camera direction, duration, and lighting continuity.
Make the camera push-in slightly slower and add a stronger condensation shimmer.
Do not change the product design or background.
```

The instruction must preserve continuity rather than regenerate an unrelated scene.

## Required Re-take behavior

The Re-take workflow must:

* start from the selected Timeline segment;
* carry forward the original prompt and structured shot context;
* preserve aspect ratio and target duration;
* preserve source references where supported;
* preserve character/product/environment continuity;
* expose the creator’s requested change;
* route explicitly to MiniMax H3;
* show progress and cancellation;
* produce a new media asset;
* retain the original take;
* avoid silent replacement before approval.

## Timeline result options

After the Re-take completes, the creator must be able to choose:

```text
Replace Current Take
Add as Alternate Take
Keep Original
```

For certification, use:

```text
Add as Alternate Take
```

Then verify:

* Take 1 remains available;
* Take 2 is linked to the same shot;
* only one take is active in the edit;
* the creator can switch between takes;
* reload preserves both takes and the active selection.

## Re-take provenance

The new take must record:

```text
engine = MiniMax H3
deployment = private-local
access = owner-only
runtime = route-a
nativeAudio = true where produced
sourceTakeId = <Take 1 ID>
retake = true
apiUsed = false
ltxUsed = false
```

Also preserve:

* project ID;
* Timeline shot ID;
* source asset ID;
* original prompt;
* delta instruction;
* runtime job ID;
* checkpoint identity;
* duration;
* resolution;
* timestamps;
* cancellation/retry history.

The result must not be mislabeled as LTX, API generation, or a fresh unrelated shot.

## Real continuity assertions

The test should verify at minimum:

* same shot identity;
* same bottle/product identity;
* same environment;
* same broad framing;
* same aspect ratio;
* requested motion change reflected in the new take;
* requested condensation change represented in the job contract;
* original take unchanged.

Visual similarity may be reviewed through snapshots and metadata, but the test must not claim pixel-perfect identity.

## Cancellation and recovery

Before the successful Re-take, exercise cancellation on a disposable Re-take attempt:

1. Start Re-take through Timeline.
2. Wait until the job is accepted or running.
3. Select Cancel.
4. Verify status becomes cancelled.
5. Verify no broken Timeline take is created.
6. Verify the original shot remains playable.
7. Start the successful Re-take afterward.

If the runtime is unavailable, Timeline must show an honest MiniMax readiness error and offer LTX only as an explicit alternative. The final certification still requires one real successful MiniMax Re-take.

## Playwright scenario

Add a dedicated phase:

```text
Phase — Timeline MiniMax Re-take
```

Required steps:

1. Open the disposable product-ad project.
2. Open Timeline.
3. Select the approved generated shot.
4. Open Re-take.
5. Confirm MiniMax H3 is explicitly selected.
6. Submit a first attempt and cancel it.
7. Verify no alternate take was added.
8. Reopen Re-take.
9. Enter the bounded continuity instruction.
10. Generate through MiniMax H3.
11. Wait for real completion.
12. Validate playable output.
13. Add as Alternate Take.
14. Switch between Take 1 and Take 2.
15. Select Take 2 as active.
16. Reload the project.
17. Verify both takes persist and Take 2 remains active.
18. Verify provenance and no silent fallback.
19. Verify original media asset remains intact.

## Hard failures

The test must return NO-GO if:

* Re-take creates an unrelated new Timeline shot;
* original take is destroyed;
* H3 silently falls back to LTX;
* direct `:8192` browser access occurs;
* no real media is produced;
* cancelled attempt creates a ghost take;
* alternate takes disappear after reload;
* provenance is missing or incorrect;
* Take 2 cannot be selected or restored;
* the Re-take control is absent from Timeline.

## Required Re-take verdict

```text
GO — TIMELINE MINIMAX H3 RE-TAKE READY
```

or:

```text
NO-GO — TIMELINE MINIMAX H3 RE-TAKE FAILED
```

## Timeline Integrity Rule

No generation, re-take, replacement, alternate take, or editorial operation may invalidate the edit history.

Timeline revisions must remain reversible.

Every editorial change must preserve provenance.

This protects the editor experience as Timeline grows. Re-take certification must demonstrate Take 1 preservation, Take 2 linkage, active-take switching, and reload durability without rewriting history.

## Final automated gate (binding)

The overall Final Systems & Resilience certification may issue:

```text
GO — ADEPT UI FINAL SYSTEMS AND RESILIENCE CERTIFICATION PASSED
```

only if this MiniMax Timeline Re-take gate passes **and** the Product Law (100% creator actions inside Adept UI) is satisfied, alongside the remaining final systems coverage.

After independent verification:

```text
AUTOMATED BETA GATE COMPLETE — READY FOR HUMAN BETA
```

## Release Freeze Rule

Once:

```text
AUTOMATED BETA GATE COMPLETE — READY FOR HUMAN BETA
```

has been achieved, no new features may be introduced before the manual Beta.

Only defect fixes discovered during manual testing may be implemented.

Feature work resumes only after the manual Beta closes and a new milestone begins.

Given the size of Adept UI, this prevents scope creep after the automated gate.

---

# Operator / agent instructions (when executing this prompt)

1. Treat Product Law, Creator Illusion Rule, MiniMax Timeline Re-take, and Timeline Integrity Rule as **non-negotiable**. Do not skip, mock, or substitute with direct engine calls.
2. Reuse a **single** disposable named project for the full path; never spam `POST /api/projects` per step.
3. Never mutate protected project `77a4b96c-8e3f-4501-897c-51bab99bedb7`.
4. GPU-designated work (including MiniMax H3 Route A) must preflight the accelerator and never silently fall back to CPU (Build Law #26).
5. Evidence before verdict: Playwright logs, provenance JSON, take IDs, reload proof, Beta URLs (Law 31).
6. Independent verifier may only return `READY FOR PRIMARY REVIEW`; primary owns final GO|NO-GO.
7. Subagents for this certification follow standing model policy unless the user overrides in the current message.
8. After `AUTOMATED BETA GATE COMPLETE — READY FOR HUMAN BETA`, enforce the **Release Freeze Rule** (no new features until manual Beta closes).

## Beta handoff URLs (when live)

* Creator UI: `http://127.0.0.1:8760/`
* Studio API: `http://127.0.0.1:8758/`
