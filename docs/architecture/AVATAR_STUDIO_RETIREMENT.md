# Avatar Studio — temporary retirement from current Adept UI

**Governing note for current Adept UI production.** Historical Avatar Studio cert docs remain historical.

Avatar Studio is **temporarily retired from the current Adept UI**. It is no longer a product surface, menu item, Explore card, Co-Director destination, or setup/runtime install target.

Reconsider for **Adept UI v1.2** as a **cloud** Avatar product. No delivery date is promised.

## Why

InfiniteTalk / Wan-based local avatar runtimes are unsuitable for the current production direction (aligns with InfiniteTalk sample NO-GO Wan policy). Owner local-video allowlist: MiniMax H3 + LTX 2.5 only.

## Active product (removed / gated)

- Production menu → Creative Studios → Avatar Studio
- Home Explore card `avatar`
- Project Home dashboard card
- `?workspace=avatar` (aliases `avatar-studio`, `avatar_studio`) — deep links → Project Home
- ProjectEditor mount of `AvatarStudioWorkspace` (retired notice only if tab somehow set)
- Co-Director `avatar.*` tools (registered but not exposed; handlers refuse execution)
- Setup catalog Avatar Runtimes (excluded from `public_components`)
- Source Manager Avatar runtime install panel
- Ai-Guided Setup recommendations for talking-presenter avatar runtimes

## Intentionally preserved

| Kind | What | Why |
|---|---|---|
| Source | `avatar_studio.py`, `avatar_runtimes.py`, providers, web components | Owner may revisit; do not delete |
| Model weights | InfiniteTalk / Wan / wav2vec / LongCat / etc. | Orphaned/retired — owner deletes later |
| Library outputs | Existing Avatar sessions / media | Valid historical media |
| Voice Creator | Voice Studio / clones / TTS / dialogue | Separate product — must remain |
| Docs | `docs/avatar-studio/**`, release-gate avatar certs | Historical |

## Do not

- Re-add Avatar Studio to Production menu, Explore, or command palette as an active feature
- Re-expose `avatar.*` Co-Director tools without an explicit owner un-retire decision
- Fake healthy readiness for Avatar runtimes — they are excluded from the readiness contract
- Delete model weights without owner approval
- Touch Timeline, MiniMax H3, LTX 2.5, MAGI, Scene Creator, Image Generator, 1F/3F/T2V shared paths except Avatar-specific wiring
