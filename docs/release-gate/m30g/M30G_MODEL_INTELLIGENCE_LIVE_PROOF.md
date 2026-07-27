# M30G Model Intelligence Live Proof

| Field | Value |
|-------|-------|
| Branch | `phase2/codirector-m2-9-production-suite` |
| Starting SHA | `77c664c77a5a3caf6347ea32080f8b6a346a35cd` |
| Implementation SHA | `de14e734406430d99ba95b67f92a7d69937f19c7` |
| Documentation SHA | `b367599b7c83f67c47042f3799ba36cccae54442` |
| Documentation stamp tip | 2bb349174cc8ff29732b40a52f4d9678f32e0f2f |
| Final tip | 2bb349174cc8ff29732b40a52f4d9678f32e0f2f |
| Provider Manifest SHA | `cf99d7e5a91d192891495dbbb6f24feead24e6a9aec3ad236258ab39a4bba7bc` |
| Date | 2026-07-27 |


## Live status

`BLOCKED_NO_LIVE_GENERATE`

## Audio classification

`INCONCLUSIVE`

Allowed GREEN classes: `NO_AUDIO_STREAM`, `AUDIO_STREAM_WITH_NO_DETECTED_MUSIC`, `AUDIO_STREAM_WITH_AMBIENCE_ONLY`.

Artifact: `artifacts/m30g/live-fal-music-off/live_proof.json`

Compile path proves `generate_audio=false` for Seedance when music prohibited. Live shared-queue generate + media inspection remain incomplete without `ADEPT_M30G_FAL_LIVE=1` and key.

LTX remains `BEST_EFFORT_EXTERNAL_AUDIO`.
