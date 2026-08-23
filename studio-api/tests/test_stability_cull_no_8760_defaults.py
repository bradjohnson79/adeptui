from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FORBIDDEN = '|| "http://127.0.0.1:8760"'
FORBIDDEN_ALT = "|| 'http://127.0.0.1:8760'"


def test_playwright_specs_do_not_default_to_retired_8760():
    offenders: list[str] = []
    for path in (ROOT / "tests" / "e2e").rglob("*.ts"):
        text = path.read_text(encoding="utf-8")
        if FORBIDDEN in text or FORBIDDEN_ALT in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], "Playwright specs still default to retired :8760:\n" + "\n".join(offenders)


def test_beta_certify_defaults_to_vite_not_retired_8760():
    text = (ROOT / "scripts" / "beta_runtime" / "certify.py").read_text(encoding="utf-8")
    assert 'STUDIO_WEB_PORT", "5173"' in text or "STUDIO_WEB_PORT', '5173'" in text
    assert '"ui": 8760' not in text
    assert "web_server.py" not in text or "retiredWebServer" in text
    pkg = (ROOT / "package.json").read_text(encoding="utf-8")
    assert "beta:certify" in pkg
