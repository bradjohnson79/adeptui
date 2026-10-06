"""Domain-first term resolution for Adept platform knowledge.

Loads ``lexicon.yaml`` when present. The only hardcoded context rule is
computer-networking vs Adept production for shared acronyms such as WAN
(production WAN is retired in v1.1; networking meaning stays Wide Area Network).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .loader import KB_ROOT

LEXICON_PATH = KB_ROOT / "lexicon.yaml"

DOMAIN_PRODUCTION = "adept_production"
DOMAIN_NETWORKING = "computer_networking"
NETWORKING_WAN_SPOKEN = "In computer networking, WAN means Wide Area Network."

_DEFAULT_NETWORKING_CUES = (
    "wide area network",
    "computer networking",
    "computer network",
    "local area network",
    "ethernet",
    "wi-fi",
    "wifi",
    "router",
    "packet",
    r"\bisp\b",
    r"\blan\b",
    r"\btcp\b",
    r"\budp\b",
)

_DEFAULT_TERMS: dict[str, Any] = {
    "WAN": {
        "aliases": ["wan"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "adept-terminology",
                "spoken": (
                    "WAN is retired in Adept UI v1.1. Timeline uses MiniMax H3 "
                    "and LTX 2.5 for Reference-to-Video. Do not restore WAN."
                ),
            },
            {
                "domain": DOMAIN_NETWORKING,
                "entity_id": "wan-networking",
                "spoken": "In computer networking, WAN means Wide Area Network.",
            }
        ],
    },
    "LTX": {
        "aliases": ["ltx"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "ltx-2.5",
                "also": ["adept-readiness"],
            }
        ],
    },
    "H3": {
        "aliases": ["h3", "minimax h3", "minimax"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "minimax-h3",
                "also": ["adept-platform"],
            }
        ],
    },
    "Qwen": {"aliases": ["qwen"], "senses": [{"domain": DOMAIN_PRODUCTION, "entity_id": "qwen-2512"}]},
    "FLUX": {"aliases": ["flux"], "senses": [{"domain": DOMAIN_PRODUCTION, "entity_id": "flux"}]},
    "ERS": {
        "aliases": ["ers", "environment reference sheet"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "ers-spec",
                "also": ["gpt-image-2"],
            }
        ],
    },
    "CRS": {
        "aliases": ["crs", "character reference sheet", "character sheet"],
        "senses": [{"domain": DOMAIN_PRODUCTION, "entity_id": "character-creator"}],
    },
    "PRS": {
        "aliases": ["prs", "prop reference sheet"],
        "senses": [{"domain": DOMAIN_PRODUCTION, "entity_id": "prop-creator"}],
    },
    "PoseCraft": {
        "aliases": ["posecraft", "pose craft"],
        "senses": [{"domain": DOMAIN_PRODUCTION, "entity_id": "posecraft"}],
    },
    "Spatial Map": {
        "aliases": ["spatial map", "atlas"],
        "senses": [{"domain": DOMAIN_PRODUCTION, "entity_id": "spatial-map"}],
    },
    "Route A": {
        "aliases": ["route a", "route-a"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "adept-platform",
                "also": ["minimax-h3", "adept-readiness", "video-generation", "timeline"],
            }
        ],
    },
    "On Demand": {
        "aliases": ["on demand"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "adept-readiness",
                "also": ["adept-platform"],
            }
        ],
    },
    "Lip Sync": {
        "aliases": ["lip sync", "lipsync", "timeline lip sync"],
        "senses": [
            {
                "domain": DOMAIN_PRODUCTION,
                "entity_id": "voice-creator",
                "also": ["minimax-h3"],
            }
        ],
    },
}


@dataclass(frozen=True)
class LexiconSense:
    domain: str
    entity_id: str
    spoken: str = ""
    label: str = ""
    also: tuple[str, ...] = ()


@dataclass(frozen=True)
class LexiconTerm:
    key: str
    aliases: tuple[str, ...]
    senses: tuple[LexiconSense, ...]


@dataclass(frozen=True)
class LexiconHit:
    term: str
    domain: str
    entity_id: str
    spoken: str = ""
    label: str = ""
    aliases: tuple[str, ...] = ()
    also: tuple[str, ...] = ()


@dataclass(frozen=True)
class Lexicon:
    default_domain: str = DOMAIN_PRODUCTION
    networking_cues: tuple[str, ...] = _DEFAULT_NETWORKING_CUES
    terms: tuple[LexiconTerm, ...] = ()
    path: Path | None = None
    losing_ids: dict[str, tuple[str, ...]] = field(default_factory=dict)


_cache: tuple[float | None, Lexicon] | None = None


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        token = value.strip()
        return (token,) if token else ()
    if isinstance(value, (list, tuple, set)):
        out: list[str] = []
        for item in value:
            token = str(item or "").strip()
            if token and token not in out:
                out.append(token)
        return tuple(out)
    return ()


def _parse_sense(raw: Any) -> LexiconSense | None:
    if not isinstance(raw, dict):
        return None
    entity_id = str(raw.get("entity_id") or raw.get("id") or "").strip()
    if not entity_id:
        return None
    return LexiconSense(
        domain=_canonical_domain(raw.get("domain") or DOMAIN_PRODUCTION),
        entity_id=entity_id,
        spoken=str(raw.get("spoken") or "").strip(),
        label=str(raw.get("label") or "").strip(),
        also=_string_tuple(raw.get("also")),
    )


def _parse_term(key: str, raw: Any) -> LexiconTerm | None:
    if not isinstance(raw, dict):
        return None
    aliases = _string_tuple(raw.get("aliases"))
    if key and key not in aliases:
        aliases = (key, *aliases)
    senses = tuple(sense for item in (raw.get("senses") or []) if (sense := _parse_sense(item)))
    if not senses:
        entity_id = str(raw.get("entity_id") or raw.get("id") or "").strip()
        if entity_id:
            senses = (
                LexiconSense(
                    domain=_canonical_domain(raw.get("domain") or DOMAIN_PRODUCTION),
                    entity_id=entity_id,
                    spoken=str(raw.get("spoken") or "").strip(),
                    also=_string_tuple(raw.get("also")),
                ),
            )
    if not senses:
        return None
    return LexiconTerm(key=key, aliases=aliases, senses=senses)


def _canonical_domain(raw: Any) -> str:
    token = str(raw or "").strip().lower()
    if token in {DOMAIN_NETWORKING, "networking"}:
        return DOMAIN_NETWORKING
    return DOMAIN_PRODUCTION


def _term_key(alias: str) -> str:
    token = (alias or "").strip()
    if not token:
        return ""
    if len(token) <= 3:
        return token.upper()
    return token


def _lexicon_from_entries(data: dict[str, Any], *, path: Path | None = None) -> Lexicon:
    grouped: dict[str, dict[str, Any]] = {}
    for raw in data.get("entries") or []:
        if not isinstance(raw, dict):
            continue
        alias = str(raw.get("alias") or "").strip()
        entity_id = str(raw.get("id") or raw.get("entity_id") or "").strip()
        if not alias or not entity_id:
            continue
        key = _term_key(alias)
        bucket = grouped.setdefault(key, {"aliases": [], "senses": []})
        if alias not in bucket["aliases"]:
            bucket["aliases"].append(alias)
        if key not in bucket["aliases"]:
            bucket["aliases"].insert(0, key)
        domain = _canonical_domain(raw.get("domain"))
        spoken = str(raw.get("spoken") or raw.get("note") or "").strip()
        if domain == DOMAIN_NETWORKING and key == "WAN" and "wide area network" not in spoken.lower():
            spoken = NETWORKING_WAN_SPOKEN
        sense = {
            "domain": domain,
            "entity_id": entity_id,
            "spoken": spoken,
            "also": _string_tuple(raw.get("also")),
        }
        existing = next(
            (
                item
                for item in bucket["senses"]
                if item["domain"] == domain and item["entity_id"] == entity_id
            ),
            None,
        )
        if existing is None:
            bucket["senses"].append(sense)
    terms_map = {
        key: {"aliases": payload["aliases"], "senses": payload["senses"]}
        for key, payload in grouped.items()
    }
    merged = dict(data)
    merged["terms"] = terms_map
    merged.setdefault("default_domain", DOMAIN_PRODUCTION)
    return _lexicon_from_mapping(merged, path=path)


def _lexicon_from_mapping(data: dict[str, Any], *, path: Path | None = None) -> Lexicon:
    networking = data.get("networking") if isinstance(data.get("networking"), dict) else {}
    cues = _string_tuple(networking.get("cues") or data.get("networking_cues")) or _DEFAULT_NETWORKING_CUES
    raw_terms = data.get("terms") if isinstance(data.get("terms"), dict) else {}
    terms = tuple(
        term
        for key, payload in raw_terms.items()
        if (term := _parse_term(str(key), payload))
    )
    losing: dict[str, tuple[str, ...]] = {}
    for term in terms:
        ids = [sense.entity_id for sense in term.senses]
        for sense in term.senses:
            others = tuple(item for item in ids if item != sense.entity_id)
            if others:
                losing[f"{term.key}::{sense.entity_id}"] = others
    return Lexicon(
        default_domain=_canonical_domain(data.get("default_domain") or DOMAIN_PRODUCTION),
        networking_cues=cues,
        terms=terms,
        path=path,
        losing_ids=losing,
    )


def _default_lexicon() -> Lexicon:
    return _lexicon_from_mapping(
        {"default_domain": DOMAIN_PRODUCTION, "terms": _DEFAULT_TERMS},
        path=None,
    )


def clear_lexicon_cache() -> None:
    global _cache
    _cache = None


def load_lexicon(*, path: Path | None = None, force: bool = False) -> Lexicon:
    global _cache
    target = Path(path) if path is not None else LEXICON_PATH
    mtime: float | None
    try:
        mtime = target.stat().st_mtime if target.is_file() else None
    except OSError:
        mtime = None
    if not force and _cache is not None and _cache[0] == mtime and path is None:
        return _cache[1]
    if mtime is None:
        lexicon = _default_lexicon()
    else:
        try:
            loaded = yaml.safe_load(target.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            loaded = None
        if isinstance(loaded, dict) and loaded.get("entries"):
            lexicon = _lexicon_from_entries(loaded, path=target)
        elif isinstance(loaded, dict) and loaded.get("terms"):
            lexicon = _lexicon_from_mapping(loaded, path=target)
        else:
            lexicon = _default_lexicon()
    if path is None:
        _cache = (mtime, lexicon)
    return lexicon


def _cue_matches(text: str, cue: str) -> bool:
    raw = (cue or "").strip()
    if not raw:
        return False
    hay = text or ""
    if raw.startswith(r"\b") or any(ch in raw for ch in ".+*?[]()"):
        try:
            return bool(re.search(raw, hay, re.I))
        except re.error:
            pass
    if " " in raw or "-" in raw:
        return raw.lower() in hay.lower()
    return bool(re.search(rf"\b{re.escape(raw)}\b", hay, re.I))


def is_networking_context(text: str, *, lexicon: Lexicon | None = None) -> bool:
    pack = lexicon or load_lexicon()
    hay = text or ""
    return any(_cue_matches(hay, cue) for cue in pack.networking_cues)


def resolve_domain(
    text: str,
    *,
    workspace: str | None = None,
    domain_hint: str | None = None,
    lexicon: Lexicon | None = None,
) -> str:
    hint = str(domain_hint or "").strip()
    if hint:
        return hint
    workspace_token = str(workspace or "").strip().lower()
    if workspace_token in {DOMAIN_NETWORKING, "networking"}:
        return DOMAIN_NETWORKING
    pack = lexicon or load_lexicon()
    if is_networking_context(text, lexicon=pack):
        return DOMAIN_NETWORKING
    return pack.default_domain or DOMAIN_PRODUCTION


def _mentioned(text: str, alias: str) -> bool:
    token = (alias or "").strip()
    if not token:
        return False
    hay = text or ""
    if len(token) <= 3:
        return bool(re.search(rf"\b{re.escape(token)}\b", hay, re.I))
    if re.search(rf"\b{re.escape(token)}\b", hay, re.I):
        return True
    folded_alias = re.sub(r"[^a-z0-9]+", "", token.lower())
    folded_hay = re.sub(r"[^a-z0-9]+", "", hay.lower())
    return len(folded_alias) >= 4 and folded_alias in folded_hay


def _sense_for_domain(term: LexiconTerm, domain: str) -> LexiconSense:
    wanted = _canonical_domain(domain)
    for sense in term.senses:
        if _canonical_domain(sense.domain) == wanted:
            return sense
    for sense in term.senses:
        if _canonical_domain(sense.domain) == DOMAIN_PRODUCTION:
            return sense
    return term.senses[0]


def losing_entity_ids(term_key: str, chosen_entity_id: str, *, lexicon: Lexicon | None = None) -> tuple[str, ...]:
    pack = lexicon or load_lexicon()
    return pack.losing_ids.get(f"{term_key}::{chosen_entity_id}", ())


def resolve_terms(
    text: str,
    *,
    workspace: str | None = None,
    domain_hint: str | None = None,
) -> list[LexiconHit]:
    pack = load_lexicon()
    domain = resolve_domain(text, workspace=workspace, domain_hint=domain_hint, lexicon=pack)
    hay = text or ""
    index: list[tuple[int, str, LexiconTerm]] = []
    for term in pack.terms:
        for alias in term.aliases:
            index.append((len(alias), alias, term))
    index.sort(key=lambda item: (-item[0], item[1].lower()))
    hits: list[LexiconHit] = []
    seen: set[str] = set()
    for _length, alias, term in index:
        if term.key in seen:
            continue
        if not _mentioned(hay, alias):
            continue
        seen.add(term.key)
        sense = _sense_for_domain(term, domain)
        hits.append(
            LexiconHit(
                term=term.key,
                domain=sense.domain,
                entity_id=sense.entity_id,
                spoken=sense.spoken,
                label=sense.label,
                aliases=term.aliases,
                also=sense.also,
            )
        )
    return hits
