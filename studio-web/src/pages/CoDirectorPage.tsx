import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, bindAssetUrlProject } from "../api";
import { CoDirectorFullScreen } from "../components/CoDirector";
import { useCoDirectorSession } from "../components/CoDirector/CoDirectorSession";
import { StudioChrome } from "../components/dashboard/StudioChrome";
import { buildCoDirectorSearch, loadLastSelectedScene, parseSceneIdFromSearch, persistWorkspaceKey } from "../sceneSelection";
import { buildProjectWorkspaceLocation } from "../navigation/projectWorkspaceNavigation";

export default function CoDirectorPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const projectId = params.get("projectId");
  const { bindWorkspace, unbindWorkspace } = useCoDirectorSession();
  const [projectName, setProjectName] = useState<string | undefined>();
  const [primaryProjectType, setPrimaryProjectType] = useState<string | undefined>();
  const [sceneName, setSceneName] = useState<string | undefined>();
  const querySceneId = params.get("sceneId") || parseSceneIdFromSearch(`?${params.toString()}`);
  const workspaceTab = persistWorkspaceKey(params.get("workspace") || "timeline");
  const persistedSceneId = projectId ? loadLastSelectedScene(projectId, workspaceTab || "timeline") : null;
  const sceneId = querySceneId || persistedSceneId || undefined;

  useEffect(() => {
    bindAssetUrlProject(projectId);
    return () => bindAssetUrlProject(null);
  }, [projectId]);

  useEffect(() => {
    if (!projectId) {
      setProjectName(undefined);
      setPrimaryProjectType(undefined);
      setSceneName(undefined);
      return;
    }
    let cancelled = false;
    api
      .getProject(projectId)
      .then((p) => {
        if (!cancelled) {
          setProjectName(p?.name);
          setPrimaryProjectType(p?.primary_project_type || "custom");
          const scene = (p?.scenes || []).find((row) => row.id === sceneId);
          setSceneName(scene?.name);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProjectName(undefined);
          setPrimaryProjectType(undefined);
          setSceneName(undefined);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, sceneId]);

  useEffect(() => {
    const onRenamed = (event: Event) => {
      const detail = (event as CustomEvent<{ projectId?: string; projectName?: string }>).detail;
      if (!detail?.projectId || detail.projectId !== projectId) return;
      if (detail.projectName) setProjectName(detail.projectName);
    };
    window.addEventListener("adept:project-renamed", onRenamed as EventListener);
    return () => window.removeEventListener("adept:project-renamed", onRenamed as EventListener);
  }, [projectId]);

  useEffect(() => {
    // Canonical binding comes from the route only — never silent restore from last-project suggestion.
    if (!projectId) {
      unbindWorkspace();
      return;
    }
    const generation = bindWorkspace({
      projectId,
      projectName: projectName || "Project",
      primaryProjectType: primaryProjectType || "custom",
      sceneId: sceneId || undefined,
      sceneName,
      workspaceTab: workspaceTab || undefined,
      // Allow embedded Project Building panes (Character Creator, Scriptwriter, etc.)
      // to deep-link into the standalone project workspaces, preserving extra params
      // such as characterId / returnWorkspace. Without this, onGoTab is undefined in
      // fullscreen Co-Director and "Open Full Character Creator" is a no-op.
      onGoTab: (tab: string, extra?: Record<string, string>) => {
        const location = buildProjectWorkspaceLocation({
          projectId,
          tab,
          sceneId,
          extra,
        });
        if (!location) return;
        navigate({ pathname: location.pathname, search: location.search });
      },
    });
    return () => unbindWorkspace({ bindGeneration: generation });
  }, [bindWorkspace, unbindWorkspace, navigate, projectId, projectName, primaryProjectType, sceneId, sceneName, workspaceTab]);

  return (
    <div className="app-shell atmosphere app-shell-fixed">
      <StudioChrome
        variant={projectId ? "project" : "home"}
        projectId={projectId || undefined}
        projectName={projectName}
        onOpenCoDirector={() =>
          navigate(
            projectId
              ? `/co-director${buildCoDirectorSearch({
                  projectId,
                  sceneId,
                  workspace: workspaceTab,
                })}`
              : "/co-director",
          )
        }
        breadcrumbs={[
          { label: "Home", onClick: () => navigate("/") },
          ...(projectId
            ? [{ label: "Project", onClick: () => navigate(`/project/${projectId}`) }]
            : []),
          { label: "Co-Director" },
        ]}
      />
      <CoDirectorFullScreen />
    </div>
  );
}
