import { PanelHeading } from "../../HelpTip";
import type { PoseCraftScene } from "../../../posecraft/types";

export function StageTreePanel({ scene }: { scene: PoseCraftScene }) {
  const objects = scene.objects ?? [];
  const shots = scene.shots ?? [];
  return (
    <section className="panel" data-testid="posecraft-stage-tree">
      <PanelHeading title="Stage tree" tip="Everything on the stage: environment, objects, characters, cameras, and shots." />
      <p className="muted">Environment: {scene.environment?.name || "Empty stage"}</p>
      <ul>
        {objects.map((obj) => (
          <li key={obj.id}>{obj.name}{obj.detectedHuman || obj.detectedLabel === "person" ? " · looks like a person" : ""}</li>
        ))}
        {scene.figures.map((fig) => (
          <li key={fig.id}>{fig.name} · character</li>
        ))}
        {(scene.cameras ?? []).map((cam) => (
          <li key={cam.id}>{cam.name}</li>
        ))}
        {shots.map((shot) => (
          <li key={shot.shotId || shot.id}>{shot.name}</li>
        ))}
      </ul>
    </section>
  );
}
