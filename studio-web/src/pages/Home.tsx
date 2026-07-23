import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import type { Health, Project } from "../types";
import { AssistantPanel } from "../components/AssistantPanel";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [health, setHealth] = useState<Health | null>(null);
  const [name, setName] = useState("Untitled Project");
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();

  const refresh = async () => {
    const [p, h] = await Promise.all([api.listProjects(), api.health().catch(() => null)]);
    setProjects(p);
    setHealth(h);
  };

  useEffect(() => {
    refresh().catch(console.error);
  }, []);

  const statusPill = useMemo(() => {
    if (!health) return <span className="pill warn">Checking ComfyUI…</span>;
    if (!health.comfy_reachable) return <span className="pill bad">ComfyUI offline</span>;
    if (health.missing_models?.length)
      return <span className="pill warn">ComfyUI up · missing {health.missing_models.length} models</span>;
    return <span className="pill">ComfyUI connected</span>;
  }, [health]);

  const create = async () => {
    setBusy(true);
    try {
      const p = await api.createProject(name.trim() || "Untitled Project");
      navigate(`/project/${p.id}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">Adept <span>UI Video Studio</span></div>
        <div className="topbar-meta">{statusPill}</div>
      </header>
      <main className="page">
        <section className="hero">
          <h1>Direct local AI video.</h1>
          <p>
            Timeline-first studio for LTX 2.3 and WAN 2.2 — keyframes, @references, lip sync,
            and spatial continuity — without living in the node graph.
          </p>
        </section>

        <div className="card" style={{ maxWidth: 520 }}>
          <h3>New project</h3>
          <p>720p multi-scene director timeline, up to ~30 seconds.</p>
          <div className="field" style={{ marginTop: "0.9rem" }}>
            <label>Project name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="row">
            <button className="primary" disabled={busy} onClick={create}>
              {busy ? "Creating…" : "Create project"}
            </button>
          </div>
        </div>

        <h2 style={{ fontFamily: "var(--font-display)", marginTop: "2rem" }}>Projects</h2>
        {projects.length === 0 ? (
          <p className="empty">No projects yet.</p>
        ) : (
          <div className="grid-cards">
            {projects.map((p) => (
              <div className="card" key={p.id}>
                <h3>{p.name}</h3>
                <p>
                  {p.scenes?.length || 0} scenes · {p.width}×{p.height} · {p.engine_default.toUpperCase()}
                </p>
                <div className="row">
                  <Link to={`/project/${p.id}`}>
                    <button className="primary">Open</button>
                  </Link>
                  <button
                    className="danger"
                    onClick={async () => {
                      await api.deleteProject(p.id);
                      refresh();
                    }}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
      <AssistantPanel />
    </div>
  );
}
