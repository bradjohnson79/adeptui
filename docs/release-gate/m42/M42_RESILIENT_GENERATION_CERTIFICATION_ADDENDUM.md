# M42 Certification Addendum — Resilient Generation & Continuous Correction

**Verdict:** Global engineering policy adopted.  
**Mock:** false  
**Conditional GO:** Not permitted.  
**Scope:** Applies to every generative subsystem within M42 unless a later addendum explicitly supersedes this policy.

This addendum is platform-wide engineering doctrine. Future phases (Voice Performance, Audio Studio, Editing Suite, Enhancement Studio, and beyond) inherit it automatically so certification reports remain consistent without restating the principle in every milestone.

---

## Principle

The purpose of M42 certification is to certify that Adept UI is correctly wired end-to-end.

Model output quality should not automatically fail a milestone when the infrastructure is functioning correctly.

---

## Canonical Rule

| Class | Outcome |
| ----- | ------- |
| Infrastructure failures | **NO-GO** |
| Model generation quality issues | Auto-correction workflow → Retry → Refine → Continue milestone |

```text
Infrastructure failures
→ NO-GO

Model generation quality issues
→ Auto-correction workflow
→ Retry
→ Refine
→ Continue milestone
```

---

## Character Sheet Generation (example)

```text
Generate Character Sheet
↓
Identity Validation
↓
Pass?
```

**If Yes** → Continue.

**If No:**

```text
Analyze differences
↓
Generate correction plan
↓
Retry generation
↓
Validate again
↓
Continue until tolerance reached
```

Do **not** fail the milestone simply because:

- hairstyle drifted
- eye color slightly incorrect
- clothing detail missing
- pose inconsistent
- expression off
- accessory omitted
- proportions slightly inaccurate

These are expected characteristics of generative models.

---

## What DOES Fail Certification

Certification fails only when the platform itself is broken. Examples:

- provider not wired
- request never reaches provider
- provider response not handled
- asset not registered
- Timeline insertion fails
- provenance missing
- VersionGraph broken
- Co-Director bypasses approval
- persistence missing
- security failure
- project isolation failure
- password protection bypass
- API contract broken
- Playwright regression
- corrupted workflow
- uncaught runtime exceptions
- orphaned jobs

These are platform failures → **NO-GO**.

---

## Generation Quality Workflow

Generation quality enters a refinement loop. Every iteration must be stored.

```text
Generate
↓
Identity Evaluation
↓
Deviation Report
↓
Correction Intent
↓
Regenerate
↓
Evaluate
↓
Accept
```

---

## Co-Director Behavior

Co-Director must **never** respond with:

```text
Character sheet generation failed.
```

Instead, report variance and continue automatically, for example:

```text
Identity variance detected.
Hair style: 82%
Eye color: 97%
Outfit: 91%
Expression: 79%
Generating corrective revision...
```

Then continue the correction workflow without treating quality variance as a hard platform failure.

---

## Quality Thresholds

Use scored evaluation rather than binary success/failure for generative match:

| Dimension | Target |
| --------- | ------ |
| Identity Match | 95% |
| Costume | 93% |
| Color Palette | 98% |
| Accessories | 90% |
| Pose | 96% |
| Overall | 94% |

The user may:

- Accept
- Refine
- Retry
- Switch provider
- Edit manually

---

## Certification Wording Replacement

Replace any milestone wording that says:

```text
Image mismatch
↓
Certification failed
```

with:

```text
Image mismatch
↓
Correction workflow initiated
↓
Retry
↓
Re-evaluate
↓
Continue certification
```

---

## Automatic NO-GO Revision

Remove any NO-GO condition similar to:

```text
Generated image differs from the approved character sheet.
```

Replace it with:

```text
NO-GO occurs only when the automated correction workflow cannot execute
because the platform, persistence, provider integration, asset registration,
or approval pipeline is non-functional.
```

Quality mismatch alone is never an automatic NO-GO when the correction path can run.

---

## Global Scope and Inheritance

The same philosophy applies across all M42 generative subsystems:

- Character Creator
- Environment Builder
- Storyboard
- Generate Studio
- Voice Performance
- Audio Studio
- Editing Suite
- Enhancement Studio
- any later M42 generative surface

**Wiring failures stop certification. Generation-quality issues trigger iterative correction and refinement until the user approves or stops the process.**

This keeps certification focused on whether Adept UI functions correctly as a production platform while acknowledging that generative AI outputs are inherently iterative.

Future certification reports inherit this doctrine automatically unless a later addendum explicitly supersedes it. Product-specific reports should adopt this rule rather than reinvent it.

---

## Cross-References

Related M42 policy and certification surfaces:

- [M42_W43_GENERATED_IMAGE_PROFILE_ADDENDUM.md](./M42_W43_GENERATED_IMAGE_PROFILE_ADDENDUM.md)
- [M42_W43_CHARACTER_CREATOR_COMPLETION_REPORT.md](./M42_W43_CHARACTER_CREATOR_COMPLETION_REPORT.md)
- [M42_W43_KORRI_CERTIFICATION_REPORT.md](./M42_W43_KORRI_CERTIFICATION_REPORT.md)
- [M42_W44_FINAL_CERTIFICATION.md](./M42_W44_FINAL_CERTIFICATION.md)
- [M42_HOSTED_PROVIDERS_ADDENDUM.md](./M42_HOSTED_PROVIDERS_ADDENDUM.md)

Follow-on work may update historical NO-GO lists product-by-product to align with this addendum. This document alone establishes the global rule.
