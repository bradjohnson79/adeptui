import { useNavigate } from "react-router-dom";
import { useOpenCoDirector } from "../CoDirector";
import { truncateDockLabel } from "./dockLabels";
import type { ProductionDockApi } from "./useProductionDock";

export function CoDirectorDockControl({ dock }: { dock: ProductionDockApi }) {
  const navigate = useNavigate();
  const openCoDirector = useOpenCoDirector();
  const llmLabel = dock.activeLabels.llm;
  const shortLlm = truncateDockLabel(llmLabel, 14);

  return (
    <button
      type="button"
      className="production-dock-chip production-dock-chip--codirector"
      aria-label={`Open Co-Director · ${llmLabel}`}
      title={`Co-Director · ${llmLabel}`}
      data-testid="production-dock-codirector"
      onClick={(e) => {
        if (e.shiftKey) {
          navigate("/co-director");
          return;
        }
        openCoDirector(undefined, { fullscreen: false });
      }}
      onDoubleClick={() => navigate("/co-director")}
    >
      <span aria-hidden>✦</span>
      <span>Co-Director</span>
      <span className="production-dock-chip__sub">{shortLlm}</span>
    </button>
  );
}
