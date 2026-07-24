import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { CoDirectorPopup } from "./CoDirectorPopup";
import { useCoDirectorSession } from "./CoDirectorSession";

/** Global FAB + popup host (hidden on full-screen Co-Director route). */
export function CoDirectorHost() {
  const location = useLocation();
  const { open, toggleOpen, displayMode, setDisplayMode } = useCoDirectorSession();
  const onFullScreenRoute = location.pathname.startsWith("/co-director");

  useEffect(() => {
    if (!onFullScreenRoute && displayMode === "fullscreen") {
      setDisplayMode("popup");
    }
  }, [displayMode, onFullScreenRoute, setDisplayMode]);

  if (onFullScreenRoute) return null;

  return (
    <>
      <button
        type="button"
        className="assistant-fab codirector-fab"
        onClick={() => toggleOpen()}
        aria-expanded={open}
        aria-controls="codirector-popup"
        title="Co-Director"
      >
        {open ? "Close" : "Co-Director"}
      </button>
      <div id="codirector-popup">
        <CoDirectorPopup />
      </div>
    </>
  );
}
