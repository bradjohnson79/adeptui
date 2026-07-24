import { useEffect } from "react";
import { CoDirectorShell } from "./CoDirectorShell";
import { useCoDirectorSession } from "./CoDirectorSession";

export function CoDirectorFullScreen() {
  const { collapseToPopup, setDisplayMode, setOpen } = useCoDirectorSession();

  useEffect(() => {
    setDisplayMode("fullscreen");
    setOpen(true);
  }, [setDisplayMode, setOpen]);

  return (
    <div className="codirector-fullscreen-page app-shell atmosphere">
      <CoDirectorShell
        mode="fullscreen"
        showContextPanel
        onClose={() => {
          setOpen(false);
          setDisplayMode("popup");
          collapseToPopup();
        }}
      />
    </div>
  );
}
