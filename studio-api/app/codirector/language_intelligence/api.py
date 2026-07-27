"""Admin / language intelligence HTTP API."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import get_db
from . import audio_phrases, dialogue, glossary, intent, translate
from .registry import LOCALE_REGISTRY, is_supported_locale, resolve_locale

router = APIRouter(prefix="/language-intelligence", tags=["language-intelligence"])


class NormalizeBody(BaseModel):
    text: str
    sourceLanguage: Optional[str] = None
    protectedTerms: list[str] = Field(default_factory=list)
    mustInclude: list[str] = Field(default_factory=list)
    mustAvoid: list[str] = Field(default_factory=list)


class TranslateBody(BaseModel):
    text: str
    sourceLanguage: str = "en"
    targetLanguage: str
    glossary: list[dict[str, Any]] = Field(default_factory=list)
    locked: bool = False


class GlossaryUpsertBody(BaseModel):
    canonicalTerm: str
    sourceLanguage: str = "en"
    translations: dict[str, Optional[str]] = Field(default_factory=dict)
    translationPolicy: str = "PRESERVE"
    caseSensitive: bool = True
    notes: str = ""
    termId: Optional[str] = None


class AudioNormalizeBody(BaseModel):
    text: str


class DialogueBody(BaseModel):
    sceneId: str
    speakerId: str
    originalLanguage: str = "en"
    originalText: str
    start: float = 0.0
    end: float = 0.0


class DialogueVariantBody(BaseModel):
    dialogue: dict[str, Any]
    locale: str
    text: str
    status: str = "draft"


@router.get("/locales")
def list_locales() -> dict[str, Any]:
    return {"locales": LOCALE_REGISTRY, "default": "en"}


@router.post("/normalize-intent")
def normalize_intent(body: NormalizeBody) -> dict[str, Any]:
    result = intent.normalize_creative_intent(
        body.text,
        source_language=body.sourceLanguage,
        protected_terms=body.protectedTerms,
        must_include=body.mustInclude,
        must_avoid=body.mustAvoid,
    )
    return result.model_dump()


@router.post("/translate")
def translate_endpoint(body: TranslateBody) -> dict[str, Any]:
    if not is_supported_locale(resolve_locale(body.targetLanguage)):
        raise HTTPException(status_code=400, detail={"code": "UNSUPPORTED_LOCALE"})
    return translate.translate_text(
        body.text,
        source_language=body.sourceLanguage,
        target_language=body.targetLanguage,
        glossary=body.glossary,
        locked=body.locked,
    )


@router.post("/normalize-audio")
def normalize_audio(body: AudioNormalizeBody) -> dict[str, Any]:
    audio = audio_phrases.normalize_audio_from_multilingual_text(body.text)
    return audio.model_dump()


@router.get("/projects/{project_id}/glossary")
def get_glossary(project_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    return {"projectId": project_id, "terms": glossary.list_glossary(db, project_id)}


@router.post("/projects/{project_id}/glossary")
def put_glossary(
    project_id: str, body: GlossaryUpsertBody, db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        entry = glossary.upsert_glossary_term(
            db,
            project_id,
            canonical_term=body.canonicalTerm,
            source_language=body.sourceLanguage,
            translations=body.translations,
            translation_policy=body.translationPolicy,  # type: ignore[arg-type]
            case_sensitive=body.caseSensitive,
            notes=body.notes,
            term_id=body.termId,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail={"code": str(exc)}) from exc
    return entry


@router.post("/dialogue")
def create_dialogue(body: DialogueBody) -> dict[str, Any]:
    return dialogue.make_dialogue(
        scene_id=body.sceneId,
        speaker_id=body.speakerId,
        original_language=body.originalLanguage,
        original_text=body.originalText,
        start=body.start,
        end=body.end,
    )


@router.post("/dialogue/variant")
def dialogue_variant(body: DialogueVariantBody) -> dict[str, Any]:
    return dialogue.add_variant(
        body.dialogue, locale=body.locale, text=body.text, status=body.status
    )


@router.get("/platform-protected-terms")
def platform_terms() -> dict[str, Any]:
    return {"terms": glossary.PLATFORM_PROTECTED_TERMS}
