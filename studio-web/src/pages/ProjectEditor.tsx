import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import type { Project } from "../types";
import { Timeline } from "../components/Timeline";
import { AssetTray, PromptComposer } from "../components/AssetTray";
import { AdvancedPanel, JobPanel, PreviewPlayer } from "../components/JobPanel";
import { GpuVramPanel } from "../components/GpuVramPanel";
import { SpatialMapEditor } from "../components/SpatialMap";
import { AssistantPanel } from "../components/AssistantPanel";
import { ImageToolsPanel } from "../components/ImageTools";
import { DirectorTracks } from "../components/DirectorTracks";
import { OneFramePanel, ThreeFramePanel } from "../components/FrameModes";
import { PanelHeading } from "../components/HelpTip";

type EditorTab = "one" | "three" | "director" | "tools" | "spatial";

export default function ProjectEditor() {
  const { id } = useParams();
  const [project, setProject] = useState<Project | null>(null);
  const [selectedScene, setSelectedScene] = useState<string>();
  const [tab, setTab] = useState<EditorTab>("director");

  const refresh = useCallback(async () => {
    if (!id) return;
    const p = await api.getProject(id);
    setProject(p);
    setSelectedScene((prev) => prev || p.scenes[0]?.id);
  }, [id]);

  useEffect(() => {
    refresh().catch(console.error);
  }, [refresh]);

  if (!project) {
    return (
      <div className="app-shell">
        <header className="topbar">
          <div className="brand">
            Adept <span>UI Video Studio</span>
          </div>
        </header>
        <p className="empty">Loading project…</p>
      </div>
    );
  }

  const applyPrompt = async (prompt: string) => {
    const scene = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];
    if (!scene) return;
    await api.updateScene(project.id, scene.id, { ...scene, prompt });
    await refresh();
  };

  const selected = project.scenes.find((s) => s.id === selectedScene) || project.scenes[0];
  const showStudioChrome = tab === "one" || tab === "three" || tab === "director";

  return (
    <div className="app-shell">
      <header className="topbar">
        <div style={{ display: "flex", gap: "1rem", alignItems: "center" }}>
          <Link to="/" style={{ color: "inherit", textDecoration: "none" }}>
            <div className="brand">
              Adept <span>UI Video Studio</span>
            </div>
          </Link>
          <span className="scene-meta">{project.name}</span>
        </div>
        <nav className="topbar-meta topbar-nav">
          <button className={tab === "one" ? "primary" : ""} onClick={() => setTab("one")}>
            1 Frame
          </button>
          <button className={tab === "three" ? "primary" : ""} onClick={() => setTab("three")}>
            3 Frame
          </button>
          <button className={tab === "director" ? "primary" : ""} onClick={() => setTab("director")}>
            Director
          </button>
          <button className={tab === "tools" ? "primary" : ""} onClick={() => setTab("tools")}>
            Character / Angles
          </button>
          <button className={tab === "spatial" ? "primary" : ""} onClick={() => setTab("spatial")}>
            Spatial Map
          </button>
          <button
            className="primary"
            onClick={async () => {
              await api.render(project.id, "timeline");
              refresh();
            }}
          >
            Generate Timeline
          </button>
        </nav>
      </header>

      {showStudioChrome ? (
        <div className="editor">
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <AssetTray project={project} onChange={refresh} />
            <Timeline
              project={project}
              selectedId={selectedScene}
              onSelect={setSelectedScene}
              onChange={refresh}
            />
            <AdvancedPanel project={project} onChange={refresh} />
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {tab === "one" && <OneFramePanel project={project} scene={selected} onChange={refresh} />}
            {tab === "three" && <ThreeFramePanel project={project} scene={selected} onChange={refresh} />}
            {tab === "director" && <DirectorTracks project={project} scene={selected} onChange={refresh} />}
            {tab !== "director" && (
              <PromptComposer project={project} sceneId={selectedScene} onChange={refresh} />
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            <PreviewPlayer project={project} />
            <div className="panel global-prompt-panel">
              <PanelHeading
                title="Global prompt"
                tip="Look, feel, and theme for the whole scene—wardrobe, lighting, weather—applied across every cut and character."
              />
              <p className="scene-meta">
                Sets look, feel, and theme for the whole scene — e.g. wardrobe changes that apply to both
                characters across the cut.
              </p>
              <textarea
                value={project.global_prompt}
                onChange={(e) => setProject({ ...project, global_prompt: e.target.value })}
                onBlur={() => api.updateProject(project.id, { global_prompt: project.global_prompt }).then(refresh)}
                placeholder="cinematic warm tungsten look, rainy night, both wear dark coats…"
              />
            </div>
            <JobPanel projectId={project.id} onDone={refresh} />
            <GpuVramPanel project={project} onChange={refresh} />
          </div>
        </div>
      ) : tab === "tools" ? (
        <>
          <ImageToolsPanel project={project} onChange={refresh} />
          <div className="page" style={{ width: "min(1100px, calc(100% - 2rem))", paddingTop: 0 }}>
            <JobPanel projectId={project.id} onDone={refresh} />
            <div style={{ marginTop: "1rem" }}>
              <GpuVramPanel project={project} onChange={refresh} />
            </div>
          </div>
        </>
      ) : (
        <div className="page" style={{ width: "min(900px, calc(100% - 2rem))" }}>
          <SpatialMapEditor project={project} onChange={refresh} />
        </div>
      )}

      <AssistantPanel
        project={project}
        sceneId={selectedScene}
        onApplyPrompt={applyPrompt}
        onAppliedSetup={refresh}
      />
    </div>
  );
}
