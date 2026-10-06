import { useCallback, useEffect, useState } from "react";
import { VoiceIdentityPanel } from "../../voiceStudio/VoiceIdentityPanel";
import type { VoiceIdentityMethod } from "../../voiceStudio/voiceIdentityRoute";
import {
  OPEN_VOICE_CREATOR_EVENT,
  VOICE_CREATOR_OPENED_EVENT,
  readVoiceCreatorHandoff,
  type VoiceCreatorHandoff,
} from "./openVoiceCreator";

export type VoiceCreatorPanelProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

function methodFromHandoff(value: string | undefined): VoiceIdentityMethod | null {
  if (value === "create" || value === "clone" || value === "existing") return value;
  return null;
}

export function VoiceCreatorPanel({ projectId, onGoTab }: VoiceCreatorPanelProps) {
  const [characterId, setCharacterId] = useState("");
  const [method, setMethod] = useState<VoiceIdentityMethod | null>(null);
  const [notice, setNotice] = useState("");

  const applyHandoff = useCallback((detail: VoiceCreatorHandoff | null) => {
    if (!detail) return;
    if (detail.characterId) setCharacterId(detail.characterId);
    const nextMethod = methodFromHandoff(detail.method);
    if (nextMethod) setMethod(nextMethod);
  }, []);

  useEffect(() => {
    applyHandoff(readVoiceCreatorHandoff());
    const onOpen = (event: Event) => {
      applyHandoff((event as CustomEvent<VoiceCreatorHandoff>).detail || {});
      window.dispatchEvent(new CustomEvent(VOICE_CREATOR_OPENED_EVENT));
    };
    window.addEventListener(OPEN_VOICE_CREATOR_EVENT, onOpen);
    return () => window.removeEventListener(OPEN_VOICE_CREATOR_EVENT, onOpen);
  }, [applyHandoff]);

  return (
    <div className="voice-creator-express" data-testid="voice-creator-express">
      {notice ? (
        <p className="muted" data-testid="voice-creator-notice">
          {notice}
        </p>
      ) : null}
      <VoiceIdentityPanel
        variant="express"
        projectId={projectId}
        characterId={characterId}
        preferredMethod={method}
        onMsg={setNotice}
        onCharacterChange={setCharacterId}
        onOpenFullStudio={(id) =>
          onGoTab?.(
            "voicestudio",
            id ? { characterId: id, returnWorkspace: "codirector" } : { returnWorkspace: "codirector" },
          )
        }
      />
    </div>
  );
}
