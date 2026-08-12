# M42 Blocking Addendum — Qwen-Image-2512 Default & Character Consistency

| Field | Value |
|---|---|
| **Status** | ACTIVE HARD STOP |
| **Canonical model key** | `qwen-image-2512` |
| **Default open-weight image model** | Qwen-Image-2512 |
| **Alternative open-weight image model** | FLUX (preserved) |
| **Prior executable default** | Z-Image (`zimage.txt2img`) — replaced as recommendation/Character Creator default |
| **mockData** | `false` |
| **mockBuild** | `false` |
| **Subagent model** | GPT-5.4 (`gpt-5.4-medium`) |
| **Artifacts** | `artifacts/m42/w43-qwen-2512/` |

## Blocking path (must succeed)

```text
Adept UI
→ Co-Director prompt compilation
→ Qwen-Image-2512 workflow
→ ComfyUI execution
→ Korri character profile generation
→ visual consistency validation
→ Asset Library registration
→ Identity Registry linkage
→ VersionGraph
→ persistence after reload
```

## Policy

- Do not relabel FLUX or Z-Image workflows as Qwen.
- Dedicated workflow family under `comfyui/workflows/qwen-image-2512/` + Python builders.
- Co-Director never sends unstructured conversational prompts to Qwen-Image-2512.
- Character identity is separate from visual style.
- GO only after real Korri consistency through Adept UI → ComfyUI.

## Ownership

See `M42_SUBAGENT_OWNERSHIP_MATRIX.md` (Qwen-2512 sprint section) and
`docs/release-gate/m42/subagent-assignments/Qwen2512*.md`.

## Gate flags

Extended W43 / Qwen-2512 gate — all must be `true` before Phase 4.5+.
See `studio-api/app/m42_w43/production_gate.py` (qwen2512* flags) once integrated.
