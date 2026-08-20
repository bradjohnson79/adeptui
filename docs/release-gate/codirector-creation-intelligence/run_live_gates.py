"""Live GPU gates for Revision B on Schnick Coffee. Never POST /api/projects."""

from __future__ import annotations

import json
import sys
import time
import traceback
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "studio-api"))

API = "http://127.0.0.1:8758"
PROJECT = "2347bf46-3762-4763-86c5-4a6032522278"
MAP_ID = "6bc36d92-d21a-4c2f-b85f-71d1f6aa9081"
SCENE_ID = "e4550745-f0ef-44c8-99a5-ef9e20bd47d2"
KORRI = "c49371ed-ba6b-4c16-ba98-a8b28b72118b"
ANADRIYA = "284411ea-596f-4b8d-9a0e-8da81a67edbf"
NL = (
    "Put Korri behind the service counter beside the espresso machine "
    "while Anadriya stands on the customer side facing Korri."
)
EVIDENCE = Path(__file__).resolve().parent / "evidence"
EVIDENCE.mkdir(parents=True, exist_ok=True)


def log(msg: str) -> None:
    print(msg, flush=True)


def write(name: str, payload: object) -> Path:
    path = EVIDENCE / name
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def req(method: str, path: str, payload: dict | None = None, timeout: int = 90, retries: int = 3) -> tuple[int, dict | list | str]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"} if payload is not None else {}
    last: tuple[int, dict | list | str] = (0, {"detail": "no attempt"})
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(f"{API}{path}", data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as res:
                raw = res.read().decode("utf-8") or "{}"
                try:
                    return res.status, json.loads(raw)
                except json.JSONDecodeError:
                    return res.status, raw
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8") if exc.fp else ""
            try:
                parsed = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                parsed = {"detail": raw}
            return exc.code, parsed
        except Exception as exc:
            last = (0, {"detail": str(exc), "attempt": attempt})
            log(f"  retry {attempt}/{retries} {method} {path}: {exc}")
            time.sleep(min(8, attempt * 2))
    return last


def download_asset(asset_id: str, dest: Path) -> bool:
    for url in (
        f"{API}/api/assets/{asset_id}/file",
        f"{API}/api/projects/{PROJECT}/assets/{asset_id}/file",
    ):
        try:
            urllib.request.urlretrieve(url, dest)
            if dest.exists() and dest.stat().st_size > 32:
                return True
        except Exception:
            continue
    return False


def snapshot_slots(document: dict) -> dict:
    return {
        "characters": len(document.get("characters") or []),
        "props": len(document.get("props") or []),
        "cameras": len(document.get("cameras") or []),
        "zones": document.get("zones"),
        "characterIds": [
            item.get("characterId") or item.get("character_id")
            for item in (document.get("characters") or [])
            if isinstance(item, dict)
        ],
    }


def occupied_indexes(document: dict, kind: str) -> set[int]:
    key = {"character": "characters", "prop": "props", "camera": "cameras"}[kind]
    found: set[int] = set()
    for index, item in enumerate(document.get(key) or []):
        if not isinstance(item, dict):
            continue
        slot = item.get("slotIndex")
        if slot is None:
            slot = item.get("slot")
        if slot is None:
            slot = index
        try:
            found.add(int(slot))
        except (TypeError, ValueError):
            found.add(index)
    return found


def extract_spatial_facts(blob: object) -> dict:
    text = json.dumps(blob, default=str).lower()
    return {
        "behind": "behind" in text,
        "beside": "beside" in text or "besides" in text,
        "facing": "facing" in text,
        "customer": "customer" in text,
        "employee": "employee" in text or "service counter" in text,
        "spatial_language": "spatial_language" in text or "spatial relation" in text or "zone:" in text,
        "korri": "korri" in text,
        "anadriya": "anadriya" in text,
    }


def poll_job(job_id: str, deadline: float) -> dict:
    last: dict = {}
    while time.time() < deadline:
        status, body = req("GET", f"/api/jobs/{job_id}", timeout=45)
        if isinstance(body, dict):
            last = body
            label = str(body.get("status") or "").lower()
            log(f"  job {job_id[:8]} {label} {body.get('progress')}")
            if label in {"done", "complete", "failed", "error", "cancelled"}:
                return last
        time.sleep(8)
    return last


def poll_shot(shot_id: str, deadline: float, want_kind: str = "") -> tuple[str, dict]:
    latest: dict = {}
    asset_id = ""
    while time.time() < deadline:
        _, latest = req("GET", f"/api/scene-creator/projects/{PROJECT}/shots/{shot_id}", timeout=45)
        shot_row = latest.get("shot") if isinstance(latest, dict) else {}
        if not isinstance(shot_row, dict):
            shot_row = latest if isinstance(latest, dict) else {}
        for cand in shot_row.get("candidates") or []:
            if not isinstance(cand, dict):
                continue
            if want_kind and str(cand.get("kind") or "") not in {"", want_kind}:
                if cand.get("kind") != want_kind:
                    continue
            aid = str(cand.get("asset_id") or cand.get("assetId") or "")
            st = str(cand.get("status") or "").lower()
            if aid and st in {"done", "ready", "approved", "complete"}:
                return aid, latest
            if aid and st not in {"failed", "error", "cancelled"}:
                asset_id = asset_id or aid
        if asset_id:
            return asset_id, latest
        log(f"  waiting shot {shot_id[:8]}")
        time.sleep(8)
    return asset_id, latest


def poll_crs(char_id: str, deadline: float) -> tuple[str, dict]:
    last: dict = {}
    sheet_asset = ""
    while time.time() < deadline:
        req("POST", f"/api/projects/{PROJECT}/characters/{char_id}/visual-sheet/advance", {}, timeout=60)
        _, last = req("GET", f"/api/projects/{PROJECT}/characters/{char_id}/visual-sheet", timeout=60)
        row = last if isinstance(last, dict) else {}
        pack = row.get("pack") if isinstance(row.get("pack"), dict) else row
        status_label = str(pack.get("status") or "")
        roles = pack.get("roleAssets") or {}
        if isinstance(roles, dict):
            sheet_asset = str(
                roles.get("hero_identity")
                or roles.get("sheet")
                or next((v for v in roles.values() if v), "")
                or ""
            )
        for cand in pack.get("candidates") or []:
            if isinstance(cand, dict):
                sheet_asset = sheet_asset or str(
                    cand.get("sheetAssetId") or cand.get("assetId") or cand.get("heroAssetId") or ""
                )
        log(f"  CRS {status_label} asset={sheet_asset[:8] if sheet_asset else '-'}")
        if status_label in {"READY_FOR_OWNER", "READY", "FAILED", "OWNER_APPROVED"} and (
            sheet_asset or status_label == "FAILED"
        ):
            return sheet_asset, last
        time.sleep(8)
    return sheet_asset, last


def create_and_generate_shot(
    sheet_id: str,
    intent: str,
    character_ids: list[str],
    dest_name: str,
    family: str,
) -> dict:
    result: dict = {"sheetId": sheet_id, "intent": intent, "family": family, "characterIds": character_ids}
    st, shot_body = req(
        "POST",
        f"/api/scene-creator/projects/{PROJECT}/shots",
        {
            "sheet_id": sheet_id,
            "scene_id": SCENE_ID,
            "intent": intent,
            "character_ids": character_ids,
            "generator": {"local_family": family, "local_enabled": True},
        },
        timeout=90,
    )
    shot = shot_body.get("shot") if isinstance(shot_body, dict) else {}
    if not isinstance(shot, dict):
        shot = shot_body if isinstance(shot_body, dict) else {}
    shot_id = str(shot.get("id") or "")
    result["createStatus"] = st
    result["shotId"] = shot_id
    result["createBody"] = shot_body
    if not shot_id:
        return result
    st, gen = req(
        "POST",
        f"/api/scene-creator/projects/{PROJECT}/shots/{shot_id}/generate",
        {
            "local_enabled": True,
            "api_enabled": False,
            "local_family": family,
            "candidate_count": 1,
        },
        timeout=180,
    )
    result["generateStatus"] = st
    result["generateBody"] = gen
    gen_shot = gen.get("shot") if isinstance(gen, dict) else {}
    job_ids = []
    for cand in (gen_shot or {}).get("candidates") or []:
        if isinstance(cand, dict) and cand.get("job_id"):
            job_ids.append(str(cand["job_id"]))
    result["jobIds"] = job_ids
    facts = {}
    for job_id in job_ids:
        _, job = req("GET", f"/api/jobs/{job_id}", timeout=45)
        result[f"job_{job_id[:8]}"] = job
        facts.update(extract_spatial_facts(job))
        params = {}
        if isinstance(job, dict) and job.get("params_json"):
            try:
                params = json.loads(str(job["params_json"]))
            except json.JSONDecodeError:
                params = {}
        ctx = params.get("creativeContext") or params.get("creative_context") or {}
        result["spatial_language"] = ctx.get("spatial_language") or result.get("spatial_language")
        result["compiledPrompt"] = params.get("prompt") or ctx.get("prompt")
        facts.update(extract_spatial_facts({"ctx": ctx, "prompt": params.get("prompt")}))
    facts.update(extract_spatial_facts(result.get("spatial_language")))
    result["compileFacts"] = facts
    asset_id, latest = poll_shot(shot_id, time.time() + 1200)
    result["stillAssetId"] = asset_id
    result["stillPoll"] = latest
    if asset_id:
        download_asset(asset_id, EVIDENCE / dest_name)
        result["downloaded"] = (EVIDENCE / dest_name).exists()
    return result


def upload_mask(mask_path: Path) -> dict:
    import uuid

    boundary = uuid.uuid4().hex
    file_bytes = mask_path.read_bytes()
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="edit-mask.png"\r\n'
        "Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + file_bytes + (
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="tag"\r\n\r\n'
        "inpaint_mask"
        f"\r\n--{boundary}\r\n"
        'Content-Disposition: form-data; name="kind"\r\n\r\n'
        "image"
        f"\r\n--{boundary}--\r\n"
    ).encode("utf-8")
    upload = urllib.request.Request(
        f"{API}/api/projects/{PROJECT}/assets",
        data=body,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    try:
        with urllib.request.urlopen(upload, timeout=90) as res:
            return json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8") if exc.fp else ""
        try:
            return {"error": raw, "status": exc.code}
        except Exception:
            return {"error": raw, "status": exc.code}
    except Exception as exc:
        return {"error": str(exc)}


def main() -> int:
    report: dict = {
        "projectId": PROJECT,
        "mapId": MAP_ID,
        "topology": "8760→8758",
        "startedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gates": {},
    }
    write("live-gates.json", report)

    log("== health / perception ==")
    status, health = req("GET", "/api/health")
    report["health"] = {"status": status, "body": health}
    write("live-gates.json", report)
    if status != 200:
        log("NO-GO — health failed")
        return 1
    status, cap = req("GET", "/api/perception/capability")
    report["capability"] = cap
    write("live-gates.json", report)
    if status != 200:
        log("NO-GO — perception missing on 8758")
        return 1
    log(f"health ok revision={(health or {}).get('apiRevision')} started={(health or {}).get('apiStartedAt')}")

    log("== Schnick review (no slot write) ==")
    status, before = req("GET", f"/api/spatial-map/projects/{PROJECT}/maps/{MAP_ID}")
    document = (before or {}).get("document") if isinstance(before, dict) else {}
    before_slots = snapshot_slots(document if isinstance(document, dict) else {})
    report["mapBefore"] = {"status": status, **before_slots}
    status, reviewed = req(
        "POST",
        f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/review",
        timeout=120,
    )
    draft = (reviewed or {}).get("draft") if isinstance(reviewed, dict) else {}
    _, after_review = req("GET", f"/api/spatial-map/projects/{PROJECT}/maps/{MAP_ID}")
    after_doc = (after_review or {}).get("document") if isinstance(after_review, dict) else {}
    after_slots = snapshot_slots(after_doc if isinstance(after_doc, dict) else {})
    report["review"] = {
        "status": status,
        "reviewLabel": draft.get("reviewLabel"),
        "geometryStatus": draft.get("geometryStatus"),
        "fills": [
            {"id": item.get("id"), "kind": item.get("kind"), "label": item.get("label"), "slotIndex": item.get("slotIndex")}
            for item in (draft.get("proposedFills") or [])
        ],
        "slotsUnchanged": before_slots == {**after_slots, "characterIds": after_slots.get("characterIds")},
        "before": before_slots,
        "after": after_slots,
        "zones": after_slots.get("zones"),
    }
    report["review"]["slotsUnchanged"] = (
        before_slots["characters"] == after_slots["characters"]
        and before_slots["props"] == after_slots["props"]
        and before_slots["cameras"] == after_slots["cameras"]
        and after_slots.get("zones") is None
    )
    write("live-gates.json", report)
    log(f"review {status} slotsUnchanged={report['review']['slotsUnchanged']} fills={len(report['review']['fills'])}")

    fills = draft.get("proposedFills") or []
    correct_target = next((item for item in fills if item.get("kind") == "prop"), fills[0] if fills else None)
    if correct_target:
        key = f"fill:{(correct_target.get('label') or correct_target.get('id') or '').lower()}"
        req(
            "POST",
            f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/corrections",
            {"corrections": [{"factKey": key, "action": "rename", "value": {"label": "Service counter side"}}]},
        )
        req("POST", f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/review", timeout=120)
        _, persisted = req("GET", f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/draft")
        persisted_draft = (persisted or {}).get("draft") if isinstance(persisted, dict) else {}
        blob = json.dumps(persisted_draft).lower()
        report["correction"] = {
            "factKey": key,
            "survivedReview": "service counter side" in blob or key.split(":")[-1] in blob,
            "userCorrections": persisted_draft.get("userCorrections") if isinstance(persisted_draft, dict) else [],
        }
        write("live-gates.json", report)
        log(f"correction survived={report['correction']['survivedReview']}")

    _, latest_draft_body = req("GET", f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/draft")
    latest_draft = (latest_draft_body or {}).get("draft") if isinstance(latest_draft_body, dict) else {}
    latest_fills = (latest_draft or {}).get("proposedFills") or fills
    accept_items = []
    occupied = {
        "character": occupied_indexes(after_doc if isinstance(after_doc, dict) else {}, "character"),
        "prop": occupied_indexes(after_doc if isinstance(after_doc, dict) else {}, "prop"),
        "camera": occupied_indexes(after_doc if isinstance(after_doc, dict) else {}, "camera"),
    }
    for item in latest_fills:
        kind = str(item.get("kind") or "")
        slot = item.get("slotIndex")
        if kind in occupied and slot not in occupied[kind]:
            accept_items = [{"fillId": item["id"], "label": item.get("label") or ""}]
            break
    if not accept_items and latest_fills:
        accept_items = [{"fillId": latest_fills[0]["id"], "label": latest_fills[0].get("label") or ""}]
    status, accepted = req(
        "POST",
        f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/accept",
        {"items": accept_items},
    )
    _, after_accept = req("GET", f"/api/spatial-map/projects/{PROJECT}/maps/{MAP_ID}")
    accept_doc = after_accept.get("document") if isinstance(after_accept, dict) else {}
    report["accept"] = {
        "status": status,
        "items": accept_items,
        "body": accepted,
        **snapshot_slots(accept_doc if isinstance(accept_doc, dict) else {}),
    }
    write("live-gates.json", report)
    log(f"accept {status} {json.dumps(accepted, default=str)[:240]}")

    status, parsed = req(
        "POST",
        f"/api/scene-creator/projects/{PROJECT}/parse-shots",
        {"raw_text": NL, "spatial_map_id": MAP_ID},
    )
    report["nlParse"] = {"status": status, "facts": extract_spatial_facts(parsed), "body": parsed}
    write("live-gates.json", report)
    log(f"NL parse facts={report['nlParse']['facts']}")

    log("== disposable character CRS ==")
    name = f"RevB Live {int(time.time())}"
    status, created = req(
        "POST",
        f"/api/projects/{PROJECT}/characters",
        {
            "name": name,
            "description": "Disposable Revision B live-gate character. Not Korri.",
            "visual_description": "A young barista with short copper hair, green apron, and a warm smile.",
            "visual_style": "realistic_anime",
            "role": "Disposable live gate",
        },
    )
    char_id = str((created or {}).get("id") or "") if isinstance(created, dict) else ""
    report["character"] = {"createStatus": status, "id": char_id, "name": name, "body": created}
    write("live-gates.json", report)
    if char_id == KORRI:
        log("NO-GO — refused to overwrite Korri")
        return 1
    if status >= 400 or not char_id:
        log("NO-GO — disposable character create failed")
        return 1
    log(f"created {name} {char_id}")

    status, pack = req(
        "POST",
        f"/api/projects/{PROJECT}/characters/{char_id}/visual-sheet/generate",
        {
            "includeDetails": False,
            "includePerformance": False,
            "visualStyle": "realistic_anime",
            "candidateCount": 1,
            "generationMode": "PROFILE_GUIDED",
            "generatorSources": {
                "local": [{"family": "qwen2512", "enabled": True, "batchCount": 1}],
                "api": None,
                "stage2Enabled": False,
            },
        },
        timeout=180,
    )
    report["crsStart"] = {"status": status, "pack": pack}
    write("live-gates.json", report)
    log(f"CRS start {status}")
    sheet_asset, crs_poll = poll_crs(char_id, time.time() + 1200)
    report["crsPoll"] = crs_poll
    report["crsAssetId"] = sheet_asset
    write("live-gates.json", report)
    if sheet_asset:
        download_asset(sheet_asset, EVIDENCE / "character-crs.png")
        _, gates = req("GET", f"/api/projects/{PROJECT}/characters/{char_id}/visual-gates")
        report["visualGates"] = gates
        direction_id = ""
        if isinstance(gates, dict):
            concept = ((gates.get("gates") or {}).get("concept") or {})
            directions = concept.get("directions") or []
            if directions and isinstance(directions[0], dict):
                direction_id = str(directions[0].get("id") or "")
            direction_id = direction_id or str(concept.get("selectedDirectionId") or "")
        if direction_id:
            st, selected = req(
                "POST",
                f"/api/projects/{PROJECT}/characters/{char_id}/visual-gates/concept/select",
                {"directionId": direction_id, "approvedBy": "revision-b-live-closure"},
            )
            report["conceptSelect"] = {"status": st, "body": selected, "directionId": direction_id}
        st, approved = req(
            "POST",
            f"/api/projects/{PROJECT}/characters/{char_id}/visual-sheet/owner-approve",
            {"approvedBy": "revision-b-live-closure"},
        )
        report["crsApprove"] = {"status": st, "body": approved, "assetId": sheet_asset}
        _, reloaded = req("GET", f"/api/projects/{PROJECT}/characters/{char_id}")
        report["characterReload"] = reloaded
        tag = ""
        if isinstance(reloaded, dict):
            tag = str(reloaded.get("tag") or reloaded.get("slug") or name)
        report["characterTag"] = tag
        write("live-gates.json", report)
        log(f"CRS approve {st} tag={tag}")
    else:
        report["crsApprove"] = {"status": "FAILED", "reason": "no CRS asset"}
        write("live-gates.json", report)
        log("CRS produced no asset")

    log("== workspace / stills ==")
    status, workspace = req("GET", f"/api/scene-creator/projects/{PROJECT}/workspace")
    sheet_id = ""
    if isinstance(workspace, dict):
        sheet_id = str(workspace.get("selected_sheet_id") or workspace.get("selectedSheetId") or "")
        resolved = workspace.get("resolved") if isinstance(workspace.get("resolved"), dict) else {}
        sheet_id = sheet_id or str(resolved.get("sheet_id") or "")
        sheets = workspace.get("sheets") or workspace.get("sheet_summaries") or workspace.get("spatialProfiles") or []
        if not sheet_id and sheets:
            first = sheets[0] if isinstance(sheets[0], dict) else {}
            sheet_id = str(first.get("sheetId") or first.get("id") or "")
    if not sheet_id:
        _, profiles = req("GET", f"/api/scene-creator/projects/{PROJECT}/spatial-profiles")
        if isinstance(profiles, dict):
            rows = profiles.get("profiles") or []
            if rows and isinstance(rows[0], dict):
                sheet_id = str(rows[0].get("sheetId") or "")
        report["spatialProfiles"] = profiles
    report["workspace"] = {"status": status, "sheetId": sheet_id}
    write("live-gates.json", report)
    log(f"sheet_id={sheet_id}")

    if sheet_id and char_id and sheet_asset:
        at_name = f"@{name}"
        report["characterStill"] = create_and_generate_shot(
            sheet_id,
            f"{at_name} behind the service counter beside the espresso machine, customer side empty, Schnick Coffee shop recognizable",
            [char_id],
            "character-still.png",
            "zimage",
        )
        write("live-gates.json", report)
        log(f"character still={report['characterStill'].get('stillAssetId')}")

    if sheet_id:
        report["schnickStill"] = create_and_generate_shot(
            sheet_id,
            NL,
            [KORRI, ANADRIYA],
            "schnick-still.png",
            "zimage",
        )
        write("live-gates.json", report)
        log(f"schnick still={report['schnickStill'].get('stillAssetId')} facts={report['schnickStill'].get('compileFacts')}")
        still_id = str(report["schnickStill"].get("stillAssetId") or "")
        atlas_id = ""
        _, map_now = req("GET", f"/api/spatial-map/projects/{PROJECT}/maps/{MAP_ID}")
        document_now = (map_now or {}).get("document") if isinstance(map_now, dict) else {}
        if isinstance(document_now, dict):
            atlas_id = str(
                document_now.get("originalEnvironmentReferenceAssetId")
                or document_now.get("backgroundAssetId")
                or ""
            )
        if still_id:
            st, world = req(
                "POST",
                "/api/codirector/world-intelligence/evaluate",
                {
                    "projectId": PROJECT,
                    "assetId": still_id,
                    "referenceAssetIds": [atlas_id] if atlas_id else [],
                    "sceneId": SCENE_ID,
                },
                timeout=300,
            )
            report["worldEvaluate"] = {"status": st, "body": world}
            write("live-gates.json", report)
            log(f"world evaluate {st} text={(world or {}).get('advisoryText') if isinstance(world, dict) else world}")

    log("== zimage.inpaint leak ==")
    source_still = str((report.get("schnickStill") or {}).get("stillAssetId") or "")
    source_shot = str((report.get("schnickStill") or {}).get("shotId") or "")
    source_path = EVIDENCE / "schnick-still.png"
    if not source_still:
        source_still = str((report.get("characterStill") or {}).get("stillAssetId") or "")
        source_shot = str((report.get("characterStill") or {}).get("shotId") or "")
        source_path = EVIDENCE / "character-still.png"
    if source_still and source_shot and source_path.exists():
        from PIL import Image, ImageDraw

        mask_path = EVIDENCE / "edit-mask.png"
        with Image.open(source_path) as im:
            mask = Image.new("L", im.size, 0)
            draw = ImageDraw.Draw(mask)
            w, h = im.size
            box = (int(w * 0.45), int(h * 0.40), int(w * 0.92), int(h * 0.88))
            draw.ellipse(box, fill=255)
            mask.save(mask_path)
        uploaded = upload_mask(mask_path)
        report["maskUpload"] = uploaded
        mask_id = str(uploaded.get("id") or "")
        write("live-gates.json", report)
        if mask_id:
            st, edited = req(
                "POST",
                f"/api/scene-creator/projects/{PROJECT}/shots/{source_shot}/region-edit",
                {
                    "operation": "add",
                    "prompt": "add a red coffee mug on the counter",
                    "maskAssetId": mask_id,
                    "sourceAssetId": source_still,
                    "stage": "preview",
                    "local_family": "zimage",
                    "local_enabled": True,
                    "api_enabled": False,
                },
                timeout=180,
            )
            report["editStart"] = {"status": st, "body": edited}
            write("live-gates.json", report)
            edit_asset, latest = poll_shot(source_shot, time.time() + 1200, want_kind="region_edit")
            if not edit_asset:
                shot_row = latest.get("shot") if isinstance(latest, dict) else {}
                for cand in (shot_row or {}).get("candidates") or []:
                    if isinstance(cand, dict) and (cand.get("kind") == "region_edit" or cand.get("edit_operation")):
                        edit_asset = str(cand.get("asset_id") or cand.get("assetId") or "")
            report["editAssetId"] = edit_asset
            report["editPoll"] = latest
            if edit_asset:
                download_asset(edit_asset, EVIDENCE / "edit-inpaint.png")
                from app.codirector.perception.inpaint_leak import LEAK_THRESHOLD, unmasked_mean_delta

                try:
                    delta = unmasked_mean_delta(
                        EVIDENCE / "edit-inpaint.png",
                        source_path,
                        mask_path,
                    )
                except Exception as exc:
                    delta = None
                    report["leakError"] = str(exc)
                report["leak"] = {"unmasked_mean_delta": delta, "threshold": LEAK_THRESHOLD}
            write("live-gates.json", report)
            log(f"edit asset={edit_asset} leak={report.get('leak')}")

    _, draft_reload = req("GET", f"/api/perception/projects/{PROJECT}/maps/{MAP_ID}/draft")
    report["draftReload"] = draft_reload
    report["finishedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    write("live-gates.json", report)

    crs_ok = bool((report.get("crsApprove") or {}).get("assetId")) and int((report.get("crsApprove") or {}).get("status") or 500) < 400
    char_still_ok = bool((report.get("characterStill") or {}).get("stillAssetId"))
    schnick_ok = bool((report.get("schnickStill") or {}).get("stillAssetId"))
    leak = (report.get("leak") or {}).get("unmasked_mean_delta")
    leak_ok = isinstance(leak, (int, float)) and leak <= 2.0
    review_ok = bool((report.get("review") or {}).get("slotsUnchanged"))
    facts = (report.get("schnickStill") or {}).get("compileFacts") or {}
    facts_ok = bool(facts.get("behind") and facts.get("facing") and facts.get("customer"))
    log(
        json.dumps(
            {
                "review_ok": review_ok,
                "crs_ok": crs_ok,
                "char_still_ok": char_still_ok,
                "schnick_ok": schnick_ok,
                "facts_ok": facts_ok,
                "leak": leak,
                "leak_ok": leak_ok,
            },
            indent=2,
        )
    )
    if crs_ok and char_still_ok and schnick_ok and leak_ok and review_ok and facts_ok:
        log("LIVE GATES MEASURED — see evidence/live-gates.json")
        return 0
    log("LIVE GATES INCOMPLETE OR FAILED — see evidence/live-gates.json")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise
