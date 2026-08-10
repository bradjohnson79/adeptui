import { useEffect, useMemo, useState } from "react";
import { api } from "../../api";
import {
  summarizeSpatialMap,
  type SpatialMapDocumentReference,
  type SpatialReferenceSelection,
} from "../../contracts/spatialReference";

type SpatialReferenceFieldsetProps = {
  projectId: string;
  value: SpatialReferenceSelection;
  onChange: (patch: Partial<SpatialReferenceSelection>) => void;
  showMotionCameras?: boolean;
  testIdPrefix?: string;
};

export function SpatialReferenceFieldset({
  projectId,
  value,
  onChange,
  showMotionCameras = false,
  testIdPrefix = "",
}: SpatialReferenceFieldsetProps) {
  const [maps, setMaps] = useState<SpatialMapDocumentReference[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api.spatialMap
      .listMaps(projectId)
      .then((response) => {
        if (cancelled) return;
        setMaps(response.documents || []);
        setMessage(null);
      })
      .catch(() => {
        if (cancelled) return;
        setMaps([]);
        setMessage("Spatial maps are not available right now.");
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const selectedMap = useMemo(
    () => maps.find((item) => item.id === value.spatialMapId) || null,
    [maps, value.spatialMapId]
  );
  const summary = useMemo(() => summarizeSpatialMap(selectedMap), [selectedMap]);
  const cameras = selectedMap?.cameras || [];
  const prefix = testIdPrefix ? `${testIdPrefix}-` : "";

  return (
    <section className="field" data-testid={`${prefix}spatial-reference`}>
      <label>
        Spatial Reference
        <span className="muted tiny"> Match the blocked scene, camera, and geography from your saved map.</span>
      </label>
      <select
        data-testid={`${prefix}spatial-reference-select`}
        value={value.spatialMapId || ""}
        onChange={(event) => {
          const nextId = event.target.value || undefined;
          const nextMap = maps.find((item) => item.id === nextId);
          onChange({
            spatialMapId: nextId,
            spatialMapVersion: nextMap?.updatedAt,
            spatialCameraId: undefined,
            spatialStartCameraId: undefined,
            spatialEndCameraId: undefined,
          });
        }}
      >
        <option value="">None</option>
        {maps.map((item) => (
          <option key={item.id} value={item.id}>
            {item.title} · {item.characters.length} chars · {item.props.length} props
          </option>
        ))}
      </select>

      {cameras.length > 0 && !showMotionCameras ? (
        <div className="field" style={{ marginTop: "0.6rem" }}>
          <label>Camera View</label>
          <select
            data-testid={`${prefix}spatial-reference-camera-select`}
            value={value.spatialCameraId || ""}
            onChange={(event) => onChange({ spatialCameraId: event.target.value || undefined })}
          >
            <option value="">Use hero camera</option>
            {cameras.map((camera) => (
              <option key={camera.id} value={camera.id}>
                {camera.label}
                {camera.hero ? " · hero" : ""}
              </option>
            ))}
          </select>
        </div>
      ) : null}

      {cameras.length > 0 && showMotionCameras ? (
        <div className="row" style={{ gap: "0.75rem", marginTop: "0.6rem", flexWrap: "wrap" }}>
          <div className="field" style={{ flex: "1 1 220px" }}>
            <label>Start Camera</label>
            <select
              data-testid={`${prefix}spatial-reference-start-camera-select`}
              value={value.spatialStartCameraId || ""}
              onChange={(event) => onChange({ spatialStartCameraId: event.target.value || undefined })}
            >
              <option value="">Use hero camera</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.label}
                  {camera.hero ? " · hero" : ""}
                </option>
              ))}
            </select>
          </div>
          <div className="field" style={{ flex: "1 1 220px" }}>
            <label>End Camera</label>
            <select
              data-testid={`${prefix}spatial-reference-end-camera-select`}
              value={value.spatialEndCameraId || ""}
              onChange={(event) => onChange({ spatialEndCameraId: event.target.value || undefined })}
            >
              <option value="">Hold the same framing</option>
              {cameras.map((camera) => (
                <option key={camera.id} value={camera.id}>
                  {camera.label}
                  {camera.hero ? " · hero" : ""}
                </option>
              ))}
            </select>
          </div>
        </div>
      ) : null}

      {selectedMap ? (
        <div className="card" style={{ marginTop: "0.75rem", padding: "0.75rem" }}>
          <p className="muted tiny">
            <strong>Camera:</strong> {summary.camera}
          </p>
          <p className="muted tiny">
            <strong>Characters:</strong> {summary.characters}
          </p>
          <p className="muted tiny">
            <strong>Props:</strong> {summary.props}
          </p>
          <p className="muted tiny">
            <strong>Background:</strong> {summary.background}
          </p>
        </div>
      ) : null}

      {message ? <p className="muted tiny">{message}</p> : null}
    </section>
  );
}
