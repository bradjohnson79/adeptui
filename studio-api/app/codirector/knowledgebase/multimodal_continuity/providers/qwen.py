"""Qwen renderer: Chinese constraints first, then compact JSON."""

from __future__ import annotations

import json

from ..schema import InstructionPacket
from ..terminology import QWEN_KEEP, QWEN_VIEW_WHOLE


def render_qwen(packet: InstructionPacket) -> str:
    facts = packet.continuityJson
    compact = {
        "source": packet.referenceImage,
        "actors": [a.model_dump() for a in facts.actors],
        "props": [p.model_dump() for p in facts.props],
        "hardInvariants": packet.hardInvariants,
        "forbiddenChanges": packet.forbiddenChanges,
        "panelTask": packet.panelTask,
    }
    blocks = [
        "参考图像是唯一权威的物理环境。",
        QWEN_KEEP,
        packet.chinesePrompt,
        "结构约束：",
        packet.englishPrompt,
        QWEN_VIEW_WHOLE,
        "JSON:\n" + json.dumps(compact, ensure_ascii=False, indent=2),
    ]
    return "\n\n".join(blocks)
