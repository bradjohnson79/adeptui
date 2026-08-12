# M42 Character Creator Prompt Report

**Date:** 2026-07-31  
**Mock data:** false  
**Exported package:** `artifacts/m42/character-creator/prompt-package.json`

---

## Authority chain

1. `config/character-canon/korri.v1.json`  
2. `seed_korri_from_canon` → Character Profile fields  
3. `generate_prompt_package()` → `imagePrompt` (+ video/performance/etc.)  
4. `visual_sheet._identity_prompt()` appends hard `KORRI_LOCK` for slug `korri`  
5. Role suffixes for hero / coverage / details / performance  

---

## KORRI_LOCK (production)

```text
LOCKED IDENTITY: Korri, 18, Human/Sun Sprite Elf Hybrid, black twin ponytails, purple eyes,
pale skin, pointed Sun Sprite Elf ears, wooden earrings, circuit/light tattoos,
handmade black cloth wardrobe, petite slim athletic ~5'1\".
FORBIDDEN: blonde hair, aqua/blue eyes, metallic futuristic wardrobe, Anadriya face,
missing pointed ears, missing circuit markings.
```

---

## Exported imagePrompt (live)

```text
Korri, Human / Sun Sprite Elf Hybrid (Sass Queen). Appearance: black hair, twin ponytails,
pale skin, Petite, slim, athletic, Approximately 5'1\" (155 cm), pointed elf ears,
Circuit/light tattoo system — active and inactive states, ; locked: black hair twin ponytails,
purple eyes, pale skin, pointed Sun Sprite Elf ears, wooden earrings, circuit/light tattoo system,
handmade black cloth wardrobe. Wardrobe: . Expression/posture: Relaxed athletic stance;
weight rarely evenly planted. Photoreal cinematic character portrait, consistent identity.
```

---

## Role prompt coverage

| Role group | Construction |
|---|---|
| Hero | identity + portrait framing |
| Coverage (6) | identity + doubled lock + turnaround/closeup camera language |
| Details (6) | identity + DETAIL_ROLE_PROMPTS (skin/hair/wardrobe/accessory) |
| Performance (2) | identity + expression/pose sheet language |
| Negatives | blonde, aqua, metallic, Anadriya, collage, watermark, etc. |

---

## Expected vs exported checklist

| Trait | In package / lock | Notes |
|---|---|---|
| Black twin ponytails | Yes | |
| Purple eyes | Yes | |
| Pale skin | Yes | |
| Sun Sprite Elf ears | Yes | |
| Petite athletic / ~5'1" | Yes | |
| Handmade black clothing | Yes (lock + locked features) | Wardrobe object field empty in package string — lock still enforces |
| Wooden accessories | Yes | |
| Circuit markings | Yes | |
| Mischievous smile | Performance bible | Visual expression prompts separate |

---

## Prompt verdict

**PASS** — Canonical identity is serialized into production prompts with an explicit Korri lock and forbidden traits. Exported package matches expected locked features.
