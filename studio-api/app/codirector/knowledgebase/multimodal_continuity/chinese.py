"""Chinese compiled view of CanonicalContinuity. Not a free translation."""

from __future__ import annotations

from .panels import occlusion_notes, panel_includes_occupied
from .schema import CanonicalContinuity, HARD_FACT_STATUSES
from .terminology import GLOSSARY


def compile_chinese(facts: CanonicalContinuity) -> str:
    title = facts.sceneTitle or "该环境"
    src = facts.sourceAuthority
    lines: list[str] = []
    if src.assetId:
        lines.append(f"{GLOSSARY['preserve_environment'][1]}（{title}）。来源资产 {src.assetId}。")
    else:
        lines.append(f"生成锁定环境 {title}。")
    keep: list[str] = []
    if facts.fixedArchitecture.get("serviceCounterOrBar"):
        keep.append(GLOSSARY["service_counter"][1])
    if any(a.landmark == "espresso_station" for a in facts.actors):
        keep.append(GLOSSARY["espresso_station"][1])
    if (facts.geometry or {}).get("windowLocations"):
        keep.append(GLOSSARY["storefront_windows"][1])
    if (facts.geometry or {}).get("doorOrEntranceLocations"):
        keep.append(GLOSSARY["main_entrance"][1])
    if _couch_present(facts):
        keep.append(GLOSSARY["lounge_couch"][1])
    if keep:
        lines.append("保持" + "、".join(keep) + "、材质以及房间朝向不变。")
    else:
        lines.append("保持参考图像中的建筑结构、材质、色彩和房间朝向不变。")
    for actor in facts.actors:
        if not panel_includes_occupied(facts.cameraTask.panelTask):
            break
        if str(actor.factStatus) not in HARD_FACT_STATUSES:
            continue
        bits = [actor.actor, "必须"]
        loc: list[str] = []
        if actor.relativePosition == "behind_service_counter":
            loc.append(GLOSSARY["behind_service_counter"][1])
        if actor.landmark == "espresso_station":
            loc.append("靠近" + GLOSSARY["espresso_station"][1])
        if actor.barrierSide == "employee_side":
            loc.append("位于" + GLOSSARY["employee_side"][1])
        if loc:
            bits.append("站在" + "、".join(loc))
        line = "".join(bits) + "。"
        bans: list[str] = []
        if "front_of_counter" in actor.forbiddenZones:
            bans.append(GLOSSARY["front_of_counter"][1])
        if "customer_seating" in actor.forbiddenZones:
            bans.append(GLOSSARY["customer_seating"][1])
        if bans:
            line += "不要把" + actor.actor + "放在" + "或".join(bans) + "。"
        lines.append(line)
    for inv in facts.hardInvariants:
        if not inv.strip():
            continue
        if not panel_includes_occupied(facts.cameraTask.panelTask) and any(
            a.actor and a.actor in inv for a in facts.actors
        ):
            continue
        lines.append(inv.strip())
    for ban in facts.forbiddenChanges:
        if not ban.strip():
            continue
        blob = ban.lower()
        if not panel_includes_occupied(facts.cameraTask.panelTask) and any(
            k in blob for k in ("character", "seating", "place characters")
        ):
            continue
        text = ban.strip()
        if not text.startswith("不要") and not text.lower().startswith("do not"):
            text = "不要" + text
        lines.append(text)
    task = str(facts.cameraTask.panelTask or "")
    if "east" in task:
        lines.append("生成同一物理空间的东向视图。")
    for note in occlusion_notes(facts, facts.cameraTask.panelTask):
        if "couch" in note.lower() or "lounge" in note.lower():
            lines.append("休息区沙发仍然存在；从此视角可能被遮挡，不要从环境设定中删除。")
        else:
            lines.append("被遮挡不等于不存在。不要从环境设定中删除固定家具。")
    if str(facts.cameraTask.panelTask) == "occupied_scale":
        lines.append(GLOSSARY["occupied_scale_only"][1] + "。")
    elif str(facts.cameraTask.panelTask) == "top_down":
        lines.append("俯视图强调几何与动线，不要加入电影化占用叙事。")
    lines.append(GLOSSARY["only_camera"][1] + "。")
    return "\n\n".join(lines)


def _couch_present(facts: CanonicalContinuity) -> bool:
    couch = facts.persistentFurniture.get("couch")
    if isinstance(couch, dict):
        return bool(couch.get("present") is True or couch.get("location"))
    return False
