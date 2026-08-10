import { useCallback, useEffect, useRef } from "react";
import type { Modality } from "../../modelRegistry/contracts";
import { CoDirectorDockControl } from "./CoDirectorDockControl";
import { AudioMenu } from "./AudioMenu";
import { DiagnosticsDrawer } from "./DiagnosticsDrawer";
import { ImageMenu } from "./ImageMenu";
import { LlmMenu } from "./LlmMenu";
import { ProviderSetupModal } from "./ProviderSetupModal";
import { ProviderSwitchConfirm } from "./ProviderSwitchConfirm";
import { QueueDrawer } from "./QueueDrawer";
import { RuntimeSourceControls } from "./RuntimeSourceControls";
import { SettingsDrawer } from "./SettingsDrawer";
import { VideoMenu } from "./VideoMenu";
import { DockCollapseArrowIcon, DockLauncherIcon } from "./dockIcons";
import { truncateDockLabel } from "./dockLabels";
import { useProductionDock } from "./useProductionDock";
import "../../styles/production-dock/production-dock.css";

function ModelsComboMenu({
  open,
  dock,
  onClose,
}: {
  open: boolean;
  dock: ReturnType<typeof useProductionDock>;
  onClose: () => void;
}) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    panelRef.current?.focus();
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  const rows: { modality: Modality; label: string }[] = [
    { modality: "llm", label: dock.activeLabels.llm },
    { modality: "video", label: dock.activeLabels.video },
    { modality: "image", label: dock.activeLabels.image },
    { modality: "audio", label: dock.activeLabels.audio },
  ];

  return (
    <div
      ref={panelRef}
      className="production-dock-drawer"
      role="dialog"
      aria-modal="true"
      aria-label="Models"
      tabIndex={-1}
      data-testid="production-dock-menu-models"
    >
      <div className="production-dock-drawer__header">
        <h3>Models</h3>
        <button type="button" className="production-dock-collapse-btn" aria-label="Close models menu" onClick={onClose}>
          ×
        </button>
      </div>
      <ul className="production-dock-model-list">
        {rows.map((row) => (
          <li key={row.modality}>
            <button
              type="button"
              className="production-dock-model-item"
              aria-label={`Open ${row.modality} models`}
              onClick={() => dock.setOpenMenu(row.modality)}
            >
              <div className="production-dock-model-item__row">
                <span className="production-dock-model-item__label">{row.modality.toUpperCase()}</span>
              </div>
              <span className="production-dock-model-item__meta">{row.label}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ModalityChip({
  label,
  sub,
  active,
  onClick,
  testId,
}: {
  label: string;
  sub: string;
  active: boolean;
  onClick: () => void;
  testId?: string;
}) {
  const short = truncateDockLabel(sub, 14);
  return (
    <button
      type="button"
      className={`production-dock-chip${active ? " is-active" : ""}`}
      aria-label={`${label} models: ${sub}`}
      title={`${label}: ${sub}`}
      aria-expanded={active}
      data-testid={testId}
      onClick={onClick}
    >
      {label}
      <span className="production-dock-chip__sub">{short}</span>
    </button>
  );
}

export function ProductionControlDock() {
  const dock = useProductionDock();
  const shellRef = useRef<HTMLDivElement>(null);

  const closeMenu = useCallback(() => dock.setOpenMenu(null), [dock]);

  const toggleMenu = useCallback(
    (menu: NonNullable<typeof dock.openMenu>) => {
      dock.setOpenMenu(dock.openMenu === menu ? null : menu);
      if (dock.collapsed) void dock.setCollapsed(false);
    },
    [dock],
  );

  useEffect(() => {
    if (!dock.openMenu) return;
    const onPointerDown = (e: MouseEvent) => {
      if (!shellRef.current?.contains(e.target as Node)) closeMenu();
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [closeMenu, dock.openMenu]);

  const expand = () => {
    if (dock.collapsed) void dock.setCollapsed(false);
  };

  const collapseDock = () => {
    closeMenu();
    void dock.setCollapsed(true);
  };

  if (dock.collapsed) {
    return (
      <div className="production-dock-root is-launcher" data-testid="production-control-dock">
        <button
          type="button"
          className="production-dock-launcher"
          aria-label="Open production dock"
          aria-expanded={false}
          title="Production Dock"
          data-testid="production-dock-expand"
          onClick={() => void dock.setCollapsed(false)}
        >
          <DockLauncherIcon className="production-dock-launcher__icon" />
        </button>
        <ProviderSetupModal
          open={dock.providerModalOpen}
          onClose={() => dock.setProviderModalOpen(false)}
          onSaved={() => void dock.refresh()}
        />
        <ProviderSwitchConfirm
          open={Boolean(dock.providerSwitch)}
          preview={dock.providerSwitch}
          onConfirm={() => void dock.confirmProviderSwitch(true)}
          onCancel={() => void dock.confirmProviderSwitch(false)}
        />
      </div>
    );
  }

  return (
    <div className="production-dock-root is-expanded-root" data-testid="production-control-dock">
      <div ref={shellRef} className="production-dock-shell is-expanded">
        <LlmMenu open={dock.openMenu === "llm"} dock={dock} onClose={closeMenu} />
        <VideoMenu open={dock.openMenu === "video"} dock={dock} onClose={closeMenu} />
        <ImageMenu open={dock.openMenu === "image"} dock={dock} onClose={closeMenu} />
        <AudioMenu open={dock.openMenu === "audio"} dock={dock} onClose={closeMenu} />
        <ModelsComboMenu open={dock.openMenu === "models"} dock={dock} onClose={closeMenu} />
        <SettingsDrawer
          open={dock.openMenu === "settings"}
          dock={dock}
          onClose={closeMenu}
          onOpenDiagnostics={() => dock.setOpenMenu("diagnostics")}
        />
        <DiagnosticsDrawer
          open={dock.openMenu === "diagnostics"}
          dock={dock}
          onClose={closeMenu}
          onOpenQueue={() => dock.setOpenMenu("queue")}
        />
        <QueueDrawer open={dock.openMenu === "queue"} dock={dock} onClose={closeMenu} />

        <div className="production-dock-bar" data-testid="production-dock-bar">
          <button
            type="button"
            className="production-dock-collapse-btn production-dock-collapse-btn--minimize"
            aria-label="Collapse production dock"
            aria-expanded={true}
            title="Collapse Production Dock"
            data-testid="production-dock-collapse"
            onClick={collapseDock}
          >
            <DockCollapseArrowIcon className="production-dock-collapse-btn__icon" />
          </button>

          <RuntimeSourceControls dock={dock} />

          <span className="production-dock-divider production-dock-wide-only" aria-hidden />

          <div className="production-dock-group production-dock-wide-only">
            <ModalityChip
              label="LLM"
              sub={dock.activeLabels.llm}
              active={dock.openMenu === "llm"}
              onClick={() => toggleMenu("llm")}
              testId="production-dock-menu-llm"
            />
            <ModalityChip
              label="Video"
              sub={dock.activeLabels.video}
              active={dock.openMenu === "video"}
              onClick={() => toggleMenu("video")}
              testId="production-dock-menu-video"
            />
            <ModalityChip
              label="Image"
              sub={dock.activeLabels.image}
              active={dock.openMenu === "image"}
              onClick={() => toggleMenu("image")}
              testId="production-dock-menu-image"
            />
            <ModalityChip
              label="Audio"
              sub={dock.activeLabels.audio}
              active={dock.openMenu === "audio"}
              onClick={() => toggleMenu("audio")}
              testId="production-dock-menu-audio"
            />
          </div>

          <button
            type="button"
            className={`production-dock-chip production-dock-narrow-only${dock.openMenu === "models" ? " is-active" : ""}`}
            aria-label="Models menu"
            aria-expanded={dock.openMenu === "models"}
            onClick={() => toggleMenu("models")}
          >
            Models ▾
          </button>

          <CoDirectorDockControl dock={dock} />

          <button
            type="button"
            className={`production-dock-chip${dock.openMenu === "settings" || dock.openMenu === "diagnostics" ? " is-active" : ""}`}
            aria-label="Production settings"
            aria-expanded={dock.openMenu === "settings" || dock.openMenu === "diagnostics"}
            data-testid="production-dock-settings"
            onClick={() => {
              expand();
              toggleMenu("settings");
            }}
          >
            ⚙
          </button>
        </div>

        {dock.error ? (
          <p className="production-dock-error" role="status">
            {dock.error}
          </p>
        ) : null}
      </div>

      <ProviderSetupModal
        open={dock.providerModalOpen}
        onClose={() => dock.setProviderModalOpen(false)}
        onSaved={() => void dock.refresh()}
      />
      <ProviderSwitchConfirm
        open={Boolean(dock.providerSwitch)}
        preview={dock.providerSwitch}
        onConfirm={() => void dock.confirmProviderSwitch(true)}
        onCancel={() => void dock.confirmProviderSwitch(false)}
      />
    </div>
  );
}
