import { useMemo, useRef, useState } from "react";
import type { Asset, EngineName, Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

export function AssetTray({ project, onChange }: { project: Project; onChange: () => void }) {
  const [tag, setTag] = useState("");
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

  return (
    <div className="panel">
      <PanelHeading
        title="Assets"
        tip="Upload images, audio, or video and tag them. Type @tag in prompts to lock identity, set, or sound references."
      />
      <p className="scene-meta">Tag assets to reference them with @name in prompts.</p>
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
      <div className="section-label">Library</div>
      <div className="asset-list">
        {project.assets.length === 0 && <div className="empty">No assets yet</div>}
        {project.assets.map((a: Asset) => (
          <div className="asset-item" key={a.id}>
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
}: {
  project: Project;
  sceneId?: string;
  onChange: () => void;
}) {
  const scene = project.scenes.find((s) => s.id === sceneId) || project.scenes[0];
  const [suggestOpen, setSuggestOpen] = useState(false);
  const tags = useMemo(() => project.assets.filter((a) => a.tag).map((a) => a.tag), [project.assets]);

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

  return (
    <div className="panel">
      <PanelHeading
        title={scene.name}
        tip="Per-scene engine, duration, and prompt. Use @tags from Assets. Director tracks hold the full multi-track timeline."
      />
      <div className="field">
        <label>Engine</label>
        <select value={scene.engine} onChange={(e) => update({ engine: e.target.value as EngineName })}>
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
