import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import { formatBytes } from "./helpers";
import type { FirstRunScan } from "./firstRun";
import { scanAllowsCompletion } from "./firstRun";
import type { SetupComponentStatus, SetupStatusResponse } from "./types";

type WizardStep = "choice" | "details" | "providers" | "comfy" | "review" | "install" | "done" | "blocked";

const OFFICIAL_COMFY_DOWNLOAD = "https://www.comfy.org/download";
type InstallProfile = "local" | "api" | "hybrid";

const PROVIDERS = [
  { id: "fal", name: "fal.ai", detail: "Hosted image and video models." },
  { id: "kie", name: "kie.ai", detail: "Hosted image, video, and voice models." },
  { id: "wavespeed", name: "Wavespeed.ai", detail: "Hosted image and video models." },
  { id: "elevenlabs", name: "ElevenLabs", detail: "Hosted voice, sound, and music." },
] as const;

const LOCAL_BASELINE = ["zimage_models", "ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"];
const LTX_GROUP = ["ltx_2_5_checkpoint", "ltx_2_5_text_encoder", "ltx_2_5_video_vae"];

const PROFILE_COPY: Record<InstallProfile, { title: string; body: string }> = {
  local: {
    title: "Local AI Models",
    body: "I want to use local AI models through my computer. I have sufficient storage and compatible hardware.",
  },
  api: {
    title: "Commercial API Models",
    body: "I want to use commercial API models through Adept UI, using my own provider API keys.",
  },
  hybrid: {
    title: "Custom Hybrid Installation",
    body: "I want to choose which local AI models to install and connect commercial API providers.",
  },
};

function clientPlatform(): "windows" | "mac" | "linux" | "other" {
  const value = `${navigator.platform || ""} ${navigator.userAgent || ""}`.toLowerCase();
  if (value.includes("win")) return "windows";
  if (value.includes("mac")) return "mac";
  if (value.includes("linux")) return "linux";
  return "other";
}

function withLtxGroup(selected: string[]): string[] {
  const next = new Set(selected);
  if (LTX_GROUP.some((id) => next.has(id))) {
    LTX_GROUP.forEach((id) => next.add(id));
  }
  return [...next];
}

export function FirstRunSetupModal({
  status,
  installing,
  onRescan,
  onSaveProfile,
  onBegin,
  onFinish,
}: {
  status: SetupStatusResponse;
  scanning: boolean;
  installing: boolean;
  onRescan: () => Promise<SetupStatusResponse | null>;
  onSaveProfile: (body: {
    profile: InstallProfile;
    selectedLocalModels: string[];
    selectedProviders: string[];
  }) => Promise<SetupStatusResponse | null>;
  onBegin: () => Promise<{ errors?: { id: string; message: string }[] } | void>;
  onFinish: () => void;
}) {
  const saved = status.installationProfile;
  const [step, setStep] = useState<WizardStep>("choice");
  const [profile, setProfile] = useState<InstallProfile>(saved || "api");
  const [selectedModels, setSelectedModels] = useState<string[]>(status.selectedLocalModels || []);
  const [providerIds, setProviderIds] = useState<string[]>(status.selectedProviders || status.connectedProviders?.map((item) => item.id) || []);
  const [pendingDisconnect, setPendingDisconnect] = useState<string[]>([]);
  const [keys, setKeys] = useState<Record<string, string>>({});
  const [showKey, setShowKey] = useState<Record<string, boolean>>({});
  const [providerMessage, setProviderMessage] = useState<string | null>(null);
  const [shortcut, setShortcut] = useState(true);
  const [shortcutMessage, setShortcutMessage] = useState<string | null>(null);
  const [installErrors, setInstallErrors] = useState<{ id: string; message: string }[]>([]);
  const [comfyMessage, setComfyMessage] = useState<string | null>(null);
  const [comfyProbe, setComfyProbe] = useState<boolean | null>(null);
  const [exitAsk, setExitAsk] = useState(false);
  const platform = clientPlatform();
  const scan: FirstRunScan | undefined = status.firstRunScan;
  const byId = useMemo(() => new Map(status.components.map((component) => [component.id, component])), [status.components]);
  const modelChoices = status.components.filter((component) => {
    const category = component.category || "";
    return category === "Video Models" || category === "Still Image Models" || category === "Image Generation";
  });

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape" && step !== "done" && step !== "install") setExitAsk(true);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [step]);

  const chosenRows = (profile === "local"
    ? LOCAL_BASELINE
    : profile === "hybrid"
      ? withLtxGroup(selectedModels)
      : []
  ).map((id) => byId.get(id)).filter((row): row is SetupComponentStatus => Boolean(row));

  const comfyReady = comfyProbe ?? byId.get("comfyui")?.status === "ready";
  const comfyRequired = profile === "local" || (profile === "hybrid" && withLtxGroup(selectedModels).length > 0);
  const stepAfterLocalChoices = comfyRequired && !comfyReady ? "comfy" : "review";

  const openOfficialComfyDownload = () => {
    const desktop = (window as Window & {
      adeptDesktop?: { openExternal?: (url: string) => Promise<unknown> };
    }).adeptDesktop;
    if (desktop?.openExternal) {
      void desktop.openExternal(OFFICIAL_COMFY_DOWNLOAD);
      return;
    }
    window.open(OFFICIAL_COMFY_DOWNLOAD, "_blank", "noopener,noreferrer");
  };

  const rescanComfy = async () => {
    setComfyMessage(null);
    try {
      const result = await api.rescanComfy();
      setComfyProbe(result.healthy);
      setComfyMessage(result.message);
      await onRescan();
    } catch (error) {
      setComfyMessage(error instanceof Error ? error.message : "ComfyUI could not be checked.");
    }
  };

  const connectExistingComfy = async () => {
    setComfyMessage(null);
    try {
      const picked = await api.setupBrowsePath({
        mode: "directory",
        component_id: "comfyui",
        title: "Choose your ComfyUI folder",
      });
      if (!picked.path || picked.cancelled) return;
      const result = await api.connectExistingComfy(picked.path);
      setComfyProbe(result.healthy);
      setComfyMessage(result.message);
      await onRescan();
    } catch (error) {
      setComfyMessage(error instanceof Error ? error.message : "That folder could not be connected.");
    }
  };

  const missingBytes = chosenRows.reduce((sum, row) => (
    row.status === "ready" ? sum : sum + (row.download_bytes || 0)
  ), 0);

  const modelsForProfile = profile === "local" ? LOCAL_BASELINE : profile === "hybrid" ? withLtxGroup(selectedModels) : [];

  const connectProvider = (providerId: string) => {
    const value = (keys[providerId] || "").trim();
    if (!value) return;
    setProviderIds((current) => current.includes(providerId) ? current : [...current, providerId]);
    setPendingDisconnect((current) => current.filter((id) => id !== providerId));
    setProviderMessage("The key stays on this screen until you choose Begin Setup.");
  };

  const runInstall = async () => {
    setStep("install");
    setProviderMessage(null);
    for (const providerId of pendingDisconnect) {
      try {
        await api.hostedProvidersClear(providerId);
      } catch (error) {
        setProviderMessage(error instanceof Error ? error.message : "A provider could not be disconnected.");
        setStep("blocked");
        return;
      }
    }
    const connected: string[] = [];
    for (const provider of PROVIDERS) {
      const value = (keys[provider.id] || "").trim();
      const already = (status.connectedProviders || []).some((item) => item.id === provider.id)
        && !pendingDisconnect.includes(provider.id);
      if (!value && !already && !providerIds.includes(provider.id)) continue;
      if (value) {
        try {
          await api.hostedProvidersConnect(provider.id, value);
          const tested = await api.hostedProvidersTest(provider.id);
          if (tested && tested.ok === false) {
            setProviderMessage(tested.message || tested.probe?.message || `${provider.name} did not accept that key.`);
            setStep("providers");
            return;
          }
          connected.push(provider.id);
        } catch (error) {
          setProviderMessage(error instanceof Error ? error.message : `${provider.name} could not be checked.`);
          setStep("providers");
          return;
        }
      } else if (already || providerIds.includes(provider.id)) {
        connected.push(provider.id);
      }
    }
    const saved = await onSaveProfile({
      profile,
      selectedLocalModels: modelsForProfile,
      selectedProviders: connected,
    });
    if (!saved) {
      setStep("blocked");
      return;
    }
    if (shortcut && platform !== "windows") {
      const desktop = (window as Window & {
        adeptDesktop?: { createDesktopShortcut?: () => Promise<{ ok?: boolean; message?: string }> };
      }).adeptDesktop;
      if (desktop?.createDesktopShortcut) {
        try {
          const result = await desktop.createDesktopShortcut();
          setShortcutMessage(result?.message || null);
        } catch {
          setShortcutMessage("The desktop did not accept the shortcut. Adept UI can still start.");
        }
      }
    }
    const applied = await onBegin();
    const applyErrors = applied?.errors || [];
    setInstallErrors(applyErrors);
    for (let pass = 0; pass < 180; pass += 1) {
      const next = await onRescan();
      if (scanAllowsCompletion(next?.firstRunScan)) {
        try {
          await api.completeFirstRun();
        } catch {
          /* the scan is the readiness authority; a second save is attempted on finish */
        }
        setStep("done");
        return;
      }
      const working = (next?.components ?? []).some((component) =>
        component.status === "installing" || component.status === "checking",
      );
      if (!working && (applyErrors.length > 0 || pass > 2)) {
        setStep(scanAllowsCompletion(next?.firstRunScan) ? "done" : "blocked");
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 3000));
    }
    setStep("blocked");
  };

  return (
    <div className="setup-dialog-backdrop" role="presentation" data-testid="setup-wizard-modal">
      <section className="setup-dialog setup-installer" role="dialog" aria-modal="true" aria-labelledby="setup-wizard-title">
        <header className="setup-dialog-header">
          <h2 id="setup-wizard-title">
            {step === "done" ? "Adept UI Setup Complete!" : "How would you like to use Adept UI?"}
          </h2>
        </header>

        {exitAsk && step !== "done" ? (
          <>
            <p>No downloads have to start until you choose Begin Setup. Your projects and saved keys stay as they are.</p>
            <div className="row-actions">
              <button type="button" className="primary" onClick={() => setExitAsk(false)}>Continue Setup</button>
              {status.firstRunSetupComplete ? (
                <button type="button" onClick={onFinish}>Leave without changes</button>
              ) : null}
            </div>
          </>
        ) : null}

        {!exitAsk && step === "choice" && (
          <>
            <p>Choose how you want to create with Adept UI. We'll configure the necessary systems for you.</p>
            {(["local", "api", "hybrid"] as const).map((id) => (
              <label key={id} className="setup-choice">
                <input
                  type="radio"
                  name="installation-profile"
                  checked={profile === id}
                  onChange={() => setProfile(id)}
                />
                <span>
                  <strong>{PROFILE_COPY[id].title}</strong>
                  <span>{PROFILE_COPY[id].body}</span>
                </span>
              </label>
            ))}
            {platform !== "windows" && (
              <label className="setup-choice">
                <input type="checkbox" checked={shortcut} onChange={(event) => setShortcut(event.target.checked)} />
                <span>
                  <strong>Create Adept UI Desktop Shortcut</strong>
                  <span>Add an Adept UI icon to your desktop for quick access.</span>
                </span>
              </label>
            )}
            <div className="row-actions">
              <button type="button" className="primary" data-testid="setup-wizard-next" onClick={() => setStep(profile === "api" ? "providers" : "details")}>
                Next
              </button>
            </div>
          </>
        )}

        {!exitAsk && step === "details" && (
          <>
            {profile === "local" && (
              <p>
                Local includes Z-Image Turbo and LTX 2.5, plus the encoder and video VAE those models need, and Creator Engine.
                These stay required for Local. To leave them out, go back and choose API or Hybrid. Nothing is deleted on this screen.
                Files already on this computer are reused.
              </p>
            )}
            {profile === "hybrid" && <p>Choose the local models you want. Required companion files are included with the model. Nothing downloads until you review the plan.</p>}
            <ul>
              {(profile === "local" ? LOCAL_BASELINE.map((id) => byId.get(id)).filter(Boolean) : modelChoices).map((component) => {
                const row = component as SetupComponentStatus;
                const checked = profile === "local" || selectedModels.includes(row.id);
                return (
                  <li key={row.id}>
                    {profile === "hybrid" ? (
                      <label>
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => {
                            setSelectedModels((current) => withLtxGroup(
                              current.includes(row.id) ? current.filter((id) => id !== row.id && !(LTX_GROUP.includes(row.id) && LTX_GROUP.includes(id))) : [...current, row.id],
                            ));
                          }}
                        />
                        {row.name}
                      </label>
                    ) : <strong>{row.name}</strong>}
                    <span>
                      {" "}
                      {row.description ? `${row.description} ` : ""}
                      {row.dependencies?.length ? `Needs ${row.dependencies.join(", ")}. ` : ""}
                      {row.status === "ready" ? "Already installed." : `Download ${formatBytes(row.download_bytes)}`}
                      {row.installed_bytes ? `, about ${formatBytes(row.installed_bytes)} when installed` : ""}.
                      {row.model_license?.licenseName ? ` License: ${row.model_license.licenseName}.` : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
            <p>New downloads about {formatBytes(missingBytes)}. Free space {formatBytes(scan?.freeBytes)}.</p>
            <div className="row-actions">
              <button type="button" onClick={() => setStep("choice")}>Back</button>
              <button type="button" className="primary" onClick={() => setStep(profile === "hybrid" ? "providers" : stepAfterLocalChoices)}>
                {profile === "hybrid" ? "Next" : comfyRequired && !comfyReady ? "Next" : "Review"}
              </button>
            </div>
          </>
        )}

        {!exitAsk && step === "providers" && (
          <>
            <p>Connect the providers you want to use. You do not need all of them. Keys stay hidden and are not written into your project.</p>
            {(status.connectedProviders || []).length > 0 && (
              <p>Already connected: {status.connectedProviders?.map((item) => item.name).join(", ")}.</p>
            )}
            {PROVIDERS.map((provider) => (
              <div key={provider.id}>
                <strong>{provider.name}</strong>
                <p>{provider.detail}</p>
                <input
                  type={showKey[provider.id] ? "text" : "password"}
                  autoComplete="off"
                  value={keys[provider.id] || ""}
                  aria-label={`${provider.name} API key`}
                  onChange={(event) => setKeys((current) => ({ ...current, [provider.id]: event.target.value }))}
                />
                <button type="button" onClick={() => setShowKey((current) => ({ ...current, [provider.id]: !current[provider.id] }))}>
                  {showKey[provider.id] ? "Hide key" : "Show key"}
                </button>
                <button type="button" onClick={() => void connectProvider(provider.id)}>Test Connection</button>
                <button type="button" onClick={() => {
                  setPendingDisconnect((current) => current.includes(provider.id) ? current : [...current, provider.id]);
                  setProviderIds((current) => current.filter((id) => id !== provider.id));
                  setKeys((current) => ({ ...current, [provider.id]: "" }));
                }}>Remove</button>
              </div>
            ))}
            {providerMessage && <p role="status">{providerMessage}</p>}
            <div className="row-actions">
              <button type="button" onClick={() => setStep(profile === "api" ? "choice" : "details")}>Back</button>
              <button type="button" className="primary" onClick={() => setStep(stepAfterLocalChoices)}>Review</button>
            </div>
          </>
        )}

        {!exitAsk && step === "review" && (
          <>
            <p>Adept UI will install only what is missing. Projects, media, and keys you already saved stay in place. Adept UI does not download ComfyUI.</p>
            {profile === "api" && <p>ComfyUI is not required for Commercial API Models.</p>}
            {profile === "hybrid" && comfyRequired && !comfyReady && (
              <p>Commercial API providers can be connected now. Local generation stays incomplete until ComfyUI is running. This Hybrid setup is not finished until both sides check out.</p>
            )}
            {profile !== "api" && comfyReady && <p>ComfyUI is running.</p>}
            <ul>
              {chosenRows.filter((row) => row.status === "ready").map((row) => <li key={row.id}>Reuse {row.name}</li>)}
              {chosenRows.filter((row) => row.status !== "ready").map((row) => <li key={row.id}>Add {row.name}</li>)}
              {profile === "api" && <li>No local model downloads.</li>}
              {(status.connectedProviders || [])
                .filter((item) => !pendingDisconnect.includes(item.id))
                .map((item) => <li key={item.id}>Keep {item.name}</li>)}
              {providerIds.filter((id) => !(status.connectedProviders || []).some((item) => item.id === id)).map((id) => (
                <li key={id}>Connect {PROVIDERS.find((item) => item.id === id)?.name || id}</li>
              ))}
            </ul>
            <p>New downloads about {formatBytes(missingBytes)}. Free space {formatBytes(scan?.freeBytes)}.</p>
            {scan?.storageShortfall && <p>There is not enough free space for the selected downloads.</p>}
            <div className="row-actions">
              <button type="button" onClick={() => setStep("choice")}>Back</button>
              <button type="button" className="primary" data-testid="setup-wizard-begin" disabled={installing} onClick={() => void runInstall()}>
                Begin Setup
              </button>
            </div>
          </>
        )}

        {!exitAsk && step === "comfy" && (
          <>
            <p>Install and launch ComfyUI before continuing with local generation. Adept UI will detect it. Adept UI does not download or start ComfyUI.</p>
            {profile === "hybrid" && (
              <p>Commercial API providers can be configured while this is pending. Local models stay incomplete until ComfyUI is running, so Hybrid is not certified yet.</p>
            )}
            <p>{comfyReady ? "ComfyUI is running." : "ComfyUI is not running."}</p>
            {comfyMessage && <p role="status">{comfyMessage}</p>}
            <div className="row-actions">
              <button type="button" onClick={() => setStep(profile === "hybrid" ? "providers" : "details")}>Back</button>
              <button type="button" onClick={openOfficialComfyDownload}>Official ComfyUI Download</button>
              <button type="button" onClick={() => void rescanComfy()}>Re-scan ComfyUI</button>
              <button type="button" onClick={() => void connectExistingComfy()}>Connect Existing Installation</button>
              <button type="button" className="primary" disabled={!comfyReady} onClick={() => setStep("review")}>Review</button>
            </div>
          </>
        )}

        {!exitAsk && step === "install" && (
          <p role="status">{installing ? "Setting up the pieces that are still missing…" : "Checking what is already installed…"}</p>
        )}

        {!exitAsk && step === "blocked" && (
          <>
            <p>Setup stopped on a specific piece. You can try that piece again. Nothing else was marked finished.</p>
            <ul>
              {installErrors.map((item) => <li key={item.id}>{item.message}</li>)}
              {(scan?.essentialNeeded || []).map((item) => <li key={item.id}>{item.name}</li>)}
            </ul>
            {shortcutMessage && <p>{shortcutMessage}</p>}
            {comfyRequired && !comfyReady && (
              <div className="row-actions">
                <button type="button" onClick={openOfficialComfyDownload}>Official ComfyUI Download</button>
                <button type="button" onClick={() => void rescanComfy()}>Re-scan ComfyUI</button>
                <button type="button" onClick={() => void connectExistingComfy()}>Connect Existing Installation</button>
              </div>
            )}
            {comfyMessage && <p role="status">{comfyMessage}</p>}
            <div className="row-actions">
              <button type="button" className="primary" onClick={() => void runInstall()}>Try Again</button>
            </div>
          </>
        )}

        {!exitAsk && step === "done" && (
          <>
            <p>Your Adept UI production environment is ready.</p>
            <p>You can return to Setup at any time to run the Setup Wizard again.</p>
            <p>From there, you can add or remove local AI models, connect or disconnect commercial API providers, and customize your installation as your creative needs change.</p>
            <p>Essential system components required for Adept UI to operate will remain protected and cannot be removed through the Setup Wizard.</p>
            {shortcutMessage && <p>{shortcutMessage}</p>}
            <div className="row-actions">
              <button type="button" className="primary" data-testid="setup-wizard-continue" onClick={onFinish}>
                Continue to Adept UI
              </button>
            </div>
          </>
        )}
      </section>
    </div>
  );
}
