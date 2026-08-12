#!/usr/bin/env python3
"""Best-effort Beta screenshots for Timeline UX mockup parity."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "artifacts" / "m42" / "w46" / "timeline-ux"
BASE = "http://127.0.0.1:8760"


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        print(f"playwright unavailable: {exc}")
        return 0

    ART.mkdir(parents=True, exist_ok=True)
    shots = [
        ("beta-1280-night.png", 1280, 720, "aurora-night"),
        ("beta-1920-night.png", 1920, 1080, "aurora-night"),
        ("beta-1280-day.png", 1280, 720, "aurora-day"),
        ("beta-1920-day.png", 1920, 1080, "aurora-day"),
    ]
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            for name, w, h, theme in shots:
                context = browser.new_context(viewport={"width": w, "height": h})
                page = context.new_page()
                page.goto(BASE, wait_until="domcontentloaded", timeout=20000)
                page.evaluate(
                    """(theme) => {
                      document.documentElement.setAttribute('data-theme', theme);
                      try { localStorage.setItem('adept_ui_theme', theme); } catch (e) {}
                    }""",
                    theme,
                )
                # Best-effort open Timeline
                try:
                    page.locator("a[href*='/project/'], [data-testid='project-card']").first.click(timeout=5000)
                    page.get_by_role("button", name="Timeline").first.click(timeout=8000)
                    page.get_by_test_id("timeline-editor-shell").wait_for(timeout=15000)
                except Exception:
                    pass
                page.screenshot(path=str(ART / name), full_page=False)
                context.close()
                print(f"captured {name}")
            browser.close()
    except Exception as exc:
        print(f"capture failed: {exc}")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
