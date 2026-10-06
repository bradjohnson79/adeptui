import { useEffect, useState } from "react";
import { api } from "../../api";
import { setElevenLabsModelId, setElevenLabsVoiceId } from "../../audioProvider/voiceStudioProviderStore";
import { Button } from "../ui";

type VoiceOption = { voiceId: string; name: string };
type ModelOption = { modelId: string; name: string };

export type ElevenLabsGeneratedSample = {
  assetId: string;
  candidateId?: string;
  voiceProfileId?: string;
  provider?: string;
  modelId?: string;
  voiceName?: string;
  providerVoiceId?: string;
};

type Props = {
  projectId: string;
  characterId: string;
  configured: boolean;
  savedVoiceId?: string;
  savedVoiceName?: string;
  savedModelId?: string;
  restoredSample?: ElevenLabsGeneratedSample | null;
  approvedAssetId?: string;
  onSaved?: () => void;
  onSampleReady?: () => void;
  onApproveSample?: (sample: ElevenLabsGeneratedSample) => Promise<void> | void;
  onMsg: (message: string) => void;
};

function voiceModelLabel(modelId: string): string {
  const raw = modelId.trim();
  if (!raw) return "ElevenLabs";
  if (raw === "eleven_v4") return "Eleven v4";
  return raw.replaceAll("_", " ");
}

export function ElevenLabsVoiceWorkflow({
  projectId,
  characterId,
  configured,
  savedVoiceId = "",
  savedVoiceName = "",
  savedModelId = "",
  restoredSample = null,
  approvedAssetId = "",
  onSaved,
  onSampleReady,
  onApproveSample,
  onMsg,
}: Props) {
  const [voices, setVoices] = useState<VoiceOption[]>([]);
  const [models, setModels] = useState<ModelOption[]>([]);
  const [voiceId, setVoiceId] = useState(savedVoiceId);
  const [voiceName, setVoiceName] = useState(savedVoiceName);
  const [modelId, setModelId] = useState(savedModelId);
  const [line, setLine] = useState("Hello, my name is Renkoka. It's lovely to meet you.");
  const [generated, setGenerated] = useState<ElevenLabsGeneratedSample | null>(null);
  const [busy, setBusy] = useState<"sample" | "save" | "approve" | "">("");
  const [notice, setNotice] = useState("");
  const shown = generated?.assetId ? generated : restoredSample?.assetId ? restoredSample : null;
  const shownApproved = Boolean(shown?.assetId) && shown?.assetId === approvedAssetId;

  useEffect(() => {
    setVoiceId(savedVoiceId);
    setVoiceName(savedVoiceName);
    setModelId(savedModelId);
  }, [savedVoiceId, savedVoiceName, savedModelId]);

  useEffect(() => {
    if (!configured) return;
    let cancelled = false;
    void api.elevenLabsVoices().then((res: any) => {
      if (cancelled) return;
      const rows = Array.isArray(res?.voices) ? res.voices : [];
      setVoices(rows.map((row: any) => ({
        voiceId: String(row.voiceId || ""),
        name: String(row.name || "Untitled voice"),
      })).filter((row: VoiceOption) => row.voiceId));
    }).catch((error: any) => {
      if (!cancelled) setNotice(error?.message || "ElevenLabs voices could not be loaded.");
    });
    void api.elevenLabsModels().then((res: any) => {
      if (cancelled) return;
      const rows = Array.isArray(res?.models) ? res.models : [];
      setModels(rows.filter((row: any) => row?.canDoTextToSpeech && row?.modelId).map((row: any) => ({
        modelId: String(row.modelId),
        name: String(row.name || row.modelId),
      })));
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, [configured]);

  if (!configured) {
    return (
      <div className="vip-section" data-testid="elevenlabs-voice-workflow">
        <p role="alert">ElevenLabs is currently unavailable. Check your API configuration in Setup.</p>
      </div>
    );
  }

  return (
    <div className="vip-section" data-testid="elevenlabs-voice-workflow">
      <label className="vip-label">
        ElevenLabs voice
        <select
          data-testid="elevenlabs-voice-select"
          value={voiceId}
          onChange={(event) => {
            const next = event.target.value;
            const match = voices.find((row) => row.voiceId === next);
            setVoiceId(next);
            setVoiceName(match?.name || savedVoiceName);
            setElevenLabsVoiceId(next);
          }}
        >
          <option value="">Choose a voice</option>
          {voiceId && !voices.some((row) => row.voiceId === voiceId) ? (
            <option value={voiceId}>{voiceName || "Saved voice"}</option>
          ) : null}
          {voices.map((row) => (
            <option key={row.voiceId} value={row.voiceId}>{row.name}</option>
          ))}
        </select>
      </label>
      {voiceName ? <p data-testid="elevenlabs-voice-name">{voiceName}</p> : null}
      {models.length > 0 ? (
        <label className="vip-label">
          Voice model
          <select
            data-testid="elevenlabs-model-select"
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
      <label className="vip-label">
        Sample line
        <textarea
          data-testid="elevenlabs-sample-line"
          rows={3}
          value={line}
          onChange={(event) => setLine(event.target.value)}
        />
      </label>
      <div className="voice-studio-actions">
        <Button
          type="button"
          variant="primary"
          data-testid="elevenlabs-generate-sample"
          disabled={!characterId || !voiceId || !line.trim() || busy === "sample"}
          onClick={() => {
            setBusy("sample");
            setNotice("");
            void api.generateElevenLabsSample(projectId, characterId, {
              text: line.trim(),
              providerVoiceId: voiceId,
              modelId,
              voiceName,
            }).then((result) => {
              const nextId = String(result?.assetId || "");
              if (!nextId) {
                setNotice("ElevenLabs did not return audio.");
                return;
              }
              setGenerated({
                assetId: nextId,
                candidateId: String(result?.candidateId || ""),
                voiceProfileId: String(result?.voiceProfileId || ""),
                provider: "elevenlabs",
                modelId: String(result?.model || modelId || ""),
                voiceName: String(result?.voiceName || voiceName || ""),
                providerVoiceId: voiceId,
              });
              setNotice("Sample ready.");
              onSampleReady?.();
            }).catch((error: any) => {
              setNotice(error?.message || "ElevenLabs is currently unavailable. Check your API configuration in Setup.");
              onMsg(error?.message || "ElevenLabs could not generate this sample.");
            }).finally(() => setBusy(""));
          }}
        >
          {busy === "sample" ? "Generating" : "Generate sample"}
        </Button>
        <Button
          type="button"
          data-testid="elevenlabs-save-voice"
          disabled={!characterId || !voiceId || busy === "save"}
          onClick={() => {
            setBusy("save");
            setNotice("");
            void api.assignCharacterElevenLabsVoice(projectId, characterId, {
              providerVoiceId: voiceId,
              voiceName,
              modelId,
            }).then(() => {
              setNotice("Saved to this character.");
              onSaved?.();
            }).catch((error: any) => {
              setNotice(error?.message || "Could not save this voice.");
              onMsg(error?.message || "Could not save this voice.");
            }).finally(() => setBusy(""));
          }}
        >
          Save Voice
        </Button>
      </div>
      {shown?.assetId ? (
        <div className="vip-generated-sample" data-testid="elevenlabs-generated-sample">
          <strong>New sample</strong>
          <audio
            controls
            src={api.assetUrl(shown.assetId, undefined, projectId)}
            data-testid="elevenlabs-sample-player"
          />
          <p data-testid="elevenlabs-sample-meta">
            ElevenLabs · {voiceModelLabel(shown.modelId || modelId)}
          </p>
          <Button
            type="button"
            variant={shownApproved ? "secondary" : "primary"}
            data-testid="elevenlabs-sample-approve"
            disabled={shownApproved || busy === "approve" || !onApproveSample}
            aria-pressed={shownApproved}
            onClick={() => {
              if (!onApproveSample || shownApproved) return;
              setBusy("approve");
              setNotice("");
              void Promise.resolve(onApproveSample(shown)).then(() => {
                setNotice(shownApproved ? "" : "This sample is now the current voice.");
              }).catch((error: any) => {
                setNotice(error?.message || "Could not approve this sample.");
                onMsg(error?.message || "Could not approve this sample.");
              }).finally(() => setBusy(""));
            }}
          >
            {shownApproved ? "Approved ✓" : busy === "approve" ? "Approving" : "Approve"}
          </Button>
        </div>
      ) : null}
      {notice ? <p role="status">{notice}</p> : null}
    </div>
  );
}
