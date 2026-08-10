import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { AudioMixerPanel, normalizeAudioMixerMix, type AudioMixerClipDescriptor, type AudioMixerMixState } from "./AudioMixerPanel";

type AudioMixerWorkspaceProps = {
  projectId: string;
  clips: AudioMixerClipDescriptor[];
  emptyMessage?: string;
  onAfterSave?: () => Promise<void> | void;
  onRequestStemReplace?: (clip: AudioMixerClipDescriptor, stemRole?: string) => void;
};

const EMPTY_MIX: AudioMixerMixState = {
  master: {
    gain: 1,
    peak: null,
    lufsIntegrated: null,
    lufsShortTerm: null,
  },
  clips: {},
};

export function AudioMixerWorkspace({
  projectId,
  clips,
  emptyMessage,
  onAfterSave,
  onRequestStemReplace,
}: AudioMixerWorkspaceProps) {
  const [mix, setMix] = useState<AudioMixerMixState>(() => normalizeAudioMixerMix(EMPTY_MIX, clips));
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("");

  const loadMix = useCallback(async () => {
    setLoading(true);
    try {
      const response = await api.audioStudioGetMix(projectId);
      setMix(normalizeAudioMixerMix(response?.mix || EMPTY_MIX, clips));
      setStatus("");
    } catch (error) {
      setMix(normalizeAudioMixerMix(EMPTY_MIX, clips));
      setStatus(error instanceof Error ? error.message : "Could not load Audio Mixer.");
    } finally {
      setLoading(false);
    }
  }, [clips, projectId]);

  useEffect(() => {
    void loadMix();
  }, [loadMix]);

  const savePatch = useCallback(
    async (body: { master?: Record<string, unknown>; clips?: Record<string, Record<string, unknown>>; clip?: Record<string, unknown> }) => {
      setBusy(true);
      try {
        await api.audioStudioUpdateMix(projectId, body);
        await loadMix();
        await onAfterSave?.();
        setStatus("Mixer saved.");
      } catch (error) {
        setStatus(error instanceof Error ? error.message : "Could not save Audio Mixer.");
      } finally {
        setBusy(false);
      }
    },
    [loadMix, onAfterSave, projectId]
  );

  return (
    <AudioMixerPanel
      clips={clips}
      mix={mix}
      busy={busy}
      status={loading ? "Loading mixer…" : status}
      emptyMessage={emptyMessage}
      onSavePatch={savePatch}
      onReload={loadMix}
      onRequestStemReplace={onRequestStemReplace}
    />
  );
}
