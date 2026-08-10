import { useEffect, useRef, useState, type ReactNode } from "react";
import { HelpTip } from "../HelpTip";
import { getTimelineHelp } from "../../timelineMaster/helpCatalog";
import {
  loadTimelineWorkspaceLayout,
  saveTimelineWorkspaceLayout,
  type TimelineWorkspaceLayout,
} from "../../timelineMaster/workspaceLayout";

type Props = {
  open: boolean;
  onClose: () => void;
  onGuidancePriorityChange?: (value: TimelineWorkspaceLayout["guidancePriority"]) => void;
  onLayoutChange?: (layout: TimelineWorkspaceLayout) => void;
};

function SettingRow({
  label,
  helpId,
  children,
}: {
  label: string;
  helpId?: string;
  children: ReactNode;
}) {
  const help = helpId ? getTimelineHelp(helpId) : null;
  return (
    <label className="timeline-settings-row">
      <span className="timeline-settings-row__label">
        {label}
        {help ? <HelpTip label={help.title} content={help.body} text={help.title} /> : null}
      </span>
      {children}
    </label>
  );
}

export function TimelineSettingsDrawer({ open, onClose, onGuidancePriorityChange, onLayoutChange }: Props) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState(() => loadTimelineWorkspaceLayout());

  useEffect(() => {
    if (open) setLayout(loadTimelineWorkspaceLayout());
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const patch = (next: Partial<TimelineWorkspaceLayout>) => {
    const saved = saveTimelineWorkspaceLayout(next);
    setLayout(saved);
    onLayoutChange?.(saved);
    if (next.guidancePriority != null) {
      onGuidancePriorityChange?.(next.guidancePriority);
    }
  };

  if (!open) return null;

  return (
    <div className="timeline-settings-drawer" ref={panelRef} data-testid="timeline-settings-drawer">
      <div className="timeline-settings-drawer__header">
        <strong>Timeline Settings</strong>
        <HelpTip
          label={getTimelineHelp("timeline_settings").title}
          content={getTimelineHelp("timeline_settings").body}
        />
        <button type="button" className="ghost" aria-label="Close Timeline Settings" onClick={onClose}>
          ×
        </button>
      </div>

      <div className="timeline-settings-drawer__body">
        <div className="timeline-settings-group">
          <div className="section-label">Display</div>
          <SettingRow label="Time display">
            <select
              value={layout.displayMode}
              aria-label="Timeline display mode"
              onChange={(e) =>
                patch({ displayMode: e.target.value as TimelineWorkspaceLayout["displayMode"] })
              }
            >
              <option value="seconds">Seconds</option>
              <option value="frames">Frames</option>
              <option value="timecode">Timecode</option>
            </select>
          </SettingRow>
          <SettingRow label="Track density">
            <select
              value={layout.trackDensity}
              aria-label="Track density"
              onChange={(e) =>
                patch({ trackDensity: e.target.value as TimelineWorkspaceLayout["trackDensity"] })
              }
            >
              <option value="compact">Compact</option>
              <option value="comfortable">Comfortable</option>
              <option value="expanded">Expanded</option>
            </select>
          </SettingRow>
          <label className="timeline-settings-row timeline-settings-row--check">
            <input
              type="checkbox"
              checked={layout.showThumbnails}
              onChange={(e) => patch({ showThumbnails: e.target.checked })}
            />
            Show thumbnails
          </label>
          <label className="timeline-settings-row timeline-settings-row--check">
            <input
              type="checkbox"
              checked={layout.showFilenames}
              onChange={(e) => patch({ showFilenames: e.target.checked })}
            />
            Show filenames on clips
          </label>
        </div>

        <div className="timeline-settings-group">
          <div className="section-label">Editing</div>
          <label className="timeline-settings-row timeline-settings-row--check">
            <input
              type="checkbox"
              checked={layout.snapEnabled}
              onChange={(e) => patch({ snapEnabled: e.target.checked })}
            />
            Snap clips and playhead
          </label>
          <label className="timeline-settings-row timeline-settings-row--check">
            <input
              type="checkbox"
              checked={layout.playheadFollow}
              onChange={(e) => patch({ playheadFollow: e.target.checked })}
            />
            Playhead follow (keep needle visible while scrubbing)
          </label>
        </div>

        <div className="timeline-settings-group">
          <div className="section-label">Guidance</div>
          <SettingRow label="Guidance priority" helpId="guidance_priority">
            <select
              value={layout.guidancePriority}
              aria-label="Guidance priority"
              onChange={(e) =>
                patch({
                  guidancePriority: e.target.value as TimelineWorkspaceLayout["guidancePriority"],
                })
              }
            >
              <option value="visual_first">Visual First</option>
              <option value="prompt_first">Prompt First</option>
              <option value="balanced">Balanced</option>
              <option value="custom">Custom</option>
            </select>
          </SettingRow>
        </div>

        <div className="timeline-settings-group">
          <div className="section-label">Help</div>
          <label className="timeline-settings-row timeline-settings-row--check">
            <input
              type="checkbox"
              checked={layout.showEmptyHelp}
              onChange={(e) => patch({ showEmptyHelp: e.target.checked })}
            />
            Show empty-track tips
          </label>
        </div>
      </div>
    </div>
  );
}

export function formatTimelineTime(
  sec: number,
  mode: TimelineWorkspaceLayout["displayMode"],
  fps = 24,
): string {
  const t = Math.max(0, sec);
  if (mode === "frames") {
    return `${Math.round(t * fps)}f`;
  }
  if (mode === "timecode") {
    const h = Math.floor(t / 3600);
    const m = Math.floor((t % 3600) / 60);
    const s = Math.floor(t % 60);
    const f = Math.floor((t % 1) * fps);
    if (h > 0) {
      return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}:${String(f).padStart(2, "0")}`;
    }
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}:${String(f).padStart(2, "0")}`;
  }
  return `${t.toFixed(2)}s`;
}
