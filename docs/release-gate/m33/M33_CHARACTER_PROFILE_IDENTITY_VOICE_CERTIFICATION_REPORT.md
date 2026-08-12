# M3.3 — Character Profile, Identity, and Voice System Certification Report

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Milestone** | M3.3 Character Profile, Identity, and Voice System |
| **Verdict** | **NO-GO — M3.3 Character Profile, Identity, and Voice System is not yet production-ready.** |
| **Evidence** | `artifacts/m33/character-profile/` · `artifacts/m33/character-profile-certification.json` |
| **Architecture audit** | [`M33A_ARCHITECTURE_AUDIT.md`](./M33A_ARCHITECTURE_AUDIT.md) |
| **Feature flag** | `STUDIO_FEATURE_CHARACTER_IDENTITY_V1` |

## Why NO-GO (honest)

Real-local Qwen Voice Design + Voice Clone are **installed and producing genuine WAVs**. Disposable design (≥3 previews), clone (new-text), and two dialogue lines are proven.

Remaining blockers for full GO under the locked acceptance list:

1. Disposable LatentSync on a non-Hitchhiker scene (parent video prepared; job not completed in this run).
2. Editor placement + final render for that lipsync output.
3. Real-local Playwright M33-CHAR-08..23 matrix not yet executed end-to-end against a live API under `ADEPT_M33_REAL_LOCAL=1`.

Fixtures were not used as success. Protected Hitchhiker assets were not mutated.

## Protected assets (unchanged)

| Asset | ID |
|---|---|
| Hitchhiker project | `d1683511-1cc7-4d3d-8cb7-00f48cc36aa9` |
| M3.2f LTX Shot1 | `6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f` |
| M3.2g Test 2 WAN | `e277e621-189d-471e-b435-f01620f03d0d` |
| Dialogue WAV | `c5cdd736-8f89-42e3-a7a8-9cb97043bf8a` |

## Provider readiness (proven)

| Provider | Registry | Installed | Ready | Evidence |
|---|---|---|---|---|
| Qwen3-TTS Voice Design 1.7B | `m2101-voice-design-021` | yes | yes | `qwen-install/qwen_voice_design_17b.json` |
| Qwen3-TTS Voice Clone Base 1.7B | `m2101-voice-clone-022` | yes | yes | `qwen-install/qwen_voice_clone_17b.json` |
| Kokoro | `m2101-dialogue-001` | yes | yes | preset only; no silent identity fallback |

Official HF sources only:

- `Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign`
- `Qwen/Qwen3-TTS-12Hz-1.7B-Base`

Install path: Source Manager Character Voice Models + `scripts/m33i_install_qwen_voice.py` (venv + HF snapshot; `installed=true` only when import probe passes).

## Real-local voice proof inventory

| Proof | Result | Artifact |
|---|---|---|
| Design smoke WAV | GREEN | `real-local-smoke/design_smoke.wav` |
| Clone new-text smoke WAV | GREEN | `real-local-smoke/clone_new_text_smoke.wav` |
| Product ≥3 design previews | GREEN | `voice-design/three-previews.json` |
| Product clone + consent | GREEN | `voice-clone/clone-preview.json` |
| Two dialogue lines same designed voice | GREEN | `dialogue/two-lines.json` |
| Product cert summary | GREEN | `voice-design/product-cert.json` |
| Disposable parent video for lipsync | PREPARED | `lipsync/disposable-parent.mp4` |
| LatentSync job | PENDING | — |
| Editor render | PENDING | — |

Product cert IDs (disposable):

- project: `6340157a-8ff1-4d1c-80f2-d2d16db969e1`
- character: `bbc58773-fa5f-43eb-8bb3-666ac6aba4b0`
- design voice: `9efc6890-7da9-48a5-90da-e4bb976e1922`
- clone voice: `243b5d0c-f37b-4204-a17e-2e68b9904890`

## Deliverables by phase

| Phase | Status | Notes |
|---|---|---|
| Schemas / UI / Co-Director / Bible | GREEN | Prior M3.3 work retained |
| Qwen Source Manager install | GREEN | HF executor + voice models panel |
| Isolated smoke | GREEN | Design + clone real WAVs |
| Product DESIGN/CLONE/dialogue | GREEN | Disposable project |
| LatentSync → Editor | PENDING | Parent MP4 prepared; job not certified |
| Unit tests | GREEN | M3.3 suites (see cert JSON) |
| Playwright deterministic | GREEN | M33-CHAR-01..07 |
| Playwright real-local | PENDING | Helper + spec added; full run pending live API |

## How to clear remaining NO-GO

1. Register `lipsync/disposable-parent.mp4` on a disposable scene (not Hitchhiker).
2. Run certified LatentSync with a dialogue asset from `dialogue/two-lines.json`.
3. Place output in Editor; render short mix; persist after API restart.
4. Run `ADEPT_M33_REAL_LOCAL=1` Playwright `tests/e2e/m33/character-profile-real-local.spec.ts`.
5. Flip cert JSON to GO only when lipsync + Editor + Playwright real-local pass.

## Final language

**NO-GO — M3.3 Character Profile, Identity, and Voice System is not yet production-ready.**

(Voice providers and disposable voice chain are proven; lipsync/Editor/real-local Playwright remain open.)
