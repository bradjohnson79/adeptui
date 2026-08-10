import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, isAbortError, isNavigationFetchFailure } from "../api";
import type { Project } from "../types";
import { PROJECT_TEMPLATES } from "../dashboardImages";
import { LEGACY_TO_SLUG } from "../projectTypes";
import {
  buildPendingProjectCancelDestination,
  buildPendingProjectDestination,
  buildSetupPendingEntry,
  getEligibleProjectId,
  readPendingProjectEntry,
  type PendingProjectEntry,
} from "../projectEntry";
import { StudioChrome } from "../components/dashboard/StudioChrome";
import { buildAiGuidedSetupPath } from "../setup/navigation";
import { SystemStatusStrip } from "../components/dashboard/StudioChrome";
import { CapabilityReadinessPanel } from "../components/CapabilityPanel";
import { ProjectCoverCard } from "../components/dashboard/ProjectCoverCard";
import { WorkspaceFeatureCard } from "../components/dashboard/DashboardCards";
import { focusProjectLibrary, PROJECT_LIBRARY_HASH } from "../navigation/projectLibrary";
import {
  pruneDeletedProjects,
  pushRecentProject,
  resolutionToSize,
} from "../workspacePrefs";
import {
  buildProjectWorkspacePath,
  getExploreWorkspaceCards,
} from "../core/exploreWorkspaces";
import { GenerationStudioHero } from "../components/generationStudio/GenerationStudioHero";
import { CoDirectorLaunchCard } from "../components/generationStudio/CoDirectorLaunchCard";
import { useBindCoDirectorWorkspace } from "../components/CoDirector";
import {
  StudioLaunchCards,
  type StudioLaunchTarget,
} from "../components/generationStudio/StudioLaunchCards";
import {
  BrowseTemplatesCard,
  CreateProjectCard,
} from "../components/generationStudio/CreateProjectCard";
import type { NewProductionOpts } from "../components/dashboard/NewProductionCard";
import { Dialog, EmptyState, SectionHeader } from "../components/ui";
import { resolveProjectCover } from "../lib/projectCover";
import {
  ManagePasswordModal,
  SetPasswordModal,
  UnlockProjectModal,
} from "../components/ProjectPasswordModals";
import { clearProjectUnlockToken, getProjectUnlockToken } from "../projectSecurity";
import { HomeCreateProjectModal } from "../components/generationStudio/HomeCreateProjectModal";

type StatusFilter = "All" | "Active" | "Rendering" | "Complete";

export default function Home() {
  const [projects, setProjects] = useState<Project[]>([]);
  const busy = false;
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createBusy, setCreateBusy] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);
  const [createFormKey, setCreateFormKey] = useState(0);
  const [projectsLoaded, setProjectsLoaded] = useState(false);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [view, setView] = useState<"grid" | "list">("grid");
  const [pwModal, setPwModal] = useState<
    null | { kind: "set" | "unlock" | "manage"; projectId: string }
  >(null);
  const [deleteTarget, setDeleteTarget] = useState<null | { id: string; name: string }>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const createIntentRef = useRef<string | null>(null);
  const createReturnFocusRef = useRef<HTMLElement | null>(null);
  const pendingProjectEntryRef = useRef<PendingProjectEntry | null>(null);

  const pwTarget = pwModal ? projects.find((p) => p.id === pwModal.projectId) : null;

  const openProject = async (id: string) => {
    const p = projects.find((x) => x.id === id);
    if (p?.password_protected && p.password_locked && !getProjectUnlockToken(id)) {
      setPwModal({ kind: "unlock", projectId: id });
      return;
    }
    if (p?.password_protected && !getProjectUnlockToken(id)) {
      // Re-check security status before navigating — never briefly open then bounce.
      try {
        const sec = await api.getProjectSecurity(id);
        if (sec.passwordProtected && !sec.unlocked) {
          setPwModal({ kind: "unlock", projectId: id });
          return;
        }
      } catch {
        setPwModal({ kind: "unlock", projectId: id });
        return;
      }
    }
    // Continue opens the project landing page — never dump into Setup Wizard
    // because that was the last ops tab visited, and never silently resume the
    // last creative workspace (routing contract). The landing page offers an
    // intentional Continue affordance for the remembered workspace.
    navigate(`/project/${id}`);
  };

  const mountedRef = useRef(true);
  const refreshAcRef = useRef<AbortController | null>(null);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      refreshAcRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (location.hash.replace(/^#/, "") !== PROJECT_LIBRARY_HASH) return;
    const t = window.setTimeout(() => focusProjectLibrary(), 50);
    return () => window.clearTimeout(t);
  }, [location.hash, projects.length]);

  const refresh = async () => {
    refreshAcRef.current?.abort();
    const ac = new AbortController();
    refreshAcRef.current = ac;
    try {
      const p = await api.listProjects({ signal: ac.signal });
      if (!mountedRef.current || ac.signal.aborted) return;
      setProjects(p);
      // Drop stale navigation targets referencing projects that no longer exist
      // (e.g. after a creator-data reset or deletion on another device).
      pruneDeletedProjects(new Set(p.map((proj) => proj.id)));
    } catch (error) {
      if (isAbortError(error) || ac.signal.aborted || !mountedRef.current) return;
      if (isNavigationFetchFailure(error)) {
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (!mountedRef.current || ac.signal.aborted) return;
      }
      throw error;
    } finally {
      if (mountedRef.current && !ac.signal.aborted) {
        setProjectsLoaded(true);
      }
    }
  };

  const preferredProjectId = useMemo(() => getEligibleProjectId(projects), [projects]);
  const preferredProject = useMemo(
    () => projects.find((project) => project.id === preferredProjectId) || null,
    [preferredProjectId, projects],
  );

  useBindCoDirectorWorkspace({
    projectId: preferredProject?.id,
    projectName: preferredProject?.name,
    primaryProjectType: preferredProject?.primary_project_type || "custom",
    workspaceTab: "home",
  });

  const createIntent = useMemo(() => {
    const params = new URLSearchParams(location.search);
    const pendingEntry = readPendingProjectEntry(params) ?? buildSetupPendingEntry(params);
    return {
      forcedCreate: params.get("create") === "1",
      suggestedName: params.get("createName")?.trim() || undefined,
      pendingEntry,
    };
  }, [location.search]);

  const openCreateProject = useCallback(
    (pendingEntry?: PendingProjectEntry | null) => {
      const active = document.activeElement;
      createReturnFocusRef.current = active instanceof HTMLElement ? active : null;
      pendingProjectEntryRef.current = pendingEntry || null;
      setCreateError(null);
      setCreateFormKey((prev) => prev + 1);
      setCreateModalOpen(true);
    },
    [],
  );

  const closeCreateProject = useCallback((opts?: { preserveIntent?: boolean }) => {
    if (createBusy) return;
    setCreateModalOpen(false);
    setCreateError(null);
    if (!opts?.preserveIntent) {
      pendingProjectEntryRef.current = null;
    }
  }, [createBusy]);

  const cancelCreateProject = useCallback(() => {
    const pendingEntry = pendingProjectEntryRef.current ?? createIntent.pendingEntry;
    closeCreateProject();
    if (createIntent.forcedCreate || pendingEntry?.kind === "setup") {
      navigate(buildPendingProjectCancelDestination(pendingEntry), { replace: true });
    }
  }, [closeCreateProject, createIntent.forcedCreate, createIntent.pendingEntry, navigate]);

  useEffect(() => {
    refresh().catch(async (error: unknown) => {
      if (isAbortError(error) || !mountedRef.current) return;
      if (isNavigationFetchFailure(error)) {
        await new Promise((resolve) => window.setTimeout(resolve, 0));
        if (!mountedRef.current) return;
      }
      console.error(error);
    });
  }, []);

  useEffect(() => {
    const pendingEntry = createIntent.pendingEntry;
    const setupEntry = pendingEntry?.kind === "setup" ? pendingEntry : null;
    const isAiGuided = setupEntry?.setupMode === "ai_guided";
    if (setupEntry && !projectsLoaded) {
      return;
    }
    if (!isAiGuided && !createIntent.forcedCreate) {
      createIntentRef.current = null;
      return;
    }
    if (createIntentRef.current === location.search) return;

    let cancelled = false;

    const redirectToSetup = async () => {
      if (createIntent.forcedCreate) {
        createIntentRef.current = location.search;
        if (!cancelled) {
          openCreateProject(pendingEntry);
        }
        return;
      }
      const id = preferredProjectId;
      if (!id) {
        createIntentRef.current = location.search;
        if (!cancelled) {
          openCreateProject(setupEntry);
        }
        return;
      }
      if (cancelled) return;
      createIntentRef.current = location.search;
      navigate(
        buildAiGuidedSetupPath({
          projectId: id,
          componentId: setupEntry?.setupComponent,
          source: setupEntry?.setupSource || "workspace_launch",
        }),
        { replace: true },
      );
    };

    void redirectToSetup();
    return () => {
      cancelled = true;
    };
  }, [createIntent, location.search, navigate, openCreateProject, preferredProjectId, projectsLoaded]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return projects.filter((p) => {
      const status = p.status_label || "Active";
      if (statusFilter !== "All" && status !== statusFilter) return false;
      if (!q) return true;
      return (
        p.name.toLowerCase().includes(q) ||
        (p.description || "").toLowerCase().includes(q) ||
        (p.tags_json || "").toLowerCase().includes(q)
      );
    });
  }, [projects, query, statusFilter]);

  const createWithDefaults = async (opts: {
    name: string;
    primaryProjectType: string;
    projectTraits?: string[];
    aspect?: string;
    resolution?: string;
    fps?: number | "auto";
    storyboard_style?: string;
    stayOnHome?: boolean;
    /** @deprecated legacy template path */
    type?: string;
  }) => {
    if (createBusy) return;
    setCreateBusy(true);
    setCreateError(null);
    try {
      const primary =
        opts.primaryProjectType ||
        (opts.type ? String(opts.type).toLowerCase().replace(/\s+/g, "_") : "custom");
      const { width, height } = resolutionToSize(opts.resolution || "1080p", opts.aspect || "16:9");
      const p = await api.createProject(opts.name, {
        primary_project_type: primary,
        project_traits: opts.projectTraits || [],
        width,
        height,
        fps: typeof opts.fps === "number" ? opts.fps : undefined,
        profile_overrides: {
          aspectRatio: opts.aspect || "16:9",
          resolution: opts.resolution || "1080p",
          frameRate: typeof opts.fps === "number" ? opts.fps : undefined,
          storyboardStyle: opts.storyboard_style || "Pencil storyboard",
        },
      });
      pushRecentProject(p.id, p.name);
      await refresh().catch(() => undefined);
      const pendingEntry = pendingProjectEntryRef.current;
      const stayOnHome = Boolean(opts.stayOnHome) && !createIntent.forcedCreate && !pendingEntry;
      setCreateModalOpen(false);
      setCreateError(null);
      pendingProjectEntryRef.current = null;
      if (stayOnHome) {
        setQuery("");
        setStatusFilter("All");
        return;
      }
      navigate(buildPendingProjectDestination(p.id, pendingEntry), {
        replace: Boolean(createIntent.forcedCreate || pendingEntry?.kind === "setup"),
      });
    } catch (error) {
      setCreateError(error instanceof Error ? error.message : "Could not create the project. Try again.");
    } finally {
      setCreateBusy(false);
    }
  };

  const onCreateFromDrawer = (opts: NewProductionOpts) => {
    void createWithDefaults({ ...opts, stayOnHome: true });
  };

  const useTemplateById = (templateId: string, opts?: { stayOnHome?: boolean }) => {
    const t = PROJECT_TEMPLATES.find((x) => x.id === templateId);
    if (!t) return;
    void createWithDefaults({
      name: t.title,
      primaryProjectType: t.primaryProjectType || LEGACY_TO_SLUG[t.type] || "custom",
      type: t.type,
      ...t.defaults,
      stayOnHome: opts?.stayOnHome,
    });
  };

  const exploreItems = getExploreWorkspaceCards();

  return (
    <div className="app-shell atmosphere aurora-landing" data-testid="generation-studio-home">
      <StudioChrome
        variant="home"
        projectId={preferredProjectId || undefined}
        projectName={preferredProject?.name}
        onOpenCoDirector={() =>
          navigate(preferredProjectId ? `/co-director?projectId=${encodeURIComponent(preferredProjectId)}` : "/co-director")
        }
        onSetup={async () => {
          const id = preferredProjectId;
          if (!id) {
            openCreateProject({
              kind: "setup",
              setupMode: "ai_guided",
              setupSource: "workspace_launch",
            });
            return;
          }
          navigate(
            buildAiGuidedSetupPath({
              projectId: id,
              source: "workspace_launch",
            }),
          );
        }}
        onNewProject={() => openCreateProject()}
        breadcrumbs={[{ label: "Home" }]}
      />
      <main className="studio-page">
        <GenerationStudioHero />

        <CoDirectorLaunchCard activeProjectName={preferredProject?.name} />

        <StudioLaunchCards
          busy={busy || createBusy}
          onOpen={async (target: StudioLaunchTarget) => {
            const id = preferredProjectId;
            const workspace = target === "director" ? "timeline" : target;
            if (!id) {
              openCreateProject({ kind: "project", workspace });
              return;
            }
            navigate(`/project/${id}?workspace=${workspace}`);
          }}
        />

        <section id="projects" className="gs-projects" aria-labelledby="projects-heading">
          <h2 id="projects-heading" className="section-heading">
            Projects
          </h2>
          <div className="gs-projects-split">
            <CreateProjectCard
              busy={busy || createBusy}
              onOpen={() => openCreateProject()}
              activeProjectName={preferredProject?.name}
              onOpenActive={preferredProject?.id ? () => void openProject(preferredProject.id) : undefined}
            />
            <BrowseTemplatesCard onSelectTemplate={useTemplateById} />
          </div>
        </section>

        <section id="projects-library" className="gs-library glass-section" aria-labelledby="library-heading">
          <h2 id="library-heading" className="section-heading">
            Your library
          </h2>
          <div className="library-toolbar">
            <input
              aria-label="Search projects"
              placeholder="Search projects…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <div className="filter-chips" role="group" aria-label="Status filter">
              {(["All", "Active", "Rendering", "Complete"] as StatusFilter[]).map((s) => (
                <button
                  key={s}
                  type="button"
                  className={statusFilter === s ? "primary" : ""}
                  onClick={() => setStatusFilter(s)}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="view-toggle" role="group" aria-label="View mode">
              <button type="button" className={view === "grid" ? "primary" : ""} onClick={() => setView("grid")}>
                Grid
              </button>
              <button type="button" className={view === "list" ? "primary" : ""} onClick={() => setView("list")}>
                List
              </button>
            </div>
          </div>
          {!filtered.length ? (
            <EmptyState
              kind="first-use"
              title="No Projects Yet"
              description="Create your first production or start from a template to open the command center."
              artworkSrc="/images/ui/empty-states/empty-projects.svg"
              artworkAlt=""
              actions={
                <button
                  type="button"
                  className="ui-btn ui-btn--primary"
                  data-testid="empty-state-create-project"
                  onClick={() => openCreateProject()}
                >
                  Create Project
                </button>
              }
            />
          ) : (
            <div className={`project-library-grid ${view}`}>
              {[...(preferredProjectId ? filtered.filter((project) => project.id === preferredProjectId) : []), ...filtered.filter((project) => project.id !== preferredProjectId)].map((p) => {
                const cover = resolveProjectCover(p);
                return (
                <ProjectCoverCard
                  key={p.id}
                  view={view}
                  active={p.id === preferredProjectId}
                  project={{
                    id: p.id,
                    name: p.name,
                    description: p.description,
                    engine_default: p.engine_default,
                    updated_at: p.updated_at,
                    scene_count: p.scene_count ?? p.scenes?.length ?? 0,
                    asset_count: p.asset_count ?? p.assets?.length ?? 0,
                    render_pct: p.render_pct ?? 0,
                    status: p.status_label || "Active",
                    cover_url: cover.url,
                    cover_kind: cover.kind,
                    width: p.width,
                    height: p.height,
                    password_protected: p.password_protected,
                    password_locked: p.password_locked,
                  }}
                  onOpen={(id) => void openProject(id)}
                  onRename={async (id) => {
                    const next = window.prompt("Rename project", projects.find((x) => x.id === id)?.name || "");
                    if (!next?.trim()) return;
                    await api.updateProject(id, { name: next.trim() });
                    refresh();
                  }}
                  onDuplicate={async (id) => {
                    const src = projects.find((x) => x.id === id);
                    if (src?.password_protected) {
                      const mode = window.prompt(
                        "Duplicate protection: none | new_password | same_password",
                        "new_password",
                      );
                      if (mode === null) return;
                      let password = "";
                      let confirmPassword = "";
                      let authorizePassword = "";
                      if (mode === "new_password" || mode === "same_password") {
                        password = window.prompt("Password for duplicate (min 12)") || "";
                        confirmPassword = password;
                      }
                      if (src.password_locked && !getProjectUnlockToken(id)) {
                        authorizePassword = window.prompt("Current project password to authorize duplicate") || "";
                      }
                      await api.duplicateProject(id, {
                        protectionMode: mode || "none",
                        password,
                        confirmPassword,
                        authorizePassword,
                      });
                    } else {
                      await api.duplicateProject(id);
                    }
                    refresh();
                  }}
                  onExport={async (id) => {
                    try {
                      const src = projects.find((x) => x.id === id);
                      if (src?.password_protected) {
                        const choice = window.prompt(
                          "Export: without_password | encrypted_archive | cancel",
                          "without_password",
                        );
                        if (!choice || choice === "cancel") return;
                        await api.exportProject(id, { exportMode: choice });
                      } else {
                        await api.exportProject(id);
                      }
                      alert("Export job queued.");
                    } catch (e) {
                      alert(e instanceof Error ? e.message : String(e));
                    }
                  }}
                  onPasswordProtect={(id) => setPwModal({ kind: "set", projectId: id })}
                  onManagePassword={(id) => setPwModal({ kind: "manage", projectId: id })}
                  onLockNow={async (id) => {
                    await api.lockProjectNow(id);
                    clearProjectUnlockToken(id);
                    refresh();
                  }}
                  onArchive={async (id) => {
                    if (!window.confirm("Archive this project? It will hide from the library.")) return;
                    await api.archiveProject(id, true);
                    refresh();
                  }}
                  onDelete={(id) => {
                    const src = projects.find((x) => x.id === id);
                    setDeleteTarget({
                      id,
                      name: (src?.name || "").trim() || "this project",
                    });
                  }}
                />
                );
              })}
            </div>
          )}
          <Dialog
            open={Boolean(deleteTarget)}
            title="Delete this project?"
            danger
            closeOnPrimary={false}
            primaryLoading={deleteBusy}
            primaryLabel={deleteBusy ? "Deleting…" : "Delete permanently"}
            secondaryLabel="Keep project"
            testId="project-delete-confirm"
            onClose={() => {
              if (deleteBusy) return;
              setDeleteTarget(null);
            }}
            onPrimary={() => {
              if (!deleteTarget || deleteBusy) return;
              const target = deleteTarget;
              void (async () => {
                setDeleteBusy(true);
                try {
                  await api.deleteProject(target.id);
                  setDeleteTarget(null);
                  refresh();
                } catch (e) {
                  alert(e instanceof Error ? e.message : String(e));
                } finally {
                  setDeleteBusy(false);
                }
              })();
            }}
          >
            <p>
              Permanently delete <strong>{deleteTarget?.name}</strong>? This cannot be undone.
              Scenes, Library files, and project settings for this project will be removed.
            </p>
          </Dialog>
          {pwModal?.kind === "set" && pwTarget && (
            <SetPasswordModal
              projectId={pwTarget.id}
              projectName={pwTarget.name}
              onClose={() => setPwModal(null)}
              onSaved={() => void refresh()}
            />
          )}
          {pwModal?.kind === "unlock" && pwTarget && (
            <UnlockProjectModal
              projectId={pwTarget.id}
              projectName={pwTarget.name}
              onClose={() => setPwModal(null)}
              onUnlocked={() => {
                void refresh().then(() => navigate(`/project/${pwTarget.id}`));
              }}
            />
          )}
          {pwModal?.kind === "manage" && pwTarget && (
            <ManagePasswordModal
              projectId={pwTarget.id}
              projectName={pwTarget.name}
              onClose={() => setPwModal(null)}
              onChanged={() => void refresh()}
            />
          )}
        </section>

        <section id="explore" className="glass-section" aria-labelledby="explore-heading">
          <SectionHeader
            title="Explore Adept UI"
            description="Open a workspace — creates a project first if you need one."
          />
          <div className="explore-grid" data-testid="explore-adept-ui">
            {exploreItems.map((item) => (
              <WorkspaceFeatureCard
                key={item.id}
                title={item.label}
                description={item.description}
                image={item.image}
                testId={`explore-workspace-${item.id}`}
                onContinue={() => {
                  const id = preferredProjectId;
                  if (!id) {
                    openCreateProject({ kind: "project", workspace: item.workspace });
                    return;
                  }
                  navigate(buildProjectWorkspacePath(id, item.workspace));
                }}
              />
            ))}
          </div>
        </section>

        <div className="home-system-block glass-section" data-testid="system-status-block">
          <SectionHeader title="System Status" />
          <SystemStatusStrip
            onOpenCoDirector={() =>
              navigate(preferredProjectId ? `/co-director?projectId=${encodeURIComponent(preferredProjectId)}` : "/co-director")
            }
          />
        </div>

        <div data-testid="capability-readiness-block">
          <CapabilityReadinessPanel />
        </div>
      </main>
      <HomeCreateProjectModal
        open={createModalOpen}
        busy={createBusy}
        error={createError}
        formKey={createFormKey}
        onClose={cancelCreateProject}
        onSelectTemplate={(templateId) => {
          useTemplateById(templateId, { stayOnHome: true });
        }}
        onCreate={onCreateFromDrawer}
        returnFocusRef={createReturnFocusRef}
        initialName={createIntent.suggestedName}
      />
    </div>
  );
}
