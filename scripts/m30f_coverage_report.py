#!/usr/bin/env python3
"""Translation coverage report — English is authoritative; EN fallback ≠ translated."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_ROOT = ROOT / "studio-web" / "src" / "i18n" / "locales"
META = json.loads((ROOT / "studio-web" / "src" / "i18n" / "locale-meta.json").read_text(encoding="utf-8"))
OUT = ROOT / "artifacts" / "m30f-i18n" / "translation_coverage.json"

BETA = set(META["betaCriticalNamespaces"])


def load_ns(locale: str, ns: str) -> dict:
    path = LOCALE_ROOT / locale / f"{ns}.json"
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    en = {ns: load_ns("en", ns) for ns in META["namespaces"]}
    report = {"locales": {}, "betaCritical": {}, "reviewLevels": {}}
    for loc in META["locales"]:
        code = loc["locale"]
        report["reviewLevels"][code] = loc.get("reviewLevel", "MACHINE_DRAFT")
        ns_scores = {}
        beta_ok = True
        for ns in META["namespaces"]:
            en_keys = en.get(ns) or {}
            other = load_ns(code, ns)
            if not en_keys:
                ns_scores[ns] = 100.0
                continue
            present = 0
            translated = 0
            for k, en_val in en_keys.items():
                if k in other and str(other[k]).strip():
                    present += 1
                    if code == "en" or str(other[k]) != str(en_val):
                        translated += 1
                    elif ns not in BETA:
                        translated += 1  # non-critical may share brand tokens
                    else:
                        # identical to English in beta-critical counts as untranslated
                        pass
                elif ns in BETA:
                    beta_ok = False
            # For coverage %: keys present (not necessarily linguistically distinct)
            pct = 100.0 * present / len(en_keys) if en_keys else 100.0
            # Distinct translation rate for honesty
            distinct = 100.0 * translated / len(en_keys) if en_keys else 100.0
            ns_scores[ns] = {"keyCoverage": round(pct, 1), "distinctFromEnglish": round(distinct, 1)}
            if ns in BETA and pct < 100:
                beta_ok = False
        overall = sum(v["keyCoverage"] if isinstance(v, dict) else v for v in ns_scores.values()) / max(
            len(ns_scores), 1
        )
        report["locales"][code] = {"namespaces": ns_scores, "overallKeyCoverage": round(overall, 1)}
        report["betaCritical"][code] = {
            "complete": beta_ok,
            "reviewLevel": loc.get("reviewLevel"),
            "linguisticallyVerified": loc.get("reviewLevel")
            in ("LINGUISTICALLY_REVIEWED", "PRODUCTION_APPROVED", "HUMAN_APPROVED"),
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"wrote": str(OUT), "betaCritical": report["betaCritical"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
