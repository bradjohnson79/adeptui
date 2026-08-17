"""GPT Image 2 renderer: English production instruction, compact Chinese, JSON."""

from __future__ import annotations

import json

from ..schema import InstructionPacket
from ..terminology import GPT_KEEP, GPT_VIEW_WHOLE


def render_gpt_image2(packet: InstructionPacket) -> str:
    facts = packet.continuityJson
    compact = {
        "source": packet.referenceImage,
        "actors": [a.model_dump() for a in facts.actors],
        "props": [p.model_dump() for p in facts.props],
        "hardInvariants": packet.hardInvariants,
        "forbiddenChanges": packet.forbiddenChanges,
        "panelTask": packet.panelTask,
    }
    chinese_block = packet.chinesePrompt
    if len(chinese_block) > 1800:
        chinese_block = chinese_block[:1800]
    invariants = packet.hardInvariants[:12] or ["Preserve the supplied reference environment."]
    blocks = [
        GPT_KEEP,
        packet.englishPrompt,
        "Hard invariants:\n- " + "\n- ".join(invariants),
        "Chinese constraints:\n" + chinese_block,
        GPT_VIEW_WHOLE,
        "JSON:\n" + json.dumps(compact, ensure_ascii=False, indent=2),
    ]
    return "\n\n".join(blocks)
