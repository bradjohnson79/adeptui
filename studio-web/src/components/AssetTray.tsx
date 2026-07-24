import { useEffect, useMemo, useRef, useState } from "react";
import type { Asset, EngineName, Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";
import {
  CONTINUITY_KEYS,
  parseContinuity,
  type ContinuityKey,
  type ContinuityLock,
} from "../directorSelection";

export function AssetTray({ project, onChange }: { project: Project; onChange: () => void }) {
  const [tag, setTag] = useState("");
  const [filter, setFilter] = useState<"all" | "image" | "audio" | "video">("all");
  const fileRef = useRef<HTMLInputElement>(null);

  const upload = async (files: FileList | null, kind: string) => {
    if (!files?.length) return;
    for (const file of Array.from(files)) {
      const autoTag = tag || file.name.replace(/\.[^.]+$/, "").replace(/\s+/g, "_").toLowerCase();
      await api.uploadAsset(project.id, file, autoTag, kind);
    }
    setTag("");
    onChange();
  };

  const filtered = project.assets.filter((a) => filter === "all" || a.kind === filter);

  return (
    <div className="panel">
      <PanelHeading
        title="Assets"
        tip="Upload images, audio, or video and tag them. Drag onto Director tracks. Type @tag in prompts."
      />
      <p className="scene-meta">Tag assets to reference them with @name in prompts. Drag onto timeline tracks.</p>
      <div className="field">
        <label>Tag for next upload</label>
        <input placeholder="hero" value={tag} onChange={(e) => setTag(e.target.value)} />
      </div>
      <div className="row-actions">
        <button onClick={() => fileRef.current?.click()}>Upload image</button>
        <label className="ghost">
          <button
            onClick={() => {
              const input = document.createElement("input");
              input.type = "file";
              input.accept = "audio/*";
              input.onchange = () => upload(input.files, "audio");
              input.click();
            }}
          >
            Upload audio
          </button>
        </label>
        <button
          onClick={() => {
            const input = document.createElement("input");
            input.type = "file";
            input.accept = "video/*";
            input.onchange = () => upload(input.files, "video");
            input.click();
          }}
        >
          Upload video
        </button>
      </div>
      <input
        ref={fileRef}
        type="file"
        accept="image/*"
        hidden
        multiple
        onChange={(e) => upload(e.target.files, "image")}
      />
      <div className="asset-filters">
        {(["all", "image", "audio", "video"] as const).map((f) => (
          <button
            key={f}
            type="button"
            className={filter === f ? "primary" : "ghost"}
            onClick={() => setFilter(f)}
          >
            {f}
          </button>
        ))}
      </div>
      <div className="section-label">Library</div>
      <div className="asset-list">
        {filtered.length === 0 && <div className="empty">No assets yet</div>}
        {filtered.map((a: Asset) => (
          <div
            className="asset-item"
            key={a.id}
            draggable
            onDragStart={(e) => {
              e.dataTransfer.setData("application/x-adept-asset", a.id);
              e.dataTransfer.setData("application/x-adept-kind", a.kind);
              e.dataTransfer.effectAllowed = "copy";
            }}
          >
            {a.kind === "image" ? (
              <img src={api.assetUrl(a.id)} alt={a.filename} />
            ) : (
              <div className="ph">{a.kind}</div>
            )}
            <div>
              <div className="tag">@{a.tag || "untagged"}</div>
              <div className="scene-meta">{a.filename}</div>
            </div>
            <span className="scene-meta">{a.kind}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function PromptComposer({
  project,
  sceneId,
  onChange,
  showContinuity,
}: {
  project: Project;
  sceneId?: string;
  onChange: () => void;
  showContinuity?: boolean;
}) {
  const scene = project.scenes.find((s) => s.id === sceneId) || project.scenes[0];
  const [suggestOpen, setSuggestOpen] = useState(false);
  const [rec, setRec] = useState<Awaited<ReturnType<typeof api.recommendEngine>> | null>(null);
  const tags = useMemo(() => project.assets.filter((a) => a.tag).map((a) => a.tag), [project.assets]);

  useEffect(() => {
    if (!scene || !showContinuity) return;
    api.recommendEngine(project.id, scene.id).then(setRec).catch(() => setRec(null));
  }, [project.id, scene?.id, scene?.engine, scene?.duration_sec, showContinuity]);

  if (!scene) return null;

  const update = async (patch: Partial<typeof scene>) => {
    await api.updateScene(project.id, scene.id, { ...scene, ...patch });
    onChange();
  };

  const onPrompt = (value: string) => {
    update({ prompt: value });
    setSuggestOpen(value.endsWith("@") || /@\w*$/.test(value));
  };

  const insertTag = (tag: string) => {
    const next = scene.prompt.replace(/@\w*$/, `@${tag}`) + (scene.prompt.endsWith("@") ? tag : "");
    const fixed = /@\w*$/.test(scene.prompt)
      ? scene.prompt.replace(/@\w*$/, `@${tag} `)
      : `${scene.prompt}@${tag} `;
    update({ prompt: fixed || next });
    setSuggestOpen(false);
  };

  const continuity = parseContinuity(scene.continuity_json);
  const setLock = async (key: ContinuityKey, mode: ContinuityLock) => {
    const next = { ...continuity, [key]: mode };
    await update({ continuity_json: JSON.stringify(next) });
  };

  return (
    <div className="panel">
      <PanelHeading
        title={scene.name}
        tip="Per-scene engine, duration, and prompt. Use @tags from Assets. Continuity locks are production instructions until adapters consume them."
      />
      <div className="field">
        <label>Engine {scene.engine === "auto" ? <span className="pill">Auto</span> : null}</label>
        <select value={scene.engine} onChange={(e) => update({ engine: e.target.value as EngineName })}>
          <optgroup label="Auto">
            <option value="auto">Auto Select</option>
          </optgroup>
          <optgroup label="Local (ComfyUI)">
            <option value="ltx">LTX 2.3</option>
            <option value="wan">WAN 2.2</option>
          </optgroup>
          <optgroup label="Cloud API (fal.ai)">
            <option value="fal_seedance">Seedance 2.0</option>
            <option value="fal_kling">Kling 2.5 Turbo Pro</option>
            <option value="fal_veo">Veo 3.1</option>
            <option value="fal_runway">Runway Gen-3 Turbo</option>
          </optgroup>
        </select>
      </div>
      {rec && showContinuity && (
        <div className="recommend-card">
          <div className="scene-meta">
            Recommends <strong>{rec.engineId}</strong> ({Math.round(rec.confidence * 100)}%)
          </div>
          <button
            type="button"
            onClick={() => update({ engine: rec.engineId as EngineName })}
          >
            Apply recommendation
          </button>
        </div>
      )}
      <div className="field">
        <label>Duration (seconds)</label>
        <input
          type="number"
          min={1}
          max={30}
          step={0.5}
          value={scene.duration_sec}
          onChange={(e) => update({ duration_sec: Number(e.target.value) })}
        />
      </div>
      <div className="field">
        <label>Aspect ratio</label>
        <select
          value={scene.aspect_ratio || "16:9"}
          onChange={(e) => update({ aspect_ratio: e.target.value })}
        >
          {["1:1", "4:3", "3:2", "16:10", "16:9", "18:9", "21:9", "9:16", "2.39:1", "custom"].map((a) => (
            <option key={a} value={a}>
              {a}
            </option>
          ))}
        </select>
      </div>
      {(scene.aspect_ratio || "16:9") === "custom" && (
        <div className="row-actions">
          <label className="scene-meta">
            W
            <input
              style={{ width: 80 }}
              type="number"
              value={scene.width || project.width}
              onChange={(e) => update({ width: Number(e.target.value) })}
            />
          </label>
          <label className="scene-meta">
            H
            <input
              style={{ width: 80 }}
              type="number"
              value={scene.height || project.height}
              onChange={(e) => update({ height: Number(e.target.value) })}
            />
          </label>
        </div>
      )}
      <div className="field">
        <label>Frame rate</label>
        <select
          value={scene.fps_mode || "auto"}
          onChange={(e) => {
            const v = e.target.value;
            if (v === "auto") update({ fps_mode: "auto", fps: 0 });
            else update({ fps_mode: v, fps: Number(v) });
          }}
        >
          <option value="auto">Auto</option>
          {[12, 16, 18, 24, 25, 30, 48, 50, 60].map((f) => (
            <option key={f} value={String(f)}>
              {f} fps
            </option>
          ))}
        </select>
        {(project.vram_gb || 32) < 32 && (scene.fps_mode || "auto") !== "auto" && (
          <p className="scene-meta">Override on &lt;32 GB VRAM may be clamped by the execution plan.</p>
        )}
      </div>
      <div className="field prompt-box">
        <label>Scene prompt (@tags supported)</label>
        <textarea value={scene.prompt} onChange={(e) => onPrompt(e.target.value)} />
        {suggestOpen && tags.length > 0 && (
          <div className="suggest">
            {tags.map((t) => (
              <button key={t} type="button" onClick={() => insertTag(t)}>
                @{t}
              </button>
            ))}
          </div>
        )}
      </div>
      <div className="field">
        <label>Camera note</label>
        <input
          value={scene.camera_note}
          onChange={(e) => update({ camera_note: e.target.value })}
          placeholder="slow push in from doorway"
        />
      </div>
      <div className="field">
        <label>Seed</label>
        <input type="number" value={scene.seed} onChange={(e) => update({ seed: Number(e.target.value) })} />
      </div>
      <div className="field">
        <label>
          <input
            type="checkbox"
            checked={!!scene.lipsync_enabled}
            onChange={(e) => update({ lipsync_enabled: e.target.checked })}
            style={{ width: "auto", marginRight: 8 }}
          />
          Enable lip sync after render
        </label>
      </div>
      <div className="field">
        <label>Lip sync / dialogue audio</label>
        <select
          value={scene.lipsync_audio_asset_id || scene.audio_asset_id || ""}
          onChange={(e) =>
            update({
              lipsync_audio_asset_id: e.target.value || null,
              audio_asset_id: e.target.value || null,
            })
          }
        >
          <option value="">None</option>
          {project.assets
            .filter((a) => a.kind === "audio")
            .map((a) => (
              <option key={a.id} value={a.id}>
                @{a.tag || a.filename}
              </option>
            ))}
        </select>
      </div>
      {showContinuity && (
        <>
          <div className="section-label">Continuity locks</div>
          <p className="scene-meta">Production instructions — not model guarantees.</p>
          <div className="continuity-grid">
            {CONTINUITY_KEYS.map((k) => (
              <label key={k} className="continuity-row">
                <span>{k.replace(/_/g, " ")}</span>
                <select
                  value={continuity[k]}
                  onChange={(e) => setLock(k, e.target.value as ContinuityLock)}
                >
                  <option value="locked">locked</option>
                  <option value="unlocked">unlocked</option>
                  <option value="inherit_project">inherit project</option>
                  <option value="inherit_previous">inherit previous</option>
                </select>
              </label>
            ))}
          </div>
        </>
      )}
      <div className="row-actions">
        <button
          className="primary"
          onClick={async () => {
            await api.render(project.id, "scene", scene.id);
            onChange();
          }}
        >
          Retake scene
        </button>
        <button
          onClick={async () => {
            await api.lipsync(project.id, scene.id);
            onChange();
          }}
        >
          Lip sync only
        </button>
        <button
          className="danger"
          onClick={async () => {
            await api.deleteScene(project.id, scene.id);
            onChange();
          }}
        >
          Delete scene
        </button>
      </div>
    </div>
  );
}
