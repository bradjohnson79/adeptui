import { openExpressStandardWorkspace } from "../../../navigation/projectWorkspaceNavigation";
import { useCoDirectorSession } from "../CoDirectorSession";
import { markOpenPopupAfterNav } from "../types";
import "../SceneCreator/sceneCreator.css";

export type TimelineExpressLauncherProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function TimelineExpressLauncher({
  projectId,
  onGoTab,
}: TimelineExpressLauncherProps) {
  const session = useCoDirectorSession();

  const openStandard = () => {
    markOpenPopupAfterNav();
    session.setDisplayMode("popup");
    session.setOpen(true);
    openExpressStandardWorkspace(onGoTab, "timeline", session.uiContext.sceneId);
  };

  return (
    <section className="scene-creator-launcher" data-testid="timeline-panel">
      <p className="eyebrow">Timeline</p>
      <h2 className="scene-creator-launcher__title">Timeline</h2>
      <p className="scene-creator-launcher__lead">
        Bring your completed scenes, shots, video generations, audio, and production assets
        together in Adept UI's full Timeline workspace. Timeline gives you the production tools
        to assemble and refine your project, organize shots, work with timing and tracks, and
        prepare your finished sequence.
      </p>
      <p className="muted scene-creator-launcher__note">
        Timeline uses Adept UI's full Standard workspace so you have access to the complete
        editing and production toolset.
      </p>
      <button
        type="button"
        className="primary"
        data-testid="timeline-open-standard"
        disabled={!projectId}
        onClick={openStandard}
      >
        Open Timeline
      </button>
    </section>
  );
}
