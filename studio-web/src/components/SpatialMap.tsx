import { useEffect, useState } from "react";
import type { Project, SpatialMap, SpatialPoint } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

const KINDS: SpatialPoint["kind"][] = ["camera", "prop", "wall", "marker"];

export function SpatialMapEditor({ project, onChange }: { project: Project; onChange: () => void }) {
  const [map, setMap] = useState<SpatialMap>({ width: 1000, height: 700, points: [], notes: "" });
  const [kind, setKind] = useState<SpatialPoint["kind"]>("camera");
  const [label, setLabel] = useState("Cam A");

  useEffect(() => {
    api.getSpatial(project.id).then(setMap).catch(console.error);
  }, [project.id]);

  const save = async (next: SpatialMap) => {
    setMap(next);
    await api.putSpatial(project.id, next);
    onChange();
  };

  return (
    <div className="panel">
      <PanelHeading
        title="Spatial map"
        tip="Top-down set layout. Drop cameras, props, and walls so prompts stay continuous and @set notes attach automatically."
      />
      <p className="scene-meta">Top-down layout for set continuity. Tags like @set / @map attach automatically.</p>
      <div
        className="spatial-canvas"
        onClick={(e) => {
          const rect = (e.currentTarget as HTMLDivElement).getBoundingClientRect();
          const x = ((e.clientX - rect.left) / rect.width) * map.width;
          const y = ((e.clientY - rect.top) / rect.height) * map.height;
          const point: SpatialPoint = {
            id: crypto.randomUUID(),
            kind,
            x,
            y,
            label,
            rotation: 0,
            asset_id: null,
          };
          save({ ...map, points: [...map.points, point] });
        }}
      >
        {map.points.map((p) => (
          <button
            key={p.id}
            className={`spatial-point ${p.kind}`}
            style={{ left: `${(p.x / map.width) * 100}%`, top: `${(p.y / map.height) * 100}%` }}
            title="Right-click to remove"
            onContextMenu={(e) => {
              e.preventDefault();
              e.stopPropagation();
              save({ ...map, points: map.points.filter((x) => x.id !== p.id) });
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {p.label || p.kind}
          </button>
        ))}
      </div>
      <div className="row-actions" style={{ marginTop: 8 }}>
        <select value={kind} onChange={(e) => setKind(e.target.value as SpatialPoint["kind"])}>
          {KINDS.map((k) => (
            <option key={k} value={k}>
              {k}
            </option>
          ))}
        </select>
        <input style={{ maxWidth: 140 }} value={label} onChange={(e) => setLabel(e.target.value)} />
      </div>
      <div className="field">
        <label>Set notes (injected into prompts)</label>
        <textarea
          value={map.notes}
          onChange={(e) => setMap({ ...map, notes: e.target.value })}
          onBlur={() => save(map)}
          placeholder="Warm wood interior, window left, desk center"
        />
      </div>
      <div className="field">
        <label>Background / plate asset</label>
        <select
          value={map.background_asset_id || ""}
          onChange={(e) => save({ ...map, background_asset_id: e.target.value || null })}
        >
          <option value="">None</option>
          {project.assets
            .filter((a) => a.kind === "image")
            .map((a) => (
              <option key={a.id} value={a.id}>
                @{a.tag || a.filename}
              </option>
            ))}
        </select>
      </div>
    </div>
  );
}
