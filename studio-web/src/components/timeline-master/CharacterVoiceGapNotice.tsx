import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { noApprovedDefaultVoiceMessage } from "../voiceStudio/defaultVoiceCopy";
import { openVoiceCreator } from "../CoDirector/VoiceCreator/openVoiceCreator";
import type { TimedPromptNameBinding } from "../../timelineMaster/timedPromptNameBindings";
import type { ReferenceBindingView } from "../../sceneReferences/referenceTokens";

type Gap = { characterId: string; name: string };

export function speakingCharactersWithoutApprovedVoice(
  rows: TimedPromptNameBinding[],
  bindings: ReferenceBindingView[],
  approvedIds: Set<string>,
): Gap[] {
  const gaps: Gap[] = [];
  const seen = new Set<string>();
  for (const row of rows) {
    if (row.type !== "character") continue;
    const binding = bindings.find((item) => item.id === row.binding_id);
    const characterId = String(binding?.identity_id || "").trim();
    if (!characterId || seen.has(characterId) || approvedIds.has(characterId)) continue;
    seen.add(characterId);
    const name = String(row.prompt_name || binding?.asset_name || binding?.alias || "This character").trim();
    gaps.push({ characterId, name });
  }
  return gaps;
}

export function CharacterVoiceGapNotice({
  projectId,
  rows,
  bindings,
}: {
  projectId: string;
  rows: TimedPromptNameBinding[];
  bindings: ReferenceBindingView[];
}) {
  const [approvedIds, setApprovedIds] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    void api.voiceApprovedStatus(projectId).then((res) => {
      if (cancelled) return;
      setApprovedIds(new Set((res.items || []).map((item) => String(item.characterId || ""))));
    }).catch(() => {
      if (!cancelled) setApprovedIds(new Set());
    });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const gaps = useMemo(
    () => speakingCharactersWithoutApprovedVoice(rows, bindings, approvedIds),
    [rows, bindings, approvedIds],
  );
  if (!gaps.length) return null;

  return (
    <div className="timed-prompt-voice-gaps" data-testid="timed-prompt-voice-gaps">
      {gaps.map((gap) => (
        <p key={gap.characterId} className="scene-meta" data-testid="timed-prompt-missing-voice">
          {noApprovedDefaultVoiceMessage(gap.name)}{" "}
          <button
            type="button"
            className="ghost"
            data-testid="timed-prompt-open-voice-creator"
            onClick={() => openVoiceCreator({ characterId: gap.characterId })}
          >
            Open Voice Creator
          </button>
        </p>
      ))}
    </div>
  );
}
