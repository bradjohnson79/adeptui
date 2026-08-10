import { useEffect, useMemo, useState } from "react";
import { Button } from "../ui";
import { HelpTip, PanelHeading } from "../HelpTip";
import type { Asset } from "../../types";
import {
  directionLabel,
  SPATIAL_REQUIRED_DIRECTIONS,
  type Spatial360Collage,
  type SpatialCapturePlan,
  type SpatialMapDocument,
  type SpatialRequiredDirection,
  type Spatial360ViewUpsertBody,
} from "../../contracts/spatialMapM411";

type Collage360PanelProps = {
  document: SpatialMapDocument;
  assets: Asset[];
  capturePlan: SpatialCapturePlan | null;
  busy: boolean;
  onGenerate: () => void;
  onUpdateView: (direction: SpatialRequiredDirection, body: Spatial360ViewUpsertBody) => void;
};

function slotSummary(document: SpatialMapDocument, direction: SpatialRequiredDirection) {
  const characterLine = document.characters.length
    ? `${document.characters.map((item) => item.label).join(", ")} in this sweep`
    : "No performers placed yet";
  const propLine = document.props.length
    ? `${document.props.length} prop${document.props.length === 1 ? "" : "s"} to track`
    : "No props placed yet";
  const heroCamera = document.cameras.find((item) => item.hero) || document.cameras[0];
  const cameraLine = heroCamera ? `${heroCamera.label} can anchor the ring` : "Add a camera to guide the ring";
  return `${directionLabel(direction)} view. ${characterLine}. ${propLine}. ${cameraLine}.`;
}

function viewLookup(collage: Spatial360Collage | null | undefined) {
  const map = new Map<string, Spatial360Collage["views"][number]>();
  (collage?.views || []).forEach((view) => map.set(view.direction, view));
  return map;
}

export function Collage360Panel({
  document,
  assets,
  capturePlan,
  busy,
  onGenerate,
  onUpdateView,
}: Collage360PanelProps) {
  const assetChoices = assets.filter((asset) => asset.kind === "image" || asset.kind === "environment");
  const views = useMemo(() => viewLookup(document.collage), [document.collage]);
  const [promptDrafts, setPromptDrafts] = useState<Record<string, string>>({});

  useEffect(() => {
    const nextDrafts: Record<string, string> = {};
    SPATIAL_REQUIRED_DIRECTIONS.forEach((direction) => {
      nextDrafts[direction] = views.get(direction)?.prompt || "";
    });
    setPromptDrafts(nextDrafts);
  }, [views]);

  return (
    <section className="spatial-map-panel">
      <PanelHeading
        title="360° Collage"
        tip="Collect eight surrounding views so the location keeps its shape from every angle."
      />
      <p className="scene-meta">
        Build the full ring first, then refine each direction with a guide image and a short note for the next capture pass.
      </p>

      <div className="spatial-map-collage-grid">
        {SPATIAL_REQUIRED_DIRECTIONS.map((direction) => {
          const view = views.get(direction);
          return (
            <article
              key={direction}
              className="spatial-map-collage-card"
              data-testid={`spatial-360-slot-${direction}`}
            >
              <div className="spatial-map-collage-card__head">
                <strong>{directionLabel(direction)}</strong>
                <HelpTip text={slotSummary(document, direction)} />
              </div>

              <label className="field">
                <span>Reference Image</span>
                <select
                  value={view?.assetId || ""}
                  onChange={(event) => onUpdateView(direction, { assetId: event.target.value || null })}
                >
                  <option value="">Choose an image…</option>
                  {assetChoices.map((asset) => (
                    <option key={asset.id} value={asset.id}>
                      {asset.tag || asset.filename}
                    </option>
                  ))}
                </select>
              </label>

              <label className="field">
                <span>Capture Status</span>
                <select
                  value={view?.status || "planned"}
                  onChange={(event) =>
                    onUpdateView(direction, {
                      status: event.target.value as Spatial360ViewUpsertBody["status"],
                    })
                  }
                >
                  <option value="planned">Planned</option>
                  <option value="captured">Captured</option>
                  <option value="approved">Approved</option>
                </select>
              </label>

              <label className="field">
                <span>Creative Note</span>
                <textarea
                  rows={3}
                  value={promptDrafts[direction] || ""}
                  placeholder="Keep the lantern wall intact and hold the table in frame."
                  onChange={(event) =>
                    setPromptDrafts((current) => ({ ...current, [direction]: event.target.value }))
                  }
                  onBlur={() => onUpdateView(direction, { prompt: promptDrafts[direction] || "" })}
                />
              </label>

              {view?.adjacencyWarnings?.length ? (
                <p className="pill warn">{view.adjacencyWarnings.join(" ")}</p>
              ) : null}
            </article>
          );
        })}
      </div>

      <div className="spatial-map-export-actions">
        <Button variant="primary" data-testid="spatial-generate-360" loading={busy} onClick={onGenerate}>
          {busy ? "Generating 360…" : "Generate 360"}
        </Button>
        <p className="scene-meta">
          This calls the real capture planner, then lays out the eight-view collage document.
        </p>
      </div>

      {document.collage?.continuityWarnings?.length ? (
        <div className="pill warn">{document.collage.continuityWarnings.join(" ")}</div>
      ) : null}

      {capturePlan ? (
        <pre className="spatial-propose">
          {[
            `Master environment: ${capturePlan.masterEnvironmentPrompt || "Not set yet."}`,
            "",
            ...capturePlan.instructions,
            "",
            ...capturePlan.shots.map(
              (shot) => `${directionLabel(shot.direction)} · ${Math.round(shot.yawDegrees)}° · ${shot.prompt}`
            ),
          ].join("\n")}
        </pre>
      ) : null}
    </section>
  );
}
