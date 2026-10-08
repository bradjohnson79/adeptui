import { useMemo, useState } from "react";
import { api } from "../api";
import { formatBytes } from "./helpers";
import type { SetupComponentStatus } from "./types";

type HardwareScan = {
  gpu?: {
    ok?: boolean;
    gpus?: Array<{ name?: string; memory_total_mib?: number }>;
  };
  freeBytes?: number | null;
  systemRamBytes?: number | null;
};

type Step = "intro" | "system" | "choose" | "review" | "install" | "done";

const OPTIONAL_CATEGORIES = new Set([
  "Video Models",
  "Still Image Models",
  "Image Generation",
  "Character Voice Models",
  "Music Runtimes",
]);

function isListedOptional(component: SetupComponentStatus): boolean {
  if (component.required || component.experimental) return false;
  const blob = `${component.id} ${component.name} ${component.category || ""}`.toLowerCase();
  if (/scenecraft|sensenova|spatial.?upscaler|retired|creative pack|draft|lora/.test(blob)) return false;
  return OPTIONAL_CATEGORIES.has(component.category || "");
}

function isInstalled(component: SetupComponentStatus): boolean {
  return component.status === "ready" || component.status === "update_available";
}

function downloadBytes(component: SetupComponentStatus): number {
  return component.expected_download_bytes || component.download_bytes || component.download_size_bytes || 0;
}

function installedBytes(component: SetupComponentStatus): number {
  return component.expected_installed_bytes || component.installed_bytes || component.installed_size_bytes || downloadBytes(component);
}

function roundGb(bytes: number | null | undefined): string {
  if (!bytes || bytes <= 0) return "Unavailable";
  return `${Math.round(bytes / (1024 ** 3))} GB`;
}

function vramGb(hardware: HardwareScan | null): number | null {
  const mib = hardware?.gpu?.gpus?.[0]?.memory_total_mib;
  if (!mib || mib <= 0) return null;
  return Math.round(mib / 1024);
}

function guidance(component: SetupComponentStatus, hardware: HardwareScan | null): string {
  const need = component.vramRecommendationGb ?? component.recommended_vram_gb ?? null;
  const vram = vramGb(hardware);
  const gpuOk = Boolean(hardware?.gpu?.ok || (vram && vram > 0));
  const free = hardware?.freeBytes ?? null;
  const bytes = downloadBytes(component);
  if (!gpuOk) return "UNSUPPORTED HARDWARE";
  if (!isInstalled(component) && free != null && bytes > free) return "INSUFFICIENT STORAGE";
  if (need && vram && vram < need) return "MAY RUN SLOWLY";
  if (need && need >= 20) return "HIGH RESOURCE REQUIREMENT";
  if ((component.badges || []).some((badge) => badge.toLowerCase() === "recommended")) {
    return "RECOMMENDED FOR YOUR SYSTEM";
  }
  if (need && vram && vram >= need && need <= 16) return "RECOMMENDED FOR YOUR SYSTEM";
  return "COMPATIBLE";
}

export function OptionalToolsWizard({
  open,
  components,
  onClose,
  onRefresh,
  onNeedLicense,
}: {
  open: boolean;
  components: SetupComponentStatus[];
  onClose: () => void;
  onRefresh: () => Promise<unknown>;
  onNeedLicense: (component: SetupComponentStatus) => void;
}) {
  const [step, setStep] = useState<Step>("intro");
  const [hardware, setHardware] = useState<HardwareScan | null>(null);
  const [scanning, setScanning] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [installedNames, setInstalledNames] = useState<string[]>([]);

  const tools = useMemo(() => components.filter(isListedOptional), [components]);
  const groups = useMemo(() => {
    const byCategory = new Map<string, SetupComponentStatus[]>();
    for (const tool of tools) {
      const category = tool.category || "Optional";
      const list = byCategory.get(category) || [];
      list.push(tool);
      byCategory.set(category, list);
    }
    return [...byCategory.entries()];
  }, [tools]);

  if (!open) return null;

  const chosen = tools.filter((tool) => selected.has(tool.id) && !isInstalled(tool));
  const downloadTotal = chosen.reduce((sum, tool) => sum + downloadBytes(tool), 0);
  const storageTotal = chosen.reduce((sum, tool) => sum + installedBytes(tool), 0);
  const free = hardware?.freeBytes ?? null;
  const storageShort = free != null && storageTotal > free;
  const vram = vramGb(hardware);
  const gpuName = hardware?.gpu?.gpus?.[0]?.name || "Not detected";

  const scan = async () => {
    setScanning(true);
    setNote(null);
    try {
      const next = await api.setupLifecycleHardware();
      setHardware(next as HardwareScan);
      setStep("system");
    } catch (error) {
      setNote(error instanceof Error ? error.message : String(error));
    } finally {
      setScanning(false);
    }
  };

  const toggle = (component: SetupComponentStatus) => {
    if (isInstalled(component)) return;
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(component.id)) next.delete(component.id);
      else next.add(component.id);
      return next;
    });
  };

  const selectRecommended = () => {
    setSelected(new Set(
      tools
        .filter((tool) => !isInstalled(tool) && guidance(tool, hardware) === "RECOMMENDED FOR YOUR SYSTEM")
        .map((tool) => tool.id),
    ));
  };

  const begin = async () => {
    if (storageShort) {
      setNote(`These selections require approximately ${formatBytes(storageTotal)}, but the configured model drive has ${formatBytes(free)} available.`);
      return;
    }
    setStep("install");
    setNote(null);
    const finished: string[] = [];
    try {
    for (const tool of chosen) {
      const live = components.find((item) => item.id === tool.id) || tool;
      if (isInstalled(live)) {
        finished.push(live.name);
        continue;
      }
      if (live.model_license && !live.model_license.installationUnlocked) {
        onNeedLicense(live);
        setNote(`${live.name} needs its existing license acknowledgement before installation.`);
        setStep("review");
        return;
      }
      setActiveId(live.id);
      if (live.install_kind === "detect_only" || live.installer === "detect_only") {
        await api.setupRecommendedAction(live.id);
        await api.setupLifecycleVerify(live.id);
      } else {
        await api.installJobs.create(live.id, {
          action: "install",
          confirm: true,
          confirmDownloadModels: true,
        });
      }
      finished.push(live.name);
      await onRefresh();
    }
    setActiveId(null);
    setInstalledNames(finished);
    setStep("done");
    await onRefresh();
    } catch (error) {
      setActiveId(null);
      setNote(error instanceof Error ? error.message : String(error));
      setStep("review");
    }
  };

  return (
    <div className="setup-dialog-backdrop" role="presentation">
      <div className="setup-dialog setup-installer" role="dialog" aria-modal="true" aria-labelledby="optional-tools-title" data-testid="optional-tools-wizard">
        <header className="setup-dialog-header">
          <h2 id="optional-tools-title">
            {step === "done" ? "Optional tools installed" : "Expand Adept UI"}
          </h2>
        </header>
        {step === "intro" && (
          <div>
            <p>Add optional models and tools based on what you want to create. Adept UI will check your hardware and storage and help you choose.</p>
            <button type="button" className="primary" data-testid="optional-tools-scan" disabled={scanning} onClick={() => void (hardware ? setStep("system") : scan())}>
              {scanning ? "Scanning…" : hardware ? "Use recent scan" : "Scan My System"}
            </button>
          </div>
        )}
        {step === "system" && (
          <div data-testid="optional-tools-system">
            <h3>Your system</h3>
            <ul>
              <li>GPU: {gpuName}</li>
              <li>VRAM: {vram ? `${vram} GB` : "Unavailable"}</li>
              <li>System RAM: {roundGb(hardware?.systemRamBytes)}</li>
              <li>Available model storage: {free == null ? "Unavailable" : formatBytes(free)}</li>
              <li>Current local models: {tools.filter(isInstalled).length}</li>
            </ul>
            <p>Adept UI has evaluated which optional tools are suitable for this computer.</p>
            <button type="button" className="primary" onClick={() => setStep("choose")}>Next</button>
          </div>
        )}
        {step === "choose" && (
          <div data-testid="optional-tools-choose">
            <p>
              {vram
                ? `Based on your ${vram} GB GPU, tools marked Recommended fit this computer. Optional tools add generation choices and are not required.`
                : "Optional tools add generation choices and are not required. Hardware guidance appears after a system scan."}
            </p>
            <button type="button" data-testid="optional-tools-select-recommended" onClick={selectRecommended}>Select Recommended</button>
            {groups.map(([category, items]) => (
              <section key={category}>
                <h3>{category}</h3>
                <ul>
                  {items.map((item) => {
                    const installed = isInstalled(item);
                    const fit = guidance(item, hardware);
                    return (
                      <li key={item.id} data-testid={`optional-tool-${item.id}`}>
                        <label>
                          <input
                            type="checkbox"
                            checked={installed || selected.has(item.id)}
                            disabled={installed || fit === "UNSUPPORTED HARDWARE" || fit === "INSUFFICIENT STORAGE"}
                            onChange={() => toggle(item)}
                          />
                          <strong>{item.name}</strong>
                        </label>
                        <div>{installed ? "✓ INSTALLED" : "OPTIONAL — NOT INSTALLED"}</div>
                        <div>{(item.bestFor || []).slice(0, 3).join(" · ") || item.description}</div>
                        <div>Download: {item.downloadSizeLabel || formatBytes(downloadBytes(item))}</div>
                        <div>Hardware: {fit}</div>
                        {item.vramRecommendationGb ? <div>VRAM guidance: {item.vramRecommendationGb} GB</div> : null}
                      </li>
                    );
                  })}
                </ul>
              </section>
            ))}
            <p>
              Selected: {chosen.length} optional tools. Download: {formatBytes(downloadTotal)}. Storage after installation: {formatBytes(storageTotal)}.
              {free != null ? ` Available: ${formatBytes(free)}.` : ""}
            </p>
            <div className="row-actions">
              <button type="button" onClick={() => setStep("system")}>Back</button>
              <button type="button" className="primary" disabled={chosen.length === 0 || storageShort} onClick={() => setStep("review")}>Review</button>
            </div>
          </div>
        )}
        {step === "review" && (
          <div data-testid="optional-tools-review">
            <h3>Optional installation plan</h3>
            <ul>{chosen.map((item) => <li key={item.id}>{item.name}</li>)}</ul>
            <p>Download: {formatBytes(downloadTotal)}</p>
            <p>Required storage: {formatBytes(storageTotal)}</p>
            <p>Hardware compatibility: {storageShort ? "Not enough storage" : "Compatible"}</p>
            <p>Existing components will not be downloaded again.</p>
            {storageShort && (
              <p>These selections require approximately {formatBytes(storageTotal)}, but the configured model drive has {formatBytes(free)} available.</p>
            )}
            <div className="row-actions">
              <button type="button" onClick={() => setStep("choose")}>Back</button>
              <button type="button" className="primary" data-testid="optional-tools-begin" disabled={storageShort} onClick={() => void begin()}>Begin Installation</button>
            </div>
          </div>
        )}
        {step === "install" && (
          <div data-testid="optional-tools-install">
            <ul>
              {chosen.map((item) => {
                const live = components.find((row) => row.id === item.id) || item;
                const label = isInstalled(live)
                  ? "Already Installed"
                  : activeId === item.id
                    ? (live.progress != null ? `Downloading… ${Math.round(live.progress)}%` : (live.stage || "Working"))
                    : "Waiting";
                return <li key={item.id}>{item.name} — {label}</li>;
              })}
            </ul>
          </div>
        )}
        {step === "done" && (
          <div data-testid="optional-tools-done">
            <p>Adept UI has added these tools to your production environment.</p>
            <ul>{installedNames.map((name) => <li key={name}>✓ {name}</li>)}</ul>
            <button type="button" className="primary" data-testid="optional-tools-finish" onClick={onClose}>Finish</button>
          </div>
        )}
        {note && <p role="status">{note}</p>}
        {step !== "install" && step !== "done" && (
          <button type="button" className="ghost" onClick={onClose}>Close</button>
        )}
      </div>
    </div>
  );
}
