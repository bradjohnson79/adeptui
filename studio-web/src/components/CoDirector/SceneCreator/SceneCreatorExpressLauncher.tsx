import { useCoDirectorSession } from "../CoDirectorSession";
import { markOpenPopupAfterNav } from "../types";

export type SceneCreatorExpressLauncherProps = {
  projectId: string;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

export function SceneCreatorExpressLauncher({
  projectId,
  onGoTab,
}: SceneCreatorExpressLauncherProps) {
  const session = useCoDirectorSession();

  const openStandard = () => {
    markOpenPopupAfterNav();
    session.setDisplayMode("popup");
    session.setOpen(true);
    onGoTab?.("scenecreator");
  };

  return (
    <section className="scene-creator-launcher" data-testid="scene-creator-panel">
      <p className="eyebrow">Scene Creator</p>
      <h2 className="scene-creator-launcher__title">Scene Creator</h2>
      <p className="scene-creator-launcher__lead">
        Design production-ready shots using your Spatial Map, characters, props, virtual cameras,
        image refinement, and final rendering tools.
      </p>
      <p className="muted scene-creator-launcher__note">
        Scene Creator uses Adept UI's full production workspace for maximum control.
      </p>
      <button
        type="button"
        className="primary"
        data-testid="scene-creator-open-standard"
        disabled={!projectId}
        onClick={openStandard}
      >
        Open Scene Creator
      </button>
    </section>
  );
}
