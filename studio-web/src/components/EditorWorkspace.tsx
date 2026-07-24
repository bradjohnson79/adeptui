import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Project } from "../types";
import type { EditorTab } from "../workspacePrefs";
import { PanelHeading } from "./HelpTip";

export type EditorClip = {
  id: string;
  asset_id?: string | null;
  output_path?: string | null;
  start: number;
  length: number;
  trim_start?: number;
  label?: string;
  source_director_sequence_id?: string | null;
  source_version?: number;
  source_scene_id?: string | null;
  pending_newer_version?: number | null;
  placeholder?: boolean;
  include_audio?: boolean;
  proxy?: boolean;
};

export type EditorTracks = {
  video: EditorClip[];
  video_b: EditorClip[];
  placeholder: EditorClip[];
  titles: EditorClip[];
  dialogue: EditorClip[];
  sfx: EditorClip[];
  ambience: EditorClip[];
  music: EditorClip[];
};

export type EditorProject = {
  id: string;
  project_id: string;
  name: string;
  status: string;
  tracks: EditorTracks;
  playhead?: number;
  updated_at?: string;
};

const TRACK_META: { key: keyof EditorTracks; label: string }[] = [
  { key: "video", label: "Video 1" },
  { key: "video_b", label: "Video 2" },
  { key: "placeholder", label: "Placeholder" },
  { key: "titles", label: "Titles" },
  { key: "dialogue", label: "Dialogue" },
  { key: "sfx", label: "SFX" },
  { key: "ambience", label: "Ambience" },
  { key: "music", label: "Music" },
];

const EDITORIAL_CTX_KEY = "adept_editorial_context";

export type EditorialContext = {
  needed_duration_sec?: number;
  prev_clip_label?: string;
  next_clip_label?: string;
  required_ending?: string;
  screen_direction?: string;
  audio_overlap_sec?: number;
  source_director_sequence_id?: string;
  source_scene_id?: string;
  clip_id?: string;
};

function nid() {
  return `clip-${Math.random().toString(36).slice(2, 10)}`;
}

/**
 * Editor — assemble approved Director sequences into complete scenes.
 * Director creates the shots. Editor creates the film.
 */
export function EditorWorkspace({
  project,
  onChange,
  onGo,
  onSelectScene,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
  onSelectScene?: (sceneId: string) => void;
}) {
  const [editor, setEditor] = useState<EditorProject | null>(null);
  const [sequences, setSequences] = useState<any[]>([]);
  const [selectedClip, setSelectedClip] = useState<{ track: keyof EditorTracks; id: string } | null>(null);
  const [previewIdx, setPreviewIdx] = useState(0);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string>("approved");

  const load = useCallback(async () => {
    const [ed, seqs] = await Promise.all([
      api.getEditor(project.id),
      api.listDirectorSequences(project.id).catch(() => []),
    ]);
    setEditor(ed);
    setSequences(seqs || []);
  }, [project.id]);

  useEffect(() => {
    load().catch((e) => setMsg(e instanceof Error ? e.message : "Failed to load Editor"));
  }, [load, project.updated_at]);

  const save = async (next: EditorProject) => {
    setEditor(next);
    setBusy(true);
    try {
      const saved = await api.putEditor(project.id, next as any);
      setEditor(saved);
      await onChange?.();
    } finally {
      setBusy(false);
    }
  };

  const approvedSources = useMemo(() => {
    const list = sequences.filter((s) =>
      statusFilter === "all"
        ? true
        : statusFilter === "approved"
          ? s.status === "approved" || s.status === "used_in_editor"
          : s.status === statusFilter
    );
    return list;
  }, [sequences, statusFilter]);

  const videoClips = editor?.tracks?.video || [];
  const activeClip = selectedClip
    ? (editor?.tracks?.[selectedClip.track] || []).find((c) => c.id === selectedClip.id)
    : videoClips[previewIdx];

  const previewSrc = useMemo(() => {
    if (!activeClip) return "";
    if (activeClip.asset_id) return api.assetUrl(activeClip.asset_id);
    if (activeClip.output_path) return api.mediaUrl(activeClip.output_path);
    return "";
  }, [activeClip]);

  const pendingBanners = useMemo(() => {
    if (!editor) return [];
    const out: { track: keyof EditorTracks; clip: EditorClip }[] = [];
    for (const { key } of TRACK_META) {
      for (const clip of editor.tracks?.[key] || []) {
        if (clip.pending_newer_version && clip.pending_newer_version > (clip.source_version || 0)) {
          out.push({ track: key, clip });
        }
      }
    }
    return out;
  }, [editor]);

  const addSequenceToVideo = async (seq: any) => {
    if (!editor) return;
    setBusy(true);
    try {
      const res = await api.sendDirectorToEditor(project.id, seq.id, {
        track: "video",
        include_audio: true,
        label: seq.name,
      });
      setEditor(res.editor);
      setMsg(`Added “${seq.name}” to Video 1`);
      await onChange?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Add failed");
    } finally {
      setBusy(false);
    }
  };

  const updateClip = (track: keyof EditorTracks, clipId: string, patch: Partial<EditorClip>) => {
    if (!editor) return;
    const next = {
      ...editor,
      tracks: {
        ...editor.tracks,
        [track]: (editor.tracks[track] || []).map((c) => (c.id === clipId ? { ...c, ...patch } : c)),
      },
    };
    void save(next);
  };

  const openInDirector = (clip: EditorClip) => {
    if (clip.source_scene_id) onSelectScene?.(clip.source_scene_id);
    if (clip.source_director_sequence_id) {
      try {
        sessionStorage.setItem("adept_director_sequence_id", clip.source_director_sequence_id);
      } catch {
        /* ignore */
      }
    }
    onGo("director");
  };

  const generateReplacement = (track: keyof EditorTracks, clip: EditorClip) => {
    const clips = editor?.tracks?.[track] || [];
    const idx = clips.findIndex((c) => c.id === clip.id);
    const ctx: EditorialContext = {
      needed_duration_sec: clip.length,
      prev_clip_label: idx > 0 ? clips[idx - 1]?.label : undefined,
      next_clip_label: idx >= 0 && idx < clips.length - 1 ? clips[idx + 1]?.label : undefined,
      required_ending: "",
      screen_direction: "",
      audio_overlap_sec: 0.25,
      source_director_sequence_id: clip.source_director_sequence_id || undefined,
      source_scene_id: clip.source_scene_id || undefined,
      clip_id: clip.id,
    };
    try {
      sessionStorage.setItem(EDITORIAL_CTX_KEY, JSON.stringify(ctx));
    } catch {
      /* ignore */
    }
    openInDirector(clip);
  };

  const resolveNewer = async (
    track: keyof EditorTracks,
    clip: EditorClip,
    action: "replace" | "alternate" | "compare" | "ignore"
  ) => {
    if (!editor || !clip.source_director_sequence_id) return;
    const seq = await api.getDirectorSequence(project.id, clip.source_director_sequence_id);
    const tracks = { ...editor.tracks };

    if (action === "ignore") {
      updateClip(track, clip.id, { pending_newer_version: null });
      setMsg("Ignored newer Director output");
      return;
    }

    if (action === "replace") {
      updateClip(track, clip.id, {
        asset_id: seq.asset_id,
        output_path: seq.output_path || seq.lipsync_output_path,
        source_version: seq.version,
        pending_newer_version: null,
        label: clip.label || seq.name,
      });
      setMsg("Replaced clip with newer Director version");
      return;
    }

    if (action === "alternate") {
      const alt: EditorClip = {
        id: nid(),
        asset_id: seq.asset_id,
        output_path: seq.output_path || seq.lipsync_output_path,
        start: clip.start + clip.length,
        length: clip.length,
        trim_start: 0,
        label: `${clip.label || seq.name} (alt v${seq.version})`,
        source_director_sequence_id: seq.id,
        source_version: seq.version,
        source_scene_id: seq.scene_id,
        pending_newer_version: null,
      };
      tracks[track] = [...(tracks[track] || []), alt];
      tracks[track] = (tracks[track] || []).map((c) =>
        c.id === clip.id ? { ...c, pending_newer_version: null } : c
      );
      await save({ ...editor, tracks });
      setMsg("Added alternate version beside existing clip");
      return;
    }

    // compare — leave both; clear pending and store note
    updateClip(track, clip.id, {
      pending_newer_version: null,
      label: `${clip.label || "Clip"} · compare v${seq.version} available`,
    });
    setMsg("Compare: open both versions from Director Sources — clip left unchanged");
  };

  const buildAudioFromDirector = async () => {
    if (!editor) return;
    const sources = sequences.filter((s) => s.status === "approved" || s.status === "used_in_editor");
    if (!sources.length) {
      setMsg("No approved Director sequences with audio intent");
      return;
    }
    const tracks = { ...editor.tracks };
    let added = 0;
    for (const seq of sources) {
      const intents: string[] = seq.audio_intent || [];
      const start = Math.max(
        0,
        ...((tracks.video || []).map((c) => c.start + c.length) as number[])
      );
      for (const intent of intents) {
        const kind: keyof EditorTracks = /ambi|room|atmos/i.test(intent) ? "ambience" : "sfx";
        tracks[kind] = [
          ...(tracks[kind] || []),
          {
            id: nid(),
            asset_id: null,
            start,
            length: Number(seq.settings?.duration_sec || 5),
            trim_start: 0,
            label: `[intent] ${intent}`,
            source_director_sequence_id: seq.id,
            source_version: seq.version,
            placeholder: true,
          },
        ];
        added += 1;
      }
    }
    await save({ ...editor, tracks });
    setMsg(`Added ${added} placeholder SFX/ambience clips from Director audio intent`);
  };

  const statusChips = ["all", "approved", "draft", "generating", "variations", "used_in_editor"];

  if (!editor) {
    return (
      <div className="page">
        <PanelHeading title="Editor" tip="Assemble approved Director sequences into complete scenes." />
        <p className="empty">Loading Editor…</p>
      </div>
    );
  }

  return (
    <div className="page editor-workspace">
      <PanelHeading
        title="Editor"
        tip="Assemble approved Director outputs into scenes. Non-destructive — newer Director versions never auto-overwrite clips."
      >
        <span className="scene-meta">{busy ? "Saving…" : editor.status.replace(/_/g, " ")}</span>
      </PanelHeading>
      <p className="muted">Director creates the shots. Editor creates the film.</p>
      {msg && <p className="pill">{msg}</p>}

      {pendingBanners.map(({ track, clip }) => (
        <div key={clip.id} className="dash-card" style={{ marginBottom: "0.75rem", borderColor: "var(--accent, #2a9d8f)" }}>
          <strong>Newer Director output available</strong>
          <p className="muted" style={{ margin: "0.25rem 0" }}>
            “{clip.label}” on {track} — sequence v{clip.pending_newer_version} vs clip v{clip.source_version}
          </p>
          <div className="row-actions">
            <button type="button" className="primary" onClick={() => resolveNewer(track, clip, "replace")}>
              Replace
            </button>
            <button type="button" onClick={() => resolveNewer(track, clip, "alternate")}>
              Alternate
            </button>
            <button type="button" onClick={() => resolveNewer(track, clip, "compare")}>
              Compare
            </button>
            <button type="button" onClick={() => resolveNewer(track, clip, "ignore")}>
              Ignore
            </button>
          </div>
        </div>
      ))}

      <div className="library-layout" style={{ alignItems: "stretch" }}>
        <aside className="library-inspector" style={{ maxWidth: 320 }}>
          <h2>Director Sources</h2>
          <p className="muted">Approved Prompt Timeline packages</p>
          <div className="row" style={{ flexWrap: "wrap", gap: "0.35rem", marginBottom: "0.75rem" }}>
            {statusChips.map((s) => (
              <button
                key={s}
                type="button"
                className={statusFilter === s ? "primary" : ""}
                onClick={() => setStatusFilter(s)}
              >
                {s === "used_in_editor" ? "Used in Editor" : s}
              </button>
            ))}
          </div>
          {!approvedSources.length ? (
            <p className="empty">No sequences. Approve a shot in Director, then Send to Editor.</p>
          ) : (
            <ul className="ms-list">
              {approvedSources.map((s) => (
                <li key={s.id} style={{ marginBottom: "0.5rem" }}>
                  <strong>{s.name}</strong>
                  <span className="scene-meta">
                    {" "}
                    · v{s.version} · {s.status}
                  </span>
                  <div className="row-actions" style={{ marginTop: 4 }}>
                    <button type="button" disabled={busy} onClick={() => addSequenceToVideo(s)}>
                      Add to Video 1
                    </button>
                    {s.scene_id && (
                      <button
                        type="button"
                        onClick={() => {
                          onSelectScene?.(s.scene_id);
                          onGo("director");
                        }}
                      >
                        Open in Director
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <div className="row-actions" style={{ marginTop: "1rem" }}>
            <button type="button" onClick={() => void buildAudioFromDirector()}>
              Build Audio from Director Sequence
            </button>
          </div>
        </aside>

        <div>
          <h2 className="section-heading" style={{ fontSize: "1.15rem" }}>
            Editor Preview
          </h2>
          <div className="director-stage" style={{ minHeight: 220, marginBottom: "1rem" }}>
            {previewSrc ? (
              <video key={previewSrc} src={previewSrc} controls playsInline />
            ) : (
              <div className="director-stage-empty">
                <strong>Rough stitch preview</strong>
                <span>Add approved Director sequences to Video 1</span>
              </div>
            )}
          </div>
          {videoClips.length > 0 && (
            <div className="row-actions" style={{ marginBottom: "0.75rem" }}>
              <span className="scene-meta">Stitch order</span>
              {videoClips.map((c, i) => (
                <button
                  key={c.id}
                  type="button"
                  className={previewIdx === i ? "primary" : ""}
                  onClick={() => {
                    setPreviewIdx(i);
                    setSelectedClip({ track: "video", id: c.id });
                  }}
                >
                  {i + 1}. {c.label || c.id.slice(0, 6)}
                </button>
              ))}
            </div>
          )}

          <div className="track-board" style={{ overflowX: "auto" }}>
            {TRACK_META.map(({ key, label }) => (
              <div key={key} className="track-row" style={{ marginBottom: 6 }}>
                <div className="track-label">{label}</div>
                <div className="track-lane" style={{ minHeight: 36, display: "flex", gap: 4, flexWrap: "wrap" }}>
                  {(editor.tracks[key] || []).length === 0 && (
                    <span className="track-empty scene-meta">Empty</span>
                  )}
                  {(editor.tracks[key] || []).map((clip) => (
                    <button
                      key={clip.id}
                      type="button"
                      className={`track-clip ${selectedClip?.id === clip.id ? "active" : ""}`}
                      style={{ position: "relative", minWidth: 100 }}
                      onClick={() => setSelectedClip({ track: key, id: clip.id })}
                    >
                      <strong>{clip.label || "Clip"}</strong>
                      <span>
                        {clip.start.toFixed(1)}s · {clip.length.toFixed(1)}s
                        {clip.placeholder ? " · placeholder" : ""}
                        {clip.pending_newer_version ? " · newer!" : ""}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>

          {selectedClip && activeClip && (
            <div className="segment-editor" style={{ marginTop: "1rem" }}>
              <div className="section-label">Selected clip</div>
              <div className="row-actions">
                <label className="scene-meta">
                  Start
                  <input
                    style={{ width: 72 }}
                    type="number"
                    step={0.1}
                    value={activeClip.start}
                    onChange={(e) =>
                      updateClip(selectedClip.track, activeClip.id, { start: Number(e.target.value) || 0 })
                    }
                  />
                </label>
                <label className="scene-meta">
                  Length
                  <input
                    style={{ width: 72 }}
                    type="number"
                    step={0.1}
                    min={0.1}
                    value={activeClip.length}
                    onChange={(e) =>
                      updateClip(selectedClip.track, activeClip.id, { length: Number(e.target.value) || 1 })
                    }
                  />
                </label>
                <label className="scene-meta">
                  Trim start
                  <input
                    style={{ width: 72 }}
                    type="number"
                    step={0.1}
                    min={0}
                    value={activeClip.trim_start || 0}
                    onChange={(e) =>
                      updateClip(selectedClip.track, activeClip.id, {
                        trim_start: Number(e.target.value) || 0,
                      })
                    }
                  />
                </label>
              </div>
              <div className="row-actions" style={{ marginTop: 8 }}>
                <button type="button" onClick={() => openInDirector(activeClip)}>
                  Open in Director
                </button>
                <button type="button" onClick={() => generateReplacement(selectedClip.track, activeClip)}>
                  Generate Replacement
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function readEditorialContext(): EditorialContext | null {
  try {
    const raw = sessionStorage.getItem(EDITORIAL_CTX_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as EditorialContext;
  } catch {
    return null;
  }
}

export function clearEditorialContext() {
  try {
    sessionStorage.removeItem(EDITORIAL_CTX_KEY);
  } catch {
    /* ignore */
  }
}
