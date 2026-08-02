# M4.10 Architecture

## Split of responsibilities

M4.10 keeps voice work in two distinct stages:

1. **Voice Identity** uses the approved character voice profile.
2. **Voice Performance** directs how a specific line should be played.

That split is enforced in code:

- Voice identity approval lives in `studio-api/app/character_identity/`
- M4.10 performance records and takes live in `studio-api/app/voice_performance/`
- `VoicePerformanceStudio.tsx` refuses take generation unless an approved voice identity exists

## Qwen identity vs IndexTTS2 performance

Qwen remains the identity-side system.

- `studio-api/app/voice_performance/providers/qwen.py` is a legacy provider adapter with `provider_key = "qwen3-tts"`
- M4.10 record creation defaults `providerId` to `index-tts2-local`
- `m410_service.require_approved_voice_identity()` validates that the chosen identity belongs to the same project and character and is already approved

In other words:

- **Qwen / character identity** answers "whose voice is this?"
- **IndexTTS2 / voice performance** answers "how should this line be played?"

## Local IndexTTS2 runtime

The M4.10 runtime is intentionally local and pinned:

- Provider id: `index-tts2-local`
- Official repository: `https://github.com/index-tts/index-tts`
- Locked SHA: `13495845e3028f0bb6ca1462ad22aa0e76349e40`
- Hugging Face model: `IndexTeam/IndexTTS-2`

`studio-api/app/voice_performance/runtime/index_tts2.py` owns the isolated runtime layout, repo pinning, model inspection, health checks, and take generation.

## M4.10 record flow

The record/take flow is:

1. `POST /api/voice-performance/m410/records`
2. save `performancePlan`, `manualPlan`, `codirectorPlan`, emotion metadata, and consent metadata
3. `POST /api/voice-performance/m410/records/{recordId}/generate-takes`
4. `m410_service.create_takes()` calls `runtime.index_tts2.generate_take()`
5. completed output is stored as an `Asset` plus a `Job`
6. one take may be approved for Timeline and Lip Sync handoff

## Creator-facing direction model

`studio-web/src/components/voiceStudio/VoicePerformanceStudio.tsx` exposes:

- `Co-Director Recommended` and `Manual Direction`
- emotion source selection
- creator-facing fields such as Emotion, Intensity, Delivery, Pacing, Breath, Emphasis, Subtext, and Performance Reference
- a collapsed `Advanced` area for raw emotion vectors

The backend preserves both direction modes so switching modes does not erase the other plan.
