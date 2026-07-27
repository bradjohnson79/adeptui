# M3.0d Production Certification Pack

Release-gate documentation for the **Manual User Beta** production certification pass on branch `phase2/codirector-m2-9-production-suite`.

| Field | Value |
|-------|-------|
| Certification phase | M3.0d â€” production gate closure |
| Starting tip (M3.0d) | `aff00c131a464ee9cdf156fd8a2977016264b375` |
| Prior M3.0c implementation | `8ba6b62` |
| Prior M3.0c documentation | `5a854f1` |
| Provider manifest SHA (LOCKED) | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Implementation SHA | `43a5c0f0152a39327e87b10de11fd55e5b16ad90` |
| Documentation SHA | `2ce772516ab518795d2279e2f02cbfd7f96bbbb1` |

## Pack index

| Document | Purpose |
|----------|---------|
| [M30D_MASTER_REMEDIATION_REGISTER.md](./M30D_MASTER_REMEDIATION_REGISTER.md) | Authoritative closure register for B5â€“B21, UJ, PY, PW, S01â€“S12 |
| [M30D_BACKEND_FINAL_GATE.md](./M30D_BACKEND_FINAL_GATE.md) | Full `pytest -q` gate: 631 passed / 0 failed / 6 skipped |
| [BACKEND_FAILURE_CLOSURE.md](./BACKEND_FAILURE_CLOSURE.md) | PY01â€“PY20 disposition and full-suite follow-up |
| [M30D_UNIFIED_JOBS_CERTIFICATION.md](./M30D_UNIFIED_JOBS_CERTIFICATION.md) | Co-Director inspect bridge (UJ-1) and fal queue job path (UJ-2) |
| [M30D_FAL_MOTION_PROOF.md](./M30D_FAL_MOTION_PROOF.md) | Reconciled fal Seedance proof â€” no new paid spend |
| [M30D_SPECIALIST_DAG_CERTIFICATION.md](./M30D_SPECIALIST_DAG_CERTIFICATION.md) | M2.11 specialist DAG wiring (B8) |
| [M30D_ORCHESTRATION_HONESTY_REPORT.md](./M30D_ORCHESTRATION_HONESTY_REPORT.md) | `normalize_orchestration_response` contract (B9) |
| [M30D_SCENE_IDENTITY_REPORT.md](./M30D_SCENE_IDENTITY_REPORT.md) | sceneId continuity through I2V and export (B17) |
| [M30D_DIRECTOR_EDITOR_CERTIFICATION.md](./M30D_DIRECTOR_EDITOR_CERTIFICATION.md) | Directorâ†’Editor handoff sync model |
| [M30D_TIMELINE_EXPORT_CERTIFICATION.md](./M30D_TIMELINE_EXPORT_CERTIFICATION.md) | Timeline persistence and export pack (B18) |
| [M30D_VISION_APPROVAL_CERTIFICATION.md](./M30D_VISION_APPROVAL_CERTIFICATION.md) | Vision approval bands and overrideReason (B19, B11) |
| [M30D_AUDIO_CAPABILITY_REPORT.md](./M30D_AUDIO_CAPABILITY_REPORT.md) | Import/place/syncEvent path; generative audio honest boundary (B13, B5) |
| [M30D_FAILURE_RECOVERY_CERTIFICATION.md](./M30D_FAILURE_RECOVERY_CERTIFICATION.md) | Queue restart recovery and Playwright proof (B14, PW-S3) |
| [M30D_ACCESSIBILITY_CERTIFICATION.md](./M30D_ACCESSIBILITY_CERTIFICATION.md) | axe critical checks and keyboard focus â€” conditional |
| [M30D_NATIVE_PLATFORM_SMOKE_MATRIX.md](./M30D_NATIVE_PLATFORM_SMOKE_MATRIX.md) | 18-platform smoke matrix |
| [M30D_PLAYWRIGHT_CERTIFICATION.md](./M30D_PLAYWRIGHT_CERTIFICATION.md) | Full Playwright suite and skip classification |
| [M30D_PRODUCTION_SITUATIONS.md](./M30D_PRODUCTION_SITUATIONS.md) | S01â€“S12 production situation matrix |
| [M30D_CAPSTONE_PRODUCTION_REPORT.md](./M30D_CAPSTONE_PRODUCTION_REPORT.md) | Capstone short-form production evidence |
| [M30D_SECRET_AUDIT.md](./M30D_SECRET_AUDIT.md) | Secret and production-safety audit |
| [M30D_SYSTEM_REPORT.md](./M30D_SYSTEM_REPORT.md) | Cross-cutting system certification summary |
| [M30D_PM_REPORT.md](./M30D_PM_REPORT.md) | PM gate verdict (binary YES/NO) |

## Prior-phase evidence reused (not re-run)

- fal unified queue: `docs/m3.0c/FAL_UNIFIED_QUEUE_PROOF.md`, `artifacts/m30c-fal/unified_queue_proof.json`
- Production situations: `docs/m3.0c/PRODUCTION_SITUATION_CERTIFICATION_MATRIX.md`, `artifacts/m30-situations/phase18-final-validation.json`
- Local stills: ComfyUI Z-Image path (`artifacts/m30a-local/local_artifact_summary.json`)
- Motion: reused Seedance MP4 from M3.0c proof â€” **no new fal submit in M3.0d**

## Register rule

No register item may disappear by omission. Close only with Fix + Test (+ Artifact when applicable) + Commit SHA. Items marked **Open** remain blocking for a full Manual User Beta authorization.
