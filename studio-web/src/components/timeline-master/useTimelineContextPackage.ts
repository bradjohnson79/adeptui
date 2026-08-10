import { useEffect, useState } from "react";
import { api } from "../../api";

/**
 * useTimelineContextPackage — Timeline consumes the single context package
 * produced by Co-Director (TIMELINE_CONSUMES_CONTEXT_PACKAGE). The Timeline
 * never requests Bible/Characters/References individually.
 *
 * PRODUCTION_READINESS_OWNED_BY_CODIRECTOR: readiness is consumed from this
 * package; the Timeline never invents it.
 */
export function useTimelineContextPackage(
  projectId: string,
  sceneId: string | undefined,
  actionScope: "exploration" | "production" = "exploration",
) {
  const [pkg, setPkg] = useState<Awaited<ReturnType<typeof api.getTimelineContextPackage>> | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!sceneId) return;
    let alive = true;
    setLoading(true);
    setError(null);
    api
      .getTimelineContextPackage(projectId, sceneId, actionScope)
      .then((result) => {
        if (!alive) return;
        setPkg(result);
      })
      .catch((e) => {
        if (!alive) return;
        setError(e instanceof Error ? e.message : "Failed to load Timeline context");
      })
      .finally(() => {
        if (!alive) return;
        setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [projectId, sceneId, actionScope]);

  return { pkg, loading, error };
}
