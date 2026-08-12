"""Generate Phase 4.0 local SVG artwork under studio-web/public/images/ui/."""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "studio-web" / "public" / "images" / "ui"

ITEMS = {
    "workspaces/ws-director.svg": ("#0a1220", "#2dd4bf", "#38bdf8", "Director"),
    "workspaces/ws-script.svg": ("#0a1220", "#a78bfa", "#2dd4bf", "Script"),
    "workspaces/ws-spatial.svg": ("#0a1220", "#22d3ee", "#a78bfa", "Spatial"),
    "workspaces/ws-imagegen.svg": ("#0a1220", "#2dd4bf", "#fbbf24", "ImageGen"),
    "workspaces/ws-video.svg": ("#0a1220", "#38bdf8", "#2dd4bf", "Video"),
    "workspaces/ws-library.svg": ("#0a1220", "#a78bfa", "#38bdf8", "Library"),
    "workspaces/ws-avatar.svg": ("#0a1220", "#fbbf24", "#2dd4bf", "Avatar"),
    "workspaces/ws-audio.svg": ("#0a1220", "#22d3ee", "#a78bfa", "Audio"),
    "workspaces/ws-bible.svg": ("#0a1220", "#fbbf24", "#38bdf8", "Bible"),
    "workspaces/ws-characters.svg": ("#0a1220", "#2dd4bf", "#a78bfa", "Characters"),
    "workspaces/ws-tools.svg": ("#0a1220", "#38bdf8", "#fbbf24", "Tools"),
    "workspaces/ws-sources.svg": ("#0a1220", "#a78bfa", "#22d3ee", "Sources"),
    "workspaces/ws-editor.svg": ("#0a1220", "#2dd4bf", "#38bdf8", "Editor"),
    "workspaces/ws-codirector.svg": ("#050914", "#2dd4bf", "#a78bfa", "Co-Director"),
    "templates/template-narrative.svg": ("#0a1220", "#2dd4bf", "#a78bfa", "Narrative"),
    "templates/template-dialogue.svg": ("#0a1220", "#38bdf8", "#2dd4bf", "Dialogue"),
    "templates/template-commercial.svg": ("#0a1220", "#fbbf24", "#38bdf8", "Commercial"),
    "templates/template-music.svg": ("#0a1220", "#a78bfa", "#22d3ee", "Music"),
    "templates/template-animation.svg": ("#0a1220", "#2dd4bf", "#fbbf24", "Animation"),
    "empty-states/empty-projects.svg": ("#070b14", "#2dd4bf", "#38bdf8", "No Projects"),
    "empty-states/empty-characters.svg": ("#070b14", "#a78bfa", "#2dd4bf", "No Characters"),
    "empty-states/empty-library.svg": ("#070b14", "#38bdf8", "#a78bfa", "Empty Library"),
    "cards/enhance.svg": ("#0a1220", "#fbbf24", "#2dd4bf", "Enhance"),
}

TEMPLATE = """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600" role="img">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{c1}" stop-opacity="0.55"/>
      <stop offset="55%" stop-color="{c2}" stop-opacity="0.35"/>
      <stop offset="100%" stop-color="{bg}" stop-opacity="1"/>
    </linearGradient>
    <radialGradient id="r" cx="30%" cy="25%" r="60%">
      <stop offset="0%" stop-color="{c1}" stop-opacity="0.45"/>
      <stop offset="100%" stop-color="{bg}" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <rect width="960" height="600" fill="{bg}"/>
  <rect width="960" height="600" fill="url(#g)"/>
  <rect width="960" height="600" fill="url(#r)"/>
  <circle cx="720" cy="160" r="120" fill="{c2}" fill-opacity="0.18"/>
  <circle cx="200" cy="420" r="160" fill="{c1}" fill-opacity="0.16"/>
  <text x="48" y="540" font-family="Georgia, serif" font-size="42" fill="#f3f7fb" opacity="0.92">{label}</text>
</svg>
"""


def main() -> None:
    for rel, (bg, c1, c2, label) in ITEMS.items():
        path = ROOT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(TEMPLATE.format(bg=bg, c1=c1, c2=c2, label=label), encoding="utf-8")

    hero_src = ROOT.parent / "hero"
    hero_dst = ROOT / "hero"
    hero_dst.mkdir(parents=True, exist_ok=True)
    if hero_src.exists():
        for f in hero_src.iterdir():
            if f.is_file():
                shutil.copy2(f, hero_dst / f.name)

    for name in ("dashboard", "backgrounds", "placeholders", "icons"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)
        keep = ROOT / name / ".gitkeep"
        if not keep.exists():
            keep.write_text("", encoding="utf-8")

    print(f"Artwork library ready under {ROOT}")


if __name__ == "__main__":
    main()
