import { useEffect, useRef } from "react";
import { ProviderSourceSelector } from "../audioProvider/ProviderSourceSelector";
import { useAudioStudioProviderSource } from "../../audioProvider/useProviderSource";
import type { ProductionDockApi } from "./useProductionDock";

/**
 * ORDER 15 / LANE B — Footer Dock Audio dropdown.
 * Audio Studio providers only (Local | API — ElevenLabs). No LLM/model registry list.
 * Label syncs with Systems capabilityLabel / health.displayName.
 */
export function AudioMenu(props: { open: boolean; dock: ProductionDockApi; onClose: () => void }) {
  const { open, onClose } = props;
  const panelRef = useRef<HTMLDivElement>(null);
  const audioProvider = useAudioStudioProviderSource();
  const elevenLabel = audioProvider.health?.displayName || "API — ElevenLabs";

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      ref={panelRef}
      className="production-dock-drawer production-dock-drawer--audio-providers"
      role="dialog"
      aria-modal="true"
      aria-label="Audio"
      tabIndex={-1}
      data-testid="production-dock-menu-audio"
    >
      <div className="production-dock-drawer__header">
        <h3>Audio</h3>
        <button type="button" className="production-dock-collapse-btn" aria-label="Close Audio" onClick={onClose}>
          ×
        </button>
      </div>
      <p className="production-dock-drawer__provenance">
        Audio Studio provider · {audioProvider.source === "elevenlabs" ? elevenLabel : "Local"}
      </p>
      <div className="production-dock-drawer__audio-provider" data-testid="dock-audio-studio-provider">
        <ProviderSourceSelector
          id="dock-audio"
          label="Audio Studio provider"
          source={audioProvider.source}
          onChange={audioProvider.setSource}
          health={audioProvider.health}
          healthBusy={audioProvider.healthBusy}
        />
        <p className="production-dock-drawer__audio-note">
          Audio providers only — Local or {elevenLabel}. Syncs with Audio Studio. Voice Studio keeps its own provider.
          Model lists for LLM / video / image stay in their own dock menus.
        </p>
      </div>
    </div>
  );
}
