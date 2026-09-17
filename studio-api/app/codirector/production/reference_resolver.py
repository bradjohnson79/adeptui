"""Resolve named production references against project CRS / ERS / PRS registries."""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.orm import Session

from .canonical_tags import prompt_facing_tag
from .contracts import AssetType, ProductionReferenceQuery, ResolvedReference, VerificationStatus


_STOP_WORDS = frozenset({"the", "a", "an", "prop", "environment", "character", "reference", "sheet"})


def _norm(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (value or "").lower())


def _is_generic_env(query: str) -> bool:
    compact = _norm(query)
    return compact in {"environment", "environmentreference", "reference", "place", "location"}


def _query_core(query: str) -> str:
    token = re.sub(r"\b(?:character|prop|environment)?\s*reference\s*sheet\b", "", query or "", flags=re.I)
    token = re.sub(r"\b(?:the|a|an)\b", " ", token, flags=re.I)
    return re.sub(r"\s+", " ", token).strip()


def _distinctive_words(query: str) -> list[str]:
    return [w for w in re.findall(r"[a-z0-9]+", (query or "").lower()) if w not in _STOP_WORDS and len(w) >= 5]


def _pascal(value: str) -> str:
    parts = re.findall(r"[A-Za-z0-9]+", value or "")
    return "".join(p[:1].upper() + p[1:] for p in parts) if parts else ""


def _score_name(query: str, *candidates: str) -> int:
    q = _norm(query)
    if not q:
        return 0
    best = 0
    for raw in candidates:
        token = _norm(raw)
        if not token:
            continue
        if token == q:
            return 100
        if q in token or token in q:
            best = max(best, 80)
        q_words = _distinctive_words(query)
        hits = sum(1 for w in q_words if w and w in token)
        if q_words and hits == len(q_words):
            best = max(best, 70)
    return best


def _library_environment_fallback(db: Session, project_id: str, query: str) -> ResolvedReference | None:
    from ...db import Asset

    rows = (
        db.query(Asset)
        .filter(Asset.project_id == project_id)
        .order_by(Asset.created_at.desc())
        .limit(400)
        .all()
    )
    matches: list[tuple[int, Any]] = []
    for row in rows:
        score = _score_name(query, getattr(row, "tag", "") or "", getattr(row, "filename", "") or "")
        tag = str(getattr(row, "tag", "") or "").lower()
        if "environment" in tag or "ers" in tag:
            score = min(100, score + 5)
        if score >= 70:
            matches.append((score, row))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0], reverse=True)
    if len(matches) > 1 and matches[0][0] == matches[1][0]:
        return ResolvedReference(
            status="ambiguous",
            query=query,
            expected_type="environment",
            display_name=query,
            asset_type="environment",
            notes="Multiple Library environment images matched this name.",
            candidates=[str(item[1].id) for item in matches[:4]],
        )
    row = matches[0][1]
    filename = str(getattr(row, "filename", "") or "").rsplit(".", 1)[0].replace("_", " ").replace("-", " ")
    display = query if query and not _is_generic_env(query) else (filename or query)
    tag = prompt_facing_tag("#", getattr(row, "tag", "") or "", display)
    bindable = str(row.id)
    return ResolvedReference(
        status="found" if bindable else "broken",
        query=query,
        expected_type="environment",
        asset_id=str(row.id),
        entity_id=str(row.id),
        display_name=display,
        asset_type="environment",
        bindable_asset_id=bindable,
        identity_tag=_pascal(display),
        canonical_tag=tag,
        verification="found" if bindable else "broken",
        approved_sheet=False,
        notes="Found as a Library environment image. A full Environment Reference Sheet profile was not present.",
    )


def _prefer_local_prop(project_id: str, props: list[Any]) -> list[Any]:
    local = [item for item in props if str(getattr(item, "project_id", "") or "") == project_id]
    return local or props


def _prop_has_query_identity(prop: Any, query: str) -> bool:
    words = _distinctive_words(_query_core(query) or query)
    if not words:
        return True
    blob = _norm(
        " ".join(
            [
                str(getattr(prop, "display_label", "") or ""),
                str(getattr(prop, "tag", "") or ""),
                str(getattr(prop, "canonical_tag", "") or ""),
            ]
        )
    )
    return all(word in blob for word in words)


def _resolve_prop(db: Session, project_id: str, query: str) -> ResolvedReference:
    from ...prop_creator.readiness import approved_primary_asset_id
    from ...prop_creator.service import list_visible_props

    props = list_visible_props(db, project_id)
    core = _query_core(query) or query
    exact: list[Any] = []
    scored: list[tuple[int, Any]] = []
    for prop in props:
        label = getattr(prop, "display_label", "") or ""
        tag = getattr(prop, "tag", "") or ""
        stored_canonical = getattr(prop, "canonical_tag", "") or ""
        if (
            _norm(label) == _norm(core)
            or _norm(tag) == _norm(core)
            or _norm(label) == _norm(query)
            or _norm(stored_canonical) == _norm(core)
        ):
            exact.append(prop)
            continue
        score = _score_name(core, label, tag)
        if score:
            scored.append((score, prop))
    if exact:
        exact = [item for item in exact if _prop_has_query_identity(item, query)] or exact
        exact = _prefer_local_prop(project_id, exact)
        if len(exact) > 1 and len({str(item.id) for item in exact}) > 1:
            local = [item for item in exact if str(getattr(item, "project_id", "") or "") == project_id]
            if len(local) == 1:
                exact = local
            else:
                return ResolvedReference(
                    status="ambiguous",
                    query=query,
                    expected_type="prop",
                    display_name=query,
                    candidates=[str(item.id) for item in exact[:4]],
                )
        prop = exact[0]
    else:
        scored = [(score, item) for score, item in scored if _prop_has_query_identity(item, query)]
        if not scored:
            return ResolvedReference(status="missing", query=query, expected_type="prop", display_name=query)
        scored.sort(
            key=lambda item: (
                item[0],
                1 if str(getattr(item[1], "project_id", "") or "") == project_id else 0,
            ),
            reverse=True,
        )
        if len(scored) > 1 and scored[0][0] == scored[1][0] and scored[0][0] >= 80:
            local = [item for item in scored if item[0] == scored[0][0] and str(getattr(item[1], "project_id", "") or "") == project_id]
            if len(local) == 1:
                scored = local
            else:
                return ResolvedReference(
                    status="ambiguous",
                    query=query,
                    expected_type="prop",
                    display_name=query,
                    candidates=[str(item[1].id) for item in scored[:4]],
                )
        if scored[0][0] < 70:
            return ResolvedReference(status="missing", query=query, expected_type="prop", display_name=query)
        prop = scored[0][1]
    sheet_id = str(getattr(prop, "advanced_sheet_asset_id", "") or "").strip()
    bindable = sheet_id or approved_primary_asset_id(prop) or str(getattr(prop, "library_asset_id", "") or "")
    display = str(getattr(prop, "display_label", None) or getattr(prop, "tag", None) or query)
    stored = str(getattr(prop, "canonical_tag", "") or getattr(prop, "tag", "") or "")
    is_global = bool(getattr(prop, "is_global", False) or getattr(prop, "isGlobal", False))
    verification: VerificationStatus = "global_found" if is_global else "found"
    status = "found"
    if not bindable:
        verification = "broken"
        status = "broken"
    return ResolvedReference(
        status=status,
        query=query,
        expected_type="prop",
        asset_id=str(prop.id),
        entity_id=str(prop.id),
        display_name=display,
        asset_type="prop",
        reference_sheet_id=sheet_id,
        bindable_asset_id=bindable,
        identity_tag=_pascal(display) or stored,
        canonical_tag=prompt_facing_tag("%", stored, display),
        verification=verification,
        is_global=is_global,
        approved_sheet=bool(sheet_id or bindable),
    )


def _resolve_environment(db: Session, project_id: str, query: str) -> ResolvedReference:
    from ...environment_reference_sheet.store import list_visible_sheets

    sheets = list_visible_sheets(db, project_id)
    scored: list[tuple[int, Any]] = []
    for sheet in sheets:
        score = _score_name(query, getattr(sheet, "name", "") or "", getattr(sheet, "sheetId", "") or "")
        if score:
            scored.append((score, sheet))
    if scored:
        scored.sort(key=lambda item: item[0], reverse=True)
        if scored[0][0] >= 70:
            if len(scored) > 1 and scored[0][0] == scored[1][0]:
                return ResolvedReference(
                    status="ambiguous",
                    query=query,
                    expected_type="environment",
                    display_name=query,
                    candidates=[str(getattr(item[1], "sheetId", "")) for item in scored[:4]],
                )
            sheet = scored[0][1]
            composite = str(getattr(sheet, "ers_composite_asset_id", "") or "").strip()
            display = str(getattr(sheet, "name", None) or query)
            is_global = bool(getattr(sheet, "isGlobal", False) or getattr(sheet, "is_global", False))
            if not composite:
                fallback = _library_environment_fallback(db, project_id, query)
                if fallback is not None and fallback.status == "found":
                    fallback.display_name = display
                    fallback.canonical_tag = prompt_facing_tag(
                        "#",
                        str(getattr(sheet, "canonicalTag", "") or "") or display,
                        display,
                    )
                    fallback.identity_tag = _pascal(display)
                    fallback.entity_id = str(sheet.sheetId)
                    fallback.reference_sheet_id = str(sheet.sheetId)
                    fallback.is_global = is_global
                    fallback.verification = "global_found" if is_global else "found"
                    fallback.approved_sheet = True
                    fallback.notes = "Environment profile found; bound the Library environment image."
                    return fallback
            verification: VerificationStatus = "global_found" if is_global else "found"
            status = "found"
            if not composite:
                verification = "broken"
                status = "broken"
            return ResolvedReference(
                status=status,
                query=query,
                expected_type="environment",
                asset_id=str(sheet.sheetId),
                entity_id=str(sheet.sheetId),
                display_name=display,
                asset_type="environment",
                reference_sheet_id=str(sheet.sheetId),
                bindable_asset_id=composite,
                identity_tag=_pascal(display),
                canonical_tag=prompt_facing_tag(
                    "#",
                    str(getattr(sheet, "canonicalTag", "") or "") or display,
                    display,
                ),
                verification=verification,
                is_global=is_global,
                approved_sheet=bool(composite),
            )
    fallback = _library_environment_fallback(db, project_id, query)
    if fallback is not None:
        return fallback
    return ResolvedReference(status="missing", query=query, expected_type="environment", display_name=query)


def _character_sheet_asset_id(db: Session, character_id: str) -> str:
    """Approved Character Reference Sheet asset via the authoritative identity contracts."""
    try:
        from ...character_identity.crs_service import load_persisted_crs

        persisted = load_persisted_crs(db, character_id)
        sheet = str(persisted.get("approved_sheet_asset_id") or "").strip()
        if sheet:
            return sheet
    except Exception:
        pass
    try:
        from ...character_identity.service import resolve_approved_reference

        return str(resolve_approved_reference(db, character_id) or "").strip()
    except Exception:
        return ""


def _resolve_character(db: Session, project_id: str, query: str) -> ResolvedReference:
    try:
        from ...character_identity.service import list_profiles, resolve_character_by_name
    except Exception:
        return ResolvedReference(status="missing", query=query, expected_type="character", display_name=query)
    # Authoritative identity contract first: exact name / slug / normalized match.
    row: Any | None = None
    try:
        row = resolve_character_by_name(db, project_id, query)
    except Exception:
        row = None
    if row is None:
        rows: list[Any] = []
        try:
            rows = list(list_profiles(db, project_id) or [])
        except Exception:
            rows = []
        scored: list[tuple[int, Any]] = []
        for candidate in rows:
            score = _score_name(query, getattr(candidate, "name", "") or "", getattr(candidate, "display_name", "") or "")
            if score:
                scored.append((score, candidate))
        if not scored or scored[0][0] < 70:
            return ResolvedReference(status="missing", query=query, expected_type="character", display_name=query)
        scored.sort(key=lambda item: item[0], reverse=True)
        row = scored[0][1]
    profile_id = str(getattr(row, "id", "") or getattr(row, "character_id", "") or "")
    asset_id = _character_sheet_asset_id(db, profile_id) if profile_id else ""
    display = str(getattr(row, "name", None) or query)
    stored = str(getattr(row, "slug", None) or getattr(row, "tag", None) or "")
    is_global = bool(getattr(row, "is_global", False) or getattr(row, "isGlobal", False))
    verification: VerificationStatus = "global_found" if is_global else "found"
    status = "found"
    if not asset_id:
        verification = "broken"
        status = "broken"
    return ResolvedReference(
        status=status,
        query=query,
        expected_type="character",
        asset_id=str(getattr(row, "id", "") or getattr(row, "character_id", "") or ""),
        entity_id=str(getattr(row, "id", "") or ""),
        display_name=display,
        asset_type="character",
        bindable_asset_id=asset_id,
        identity_tag=_pascal(display) or stored,
        canonical_tag=prompt_facing_tag("@", stored, display),
        verification=verification,
        is_global=is_global,
        approved_sheet=bool(asset_id),
    )


def resolve_production_reference(
    db: Session,
    *,
    project_id: str,
    query: str,
    expected_type: AssetType | None = None,
) -> ResolvedReference:
    q = (query or "").strip()
    if not q:
        return ResolvedReference(status="missing", query=query or "", expected_type=expected_type)
    if expected_type == "prop":
        hit = _resolve_prop(db, project_id, q)
        return hit
    if expected_type == "environment":
        return _resolve_environment(db, project_id, q)
    if expected_type == "character":
        return _resolve_character(db, project_id, q)

    prop = _resolve_prop(db, project_id, q)
    env = _resolve_environment(db, project_id, q)
    char = _resolve_character(db, project_id, q)
    ranked = [item for item in (prop, env, char) if item.status == "found"]
    if len(ranked) == 1:
        return ranked[0]
    if len(ranked) > 1:
        return ResolvedReference(
            status="ambiguous",
            query=q,
            display_name=q,
            notes="Matched more than one reference type.",
            candidates=[item.asset_id for item in ranked],
        )
    for item in (prop, env, char):
        if item.status == "ambiguous":
            return item
    return ResolvedReference(status="missing", query=q, display_name=q)


def resolve_project_references(
    db: Session,
    *,
    project_id: str,
    queries: list[ProductionReferenceQuery],
) -> list[ResolvedReference]:
    return [
        resolve_production_reference(
            db,
            project_id=project_id,
            query=item.query,
            expected_type=item.expected_type,
        )
        for item in queries
    ]
