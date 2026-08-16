import { useEffect } from "react";
import { useLocation } from "react-router-dom";
import { CoDirectorPopup } from "./CoDirectorPopup";
import { useCoDirectorSession } from "./CoDirectorSession";

/** Popup host only — FAB removed; Production Dock launches Co-Director. */
export function CoDirectorHost() {
  const location = useLocation();
  const { open, displayMode, setDisplayMode } = useCoDirectorSession();
  const onFullScreenRoute = location.pathname.startsWith("/co-director");

  useEffect(() => {
    if (!onFullScreenRoute && displayMode === "fullscreen") {
      setDisplayMode("popup");
    }
  }, [displayMode, onFullScreenRoute, setDisplayMode]);

  if (onFullScreenRoute) return null;
  if (!open || displayMode !== "popup") return null;

  return (
    <div id="codirector-popup">
      <CoDirectorPopup />
    </div>
  );
}
