import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api";
import { CoDirectorFullScreen } from "../components/CoDirector";
import { useCoDirectorSession } from "../components/CoDirector/CoDirectorSession";
import { StudioChrome } from "../components/dashboard/StudioChrome";

export default function CoDirectorPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const projectId = params.get("projectId");
  const { bindWorkspace, unbindWorkspace } = useCoDirectorSession();
  const [projectName, setProjectName] = useState<string | undefined>();
  const [primaryProjectType, setPrimaryProjectType] = useState<string | undefined>();

  useEffect(() => {
    if (!projectId) {
      setProjectName(undefined);
      setPrimaryProjectType(undefined);
      return;
    }
    let cancelled = false;
    api
      .getProject(projectId)
      .then((p) => {
        if (!cancelled) {
          setProjectName(p?.name);
          setPrimaryProjectType(p?.primary_project_type || "custom");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setProjectName(undefined);
          setPrimaryProjectType(undefined);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

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
    bindWorkspace({
      projectId,
      projectName: projectName || "Project",
      primaryProjectType: primaryProjectType || "custom",
    });
  }, [bindWorkspace, unbindWorkspace, projectId, projectName, primaryProjectType]);

  return (
    <div className="app-shell atmosphere app-shell-fixed">
      <StudioChrome
        variant={projectId ? "project" : "home"}
        projectId={projectId || undefined}
        projectName={projectName}
        onOpenCoDirector={() => navigate("/co-director")}
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
