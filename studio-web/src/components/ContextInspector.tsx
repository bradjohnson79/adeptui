import { useEffect, useState } from "react";
import type { Job, Project, Scene } from "../types";
import { api } from "../api";
import { continuityLockedCount, parseContinuity, CONTINUITY_KEYS, type ContinuityLock } from "../directorSelection";
import { useDirectorSelection } from "./DirectorSelectionContext";
import { JobPanel } from "./JobPanel";
import { GpuVramPanel } from "./GpuVramPanel";
import { PanelHeading } from "./HelpTip";

function GlobalPromptCard({ project, onChange }: { project: Project; onChange: () => void }) {
  const [value, setValue] = useState(project.global_prompt);
  useEffect(() => setValue(project.global_prompt), [project.global_prompt]);
  return (
    <div className="panel inspector-section">
      <PanelHeading
        title="Global prompt"
        tip="Look, feel, and theme for the whole project—applied across cuts and characters."
      />
      <textarea
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => api.updateProject(project.id, { global_prompt: value }).then(onChange)}
        placeholder="cinematic warm tungsten look…"
      />
    </div>
  );
}

function ContinuitySummary({ scene, project, onChange }: { scene: Scene; project: Project; onChange: () => void }) {
  const summary = continuityLockedCount(scene.continuity_json);
  const keys = parseContinuity(scene.continuity_json);
  const setLock = async (key: string, mode: ContinuityLock) => {
    const next = { ...keys, [key]: mode };
    await api.updateScene(project.id, scene.id, {
      ...scene,
      continuity_json: JSON.stringify(next),
    });
    onChange();
  };
  return (
    <div className="panel inspector-section">
      <PanelHeading title="Continuity" tip="Production locks for identity/wardrobe/env. Adapters do not enforce these yet." />
      <div className="pill">
        {summary.locked} of {summary.total} locked
      </div>
      <div className="continuity-grid">
        {CONTINUITY_KEYS.map((k) => (
          <label key={k} className="continuity-row">
            <span>{k.replace(/_/g, " ")}</span>
            <select value={keys[k]} onChange={(e) => setLock(k, e.target.value as ContinuityLock)}>
              <option value="locked">locked</option>
              <option value="unlocked">unlocked</option>
              <option value="inherit_project">inherit project</option>
              <option value="inherit_previous">inherit previous</option>
            </select>
          </label>
        ))}
      </div>
    </div>
  );
}

export function ContextInspector({
  project,
  scene,
  onChange,
}: {
  project: Project;
  scene?: Scene;
  onChange: () => void;
}) {
  const { selection, setSelection } = useDirectorSelection();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [rec, setRec] = useState<Awaited<ReturnType<typeof api.recommendEngine>> | null>(null);

  useEffect(() => {
    let alive = true;
    api.listJobs(project.id).then((list) => {
      if (alive) setJobs(list);
    });
    const id = setInterval(() => {
      api.listJobs(project.id).then((list) => {
        if (alive) setJobs(list);
      });
    }, 3000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, [project.id]);

  useEffect(() => {
    if (!scene || selection.kind !== "scene") {
      setRec(null);
      return;
    }
    api.recommendEngine(project.id, scene.id).then(setRec).catch(() => setRec(null));
  }, [project.id, scene?.id, selection.kind, scene?.engine]);

  const selectedJob = selection.kind === "job" ? jobs.find((j) => j.id === selection.id) : null;

  if (selection.kind === "job" && selectedJob) {
    return (
      <div className="inspector-stack">
        <div className="panel inspector-section">
          <PanelHeading title="Job" tip="Queue item details. Progress comes from worker messages — not fabricated stages." />
          <div className="scene-head">
            <strong>{selectedJob.kind}</strong>
            <span className="scene-meta">{selectedJob.status}</span>
          </div>
          <p className="scene-meta">{selectedJob.message || "No message"}</p>
          <div className="bar">
            <i style={{ width: `${Math.round((selectedJob.progress || 0) * 100)}%` }} />
          </div>
          {(selectedJob.status === "queued" || selectedJob.status === "running") && (
            <button style={{ marginTop: 8 }} onClick={() => api.cancelJob(selectedJob.id).then(onChange)}>
              Cancel
            </button>
          )}
        </div>
        <JobPanel
          projectId={project.id}
          onDone={onChange}
          onSelectJob={(id) => setSelection({ kind: "job", id })}
        />
      </div>
    );
  }

  if (selection.kind === "scene" && scene) {
    return (
      <div className="inspector-stack">
        <div className="panel inspector-section">
          <PanelHeading title="Scene" tip="Name, engine, duration, camera, seed, retake." />
          <div className="field">
            <label>Name</label>
            <input
              value={scene.name}
              onChange={(e) => api.updateScene(project.id, scene.id, { ...scene, name: e.target.value }).then(onChange)}
            />
          </div>
          <div className="field">
            <label>Engine {scene.engine === "auto" ? <span className="pill">Auto</span> : null}</label>
            <select
              value={scene.engine}
              onChange={(e) =>
                api.updateScene(project.id, scene.id, { ...scene, engine: e.target.value as Scene["engine"] }).then(onChange)
              }
            >
              <optgroup label="Auto">
                <option value="auto">Auto Select</option>
              </optgroup>
              <optgroup label="Local">
                <option value="ltx">LTX 2.3</option>
                <option value="wan">WAN 2.2</option>
              </optgroup>
              <optgroup label="Cloud">
                <option value="fal_seedance">Seedance</option>
                <option value="fal_kling">Kling</option>
                <option value="fal_veo">Veo</option>
                <option value="fal_runway">Runway</option>
              </optgroup>
            </select>
          </div>
          {rec && (
            <div className="recommend-card">
              <div className="scene-meta">
                Suggests <strong>{rec.engineId}</strong> ({Math.round(rec.confidence * 100)}%
                {rec.local ? ", local" : ", cloud"})
              </div>
              <ul className="scene-meta">
                {rec.reasons.slice(0, 3).map((r) => (
                  <li key={r}>{r}</li>
                ))}
              </ul>
              {rec.warnings[0] && <div className="pill warn">{rec.warnings[0]}</div>}
              <button
                type="button"
                className="primary"
                style={{ marginTop: 8 }}
                onClick={() =>
                  api
                    .updateScene(project.id, scene.id, { ...scene, engine: rec.engineId as Scene["engine"] })
                    .then(onChange)
                }
              >
                Apply recommendation
              </button>
            </div>
          )}
          <div className="field">
            <label>Duration</label>
            <input
              type="number"
              min={1}
              max={30}
              step={0.5}
              value={scene.duration_sec}
              onChange={(e) =>
                api
                  .updateScene(project.id, scene.id, { ...scene, duration_sec: Number(e.target.value) })
                  .then(onChange)
              }
            />
          </div>
          <div className="field">
            <label>Camera</label>
            <input
              value={scene.camera_note}
              onChange={(e) =>
                api.updateScene(project.id, scene.id, { ...scene, camera_note: e.target.value }).then(onChange)
              }
            />
          </div>
          <div className="field">
            <label>Seed</label>
            <input
              type="number"
              value={scene.seed}
              onChange={(e) =>
                api.updateScene(project.id, scene.id, { ...scene, seed: Number(e.target.value) }).then(onChange)
              }
            />
          </div>
          <button
            className="primary"
            onClick={() => api.render(project.id, "scene", scene.id).then(onChange)}
          >
            Retake scene
          </button>
        </div>
        <ContinuitySummary scene={scene} project={project} onChange={onChange} />
        <GpuVramPanel project={project} onChange={onChange} compact />
      </div>
    );
  }

  if (
    selection.kind === "promptSeg" ||
    selection.kind === "imageClip" ||
    selection.kind === "videoClip" ||
    selection.kind === "audio" ||
    selection.kind === "sfx" ||
    selection.kind === "lipsync" ||
    selection.kind === "lipsyncTrack" ||
    selection.kind === "lipsyncClip"
  ) {
    return (
      <div className="inspector-stack">
        <div className="panel inspector-section">
          <PanelHeading
            title={
              selection.kind === "promptSeg"
                ? "Prompt segment"
                : selection.kind === "imageClip"
                  ? "Image clip"
                  : selection.kind === "videoClip"
                    ? "Video clip"
                    : selection.kind === "audio"
                      ? "Audio"
                      : selection.kind === "sfx"
                        ? "SFX"
                        : selection.kind === "lipsyncTrack"
                          ? "Lip sync track"
                          : selection.kind === "lipsyncClip"
                            ? "Lip sync clip"
                            : "Lip sync"
            }
            tip="Edit details in the Timeline / Prompt / Lip Sync workspace tabs. Selection drives this inspector."
          />
          <p className="scene-meta">Selected: {selection.id || "item"}</p>
          <p className="scene-meta">Use the main workspace tabs for full editors (weight, split, replace, ROI).</p>
        </div>
        <GlobalPromptCard project={project} onChange={onChange} />
        <JobPanel projectId={project.id} onDone={onChange} onSelectJob={(id) => setSelection({ kind: "job", id })} />
        <GpuVramPanel project={project} onChange={onChange} compact />
      </div>
    );
  }

  // Default: global + jobs + GPU
  return (
    <div className="inspector-stack">
      <GlobalPromptCard project={project} onChange={onChange} />
      <JobPanel projectId={project.id} onDone={onChange} onSelectJob={(id) => setSelection({ kind: "job", id })} />
      <GpuVramPanel project={project} onChange={onChange} />
    </div>
  );
}
