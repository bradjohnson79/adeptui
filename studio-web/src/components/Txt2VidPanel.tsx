import { useEffect, useMemo, useState } from "react";
import { api } from "../api";
import type { Job, Project } from "../types";
import {
  ASPECT_PRESETS,
  FPS_OPTIONS,
  STYLE_PRESETS,
  resolutionToSize,
  type EditorTab,
} from "../workspacePrefs";
import { JobPanel } from "./JobPanel";

function projectDefaults(project: Project): Record<string, any> {
  try {
    return project.defaults_json ? JSON.parse(project.defaults_json) : {};
  } catch {
    return {};
  }
}

export function Txt2VidPanel({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const d = projectDefaults(project);
  const [prompt, setPrompt] = useState("");
  const [negative, setNegative] = useState(project.negative_prompt);
  const [style, setStyle] = useState(String(d.prompt_style || STYLE_PRESETS[0]));
  const [aspect, setAspect] = useState(String(d.aspect || "16:9"));
  const [fps, setFps] = useState<string>(String(d.fps ?? "auto"));
  const [duration, setDuration] = useState(5);
  const [engine, setEngine] = useState(String(d.engine || "auto"));
  const [resolution, setResolution] = useState(String(d.resolution || "720p"));
  const [history, setHistory] = useState<string[]>(() => {
    try {
      return JSON.parse(localStorage.getItem("adept_txt2vid_history") || "[]");
    } catch {
      return [];
    }
  });
  const [busy, setBusy] = useState(false);
  const [job, setJob] = useState<Job | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [tip, setTip] = useState<string | null>(null);
  const [outputAssetId, setOutputAssetId] = useState<string | null>(null);

  const size = useMemo(() => resolutionToSize(resolution, aspect), [resolution, aspect]);

  const vramWarn = useMemo(() => {
    const pixels = size.width * size.height;
    if (project.vram_gb < 16 && (resolution === "4K" || duration > 8)) {
      return "VRAM planner: 4K / long duration may exceed local capacity — Auto prefers fal T2V.";
    }
    if (project.vram_gb < 24 && pixels > 1920 * 1080) {
      return "VRAM planner: oversized combo for local engines — prefer fal or lower resolution.";
    }
    return null;
  }, [size, resolution, duration, project.vram_gb]);

  useEffect(() => {
    const low = prompt.toLowerCase();
    if (/\b(character|person|hero|girl|boy|man|woman)\b/.test(low) && !/@/.test(prompt)) {
      setTip("Tip: create a Character Profile and reference with @profile — never auto-applied.");
    } else if (/\b(pan|dolly|orbit|crane|tracking)\b/.test(low)) {
      setTip("Tip: Director Camera Motion can encode intentional moves after promote.");
    } else {
      setTip(null);
    }
  }, [prompt]);

  useEffect(() => {
    if (!job || job.status === "done" || job.status === "failed" || job.status === "cancelled") return;
    const t = setInterval(() => {
      api.getJob(job.id).then((j) => {
        setJob(j);
        if (j.status === "done") {
          try {
            const p = JSON.parse(j.params_json || "{}");
            if (p.output_asset_id) setOutputAssetId(p.output_asset_id);
          } catch {
            /* ignore */
          }
          onChange();
          // learning hooks
          api
            .getLearning(project.id)
            .then((state) => {
              const items = [...(state.items || [])];
              const notes = [
                { category: "prompts", text: `Preferred Txt2Vid prompt length ~${prompt.split(/\s+/).length} words` },
                { category: "engines", text: `Txt2Vid engine preference: ${engine}` },
                { category: "pacing", text: `Txt2Vid duration preference: ${duration}s` },
                { category: "render", text: `Txt2Vid aspect ${aspect} @ ${resolution}` },
              ];
              for (const n of notes) {
                if (!items.some((i: any) => i.text === n.text)) {
                  items.push({ id: crypto.randomUUID(), ...n, enabled: true });
                }
              }
              return api.putLearning(project.id, { ...state, items });
            })
            .catch(() => undefined);
        }
      });
    }, 1500);
    return () => clearInterval(t);
  }, [job, onChange, project.id, prompt, engine, duration, aspect, resolution]);

  const generate = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const nextHist = [prompt, ...history.filter((h) => h !== prompt)].slice(0, 20);
      setHistory(nextHist);
      localStorage.setItem("adept_txt2vid_history", JSON.stringify(nextHist));
      const j = await api.txt2vid(project.id, {
        prompt,
        negative,
        style,
        aspect,
        fps,
        duration_sec: duration,
        engine,
        width: size.width,
        height: size.height,
        resolution,
      });
      setJob(j as Job);
    } catch (e: any) {
      setMsg(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  };

  const promote = async (target: string) => {
    if (!outputAssetId) {
      setMsg("Wait for generation to finish (asset id).");
      return;
    }
    await api.promote(project.id, { asset_id: outputAssetId, target });
    await onChange();
    setMsg(`Promoted → ${target}`);
  };

  return (
    <div className="page gen-workspace">
      <h1>Txt2Vid</h1>
      <p className="muted">Text-to-video. Local I2V engines need a start frame — Auto prefers fal T2V when none.</p>
      {vramWarn && <p className="pill warn">{vramWarn}</p>}
      {tip && <p className="pill">{tip}</p>}
      {msg && <p className="pill warn">{msg}</p>}

      <div className="field">
        <label>Prompt (@profile · #motion)</label>
        <textarea value={prompt} onChange={(e) => setPrompt(e.target.value)} rows={4} />
      </div>
      <div className="field">
        <label>Negative</label>
        <textarea value={negative} onChange={(e) => setNegative(e.target.value)} rows={2} />
      </div>
      <div className="field">
        <label>History</label>
        <select
          value=""
          onChange={(e) => {
            if (e.target.value) setPrompt(e.target.value);
          }}
        >
          <option value="">Load previous…</option>
          {history.map((h) => (
            <option key={h} value={h}>
              {h.slice(0, 80)}
            </option>
          ))}
        </select>
      </div>

      <div className="gen-grid">
        <div className="field">
          <label>Style</label>
          <select value={style} onChange={(e) => setStyle(e.target.value)}>
            {STYLE_PRESETS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Aspect</label>
          <select value={aspect} onChange={(e) => setAspect(e.target.value)}>
            {ASPECT_PRESETS.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>FPS</label>
          <select value={fps} onChange={(e) => setFps(e.target.value)}>
            {FPS_OPTIONS.map((f) => (
              <option key={String(f)} value={String(f)}>
                {f}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Duration (s)</label>
          <input type="number" min={2} max={30} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
        </div>
        <div className="field">
          <label>Engine</label>
          <select value={engine} onChange={(e) => setEngine(e.target.value)}>
            {["auto", "fal_seedance", "fal_veo", "fal_kling", "fal_runway", "ltx", "wan"].map((e) => (
              <option key={e} value={e}>
                {e}
              </option>
            ))}
          </select>
        </div>
        <div className="field">
          <label>Resolution</label>
          <select value={resolution} onChange={(e) => setResolution(e.target.value)}>
            {["720p", "1080p", "1440p", "4K"].map((r) => (
              <option key={r} value={r}>
                {r} ({resolutionToSize(r, aspect).width}×{resolutionToSize(r, aspect).height})
              </option>
            ))}
          </select>
        </div>
      </div>

      {engine === "auto" && (
        <div className="card" style={{ marginTop: "0.75rem" }}>
          <strong>Auto recommend</strong>
          <p className="muted">No start frame → fal text-to-video path. Local LTX/WAN require ImageGen / 1 Frame first.</p>
          <button type="button" onClick={() => onGo("imagegen")}>
            Open ImageGen
          </button>
        </div>
      )}

      <div className="row" style={{ marginTop: "1rem" }}>
        <button type="button" className="primary" disabled={busy || !prompt.trim()} onClick={generate}>
          {busy ? "Queuing…" : "Generate"}
        </button>
      </div>

      {job && (
        <p className="scene-meta" style={{ marginTop: "0.75rem" }}>
          Job {job.status} · {Math.round((job.progress || 0) * 100)}% — {job.message}
        </p>
      )}

      {job?.status === "done" && (
        <div className="promote-bar">
          <h3>Promote</h3>
          <div className="row" style={{ flexWrap: "wrap", gap: "0.4rem" }}>
            <button type="button" onClick={() => promote("scene_new")}>
              Add to Director as Scene
            </button>
            <button
              type="button"
              onClick={() =>
                api
                  .promote(project.id, {
                    asset_id: outputAssetId,
                    target: "scene_start",
                    scene_id: project.scenes[0]?.id,
                  })
                  .then(onChange)
              }
            >
              Start
            </button>
            <button
              type="button"
              onClick={() =>
                api
                  .promote(project.id, {
                    asset_id: outputAssetId,
                    target: "scene_middle",
                    scene_id: project.scenes[0]?.id,
                  })
                  .then(onChange)
              }
            >
              Middle
            </button>
            <button
              type="button"
              onClick={() =>
                api
                  .promote(project.id, {
                    asset_id: outputAssetId,
                    target: "scene_end",
                    scene_id: project.scenes[0]?.id,
                  })
                  .then(onChange)
              }
            >
              End
            </button>
            <button type="button" onClick={() => promote("profile")}>
              Save to Profiles
            </button>
            <button type="button" onClick={() => onGo("director")}>
              Open Director
            </button>
          </div>
        </div>
      )}

      <div style={{ marginTop: "1.25rem" }}>
        <JobPanel projectId={project.id} onDone={() => void onChange()} />
      </div>
    </div>
  );
}
