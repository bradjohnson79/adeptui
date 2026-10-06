# Timeline Playback Voice Authority Law (Brad 2026-09-11)

## CONFIRMED VOICE AUDIT (PLAYBACK_FIX)

After PLAYBACK_FIX, Timeline playback is **split by construction**:

| Layer | Authority |
|---|---|
| **Picture (mouths / video)** | MiniMax Batch Visual (approved covered Batch visuals) |
| **Dialogue (audio)** | Qwen lipsync wavs |

## FORBIDDEN

- Do **NOT** re-prefer `lipsync_output_path` over covered Batch visuals for picture.
- That path fights the Batch 2 freeze fix.
- Do **NOT** treat "prefer lipsync video for everything" as a repair for dialogue sync.

## LIVE MUTE

- Live mute must **not** key solely off `lipsync_output_path` being set and mute video AAC for the **whole** play.
- Mute AAC only for **retake windows** where lipsync retake audio is the intended dialogue source.
- Outside those windows, Batch Visual AAC / intended mix rules apply.

## SCENE 10 AUTHORITY LOCK

**LOCKED (Brad 2026-09-11):** Split (PLAYBACK_FIX)

- **Picture** = MiniMax Batch Visual mouths / covered Batch visuals
- **Dialogue** = Qwen lipsync wavs
- Do **NOT** re-prefer `lipsync_output_path` for picture on Scene 10
## RELATED

- Batch 2 freeze fix: covered Batch visuals must remain picture authority
- ContinuityBridge / Timeline Phase 2 work is separate; this law is playback composition only

## MUTE STATUS (verified 2026-09-11 ~7:55 PM PT)

- Helper: `studio-web/src/components/timeline-master/shouldMutePreviewVideoSoundtrack.ts`
- `lipsyncOutputPath` is deprecated/ignored for mute; mute only when an enabled lipsync dialogue clip intersects playhead.
- Wired: `TimelinePreviewComposer` → `LivePreviewMonitor` (`muteVideoAudio` / `suppressOriginalVoice`).
- Vitest: `shouldMutePreviewVideoSoundtrack.test.ts` **8/8 PASS** (includes Scene 10 Batch 2: no whole-play mute from leftover `lipsync_output_path`).
