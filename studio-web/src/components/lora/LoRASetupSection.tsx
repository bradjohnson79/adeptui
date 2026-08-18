import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import { clearLoraSelectorCache } from "./loraClient";

const FAMILY_LABELS: Record<string, string> = {
  sdxl: "SDXL / SD",
  flux: "FLUX",
  "qwen-image": "Qwen Image",
  zimage: "Z-Image",
  krea2: "Krea 2",
  ltx: "LTX Video",
  wan: "WAN",
  hunyuan: "Hunyuan",
  unassigned: "Unassigned",
};

function familyLabel(family: string | undefined): string {
  return family ? FAMILY_LABELS[family] || family : "—";
}

/**
 * Setup Wizard LoRA section - one management surface over the shared registry.
 * Optional: setup completes fine with zero LoRAs installed.
 */
export function LoRASetupSection({ onMessage }: { onMessage: (message: string) => void }) {
  const [loras, setLoras] = useState<any[]>([]);
  const [catalog, setCatalog] = useState<any[]>([]);
  const [scan, setScan] = useState<any[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [registerPath, setRegisterPath] = useState("");
  const [registerFamily, setRegisterFamily] = useState("unassigned");
  const [open, setOpen] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const [listRes, catRes, scanRes] = await Promise.all([
        api.loras.list(),
        api.loras.catalog(),
        api.loras.scan(),
      ]);
      setLoras(listRes.loras || []);
      setCatalog(catRes.items || []);
      setScan(scanRes.candidates || []);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : String(error));
    }
  }, [onMessage]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const run = async (id: string, fn: () => Promise<any>, success: string) => {
    setBusyId(id);
    try {
      await fn();
      onMessage(success);
      clearLoraSelectorCache();
      await refresh();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : String(error));
    } finally {
      setBusyId(null);
    }
  };

  const unregistered = scan.filter((candidate) => !candidate.registered);
  const installedCatalogIds = new Set(loras.map((l) => l.catalog_id).filter(Boolean));
  const catalogNotInstalled = catalog.filter((item) => !installedCatalogIds.has(item.id));

  return (
    <section className="panel setup-component-section" data-testid="lora-setup-section">
      <div className="setup-section-heading">
        <div>
          <h2>LoRAs</h2>
          <p>
            Optional model adapters for style, identity, motion, or other specialized behavior.
            Installed LoRAs appear in the Advanced section of compatible generators.
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => setOpen((v) => !v)}>
          {open ? "Hide" : "Manage"}
        </button>
      </div>
      {!open ? null : (
        <>
          {unregistered.length > 0 ? (
            <div className="setup-lora-detect" data-testid="lora-detect-block">
              <h3>Detected files</h3>
              <p className="muted">
                {unregistered.length} LoRA file{unregistered.length === 1 ? "" : "s"} found in shared model storage.
              </p>
              <button
                type="button"
                className="primary"
                disabled={busyId !== null}
                onClick={() =>
                  void run(
                    "detect",
                    () => api.loras.detect(true),
                    `Registered ${unregistered.length} discovered LoRA file${unregistered.length === 1 ? "" : "s"}.`,
                  )
                }
              >
                Register detected files
              </button>
            </div>
          ) : null}

          <div className="setup-lora-register">
            <h3>Register a local LoRA file</h3>
            <div className="row" style={{ gap: "0.5rem", alignItems: "center", flexWrap: "wrap" }}>
              <input
                type="text"
                value={registerPath}
                onChange={(e) => setRegisterPath(e.target.value)}
                placeholder="C:\\models\\loras\\my_lora.safetensors"
                style={{ minWidth: "24rem" }}
                data-testid="lora-register-path"
              />
              <select value={registerFamily} onChange={(e) => setRegisterFamily(e.target.value)} data-testid="lora-register-family">
                {Object.entries(FAMILY_LABELS).map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
              <button
                type="button"
                disabled={busyId !== null || !registerPath.trim()}
                onClick={() =>
                  void run(
                    "register",
                    () => api.loras.register({ path: registerPath.trim(), modelFamily: registerFamily }),
                    "LoRA registered.",
                  )
                }
              >
                Register
              </button>
            </div>
          </div>

          <h3>Installed ({loras.length})</h3>
          {!loras.length ? (
            <p className="empty">No LoRAs registered. Detected files or catalog downloads appear here.</p>
          ) : (
            <ul className="home-list" data-testid="lora-registered-list">
              {loras.map((lora) => (
                <li key={lora.id} className={lora.enabled ? "" : "muted"}>
                  <div>
                    <strong>{lora.name}</strong>
                    <span className="muted">
                      {" "}· {familyLabel(lora.model_family)} · {lora.category} · Status: {lora.install_status}
                      {lora.install_status === "missing" ? " (file missing)" : ""}
                    </span>
                  </div>
                  <div className="row" style={{ gap: "0.4rem" }}>
                    {lora.enabled ? (
                      <button
                        type="button"
                        className="ghost"
                        disabled={busyId !== null}
                        onClick={() => void run("disable:" + lora.id, () => api.loras.disable(lora.id), `${lora.name} disabled.`)}
                      >
                        Disable
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="ghost"
                        disabled={busyId !== null}
                        onClick={() => void run("enable:" + lora.id, () => api.loras.enable(lora.id), `${lora.name} enabled.`)}
                      >
                        Enable
                      </button>
                    )}
                    <button
                      type="button"
                      className="ghost"
                      disabled={busyId !== null}
                      onClick={() => {
                        if (!window.confirm(`Remove ${lora.name} from the LoRA registry? Previously generated media stays intact.`)) return;
                        void run("remove:" + lora.id, () => api.loras.remove(lora.id), `${lora.name} removed from registry.`);
                      }}
                    >
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          <h3>Curated downloads (optional)</h3>
          {!catalogNotInstalled.length ? (
            <p className="empty">All curated LoRAs are installed.</p>
          ) : (
            <ul className="home-list" data-testid="lora-catalog-list">
              {catalogNotInstalled.map((item) => (
                <li key={item.id}>
                  <div>
                    <strong>{item.name}</strong>
                    <span className="muted">
                      {" "}· {item.compatible_model_families.map(familyLabel).join(", ") || "—"} · {item.category}
                      {" "}· {Math.round(item.file_size_mb)} MB · {item.license}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="primary"
                    disabled={busyId !== null}
                    onClick={() => {
                      if (!window.confirm(`Download ${item.name} (${Math.round(item.file_size_mb)} MB)? Nothing is downloaded silently.`)) return;
                      void run("dl:" + item.id, () => api.loras.download(item.id, true), `${item.name}: install started.`);
                    }}
                  >
                    Download
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </section>
  );
}
