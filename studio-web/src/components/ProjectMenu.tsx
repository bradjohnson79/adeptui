import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, isAbortError } from "../api";
import type { Project } from "../types";
import { loadRecentProjects, type EditorTab } from "../workspacePrefs";

export function ProjectMenu({
  project,
  open,
  onClose,
  onGo,
  onRefresh,
}: {
  project: Project;
  open: boolean;
  onClose: () => void;
  onGo: (tab: EditorTab) => void;
  onRefresh: () => Promise<void>;
}) {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [busy, setBusy] = useState(false);
  const recent = loadRecentProjects();

  useEffect(() => {
    if (!open) return;
    const ac = new AbortController();
    api
      .listProjects({ signal: ac.signal })
      .then((next) => {
        if (!ac.signal.aborted) setProjects(next);
      })
      .catch((error: unknown) => {
        if (isAbortError(error) || ac.signal.aborted) return;
        console.error(error);
      });
    return () => ac.abort();
  }, [open]);

  if (!open) return null;

  const run = async (fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="project-menu" role="menu">
      <div className="project-menu-section">
        <div className="project-menu-label">Current</div>
        <div className="project-menu-current">{project.name}</div>
      </div>
      <div className="project-menu-section">
        <div className="project-menu-label">Open / Recent</div>
        {(recent.length ? recent : projects.slice(0, 8).map((p) => ({ id: p.id, name: p.name }))).map((p) => (
          <button
            key={p.id}
            type="button"
            role="menuitem"
            disabled={busy || p.id === project.id}
            onClick={() => {
              onClose();
              navigate(`/project/${p.id}`);
            }}
          >
            {p.name}
          </button>
        ))}
        <button type="button" role="menuitem" onClick={() => { onClose(); navigate("/"); }}>
          Browse all projects…
        </button>
      </div>
      <div className="project-menu-section">
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const p = await api.createProject(`Untitled ${new Date().toLocaleDateString()}`);
              onClose();
              navigate(`/project/${p.id}`);
            })
          }
        >
          Create project
        </button>
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onClick={() =>
            run(async () => {
              const r = await api.duplicateProject(project.id);
              onClose();
              navigate(`/project/${r.id}`);
            })
          }
        >
          Duplicate
        </button>
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onClick={() =>
            run(async () => {
              await api.archiveProject(project.id, true);
              onClose();
              navigate("/");
            })
          }
        >
          Archive
        </button>
      </div>
      <div className="project-menu-section">
        <button type="button" role="menuitem" onClick={() => { onGo("settings"); onClose(); }}>
          Settings
        </button>
        <button
          type="button"
          role="menuitem"
          onClick={() => {
            onGo("settings");
            onClose();
            sessionStorage.setItem("adept_settings_tab", "learning");
          }}
        >
          Learning
        </button>
        <button type="button" role="menuitem" onClick={() => api.exportPack(project.id).then(() => onRefresh())}>
          Export / Backup
        </button>
        <button type="button" role="menuitem" onClick={() => { onGo("home"); onClose(); }}>
          Statistics (Home)
        </button>
        <button type="button" role="menuitem" onClick={() => { onClose(); navigate("/"); }}>
          Close project
        </button>
      </div>
    </div>
  );
}
