import { useState } from "react";
import { api } from "../api";
import { comfyInstallCommand, comfyInstallRequired, type ComfyPlatform } from "./comfyInstall";

function browserPlatform(): ComfyPlatform {
  const ua = typeof navigator === "undefined" ? "" : navigator.userAgent.toLowerCase();
  if (ua.includes("win")) return "windows";
  if (ua.includes("mac")) return "mac";
  if (ua.includes("linux")) return "linux";
  return "other";
}

/**
 * Terminal install instructions appear only when this profile still needs
 * ComfyUI and it is not already available. Full API never shows them.
 */
export function SetupComfyStep({
  profile,
  selectedLocalIds,
  comfyReady,
  comfyInstalled,
  onRescan,
}: {
  profile: "local" | "hybrid" | "api" | "";
  selectedLocalIds: string[];
  comfyReady: boolean;
  comfyInstalled: boolean;
  onRescan: () => Promise<void> | void;
}) {
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const needed = profile === "local" || profile === "hybrid"
    ? comfyInstallRequired(profile, selectedLocalIds, comfyReady)
    : false;
  if (!needed) return null;

  const command = comfyInstallCommand(browserPlatform());

  const rescan = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.rescanComfy();
      setMessage(result.message);
      await onRescan();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ComfyUI could not be checked.");
    } finally {
      setBusy(false);
    }
  };

  const connectExisting = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const picked = await api.setupBrowsePath({
        mode: "directory",
        component_id: "comfyui",
        title: "Choose your ComfyUI folder",
      });
      if (!picked.path || picked.cancelled) return;
      const result = await api.connectExistingComfy(picked.path);
      setMessage(result.message);
      await onRescan();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "That folder could not be connected.");
    } finally {
      setBusy(false);
    }
  };

  const startExisting = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.runtimeManagerRestartComfy();
      setMessage("Adept asked the existing ComfyUI installation to start.");
      await onRescan();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "ComfyUI did not start.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="panel" aria-label="Install ComfyUI" data-testid="setup-comfy-step">
      <h2>Install ComfyUI</h2>
      {comfyInstalled ? (
        <p>ComfyUI is already on this computer. Adept can start that installation.</p>
      ) : (
        <>
          <p>ComfyUI is used to run your selected local AI generation tools.</p>
          <p>Copy the command below, paste it into your terminal, and follow the prompts.</p>
          <p data-testid="comfy-install-command"><code>{command}</code></p>
        </>
      )}
      <div className="row-actions">
        {comfyInstalled ? (
          <button type="button" data-testid="setup-comfy-start" disabled={busy} onClick={() => void startExisting()}>
            Start existing installation
          </button>
        ) : (
          <button
            type="button"
            data-testid="copy-comfy-install"
            onClick={() => void navigator.clipboard?.writeText(command)}
          >
            Copy command
          </button>
        )}
        <button type="button" data-testid="setup-comfy-rescan" disabled={busy} onClick={() => void rescan()}>
          Re-scan System
        </button>
        <button type="button" disabled={busy} onClick={() => void connectExisting()}>
          Connect Existing Installation
        </button>
      </div>
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
