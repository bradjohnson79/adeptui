import type { RefObject } from "react";
import { useNavigate } from "react-router-dom";
import { Drawer } from "../ui";
import { useCoDirectorSession } from "./CoDirectorSession";
import { buildNavEntries, type ContentTab } from "./navEntries";

export type { ContentTab, NavTarget, NavEntry } from "./navEntries";
export { buildNavEntries } from "./navEntries";

export function CoDirectorNavDrawer({
  open,
  onClose,
  returnFocusRef,
  onSelectContent,
  mode,
  expandToFullScreen,
}: {
  open: boolean;
  onClose: () => void;
  returnFocusRef: RefObject<HTMLElement | null>;
  onSelectContent: (tab: ContentTab) => void;
  mode: "popup" | "fullscreen";
  expandToFullScreen: () => void;
}) {
  const navigate = useNavigate();
  const { uiContext, openStatusPanel } = useCoDirectorSession();
  const entries = buildNavEntries(uiContext.projectId);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title={uiContext.projectName || "Co-Director"}
      returnFocusRef={returnFocusRef}
      testId="codirector-nav-drawer"
    >
      <p className="muted" style={{ padding: "0 0.75rem 0.5rem", margin: 0, fontSize: "0.75rem" }}>
        {uiContext.projectId ? "Project navigation" : "No Project Selected"}
      </p>
      <ul className="codirector-nav-list">
        {entries.map((entry) => (
          <li key={entry.id}>
            <button
              type="button"
              data-testid={`codirector-nav-${entry.id}`}
              disabled={entry.deferred}
              aria-disabled={entry.deferred || undefined}
              title={entry.deferred ? "Job monitoring will appear here when available" : undefined}
              onClick={() => {
                if (entry.target.kind === "deferred") {
                  return;
                }
                if (entry.target.kind === "chat") {
                  onClose();
                  return;
                }
                if (entry.target.kind === "content") {
                  onSelectContent(entry.target.tab);
                  if (mode === "popup") expandToFullScreen();
                  onClose();
                  return;
                }
                if (entry.target.kind === "overflow") {
                  openStatusPanel();
                  onClose();
                  return;
                }
                onClose();
                navigate(entry.target.path);
              }}
            >
              {entry.label}
            </button>
          </li>
        ))}
      </ul>
    </Drawer>
  );
}
