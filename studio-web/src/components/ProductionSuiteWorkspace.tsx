import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../api";
import { StudioChrome } from "./dashboard/StudioChrome";

type Section =
  | "image"
  | "frames"
  | "video"
  | "lipsync"
  | "audio"
  | "edit"
  | "render"
  | "control"
  | "timeline";

const SECTIONS: { id: Section; flag: string; label: string; testId: string }[] = [
  { id: "image", flag: "imageProductionEnabled", label: "Image", testId: "m29-section-image" },
  { id: "frames", flag: "frameProductionEnabled", label: "Frames", testId: "m29-section-frames" },
  { id: "video", flag: "videoProductionEnabled", label: "Video", testId: "m29-section-video" },
  {
    id: "timeline",
    flag: "directorTimelineEnabled",
    label: "Director Timeline Generation",
    testId: "m29-section-timeline",
  },
  { id: "lipsync", flag: "lipsyncProductionEnabled", label: "Lip Sync", testId: "m29-section-lipsync" },
  { id: "audio", flag: "audioProductionEnabled", label: "Audio", testId: "m29-section-audio" },
  { id: "edit", flag: "editingProductionEnabled", label: "Edit", testId: "m29-section-edit" },
  { id: "render", flag: "renderProductionEnabled", label: "Render", testId: "m29-section-render" },
  {
    id: "control",
    flag: "codirectorProductionControlEnabled",
    label: "Control",
    testId: "m29-section-control",
  },
];

export default function ProductionSuiteWorkspace() {
  const [params] = useSearchParams();
  const [flags, setFlags] = useState<Record<string, boolean> | null>(null);
  const [projectId, setProjectId] = useState(params.get("projectId") || "");
  const [section, setSection] = useState<Section>("image");
  const [msg, setMsg] = useState("");
  const [result, setResult] = useState<Record<string, unknown> | null>(null);
  const [prompt, setPrompt] = useState("Cinematic still of Shay in the chamber");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const health = await api.health();
      if (cancelled) return;
      setFlags((health?.operator || {}) as Record<string, boolean>);
    })().catch((e) => setMsg(String(e)));
    return () => {
      cancelled = true;
    };
  }, []);

  if (flags === null) {
    return (
      <div className="page" data-testid="m29-suite-loading">
        Loading…
      </div>
    );
  }

  const anyOn = SECTIONS.some((s) => Boolean(flags[s.flag]));
  if (!anyOn) {
    return (
      <div className="app-shell atmosphere" data-testid="m29-suite-unavailable">
        <StudioChrome variant="home" />
        <div className="page">
          <h1 className="ds-type-h1">Production Suite unavailable</h1>
          <p className="ds-type-helper">
            Enable STUDIO_FEATURE_*_PRODUCTION_V1 (or director/control) flags to use M2.9 workspaces.
          </p>
        </div>
      </div>
    );
  }

  const active = SECTIONS.filter((s) => Boolean(flags[s.flag]));

  const run = async () => {
    setMsg("");
    setResult(null);
    try {
      if (!projectId) throw new Error("Project ID required");
      let out: Record<string, unknown>;
      if (section === "image") {
        out = await api.m29ImageGenerate({ projectId, prompt, operation: "generate" });
      } else if (section === "frames") {
        out = await api.m29FramesGenerate({
          projectId,
          prompt,
          frameType: "production_frame",
          count: 2,
          sequence: true,
          shotId: "shot-1",
        });
      } else if (section === "video") {
        out = await api.m29VideoGenerate({ projectId, prompt, mode: "text_to_video" });
      } else if (section === "lipsync") {
        out = await api.m29LipsyncGenerate({ projectId });
      } else if (section === "audio") {
        out = await api.m29AudioGenerate({ projectId, kind: "dialogue", prompt });
      } else if (section === "edit") {
        out = await api.m29EditingPropose({
          projectId,
          ops: [{ op: "trim", clipId: "clip-1", in: 0, out: 2 }],
        });
      } else if (section === "render") {
        out = await api.m29Render({ projectId, kind: "timeline_render" });
      } else if (section === "timeline") {
        out = await api.m29TimelinePropose({ projectId, notes: prompt });
      } else {
        out = await api.m29ControlDecompose({
          projectId,
          requestText: prompt,
          enqueue: true,
        });
      }
      setResult(out);
      setMsg("OK");
    } catch (e) {
      setMsg(String(e));
    }
  };

  return (
    <div className="app-shell atmosphere" data-testid="m29-suite-page">
      <StudioChrome
        variant="home"
        breadcrumbs={[{ label: "Home" }, { label: "Production" }, { label: "Production Suite" }]}
      />
      <div className="page m29-suite-page">
      <h1 className="ds-type-h1">Production Suite</h1>
      <p className="ds-type-helper">M2.9 native production departments (flag-gated, executive-backed).</p>
      <div className="row" style={{ gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
        {active.map((s) => (
          <button
            key={s.id}
            type="button"
            data-testid={s.testId}
            className={section === s.id ? "primary" : ""}
            onClick={() => setSection(s.id)}
          >
            {s.label}
          </button>
        ))}
      </div>
      <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
        <input
          data-testid="m29-project-id"
          placeholder="Project ID"
          value={projectId}
          onChange={(e) => setProjectId(e.target.value)}
          style={{ minWidth: 240 }}
        />
        <input
          data-testid="m29-prompt"
          placeholder="Prompt / request"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          style={{ minWidth: 360 }}
        />
        <button type="button" data-testid="m29-run-btn" className="primary" onClick={run}>
          Run
        </button>
      </div>
      {msg && (
        <p data-testid="m29-msg" className="muted">
          {msg}
        </p>
      )}
      {result && (
        <pre data-testid="m29-result" style={{ marginTop: 16, whiteSpace: "pre-wrap" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
      </div>
    </div>
  );
}
