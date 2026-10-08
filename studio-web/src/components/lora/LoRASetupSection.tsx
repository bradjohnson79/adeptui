import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import { clearLoraSelectorCache } from "./loraClient";

const FAMILY_LABELS: Record<string, string> = {
  sdxl: "SDXL / SD",
  flux: "FLUX",
  "qwen-image": "Qwen Image",
  zimage: "Z-Image",
  krea2: "Krea 2",
  ltx: "LTX Video",
  wan: "Wan",
  hunyuan: "Hunyuan",
  unassigned: "Unknown",
};

function familyLabel(family: string | undefined): string {
  return family ? FAMILY_LABELS[family] || family : "Unknown";
}

type LoraRow = {
  id: string;
  name: string;
  filename?: string;
  model_family?: string;
  user_status?: string;
  trigger_words?: string[];
  source_provider?: string;
  source_url?: string;
  source_version?: string;
  checksum_sha256?: string;
  owned_by?: string;
  author?: string;
  license?: string;
  recommended_strength?: number | null;
  strength_from_source?: boolean;
  compatible_generators?: string[];
  incompatible_generators?: string[];
  file_exists?: boolean;
  enabled?: boolean;
  download_size_bytes?: number | null;
};

/**
 * Setup entry for optional LoRAs. Opening Manage shows the Adept LoRA Manager.
 * Missing LoRAs never block first-run setup.
 */
export function LoRASetupSection({ onMessage }: { onMessage: (message: string) => void }) {
  const [open, setOpen] = useState(false);
  const [loras, setLoras] = useState<LoraRow[]>([]);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const [familyFilter, setFamilyFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [addMode, setAddMode] = useState<"link" | "file" | null>(null);
  const [url, setUrl] = useState("");
  const [resolution, setResolution] = useState<any>(null);
  const [chosenFile, setChosenFile] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);
  const [removeTarget, setRemoveTarget] = useState<LoraRow | null>(null);
  const [deleteFile, setDeleteFile] = useState(false);
  const [showTechnical, setShowTechnical] = useState(false);
  const [tokenProvider, setTokenProvider] = useState<"huggingface" | "civitai" | null>(null);
  const [tokenValue, setTokenValue] = useState("");
  const [tokens, setTokens] = useState({ huggingface: false, civitai: false });

  const refresh = useCallback(async () => {
    const listRes = await api.loras.list();
    setLoras(listRes.loras || []);
  }, []);

  useEffect(() => {
    void refresh().catch((error) => onMessage(error instanceof Error ? error.message : String(error)));
  }, [onMessage, refresh]);

  useEffect(() => {
    if (!open) return;
    void api.loras.tokenStatus().then(setTokens).catch(() => undefined);
  }, [open]);

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      clearLoraSelectorCache();
      await refresh();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  };

  const visible = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return loras.filter((lora) => {
      if (familyFilter !== "all" && (lora.model_family || "unassigned") !== familyFilter) return false;
      const status = lora.user_status || "";
      if (statusFilter === "installed" && status !== "INSTALLED") return false;
      if (statusFilter === "unknown" && status !== "UNKNOWN COMPATIBILITY") return false;
      if (statusFilter === "incompatible" && !(lora.incompatible_generators || []).length) return false;
      if (!needle) return true;
      return `${lora.name} ${lora.filename || ""} ${(lora.trigger_words || []).join(" ")}`.toLowerCase().includes(needle);
    });
  }, [familyFilter, loras, query, statusFilter]);

  const detail = loras.find((lora) => lora.id === detailId) || null;

  const applyInstallResult = (result: any) => {
    if (result?.status === "needs_token") {
      setTokenProvider(result.token_provider === "civitai" ? "civitai" : "huggingface");
      onMessage(result.message || "A token is required.");
      return;
    }
    if (result?.status === "choose_file") {
      setResolution(result.resolution);
      onMessage(result.message || "Choose which LoRA file to install.");
      return;
    }
    if (result?.status === "update_available") {
      onMessage(result.message || "An update is available.");
      setResolution({ update: true });
      return;
    }
    onMessage(result?.message || "LoRA ready.");
    setAddMode(null);
    setUrl("");
    setResolution(null);
  };

  return (
    <section className="panel setup-component-section" data-testid="lora-setup-section">
      <div className="setup-section-heading">
        <div>
          <h2>LoRAs</h2>
          <p>Optional style and character adapters. Adept UI works without any LoRAs installed.</p>
        </div>
        <button type="button" className="ghost" data-testid="lora-manage" onClick={() => setOpen(true)}>
          Manage
        </button>
      </div>
      <p className="muted">{loras.length ? `${loras.length} installed` : "None installed"}</p>

      {open ? (
        <div className="setup-dialog-backdrop" role="presentation" onClick={() => setOpen(false)}>
          <div
            className="setup-dialog lora-manager-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="lora-manager-title"
            data-testid="lora-manager"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="setup-dialog-header">
              <h2 id="lora-manager-title">Adept LoRA Manager</h2>
              <button type="button" className="ghost" onClick={() => setOpen(false)}>
                Close
              </button>
            </div>
            <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap" }}>
              <button type="button" className="primary" data-testid="lora-add" disabled={busy} onClick={() => setAddMode(addMode ? null : "link")}>
                Add LoRA
              </button>
              <button
                type="button"
                data-testid="lora-scan"
                disabled={busy}
                onClick={() =>
                  void run(async () => {
                    const found = await api.loras.scan();
                    const registered = await api.loras.detect(true);
                    const count = found.candidates?.length || 0;
                    onMessage(
                      count
                        ? `Found ${count} LoRA file${count === 1 ? "" : "s"}. Registered ${registered.count} new file${registered.count === 1 ? "" : "s"} in place.`
                        : "No LoRA files were found in the configured folders.",
                    );
                  })
                }
              >
                Scan Existing LoRAs
              </button>
            </div>

            {addMode ? (
              <div className="panel" style={{ marginTop: "0.75rem" }} data-testid="lora-add-panel">
                <div className="row" style={{ gap: "0.5rem" }}>
                  <button type="button" className={addMode === "link" ? "primary" : "ghost"} onClick={() => setAddMode("link")}>
                    Paste Link
                  </button>
                  <button type="button" className={addMode === "file" ? "primary" : "ghost"} onClick={() => setAddMode("file")}>
                    Import Local File
                  </button>
                </div>
                {addMode === "link" ? (
                  <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label>Hugging Face or Civitai link</label>
                    <input
                      data-testid="lora-paste-url"
                      value={url}
                      onChange={(event) => setUrl(event.target.value)}
                      placeholder="https://huggingface.co/… or https://civitai.com/models/…"
                    />
                    <button
                      type="button"
                      className="primary"
                      disabled={busy || !url.trim()}
                      onClick={() =>
                        void run(async () => {
                          const resolved = await api.loras.resolve(url.trim());
                          setResolution(resolved);
                          setShowTechnical(false);
                          if (resolved.needs_token) {
                            setTokenProvider(resolved.token_provider === "civitai" ? "civitai" : "huggingface");
                            onMessage(resolved.message);
                            return;
                          }
                          if (!resolved.selected && (resolved.files || []).length > 1) {
                            onMessage(resolved.message || "Choose which LoRA file to install.");
                            return;
                          }
                          const result = await api.loras.installUrl(url.trim(), resolved.selected?.filename || "");
                          applyInstallResult(result);
                        })
                      }
                    >
                      Install
                    </button>
                    {resolution?.files?.length > 1 && !resolution?.selected ? (
                      <select value={chosenFile} onChange={(event) => setChosenFile(event.target.value)} data-testid="lora-file-choice">
                        <option value="">Choose a file</option>
                        {resolution.files.map((file: { filename: string }) => (
                          <option key={file.filename} value={file.filename}>
                            {file.filename}
                          </option>
                        ))}
                      </select>
                    ) : null}
                    {chosenFile ? (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() =>
                          void run(async () => {
                            const result = await api.loras.installUrl(url.trim(), chosenFile, Boolean(resolution?.update));
                            applyInstallResult(result);
                          })
                        }
                      >
                        Install selected file
                      </button>
                    ) : null}
                    {resolution?.message ? <p>{resolution.message}</p> : null}
                    {resolution?.base_model || resolution?.family ? (
                      <p className="muted">
                        Base model: {resolution.base_model || "Unknown"} · Compatible family: {familyLabel(resolution.family) || "Unknown"}
                      </p>
                    ) : null}
                    {resolution?.detail ? (
                      <button type="button" className="ghost tiny" onClick={() => setShowTechnical((value) => !value)}>
                        View details
                      </button>
                    ) : null}
                    {showTechnical && resolution?.detail ? <p className="muted">{resolution.detail}</p> : null}
                  </div>
                ) : (
                  <div className="field" style={{ marginTop: "0.75rem" }}>
                    <label>Choose LoRA file</label>
                    <input
                      data-testid="lora-import-file"
                      type="file"
                      accept=".safetensors,application/octet-stream"
                      disabled={busy}
                      onChange={(event) => {
                        const file = event.target.files?.[0];
                        event.target.value = "";
                        if (!file) return;
                        void run(async () => {
                          const result = await api.loras.importFile(file);
                          applyInstallResult(result);
                        });
                      }}
                    />
                    <p className="muted">.safetensors weights only. Scripts and plugins are not installed.</p>
                  </div>
                )}
                {tokenProvider ? (
                  <div className="field">
                    <label>{tokenProvider === "civitai" ? "Civitai API token" : "Hugging Face token"}</label>
                    <input
                      type="password"
                      value={tokenValue}
                      autoComplete="off"
                      onChange={(event) => setTokenValue(event.target.value)}
                    />
                    <button
                      type="button"
                      disabled={busy || !tokenValue.trim()}
                      onClick={() =>
                        void run(async () => {
                          await api.loras.saveToken(tokenProvider, tokenValue.trim());
                          setTokenValue("");
                          setTokens(await api.loras.tokenStatus());
                          onMessage("Token saved on this computer.");
                        })
                      }
                    >
                      Save token
                    </button>
                    <p className="muted">{tokens[tokenProvider] ? "A token is already saved." : "No token saved yet."}</p>
                  </div>
                ) : null}
              </div>
            ) : null}

            <div className="row" style={{ gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search LoRAs" data-testid="lora-search" />
              <select value={familyFilter} onChange={(event) => setFamilyFilter(event.target.value)} data-testid="lora-family-filter">
                <option value="all">All families</option>
                {Object.entries(FAMILY_LABELS).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
              <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
                <option value="all">All statuses</option>
                <option value="installed">Installed</option>
                <option value="unknown">Unknown compatibility</option>
                <option value="incompatible">Incompatible with another family</option>
              </select>
            </div>

            <ul className="home-list" data-testid="lora-registered-list" style={{ marginTop: "0.75rem" }}>
              {!visible.length ? <li className="empty">No LoRAs match.</li> : null}
              {visible.map((lora) => (
                <li key={lora.id} data-testid="lora-card">
                  <div>
                    <strong>{lora.name}</strong>
                    <span className="muted">
                      {" "}
                      · {lora.user_status || "INSTALLED"} · {familyLabel(lora.model_family)}
                      {lora.trigger_words?.length ? ` · Trigger: ${lora.trigger_words.join(", ")}` : ""}
                      {lora.source_provider ? ` · Source: ${lora.source_provider}` : ""}
                    </span>
                  </div>
                  <div className="row" style={{ gap: "0.4rem" }}>
                    <button type="button" className="ghost" onClick={() => setDetailId(detailId === lora.id ? null : lora.id)}>
                      Details
                    </button>
                    <button
                      type="button"
                      className="ghost"
                      onClick={() => {
                        setRemoveTarget(lora);
                        setDeleteFile(false);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>

            {detail ? (
              <div className="panel" data-testid="lora-details">
                <h3>{detail.name}</h3>
                <p>{detail.user_status}</p>
                {detail.user_status === "UNKNOWN COMPATIBILITY" ? (
                  <p>Compatibility could not be established. This LoRA will not be added to a generator automatically.</p>
                ) : (
                  <>
                    <p>Compatible with: {(detail.compatible_generators || []).join(", ") || familyLabel(detail.model_family)}</p>
                    <p>Incompatible: {(detail.incompatible_generators || []).join(", ") || "—"}</p>
                  </>
                )}
                <p>Trigger: {detail.trigger_words?.length ? detail.trigger_words.join(", ") : "Unknown"}</p>
                <p>Source: {detail.source_provider || "Unknown"}</p>
                <p>Author: {detail.author || "Unknown"}</p>
                <p>License: {detail.license || "Unknown"}</p>
                {detail.strength_from_source && detail.recommended_strength != null ? (
                  <p>Suggested strength from the source: {detail.recommended_strength}</p>
                ) : null}
                <p className="muted">File: {detail.filename || "Unknown"}</p>
                <button type="button" className="ghost tiny" onClick={() => setShowTechnical((value) => !value)}>
                  View details
                </button>
                {showTechnical ? <p className="muted">SHA-256: {detail.checksum_sha256 || "Unknown"}</p> : null}
              </div>
            ) : null}

            {removeTarget ? (
              <div className="panel" data-testid="lora-remove-panel">
                <h3>Remove {removeTarget.name}</h3>
                {removeTarget.owned_by === "adept" ? (
                  <label>
                    <input type="checkbox" checked={deleteFile} onChange={(event) => setDeleteFile(event.target.checked)} /> Delete model file from disk
                  </label>
                ) : (
                  <p>This file was already on the computer. Removing it from Adept UI leaves the file in place.</p>
                )}
                <div className="row" style={{ gap: "0.5rem" }}>
                  <button
                    type="button"
                    className="primary"
                    disabled={busy}
                    onClick={() =>
                      void run(async () => {
                        await api.loras.remove(removeTarget.id, removeTarget.owned_by === "adept" && deleteFile, true);
                        onMessage(
                          removeTarget.owned_by === "adept" && deleteFile
                            ? `${removeTarget.name} was removed and the downloaded file was deleted.`
                            : `${removeTarget.name} was removed from Adept UI.`,
                        );
                        setRemoveTarget(null);
                      })
                    }
                  >
                    Remove from Adept UI
                  </button>
                  <button type="button" className="ghost" onClick={() => setRemoveTarget(null)}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      ) : null}
    </section>
  );
}
