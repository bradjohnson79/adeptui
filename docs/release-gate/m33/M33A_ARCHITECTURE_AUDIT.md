# M3.3a — Character Identity Architecture Audit

| Field | Value |
|---|---|
| **Date** | 2026-07-28 |
| **Milestone** | M3.3 Character Profile, Identity, and Voice System |
| **Phase** | M3.3a — Architecture audit + canonical schemas |
| **Prerequisites** | V1.1 3D Scope Lock GO · M3.2g Hitchhiker Test 2 GO |

## Protected production evidence (do not mutate)

| Asset | ID / path |
|---|---|
| Hitchhiker project | `d1683511-1cc7-4d3d-8cb7-00f48cc36aa9` |
| M3.2f LTX Shot1 | `6b91bb7f-0dfd-44e6-92b3-7df7ac8cea4f` |
| M3.2g Test 2 WAN | `e277e621-189d-471e-b435-f01620f03d0d` |
| Dialogue WAV | `c5cdd736-8f89-42e3-a7a8-9cb97043bf8a` |

## Parallel character concepts (pre-M3.3)

| Layer | Location | Maturity | M3.3 disposition |
|---|---|---|---|
| Production Bible `character` | `codirector/bible/domain/schemas.py` `CharacterData` | Real, versioned | Narrative facade + `characterProfileId` link |
| `profile_items` character/voice | `profiles.py` | Real CRUD, untyped JSON | Legacy bridge; never auto-APPROVED |
| Avatar Studio session | `avatar_studio.py`, `avatar/types.ts` | Real CRUD; TTS stub | Performance instance; bind to Character + Voice Profile |

## Reusable foundations

- Bible domain service + proposal gate
- Project Library `characters.*` taxonomy + lazy entity folders
- Kokoro m210b dialogue adapter (preset/draft)
- Scene lipsync + LatentSync runtime (certified M3.2f/g)
- Migration runner + `ensure_*_tables()` startup pattern
- ACE-Step / MMAudio install + subprocess worker pattern (template for Qwen)

## Gaps closed by M3.3

1. No durable `character_profiles` / versioned identity tables
2. No machine-readable Visual Identity Pack roles
3. No production Voice Profile (design/clone/consent)
4. Qwen3-TTS VoiceDesign / Base not wired (CustomVoice stub only)
5. Audio Studio lacks Character Voice / dialogue generate UI
6. Bible ↔ profile ↔ avatar links unwired
7. No Co-Director coverage / voice / wardrobe tools for Character Identity

## Canonical stack (locked)

```
CharacterProfile (SoT)
  ├── CharacterVersion (immutable when approved/locked)
  ├── CharacterReferenceAsset (role-tagged)
  ├── Wardrobe / Props / Traits / Skin / Hair / Personality / Performance
  ├── VoiceProfile (+ VoiceConsentRecord)
  ├── Production Bible character entity (same IDs)
  └── Project Library characters.* folders
```

## Non-goals

- No native 3D / mesh / mocap
- No WAN encoder reopen unless regression
- No unofficial Qwen forks
- No silent voice identity fallback
