import { Button } from "../../ui";
import { PanelHeading } from "../../HelpTip";

type Job = Record<string, unknown> | null;

export function ReconstructStagePanel({
  assetId,
  onAssetId,
  job,
  onReconstruct,
  onImport,
}: {
  assetId: string;
  onAssetId: (value: string) => void;
  job: Job;
  onReconstruct: () => void;
  onImport: () => void;
}) {
  const objects = ((job?.package as { objects?: Array<{ objectId: string; name: string; detectedHuman?: boolean }> } | undefined)?.objects) || [];
  return (
    <section className="panel" data-testid="posecraft-reconstruct-panel">
      <PanelHeading title="Reconstruct Stage" tip="Turn a Library picture into an editable 3D stage. People stay as objects until you replace them with a character." />
      <label className="field">
        <span>Library picture id</span>
        <input value={assetId} onChange={(event) => onAssetId(event.target.value)} data-testid="posecraft-reconstruct-asset" />
      </label>
      <div className="row">
        <Button variant="primary" onClick={onReconstruct} data-testid="posecraft-reconstruct-start">Reconstruct</Button>
        <Button variant="secondary" onClick={onImport} data-testid="posecraft-reconstruct-import">Import stage</Button>
      </div>
      {job ? <p className="muted">{String(job.status || "")} — {String((job.progress as { message?: string } | undefined)?.message || job.error || "")}</p> : null}
      {objects.length ? (
        <ul data-testid="posecraft-reconstruct-objects">
          {objects.map((obj) => (
            <li key={obj.objectId}>{obj.name}{obj.detectedHuman ? " · looks like a person" : ""}</li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
