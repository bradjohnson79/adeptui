import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api";

export default function VirtualStageWorkspace() {
  const [params] = useSearchParams();
  const projectId = params.get("projectId") || "";
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [stageId, setStageId] = useState("");
  const [camera, setCamera] = useState({
    orbit: 0,
    elevation: 0,
    tilt: 0,
    roll: 0,
    distance: 3,
    lensMm: 35,
    pivot: { x: 0, y: 0, z: 0 },
  });
  const [prompt, setPrompt] = useState("");
  const [sceneReady, setSceneReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const health = await api.health();
      if (cancelled) return;
      const on = Boolean(health?.operator?.virtualStageEnabled);
      setEnabled(on);
      if (!on || !projectId) return;
      const created = await api.m28VirtualStageCreate(projectId, "scene-1", "Stage");
      if (cancelled) return;
      setStageId(created.id);
      setCamera(created.camera);
      setPrompt(created.promptDerived);
      setSceneReady(true);
    })().catch(console.error);
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (enabled === null) {
    return <div className="page" data-testid="virtual-stage-loading">Loading…</div>;
  }
  if (!enabled) {
    return (
      <div className="page" data-testid="virtual-stage-unavailable">
        <h1>Virtual Stage unavailable</h1>
        <Link to="/">Home</Link>
      </div>
    );
  }

  const update = async (patch: Record<string, unknown>) => {
    if (!stageId) return;
    const next = await api.m28VirtualStageCamera(stageId, patch);
    setCamera(next.camera);
    setPrompt(next.promptDerived);
  };

  return (
    <div className="page virtual-stage-page" data-testid="virtual-stage-page">
      <header className="row" style={{ gap: 12 }}>
        <Link to="/">Home</Link>
        <h1>Virtual Stage</h1>
      </header>
      <p data-testid="scene-anchor-ready">
        Scene / Scene Anchor: {sceneReady ? "ready" : "pending"}
      </p>
      <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
        <label>
          Orbit
          <input
            data-testid="camera-orbit"
            type="number"
            value={camera.orbit}
            onChange={(e) => update({ orbit: Number(e.target.value) })}
          />
        </label>
        <label>
          Pivot X
          <input
            data-testid="camera-pivot-x"
            type="number"
            value={camera.pivot?.x ?? 0}
            onChange={(e) =>
              update({ pivot: { ...camera.pivot, x: Number(e.target.value) } })
            }
          />
        </label>
        <label>
          Elevation
          <input
            data-testid="camera-elevation"
            type="number"
            value={camera.elevation}
            onChange={(e) => update({ elevation: Number(e.target.value) })}
          />
        </label>
        <label>
          Tilt
          <input
            data-testid="camera-tilt"
            type="number"
            value={camera.tilt}
            onChange={(e) => update({ tilt: Number(e.target.value) })}
          />
        </label>
        <label>
          Roll
          <input
            data-testid="camera-roll"
            type="number"
            value={camera.roll}
            onChange={(e) => update({ roll: Number(e.target.value) })}
          />
        </label>
        <label>
          Distance
          <input
            data-testid="camera-distance"
            type="number"
            value={camera.distance}
            onChange={(e) => update({ distance: Number(e.target.value) })}
          />
        </label>
        <label>
          Lens
          <input
            data-testid="camera-lens"
            type="number"
            value={camera.lensMm}
            onChange={(e) => update({ lensMm: Number(e.target.value) })}
          />
        </label>
      </div>
      <div className="row" style={{ gap: 8, marginTop: 12 }}>
        <button type="button" data-testid="camera-save" onClick={() => update(camera)}>
          Save camera profile
        </button>
        <button
          type="button"
          data-testid="camera-reload"
          onClick={async () => {
            const s = await api.m28VirtualStageGet(stageId);
            setCamera(s.camera);
            setPrompt(s.promptDerived);
          }}
        >
          Reload
        </button>
      </div>
      <p data-testid="prompt-derived">Prompt derived: {prompt}</p>
      <p data-testid="prompt-not-sot">Prompt text is not the source of truth.</p>
      <pre data-testid="camera-json">{JSON.stringify(camera, null, 2)}</pre>
    </div>
  );
}
