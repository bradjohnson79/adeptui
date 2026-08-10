import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../../api";
import { WORKSPACES, workspacesForMenu, type EditorTab } from "../../core/workspaces";
import { resolveProductionAvailability } from "../../core/productionAvailability";
import { pushProductionRecent } from "../../core/productionRecent";
import { browseAllProjects, goHome } from "../../navigation/projectLibrary";
import { buildHomeCreateProjectPath } from "../../projectEntry";
import { loadRecentProjects } from "../../workspacePrefs";
import { Menu, MenuBarShell, type MenuItem } from "../ui/Menu";
import { CommandPalette, useCommandPaletteShortcut, type CommandItem } from "../ui/CommandPalette";
import { Button } from "../ui/Button";
import { SystemStatusStrip } from "./SystemStatusStrip";
import { ProductionMenu, focusProductionTrigger } from "./ProductionMenu";
import { useStudioHealth } from "../../hooks/useStudioHealth";

const SELECTED_CHARACTER_KEY = "adept_selected_character";

function readSelectedCharacterId(): string {
  try {
    return sessionStorage.getItem(SELECTED_CHARACTER_KEY) || "";
  } catch {
    return "";
  }
}

type AppChromeProps = {
  variant?: "home" | "project";
  projectId?: string;
  projectName?: string;
  workspaceLabel?: string;
  activeWorkspace?: EditorTab;
  onNavigateWorkspace?: (tab: EditorTab) => void;
  onOpenCoDirector?: () => void;
  onSetup?: () => void;
  onNewProject?: () => void;
  onExport?: () => void;
  /** @deprecated unused — Project menu owns project switching */
  leftExtra?: ReactNode;
  queuedJobs?: number | null;
  breadcrumbs?: { label: string; onClick?: () => void }[];
};

export function AppChrome({
  variant = "home",
  projectId,
  projectName,
  workspaceLabel,
  activeWorkspace,
  onNavigateWorkspace,
  onOpenCoDirector,
  onSetup,
  onNewProject,
  onExport,
  queuedJobs,
  breadcrumbs,
}: AppChromeProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const [commandOpen, setCommandOpen] = useState(false);
  const [searchText, setSearchText] = useState("");
  const [busy, setBusy] = useState(false);
  const [selectedCharacterId, setSelectedCharacterId] = useState(readSelectedCharacterId);
  const recent = loadRecentProjects();
  const { health, error: healthError } = useStudioHealth();
  const availability = useMemo(
    () => resolveProductionAvailability(health, healthError),
    [health, healthError],
  );

  const openCommand = useCallback(() => setCommandOpen(true), []);
  useCommandPaletteShortcut(openCommand);

  const inProject = variant === "project" && Boolean(projectId);

  useEffect(() => {
    setOpenMenu(null);
  }, [projectId]);

  useEffect(() => {
    const onChar = () => setSelectedCharacterId(readSelectedCharacterId());
    window.addEventListener("adept:selected-character", onChar);
    window.addEventListener("storage", onChar);
    return () => {
      window.removeEventListener("adept:selected-character", onChar);
      window.removeEventListener("storage", onChar);
    };
  }, []);

  const goWorkspace = useCallback(
    (tab: EditorTab) => {
      setOpenMenu(null);
      pushProductionRecent({
        tab,
        projectId,
        projectName,
        label: WORKSPACES[tab]?.label,
      });
      if (onNavigateWorkspace && projectId) {
        onNavigateWorkspace(tab);
        return;
      }
      if (projectId) {
        navigate(`/project/${encodeURIComponent(projectId)}?workspace=${encodeURIComponent(tab)}`);
        return;
      }
      // No eligible active project: open centered Create Project with pending destination.
      // Do not silently fall back to a stale recent project or a Home no-op.
      navigate(
        buildHomeCreateProjectPath({
          pendingEntry: { kind: "project", workspace: tab },
        }),
      );
    },
    [navigate, onNavigateWorkspace, projectId, projectName],
  );

  const openCoDirectorFull = useCallback(() => {
    setOpenMenu(null);
    if (onOpenCoDirector) {
      onOpenCoDirector();
      return;
    }
    navigate(projectId ? `/co-director?projectId=${projectId}` : "/co-director");
  }, [navigate, onOpenCoDirector, projectId]);

  const createProject = useCallback(async () => {
    setBusy(true);
    try {
      if (onNewProject) {
        onNewProject();
        return;
      }
      const pendingEntry =
        typeof window !== "undefined" && window.location.pathname.startsWith("/co-director")
          ? {
              kind: "co-director" as const,
              returnTo: `${location.pathname}${location.search}${location.hash}`,
            }
          : {
              kind: "project" as const,
              returnTo: `${location.pathname}${location.search}${location.hash}`,
            };
      navigate(buildHomeCreateProjectPath({ pendingEntry }));
    } finally {
      setBusy(false);
    }
  }, [location.hash, location.pathname, location.search, navigate, onNewProject]);

  const projectItems: MenuItem[] = useMemo(() => {
    const items: MenuItem[] = [{ id: "lbl-recent", type: "label", label: "OPEN / RECENT" }];
    if (projectId && projectName) {
      items.push({
        id: `cur-${projectId}`,
        label: projectName,
        selected: true,
        // On Home, keep the preferred project selectable so creators can reopen it.
        // Inside a project shell it is the current context and should not re-navigate.
        disabled: inProject,
        onSelect: inProject ? undefined : () => navigate(`/project/${encodeURIComponent(projectId)}`),
      });
    }
    for (const p of recent.slice(0, 8)) {
      if (p.id === projectId) continue;
      items.push({
        id: `recent-${p.id}`,
        label: p.name,
        onSelect: () => navigate(`/project/${encodeURIComponent(p.id)}`),
      });
    }
    if (!recent.length && !projectId) {
      items.push({ id: "no-recent", label: "No recent projects", disabled: true });
    }
    items.push({
      id: "browse",
      label: "Browse all projects…",
      onSelect: () => browseAllProjects(navigate),
    });
    items.push({ id: "sep-1", type: "separator" });
    items.push({
      id: "create",
      label: "Create project",
      disabled: busy,
      onSelect: () => void createProject(),
    });
    if (inProject && projectId) {
      items.push({
        id: "duplicate",
        label: "Duplicate",
        disabled: busy,
        onSelect: () =>
          void (async () => {
            setBusy(true);
            try {
              const r = await api.duplicateProject(projectId);
              navigate(`/project/${r.id}`);
            } finally {
              setBusy(false);
            }
          })(),
      });
      items.push({
        id: "archive",
        label: "Archive",
        disabled: busy,
        onSelect: () =>
          void (async () => {
            setBusy(true);
            try {
              await api.archiveProject(projectId, true);
              goHome(navigate);
            } finally {
              setBusy(false);
            }
          })(),
      });
      items.push({ id: "sep-2", type: "separator" });
      items.push({ id: "settings", label: "Settings", onSelect: () => goWorkspace("settings") });
      items.push({
        id: "learning",
        label: "Learning",
        onSelect: () => {
          try {
            sessionStorage.setItem("adept_settings_tab", "learning");
          } catch {
            /* ignore */
          }
          goWorkspace("settings");
        },
      });
      items.push({
        id: "export",
        label: "Export / Backup",
        onSelect: () => {
          if (onExport) onExport();
          else void api.exportPack(projectId);
        },
      });
      items.push({ id: "stats", label: "Statistics (Home)", onSelect: () => goWorkspace("home") });
      items.push({ id: "close", label: "Close project", onSelect: () => goHome(navigate) });
    }
    return items;
  }, [busy, createProject, goWorkspace, inProject, navigate, onExport, projectId, projectName, recent]);

  const setupItems: MenuItem[] = [
    {
      id: "wizard",
      label: "Wizard",
      onSelect: () => {
        if (onSetup) onSetup();
        else goWorkspace("setup");
      },
    },
    {
      id: "source-manager",
      label: "Source Manager",
      onSelect: () => navigate("/source-manager"),
    },
  ];

  const crumbItems =
    breadcrumbs ??
    (inProject
      ? [
          { label: "Project", onClick: () => goHome(navigate) },
          { label: workspaceLabel || WORKSPACES[activeWorkspace || "home"]?.label || "Home" },
        ]
      : [{ label: "Home" }]);

  const commandItems: CommandItem[] = useMemo(() => {
    const ws = [
      ...workspacesForMenu("characters"),
      ...workspacesForMenu("generate"),
      ...workspacesForMenu("production"),
      ...workspacesForMenu("project"),
    ].map((tab) => ({
      id: `ws-${tab}`,
      title: WORKSPACES[tab].label,
      meta: WORKSPACES[tab].description,
      keywords:
        tab === "characters"
          ? "character profile korri identity seed creator wardrobe voice motion performance"
          : WORKSPACES[tab].compatibilityAliases?.join(" ") || "",
      run: () => goWorkspace(tab),
    }));
    const tools: CommandItem[] = [
      { id: "home", title: "Home / Project Library", meta: "Navigate", run: () => browseAllProjects(navigate) },
      { id: "setup", title: "Setup Wizard", meta: "Setup", run: () => (onSetup ? onSetup() : goWorkspace("setup")) },
      { id: "sm", title: "Source Manager", meta: "Setup", run: () => navigate("/source-manager") },
      { id: "cd", title: "Co-Director", meta: "Assistant", run: () => openCoDirectorFull() },
    ];
    const recentCmds = loadRecentProjects().map((p) => ({
      id: `r-${p.id}`,
      title: p.name,
      meta: "Recent project",
      run: () => navigate(`/project/${p.id}`),
    }));
    return [...tools, ...ws, ...recentCmds];
  }, [goWorkspace, navigate, onSetup, openCoDirectorFull]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenMenu(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div className="app-chrome app-chrome--fixed" data-testid="app-chrome">
      <MenuBarShell
        className="app-chrome__bar"
        brand={
          <Link
            to="/"
            className="ds-menubar__brand"
            data-testid="chrome-brand"
            onClick={(e) => {
              e.preventDefault();
              goHome(navigate);
            }}
          >
            Adept <span>UI</span> Studio
          </Link>
        }
        trailing={
          <>
            <Button
              type="button"
              variant="primary"
              compact
              className="app-chrome__codirector"
              onClick={openCoDirectorFull}
              data-testid="chrome-codirector"
            >
              Co-Director
            </Button>
            <label className="app-chrome__search">
              <span className="app-chrome__search-icon" aria-hidden>
                ⌕
              </span>
              <input
                type="search"
                placeholder="Search Adept UI…"
                value={searchText}
                aria-label="Search Adept UI"
                data-testid="chrome-search"
                onChange={(e) => setSearchText(e.target.value)}
                onFocus={() => setCommandOpen(true)}
                onClick={() => setCommandOpen(true)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    setCommandOpen(true);
                  }
                }}
              />
              <kbd className="app-chrome__kbd">Ctrl+K</kbd>
            </label>
          </>
        }
      >
        <Menu
          label="Project"
          items={projectItems}
          open={openMenu === "project"}
          onOpenChange={(o) => setOpenMenu(o ? "project" : null)}
          onHoverOpen={() => {
            if (openMenu) setOpenMenu("project");
          }}
        />
        {inProject && projectName ? (
          <span className="app-chrome__project-pill" title={projectName} data-testid="chrome-project-name">
            {projectName}
          </span>
        ) : null}
        <Menu
          label="Setup"
          items={setupItems}
          open={openMenu === "setup"}
          onOpenChange={(o) => setOpenMenu(o ? "setup" : null)}
          onHoverOpen={() => {
            if (openMenu) setOpenMenu("setup");
          }}
        />
        <ProductionMenu
          open={openMenu === "production"}
          onOpenChange={(o, opts) => {
            setOpenMenu(o ? "production" : null);
            if (!o && opts?.restoreFocus) {
              queueMicrotask(() => focusProductionTrigger());
            }
          }}
          onHoverOpen={() => {
            if (openMenu) setOpenMenu("production");
          }}
          availability={availability}
          projectId={projectId}
          projectName={projectName}
          selectedCharacterId={selectedCharacterId}
          onSelectWorkspace={goWorkspace}
          onOpenCoDirector={openCoDirectorFull}
          onChooseCharacterForAvatar={() => goWorkspace("characters")}
        />
        <div className="ds-menu-root app-chrome__status-root">
          <button
            type="button"
            className="ds-menu-trigger"
            aria-haspopup="true"
            aria-expanded={openMenu === "status"}
            data-testid="chrome-status-menu-button"
            onClick={() => setOpenMenu((m) => (m === "status" ? null : "status"))}
            onMouseEnter={() => {
              if (openMenu) setOpenMenu("status");
            }}
          >
            <span>Status</span>
            <span className="ds-menu-trigger__chevron" aria-hidden>
              ▾
            </span>
          </button>
          {openMenu === "status" ? (
            <div className="ds-menu-panel app-chrome__status-panel" role="region" aria-label="System status">
              <div className="ds-menu-label">SYSTEM STATUS</div>
              <SystemStatusStrip
                compact
                stacked
                projectId={projectId}
                queuedJobs={queuedJobs}
                onOpenCoDirector={openCoDirectorFull}
              />
            </div>
          ) : null}
        </div>
      </MenuBarShell>

      <nav className="app-chrome__breadcrumbs" aria-label="Breadcrumb" data-testid="chrome-breadcrumbs">
        {crumbItems.map((c, i) => (
          <span key={`${c.label}-${i}`} className="app-chrome__crumb">
            {i > 0 ? (
              <span className="app-chrome__crumb-sep" aria-hidden>
                /
              </span>
            ) : null}
            {c.onClick ? (
              <button type="button" className="app-chrome__crumb-link" onClick={c.onClick}>
                {c.label}
              </button>
            ) : (
              <span className="app-chrome__crumb-current">{c.label}</span>
            )}
          </span>
        ))}
      </nav>

      <CommandPalette open={commandOpen} onClose={() => setCommandOpen(false)} items={commandItems} />
    </div>
  );
}
