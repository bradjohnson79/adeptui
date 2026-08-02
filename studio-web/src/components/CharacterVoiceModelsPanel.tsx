import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import { StatusBadge } from "./ui";

type VoiceModel = {
  componentId: string;
  name: string;
  description: string;
  sourceKey: string;
  modelRepository: string;
  downloadBytes: number;
  ready: boolean;
  status: string;
  recommendation?: string | null;
};

function formatBytes(n: number): string {
  if (!n) return "—";
  const gb = n / (1024 * 1024 * 1024);
  return `${gb.toFixed(1)} GB`;
}

export function CharacterVoiceModelsPanel({ onChanged }: { onChanged?: () => void }) {
  const [items, setItems] = useState<VoiceModel[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [indexConfirmOpen, setIndexConfirmOpen] = useState(false);
  const [indexModelAck, setIndexModelAck] = useState(false);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const data = await api.sourceManagerVoiceModels();
      setItems((data.components || []) as VoiceModel[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const install = async (componentId: string, confirmDownloadModels = false) => {
    setBusyId(componentId);
    setError(null);
    setMessage(null);
    try {
      const result = await api.sourceManagerVoiceModelInstall(componentId, {
        confirm: true,
        confirmDownloadModels,
      });
      if (componentId === "index_tts2") {
        if (result.downloadDeferred) {
          setMessage(
            "IndexTTS2 runtime scaffold installed. Model download was not authorized — check confirmDownloadModels to complete full install (~15 GB).",
          );
        } else {
          setMessage("IndexTTS2 full install started (runtime + official model download).");
        }
      } else {
        setMessage(
          `Queued ${componentId} (operation ${(result.operation as { id?: string })?.id || "pending"}). Watch Active Downloads.`,
        );
      }
      onChanged?.();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
      setIndexConfirmOpen(false);
      setIndexModelAck(false);
    }
  };

  const uninstall = async (componentId: string) => {
    if (!window.confirm(`Uninstall ${componentId}? This removes the local venv and model weights.`)) return;
    setBusyId(componentId);
    setError(null);
    try {
      await api.sourceManagerVoiceModelUninstall(componentId);
      setMessage(`Uninstalled ${componentId}.`);
      onChanged?.();
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section
      className="setup-component-section ds-surface"
      aria-labelledby="sm-voice-models-heading"
      data-testid="character-voice-models-panel"
    >
      <div className="setup-section-heading">
        <h2 id="sm-voice-models-heading">Character Voice Models</h2>
        <p>
          Official Qwen3-TTS Voice Design / Clone (Voice Identity) and IndexTTS2 (Voice Performance).
          Installs use isolated runtimes. Model downloads require explicit confirmation. Fixtures are
          never accepted as success.
        </p>
        <button type="button" className="linkish" onClick={() => void reload()}>
          Refresh
        </button>
      </div>
      {message && (
        <p className="setup-message" role="status">
          {message}
        </p>
      )}
      {error && (
        <p className="setup-message error" role="alert">
          {error}
        </p>
      )}
      <div className="setup-component-grid">
        {items.map((item) => {
          const isIndex = item.componentId === "index_tts2";
          return (
            <article
              key={item.componentId}
              className={`setup-component-card status-${item.ready ? "ready" : "missing"}`}
              data-testid={`voice-model-${item.componentId}`}
              data-ready={item.ready ? "true" : "false"}
            >
              <header className="setup-card-header">
                <div>
                  <h3>{item.name}</h3>
                  <span className="setup-requirement">{item.sourceKey}</span>
                </div>
                <StatusBadge
                  kind={item.ready ? "Ready" : "InstallRequired"}
                  label={item.ready ? "READY" : String(item.status || "NOT_INSTALLED").toUpperCase()}
                  compact
                />
              </header>
              <p className="setup-component-description">{item.description}</p>
              <div className="setup-card-meta">
                <span>Size ~{formatBytes(item.downloadBytes)}</span>
                <span>
                  <a href={item.modelRepository} target="_blank" rel="noreferrer">
                    Hugging Face
                  </a>
                </span>
              </div>
              {isIndex && indexConfirmOpen && !item.ready ? (
                <div className="setup-card-actions" data-testid="index-tts2-install-confirm" style={{ flexDirection: "column", alignItems: "stretch", gap: 8 }}>
                  <p>
                    <strong>Install IndexTTS2</strong>
                    <br />
                    Runtime download from the official IndexTTS repository.
                    <br />
                    Model download: approximately 15 GB from official IndexTeam Hugging Face.
                  </p>
                  <label style={{ display: "flex", gap: 8, alignItems: "flex-start" }}>
                    <input
                      type="checkbox"
                      checked={indexModelAck}
                      data-testid="index-tts2-confirm-model-download"
                      onChange={(e) => setIndexModelAck(e.target.checked)}
                    />
                    <span>I confirm the model download</span>
                  </label>
                  <div style={{ display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      disabled={busyId === item.componentId || !indexModelAck}
                      data-testid="index-tts2-install-submit"
                      onClick={() => void install("index_tts2", true)}
                    >
                      {busyId === item.componentId ? "Installing…" : "Install"}
                    </button>
                    <button
                      type="button"
                      className="linkish"
                      disabled={busyId === item.componentId}
                      onClick={() => {
                        setIndexConfirmOpen(false);
                        setIndexModelAck(false);
                      }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <div className="setup-card-actions">
                  {!item.ready ? (
                    <button
                      type="button"
                      disabled={busyId === item.componentId}
                      data-testid={`voice-model-install-${item.componentId}`}
                      onClick={() => {
                        if (isIndex) {
                          setIndexConfirmOpen(true);
                          setIndexModelAck(false);
                          return;
                        }
                        void install(item.componentId, false);
                      }}
                    >
                      {busyId === item.componentId ? "Queuing…" : isIndex ? "Install IndexTTS2…" : "Download and Install"}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="linkish"
                      disabled={busyId === item.componentId}
                      data-testid={`voice-model-uninstall-${item.componentId}`}
                      onClick={() => void uninstall(item.componentId)}
                    >
                      Uninstall
                    </button>
                  )}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </section>
  );
}
