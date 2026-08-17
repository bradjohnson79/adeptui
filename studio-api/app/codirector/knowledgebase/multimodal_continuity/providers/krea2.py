"""Krea 2 renderer: Chinese-first (Qwen-Image-based), compact JSON.

Tiny translator of the canonical continuity packet into the prompt representation
Krea 2 needs. No second continuity compiler, no Krea-specific truth model, no
duplicated production context — this only re-views the same ``InstructionPacket``
the Qwen/GPT renderers consume. Krea 2 sampling specifics (cfg 0.0, mu 1.15,
8-step turbo / 52-step raw) are handled by the workflow builder, not here.
"""

from __future__ import annotations

import json

from ..schema import InstructionPacket
from ..terminology import KREA2_KEEP, KREA2_VIEW_WHOLE


def render_krea2(packet: InstructionPacket) -> str:
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
        "参考图像是唯一权威的物理环境。" if packet.referenceImage else "保持同一物理环境。",
        KREA2_KEEP,
        packet.chinesePrompt,
        "结构约束：",
        packet.englishPrompt,
        KREA2_VIEW_WHOLE,
        "JSON:\n" + json.dumps(compact, ensure_ascii=False, indent=2),
    ]
    return "\n\n".join(blocks)
