import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";
import { PanelHeading } from "./HelpTip";

/**
 * Audio Studio stub — list/upload audio assets and hand off to Editor tracks.
 * Full Foley / music generation is out of scope this pass.
 */
export function AudioStudioWorkspace({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const [audios, setAudios] = useState<any[]>([]);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = async () => {
    const lib = await api.library(project.id).catch(() => []);
    setAudios((lib || []).filter((a: any) => a.kind === "audio"));
  };

  useEffect(() => {
    refresh().catch(console.error);
  }, [project.id, project.assets?.length]);

  const upload = async (file: File) => {
    setBusy(true);
    setMsg("");
    try {
      const tag = `audio_${Date.now()}`;
      await api.uploadAsset(project.id, file, tag, "audio");
      setMsg(`Uploaded ${file.name}`);
      await onChange?.();
      await refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusy(false);
    }
  };

  const addToEditor = async (asset: any, track: "music" | "sfx" | "ambience" | "dialogue") => {
    setBusy(true);
    setMsg("");
    try {
      const editor = await api.getEditor(project.id);
      const clips = [...(editor.tracks?.[track] || [])];
      const start = Math.max(0, ...clips.map((c: any) => Number(c.start || 0) + Number(c.length || 0)));
      clips.push({
        id: `clip-${Math.random().toString(36).slice(2, 10)}`,
        asset_id: asset.id,
        start,
        length: 5,
        trim_start: 0,
        label: asset.tag || asset.filename || "Audio",
        placeholder: false,
      });
      await api.putEditor(project.id, {
        ...editor,
        tracks: { ...editor.tracks, [track]: clips },
      });
      setMsg(`Added to Editor ${track} track`);
      await onChange?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Add failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page">
      <PanelHeading
        title="Audio Studio"
        tip="Stub workspace: manage audio assets and send them to Editor music/SFX tracks. Synthesis and DAW tools land later."
      />
      <p className="muted">
        Thin stub this pass — generation lives later. Use Director <strong>Audio Intent</strong> for cue labels, then
        build placeholders in Editor.
      </p>
      {msg && <p className="pill">{msg}</p>}

      <div className="row-actions" style={{ marginBottom: "1rem" }}>
        <input
          ref={fileRef}
          type="file"
          accept="audio/*"
          hidden
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) void upload(f);
            e.target.value = "";
          }}
        />
        <button type="button" className="primary" disabled={busy} onClick={() => fileRef.current?.click()}>
          Upload audio
        </button>
        <button type="button" onClick={() => onGo("editor")}>
          Open Editor
        </button>
        <button type="button" onClick={() => onGo("director")}>
          Open Director (Audio Intent)
        </button>
      </div>

      {!audios.length ? (
        <p className="empty">No audio assets yet. Upload dialogue, music, or SFX beds.</p>
      ) : (
        <ul className="ms-list">
          {audios.map((a) => (
            <li key={a.id} style={{ marginBottom: "0.65rem" }}>
              <strong>{a.tag || a.filename}</strong>
              <span className="scene-meta"> · audio</span>
              <div className="row-actions" style={{ marginTop: 4 }}>
                <audio src={api.assetUrl(a.id)} controls style={{ maxWidth: 280, height: 32 }} />
                <button type="button" disabled={busy} onClick={() => addToEditor(a, "music")}>
                  Add to Editor music
                </button>
                <button type="button" disabled={busy} onClick={() => addToEditor(a, "sfx")}>
                  Add to Editor SFX
                </button>
                <button type="button" disabled={busy} onClick={() => addToEditor(a, "ambience")}>
                  Add to Editor ambience
                </button>
                <button type="button" disabled={busy} onClick={() => addToEditor(a, "dialogue")}>
                  Add to Editor dialogue
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
