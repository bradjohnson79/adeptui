"""Canonical Timeline Direct Reference Route.

Authority: checked Timeline References only.
Not authority: Co-Director, prompt prose, stale batch cast, voice auto-bind,
sheet crops, first-frame substitution, previous scenes.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ...db import Asset
from ...director_timeline_bindings import dump_prompt_name_binding
from ...scene_references.sheet_tags import PREFIX_CRS, PREFIX_ERS, PREFIX_PRS, PREFIX_VIDEO
from ...video_runtime.comfy_asset_stage import (
    ComfyAssetMissing,
    resolve_library_source,
    stage_library_asset,
)
from ..contracts import BatchBlock
from .reference_compile import resolve_binding_id
from .r2v import H3_GENERATOR_IDS, LTX25_GENERATOR_IDS, R2VSlot

RefKind = Literal["character", "environment", "prop", "motion", "audio"]

IMAGE_KINDS = {"image", "crs", "ers", "prs", ""}
AUDIO_KINDS = {"audio", "voice", "wav"}
VIDEO_KINDS = {"video", "motion"}


class DirectReferenceItem(BaseModel):
    kind: RefKind
    canonicalTag: str
    bindingId: str
    assetId: str
    assetType: str = "image"
    sourcePath: str = ""
    approved: bool = False
    identityId: str | None = None
    ordinal: int = 0
    # FM3 Front transport: original creator-checked asset when Front was packed.
    checkedAssetId: str | None = None
    identityForm: str | None = None


class DirectReferenceBlock(BaseModel):
    canonicalTag: str
    bindingId: str | None = None
    reason: str
    message: str


class DirectSocketBinding(BaseModel):
    socket: str
    canonicalTag: str
    assetId: str
    sourcePath: str
    kind: RefKind


class DirectReferencePayload(BaseModel):
    projectId: str
    sceneId: str
    batchId: str
    generatorId: str
    characters: list[DirectReferenceItem] = Field(default_factory=list)
    environments: list[DirectReferenceItem] = Field(default_factory=list)
    props: list[DirectReferenceItem] = Field(default_factory=list)
    motion: list[DirectReferenceItem] = Field(default_factory=list)
    audio: list[DirectReferenceItem] = Field(default_factory=list)
    blocked: list[DirectReferenceBlock] = Field(default_factory=list)
    sockets: list[DirectSocketBinding] = Field(default_factory=list)
    authority: Literal["direct_reference_route"] = "direct_reference_route"

    def visual_items(self) -> list[DirectReferenceItem]:
        return [*self.characters, *self.environments, *self.props]

    def all_items(self) -> list[DirectReferenceItem]:
        return [*self.visual_items(), *self.motion, *self.audio]

    def tags(self) -> list[str]:
        return [item.canonicalTag for item in self.all_items()]

    def asset_ids(self) -> list[str]:
        return [item.assetId for item in self.all_items()]

    def delivery_ok(self) -> bool:
        return not self.blocked


def _identity_kind(reference_type: str | None, media_kind: str | None) -> str:
    kind = str(reference_type or "").lower()
    media = str(media_kind or "").lower()
    if media in VIDEO_KINDS or kind in {"motion", "video"}:
        return "video"
    if kind in {"environment", "location", "place", "scene"}:
        return "environment"
    if kind in {"prop", "vehicle"}:
        return "prop"
    if media in AUDIO_KINDS or kind in {"audio", "voice"}:
        return "audio"
    if kind in {"character", "wardrobe", "creature"}:
        return "character"
    if media == "entity" and kind not in {"environment", "location"}:
        return "prop" if kind in {"prop", "vehicle", ""} else "character"
    return "character"


def _canonical_tag(alias: str | None, reference_type: str | None, media_kind: str | None) -> str:
    from ...creator_scope.identity_tag import canonical_token_only, sanitize_generator_tag

    raw = str(alias or "").strip()
    kind = _identity_kind(reference_type, media_kind)
    if kind == "video":
        token = canonical_token_only(raw) or "Reference"
        return f"{PREFIX_VIDEO}{token}"
    if kind == "audio":
        return raw or canonical_token_only(raw)
    return sanitize_generator_tag(kind, raw)


def _kind_for(reference_type: str | None, media_kind: str | None, asset_kind: str | None) -> RefKind:
    media = str(media_kind or "").lower()
    ref = str(reference_type or "").lower()
    asset = str(asset_kind or "").lower()
    if media in AUDIO_KINDS or ref in {"audio", "voice"} or asset in AUDIO_KINDS:
        return "audio"
    if media in VIDEO_KINDS or ref in {"motion", "video"} or asset in VIDEO_KINDS:
        return "motion"
    if ref in {"environment", "location", "place", "scene"}:
        return "environment"
    if ref in {"prop", "vehicle"}:
        return "prop"
    return "character"


def _checked_binding_ids(batch: BatchBlock) -> list[str]:
    """Checked Timeline References only. Never batch.references leftovers."""
    ordered: list[str] = []
    seen: set[str] = set()
    for segment in batch.promptSegments or []:
        for raw in list(segment.referenceBindingIds or []):
            token = str(raw or "").strip()
            if token and token not in seen:
                seen.add(token)
                ordered.append(token)
        for row in segment.referenceNameBindings or []:
            dumped = dump_prompt_name_binding(row)
            token = dumped.get("binding_id") or ""
            if token and token not in seen:
                seen.add(token)
                ordered.append(token)
    return ordered


def _asset_record(db: Session, asset_id: str) -> Asset | None:
    return db.get(Asset, asset_id)


def build_direct_reference_payload(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    generator_id: str,
) -> DirectReferencePayload:
    payload = DirectReferencePayload(
        projectId=project_id,
        sceneId=scene_id,
        batchId=batch.id,
        generatorId=str(generator_id or batch.generatorId or ""),
    )
    buckets: dict[RefKind, list[DirectReferenceItem]] = {
        "character": payload.characters,
        "environment": payload.environments,
        "prop": payload.props,
        "motion": payload.motion,
        "audio": payload.audio,
    }
    ordinals: dict[RefKind, int] = {key: 0 for key in buckets}

    for binding_id in _checked_binding_ids(batch):
        resolved = resolve_binding_id(db, project_id, binding_id)
        tag = _canonical_tag(
            str(resolved.get("canonicalTag") or resolved.get("displayToken") or resolved.get("alias") or "").strip(),
            resolved.get("referenceType"),
            resolved.get("mediaKind"),
        )
        asset_id = str(resolved.get("assetId") or "").strip()
        if resolved.get("broken") or not asset_id:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=tag,
                    bindingId=binding_id,
                    reason=str(resolved.get("brokenReason") or "missing_asset"),
                    message=f"{tag} could not be delivered to the selected generator reference input.",
                )
            )
            continue
        asset = _asset_record(db, asset_id)
        asset_kind = str(getattr(asset, "kind", "") or "").lower() if asset is not None else ""
        kind = _kind_for(resolved.get("referenceType"), resolved.get("mediaKind"), asset_kind)
        source_path = ""
        if asset is not None:
            try:
                source_path = str(resolve_library_source(asset))
            except ComfyAssetMissing:
                payload.blocked.append(
                    DirectReferenceBlock(
                        canonicalTag=tag,
                        bindingId=binding_id,
                        reason="missing_file",
                        message=f"{tag} could not be delivered to the selected generator reference input.",
                    )
                )
                continue
        elif not asset:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=tag,
                    bindingId=binding_id,
                    reason="missing_asset",
                    message=f"{tag} could not be delivered to the selected generator reference input.",
                )
            )
            continue
        if kind in {"character", "environment", "prop"} and asset_kind and asset_kind not in IMAGE_KINDS:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=tag,
                    bindingId=binding_id,
                    reason="wrong_media",
                    message=f"{tag} could not be delivered to the selected generator reference input.",
                )
            )
            continue
        ordinals[kind] += 1
        buckets[kind].append(
            DirectReferenceItem(
                kind=kind,
                canonicalTag=tag,
                bindingId=binding_id,
                assetId=asset_id,
                assetType=asset_kind or ("audio" if kind == "audio" else "video" if kind == "motion" else "image"),
                sourcePath=source_path,
                approved=str(resolved.get("approvalStatus") or "").lower() == "approved",
                identityId=str(resolved.get("identityId") or "") or None,
                ordinal=ordinals[kind],
            )
        )

    # Explicit batch.references start_image (not a checked binding) must still
    # reach LTX start_image socket / reference-transport after entity refs are cleared.
    if not payload.visual_items():
        for ref in batch.references or []:
            if not isinstance(ref, dict) or not ref.get("assetId"):
                continue
            if ref.get("consumed") is False:
                continue
            role = str(ref.get("role") or "").lower()
            kind = str(ref.get("kind") or "").lower()
            if role not in {"start_image", "start", "i2v_start", "opening"} and not (
                kind in {"image", "start_image"} and "start" in role
            ):
                continue
            asset_id = str(ref.get("assetId") or "").strip()
            if not asset_id:
                continue
            asset = _asset_record(db, asset_id)
            asset_kind = str(getattr(asset, "kind", "") or "").lower() if asset is not None else ""
            if asset_kind and asset_kind not in IMAGE_KINDS:
                continue
            source_path = ""
            if asset is not None:
                try:
                    source_path = str(resolve_library_source(asset))
                except ComfyAssetMissing:
                    continue
            tag = str(ref.get("label") or ref.get("promptName") or "start_image")
            if not tag.startswith(("@", "#", "%", "*")):
                tag = f"@{tag}" if tag else "@start_image"
            ordinals["character"] += 1
            payload.characters.append(
                DirectReferenceItem(
                    kind="character",
                    canonicalTag=tag,
                    bindingId=str(ref.get("bindingId") or "") or f"start_image:{asset_id}",
                    assetId=asset_id,
                    assetType=asset_kind or "image",
                    sourcePath=source_path,
                    approved=True,
                    identityId=str(ref.get("identityId") or "") or None,
                    ordinal=ordinals["character"],
                )
            )
            break

    if _h3_like(payload.generatorId):
        _apply_h3_front_transport_packing(db, project_id, payload)

    _map_sockets(payload)
    return payload


def _apply_h3_front_transport_packing(
    db: Session,
    project_id: str,
    payload: DirectReferencePayload,
) -> None:
    """FM3: pack creator-visible Front into H3 character sockets when Front exists.

    When a checked character binding is a multi-panel CRS and Character Creator
    Front / hero_identity is available, deliver the Front library asset (plain
    copy) as ref_image_N instead of CRS-alone. Does not crop CRS. Does not invent
    place refs or multi-ref companions. Timed Prompt text is untouched.
    """
    if db is None:
        return
    from .h3_front_identity import (
        is_multi_panel_crs_asset,
        resolve_h3_front_character_asset,
    )

    for item in payload.characters:
        try:
            checked_id = str(item.assetId or "").strip()
            if not checked_id:
                continue
            if not is_multi_panel_crs_asset(db, project_id, checked_id):
                # Creator already attached Front / front-comparable — keep as-is.
                if not item.identityForm:
                    item.identityForm = "creator_attached"
                continue
            hit = {
                "character_id": str(item.identityId or "").strip(),
                "name": item.canonicalTag,
                "approved_reference_asset_id": checked_id,
                "visual_reference": checked_id,
            }
            front_id, form = resolve_h3_front_character_asset(db, project_id, hit)
            if not front_id or form != "front" or front_id == checked_id:
                item.identityForm = "crs_sheet_only"
                continue
            front_asset = _asset_record(db, front_id)
            if front_asset is None:
                item.identityForm = "crs_sheet_only"
                continue
            try:
                front_path = str(resolve_library_source(front_asset))
            except ComfyAssetMissing:
                item.identityForm = "crs_sheet_only"
                continue
            item.checkedAssetId = checked_id
            item.assetId = front_id
            item.sourcePath = front_path
            item.assetType = str(getattr(front_asset, "kind", "") or "image") or "image"
            item.identityForm = "front"
        except Exception:
            # Fail-open to checked asset — never block Direct Reference delivery.
            continue


def _h3_like(generator_id: str) -> bool:
    token = str(generator_id or "").strip().lower()
    return token in H3_GENERATOR_IDS or token.startswith("minimax")


def _ltx25_like(generator_id: str) -> bool:
    token = str(generator_id or "").strip().lower()
    return token in LTX25_GENERATOR_IDS or token.startswith("ltx-2.5") or token.startswith("ltx_2_5")


def _map_sockets(payload: DirectReferencePayload) -> None:
    payload.sockets = []
    generator_id = payload.generatorId
    if _h3_like(generator_id):
        visuals = payload.visual_items()
        extras = visuals[9:]
        visuals = visuals[:9]
        for item in extras:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=item.canonicalTag,
                    bindingId=item.bindingId,
                    reason="over_limit",
                    message=f"{item.canonicalTag} could not be delivered to the selected generator reference input.",
                )
            )
        for index, item in enumerate(visuals):
            payload.sockets.append(
                DirectSocketBinding(
                    socket=f"ref_image_{index}",
                    canonicalTag=item.canonicalTag,
                    assetId=item.assetId,
                    sourcePath=item.sourcePath,
                    kind=item.kind,
                )
            )
        for item in payload.motion:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=item.canonicalTag,
                    bindingId=item.bindingId,
                    reason="unsupported_motion_socket",
                    message=f"{item.canonicalTag} could not be delivered to the selected generator reference input.",
                )
            )
        for index, item in enumerate(payload.audio):
            payload.sockets.append(
                DirectSocketBinding(
                    socket=f"ref_audio_{index}",
                    canonicalTag=item.canonicalTag,
                    assetId=item.assetId,
                    sourcePath=item.sourcePath,
                    kind="audio",
                )
            )
        return

    if _ltx25_like(generator_id) or str(generator_id or "").startswith("ltx"):
        visuals = payload.visual_items()
        if not visuals:
            return
        first, *rest = visuals
        payload.sockets.append(
            DirectSocketBinding(
                socket="start_image",
                canonicalTag=first.canonicalTag,
                assetId=first.assetId,
                sourcePath=first.sourcePath,
                kind=first.kind,
            )
        )
        for item in rest:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=item.canonicalTag,
                    bindingId=item.bindingId,
                    reason="unsupported_extra_visual",
                    message=f"{item.canonicalTag} could not be delivered to the selected generator reference input.",
                )
            )
        for item in payload.motion:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=item.canonicalTag,
                    bindingId=item.bindingId,
                    reason="unsupported_motion_socket",
                    message=f"{item.canonicalTag} could not be delivered to the selected generator reference input.",
                )
            )
        for item in payload.audio:
            payload.blocked.append(
                DirectReferenceBlock(
                    canonicalTag=item.canonicalTag,
                    bindingId=item.bindingId,
                    reason="unsupported_audio_socket",
                    message=f"{item.canonicalTag} could not be delivered to the selected generator reference input.",
                )
            )
        return

    for item in payload.all_items():
        payload.blocked.append(
            DirectReferenceBlock(
                canonicalTag=item.canonicalTag,
                bindingId=item.bindingId,
                reason="unsupported_generator",
                message=f"{item.canonicalTag} could not be delivered to the selected generator reference input.",
            )
        )


def payload_to_r2v_slots(payload: DirectReferencePayload) -> list[R2VSlot]:
    slots: list[R2VSlot] = []
    picture = 0
    audio = 0
    role_map = {
        "character": "character",
        "environment": "place",
        "prop": "prop",
        "motion": "video",
        "audio": "audio",
    }
    delivered = {bind.assetId for bind in payload.sockets}
    for item in payload.all_items():
        if item.assetId not in delivered:
            continue
        role = role_map[item.kind]
        picture_index = None
        audio_index = None
        if item.kind in {"character", "environment", "prop"}:
            picture += 1
            picture_index = picture
        elif item.kind == "audio":
            audio += 1
            audio_index = audio
        slots.append(
            R2VSlot(
                role=role,  # type: ignore[arg-type]
                assetId=item.assetId,
                label=item.canonicalTag,
                identityId=item.identityId,
                pictureIndex=picture_index,
                audioIndex=audio_index,
                aliases=[item.canonicalTag.lstrip("@#%*"), item.canonicalTag],
            )
        )
    return slots


def attach_direct_reference_payload(
    request: Any,
    payload: DirectReferencePayload,
) -> None:
    request.providerOptions = dict(request.providerOptions or {})
    request.providerOptions["directReferences"] = payload.model_dump()
    visuals = [bind for bind in payload.sockets if bind.socket in {"start_image"} or bind.socket.startswith("ref_image_")]
    if visuals and not str(getattr(request, "startImageAssetId", "") or "").strip():
        if any(bind.socket == "start_image" for bind in visuals):
            request.startImageAssetId = next(bind.assetId for bind in visuals if bind.socket == "start_image")


def delivery_error(payload: DirectReferencePayload) -> dict[str, Any] | None:
    if payload.delivery_ok():
        return None
    first = payload.blocked[0]
    return {
        "ok": False,
        "error": "REFERENCE_DELIVERY_FAILED",
        "message": first.message,
        "blocked": [item.model_dump() for item in payload.blocked],
        "directReferences": payload.model_dump(),
        "mock": False,
    }


def inspect_direct_reference(
    db: Session,
    *,
    project_id: str,
    scene_id: str,
    batch: BatchBlock,
    generator_id: str | None = None,
) -> dict[str, Any]:
    payload = build_direct_reference_payload(
        db,
        project_id=project_id,
        scene_id=scene_id,
        batch=batch,
        generator_id=generator_id or batch.generatorId or "",
    )
    timeline = [
        {
            "canonicalTag": item.canonicalTag,
            "assetId": item.assetId,
            "type": item.kind,
            "status": "approved" if item.approved else "selected",
            "bindingId": item.bindingId,
            "sourcePath": item.sourcePath,
        }
        for item in payload.all_items()
    ]
    return {
        "ok": payload.delivery_ok(),
        "authority": "direct_reference_route",
        "timelineReferences": timeline,
        "directTransport": {
            "count": len(payload.all_items()),
            "characters": [item.model_dump() for item in payload.characters],
            "environments": [item.model_dump() for item in payload.environments],
            "props": [item.model_dump() for item in payload.props],
            "motion": [item.model_dump() for item in payload.motion],
            "audio": [item.model_dump() for item in payload.audio],
        },
        "comfy": {bind.socket: {"canonicalTag": bind.canonicalTag, "assetId": bind.assetId, "sourcePath": bind.sourcePath} for bind in payload.sockets},
        "blocked": [item.model_dump() for item in payload.blocked],
        "payload": payload.model_dump(),
    }


def stage_direct_reference_file(asset: Any) -> dict[str, Any]:
    """Copy the selected Library file. Never crop or substitute."""
    staged = stage_library_asset(asset)
    return {
        "comfyName": staged.comfy_name,
        "sourcePath": staged.source_path,
        "stagedPath": staged.staged_path,
        "bytes": staged.bytes,
        "identityAuthority": "reference_image",
        "uploadedTensor": "library_file",
        "transform": "copy_only",
    }


def payload_from_request(request: Any) -> DirectReferencePayload | None:
    raw = ((getattr(request, "providerOptions", None) or {}).get("directReferences"))
    if not isinstance(raw, dict) or raw.get("authority") != "direct_reference_route":
        return None
    return DirectReferencePayload.model_validate(raw)


def has_direct_reference_authority(request: Any = None, params: dict[str, Any] | None = None) -> bool:
    if request is not None and payload_from_request(request) is not None:
        return True
    raw = (params or {}).get("directReferences")
    return isinstance(raw, dict) and raw.get("authority") == "direct_reference_route"
