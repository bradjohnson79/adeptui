import { useEffect, useState } from "react";
import { api } from "../../api";
import { ProviderSourceSelector } from "../audioProvider/ProviderSourceSelector";
import { useVoiceStudioProviderSource } from "../../audioProvider/useProviderSource";
import {
  getElevenLabsModelId,
  getElevenLabsVoiceId,
  setElevenLabsModelId,
  setElevenLabsVoiceId,
} from "../../audioProvider/voiceStudioProviderStore";

type VoiceOption = { voiceId: string; name: string };
type ModelOption = { modelId: string; name: string };

type Props = {
  id?: string;
  label?: string;
  projectId?: string;
  characterId?: string;
  voiceProfileId?: string;
  boundVoiceId?: string;
  boundVoiceName?: string;
  boundModelId?: string;
  onProviderChange?: (next: "local" | "elevenlabs") => void;
  showVoiceControls?: boolean;
};

/** Shared Voice Provider control for Express and Standard. */
export function VoiceEngineLabel({
  id = "voice-provider",
  label = "Voice Provider",
  projectId,
  characterId,
  voiceProfileId,
  boundVoiceId,
  boundVoiceName,
  boundModelId,
  onProviderChange,
  showVoiceControls = true,
}: Props) {
  const provider = useVoiceStudioProviderSource();
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [voiceId, setVoiceId] = useState(getElevenLabsVoiceId);
  const [voiceName, setVoiceName] = useState("");
  const [modelId, setModelId] = useState(getElevenLabsModelId);
  const [notice, setNotice] = useState("");

  useEffect(() => {
    if (!boundVoiceId) return;
    setVoiceId(boundVoiceId);
    setVoiceName(boundVoiceName || "");
    setElevenLabsVoiceId(boundVoiceId);
    if (boundModelId) {
      setModelId(boundModelId);
      setElevenLabsModelId(boundModelId);
    }
  }, [boundVoiceId, boundVoiceName, boundModelId]);

  useEffect(() => {
    if (provider.source !== "elevenlabs" || !provider.health?.configured) return;
    let cancelled = false;
    void (api as any).elevenLabsVoices().then((res: any) => {
      if (cancelled) return;
      const rows = Array.isArray(res?.voices) ? res.voices : [];
      setVoices(rows.map((row: any) => ({
        voiceId: String(row.voiceId || ""),
        name: String(row.name || row.voiceId || ""),
      })).filter((row: VoiceOption) => row.voiceId));
    }).catch((err: any) => {
      if (!cancelled) setNotice(err?.message || "ElevenLabs voices could not be loaded.");
    });
    void (api as any).elevenLabsModels().then((res: any) => {
      if (cancelled) return;
      const rows = Array.isArray(res?.models) ? res.models : [];
      setModels(rows.filter((row: any) => row?.canDoTextToSpeech && row?.modelId).map((row: any) => ({
        modelId: String(row.modelId),
        name: String(row.name || row.modelId),
      })));
    }).catch(() => { /* model list is optional */ });
    return () => { cancelled = true; };
  }, [provider.source, provider.health?.configured]);

  const elevenSelected = showVoiceControls && provider.source === "elevenlabs" && Boolean(provider.health?.configured);

  return (
    <div data-testid={`${id}-voice-engine`} data-provider={provider.source}>
      <ProviderSourceSelector
        id={id}
        label={label}
        source={provider.source}
        onChange={onProviderChange || provider.setSource}
        health={provider.health}
        healthBusy={provider.healthBusy}
      />
      {elevenSelected ? (
        <div data-testid={`${id}-elevenlabs-controls`}>
          <label className="adept-provider-source__label" htmlFor={`${id}-elevenlabs-voice`}>
            ElevenLabs voice
            <select
              id={`${id}-elevenlabs-voice`}
              data-testid={`${id}-elevenlabs-voice`}
              value={voiceId}
              onChange={(event) => {
                const next = event.target.value;
                const match = voices.find((row) => row.voiceId === next);
                setVoiceId(next);
                setVoiceName(match?.name || boundVoiceName || "");
                setElevenLabsVoiceId(next);
              }}
            >
              <option value="">Choose a voice</option>
              {voiceId && !voices.some((row) => row.voiceId === voiceId) ? (
                <option value={voiceId}>{voiceName || voiceId}</option>
              ) : null}
              {voices.map((row) => (
                <option key={row.voiceId} value={row.voiceId}>{row.name}</option>
              ))}
            </select>
          </label>
          {voiceId ? (
            <p data-testid={`${id}-elevenlabs-voice-id`}>Voice ID {voiceId}</p>
          ) : null}
          {models.length > 0 ? (
            <label className="adept-provider-source__label" htmlFor={`${id}-elevenlabs-model`}>
              Voice model
              <select
                id={`${id}-elevenlabs-model`}
                data-testid={`${id}-elevenlabs-model`}
                value={modelId}
                onChange={(event) => {
                  setModelId(event.target.value);
                  setElevenLabsModelId(event.target.value);
                }}
              >
                <option value="">Default voice model</option>
                {models.map((row) => (
                  <option key={row.modelId} value={row.modelId}>{row.name}</option>
                ))}
              </select>
            </label>
          ) : null}
        </div>
      ) : null}
      {elevenSelected && projectId && characterId && voiceId ? (
        <button
          type="button"
          data-testid={`${id}-save-elevenlabs-voice`}
          onClick={() => {
            setNotice("");
            void (api as any).assignCharacterElevenLabsVoice(projectId, characterId, {
              providerVoiceId: voiceId,
              voiceName,
              modelId,
              voiceProfileId,
            }).then(() => setNotice("Saved to this character."))
              .catch((err: any) => setNotice(err?.message || "Could not save this voice."));
          }}
        >
          Save voice to character
        </button>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
    </div>
  );
}
