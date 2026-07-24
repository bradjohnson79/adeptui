import { useMemo, useState } from "react";
import type { Asset, Project, Scene } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

function KeyframeSlot({
  label,
  tip,
  assetId,
  images,
  onPick,
  onUpload,
}: {
  label: string;
  tip: string;
  assetId?: string | null;
  images: { id: string; tag: string; filename: string }[];
  onPick: (id: string | null) => void;
  onUpload: (file: File) => void;
}) {
  return (
    <div className="frame-slot">
      <PanelHeading title={label} tip={tip} as="strong" />
      <div className="frame-slot-preview">
        {assetId ? (
          <img src={api.assetUrl(assetId)} alt={label} />
        ) : (
          <div className="empty">No image</div>
        )}
      </div>
      <div className="row-actions" style={{ marginTop: 8 }}>
        <label className="ghost" style={{ cursor: "pointer" }}>
          Upload
          <input
            type="file"
            accept="image/*"
            hidden
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) onUpload(f);
            }}
          />
        </label>
        <select value={assetId || ""} onChange={(e) => onPick(e.target.value || null)}>
          <option value="">Library…</option>
          {images.map((a) => (
            <option key={a.id} value={a.id}>
              @{a.tag || a.filename}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/** 1 Frame — single still → video generation */
export function OneFramePanel({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const images = useMemo(() => project.assets.filter((a) => a.kind === "image"), [project.assets]);

  if (!scene) return <div className="panel"><p className="empty">Select a scene</p></div>;

  const update = async (patch: Partial<Scene>) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    onChange();
  };

  const upload = async (file: File) => {
    const tag = `${scene.name}_frame`.replace(/\s+/g, "_").toLowerCase();
    const asset = (await api.uploadAsset(project.id, file, tag, "image")) as Asset;
    await update({ start_asset_id: asset.id, middle_asset_id: null, end_asset_id: null });
  };

  return (
    <div className="panel frame-mode-panel">
      <PanelHeading
        title="1 Frame"
        tip="Generate video from one still. Upload or pick a single image, write motion, then retake the scene."
      />
      <p className="scene-meta">Single-frame image-to-video — one keyframe drives the whole clip.</p>
      <div className="frame-slots one">
        <KeyframeSlot
          label="Frame"
          tip="The only still used for this scene. Motion and camera come from the prompt."
          assetId={scene.start_asset_id}
          images={images}
          onPick={(id) => update({ start_asset_id: id, middle_asset_id: null, end_asset_id: null })}
          onUpload={upload}
        />
      </div>
      <div className="field">
        <label>Motion prompt</label>
        <textarea
          value={scene.prompt}
          onChange={(e) => update({ prompt: e.target.value })}
          placeholder="camera slowly pushes in, soft wind, she turns toward the light…"
        />
      </div>
      <div className="field">
        <label>Duration (seconds)</label>
        <input
          type="number"
          min={1}
          max={30}
          step={0.5}
          value={scene.duration_sec}
          onChange={(e) => update({ duration_sec: Number(e.target.value) || 5 })}
        />
      </div>
      <div className="row-actions">
        <button
          className="primary"
          disabled={busy || !scene.start_asset_id}
          onClick={async () => {
            setBusy(true);
            try {
              await api.render(project.id, "scene", scene.id);
              onChange();
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Queuing…" : "Generate from 1 frame"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const director = await api.getDirector(project.id, scene.id);
              const clips = [];
              if (scene.start_asset_id) {
                clips.push({
                  id: Math.random().toString(36).slice(2, 10),
                  start: 0,
                  length: Math.min(2, scene.duration_sec),
                  label: "From 1 Frame",
                  role: "guide",
                  asset_id: scene.start_asset_id,
                });
              }
              await api.putDirector(project.id, scene.id, {
                ...director,
                media_mode: "image",
                image_clips: clips.length ? clips : director.image_clips,
                duration_sec: scene.duration_sec,
                prompt_segments: director.prompt_segments?.length
                  ? director.prompt_segments
                  : [{ id: Math.random().toString(36).slice(2, 10), start: 0, length: scene.duration_sec, text: scene.prompt, weight: 1 }],
              });
              onChange();
            } finally {
              setBusy(false);
            }
          }}
        >
          Add to Director
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            await api.addScene(project.id, {
              name: `${scene.name} copy`,
              engine: scene.engine,
              prompt: scene.prompt,
              duration_sec: scene.duration_sec,
              start_asset_id: scene.start_asset_id,
              camera_note: scene.camera_note,
              seed: scene.seed,
            });
            onChange();
          }}
        >
          Save as Scene
        </button>
      </div>
    </div>
  );
}

/** 3 Frame — Start / Middle / End keyframe generation */
export function ThreeFramePanel({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const images = useMemo(() => project.assets.filter((a) => a.kind === "image"), [project.assets]);

  if (!scene) return <div className="panel"><p className="empty">Select a scene</p></div>;

  const update = async (patch: Partial<Scene>) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    onChange();
  };

  const uploadSlot = async (role: "start" | "middle" | "end", file: File) => {
    const tag = `${scene.name}_${role}`.replace(/\s+/g, "_").toLowerCase();
    const asset = (await api.uploadAsset(project.id, file, tag, "image")) as Asset;
    const key = `${role}_asset_id` as const;
    await update({ [key]: asset.id } as Partial<Scene>);
  };

  return (
    <div className="panel frame-mode-panel">
      <PanelHeading
        title="3 Frame"
        tip="Start, middle, and end stills guide the arc. Fill the slots, write motion, then generate the scene."
      />
      <p className="scene-meta">Keyframe path — beginning, midpoint, and ending images for guided video generation.</p>
      <div className="frame-slots three">
        <KeyframeSlot
          label="Start"
          tip="Opening still. Sets identity and framing at time zero."
          assetId={scene.start_asset_id}
          images={images}
          onPick={(id) => update({ start_asset_id: id })}
          onUpload={(f) => uploadSlot("start", f)}
        />
        <KeyframeSlot
          label="Middle"
          tip="Mid-clip still. Optional bridge pose or camera position."
          assetId={scene.middle_asset_id}
          images={images}
          onPick={(id) => update({ middle_asset_id: id })}
          onUpload={(f) => uploadSlot("middle", f)}
        />
        <KeyframeSlot
          label="End"
          tip="Closing still. Anchors where the motion should finish."
          assetId={scene.end_asset_id}
          images={images}
          onPick={(id) => update({ end_asset_id: id })}
          onUpload={(f) => uploadSlot("end", f)}
        />
      </div>
      <div className="field">
        <label>Motion prompt</label>
        <textarea
          value={scene.prompt}
          onChange={(e) => update({ prompt: e.target.value })}
          placeholder="walks from door to window, camera follows, rain on glass…"
        />
      </div>
      <div className="field">
        <label>Duration (seconds)</label>
        <input
          type="number"
          min={1}
          max={30}
          step={0.5}
          value={scene.duration_sec}
          onChange={(e) => update({ duration_sec: Number(e.target.value) || 5 })}
        />
      </div>
      <div className="row-actions">
        <button
          className="primary"
          disabled={busy || !scene.start_asset_id}
          onClick={async () => {
            setBusy(true);
            try {
              await api.render(project.id, "scene", scene.id);
              onChange();
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Queuing…" : "Generate from 3 frames"}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              const director = await api.getDirector(project.id, scene.id);
              const clips = [];
              let t = 0;
              const step = Math.max(1, scene.duration_sec / 3);
              for (const [label, id] of [
                ["Start", scene.start_asset_id],
                ["Middle", scene.middle_asset_id],
                ["End", scene.end_asset_id],
              ] as const) {
                if (!id) continue;
                clips.push({
                  id: Math.random().toString(36).slice(2, 10),
                  start: t,
                  length: Math.min(step, scene.duration_sec - t || step),
                  label,
                  role: "guide" as const,
                  asset_id: id,
                });
                t += step;
              }
              await api.putDirector(project.id, scene.id, {
                ...director,
                media_mode: "image",
                image_clips: clips.length ? clips : director.image_clips,
                duration_sec: scene.duration_sec,
              });
              onChange();
            } finally {
              setBusy(false);
            }
          }}
        >
          Add to Director
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={async () => {
            await api.addScene(project.id, {
              name: `${scene.name} copy`,
              engine: scene.engine,
              prompt: scene.prompt,
              duration_sec: scene.duration_sec,
              start_asset_id: scene.start_asset_id,
              middle_asset_id: scene.middle_asset_id,
              end_asset_id: scene.end_asset_id,
              camera_note: scene.camera_note,
              seed: scene.seed,
            });
            onChange();
          }}
        >
          Save as Scene
        </button>
      </div>
    </div>
  );
}
