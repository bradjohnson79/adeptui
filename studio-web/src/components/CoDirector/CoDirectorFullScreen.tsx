import { useEffect } from "react";
import { CoDirectorShell } from "./CoDirectorShell";
import { useCoDirectorSession } from "./CoDirectorSession";

export function CoDirectorFullScreen() {
  const { collapseToPopup, setDisplayMode, setOpen, setContextPanelOpen } = useCoDirectorSession();

  useEffect(() => {
    setDisplayMode("fullscreen");
    setOpen(true);
    setContextPanelOpen(true);
  }, [setDisplayMode, setOpen, setContextPanelOpen]);

  return (
    <div className="codirector-fullscreen-page" data-testid="codirector-fullscreen">
      <CoDirectorShell
        mode="fullscreen"
        onClose={() => {
          setOpen(false);
          setDisplayMode("popup");
          collapseToPopup();
        }}
      />
    </div>
  );
}
