import { useEffect, useState } from "react";
import { api } from "../../../api";
import { CoDirectorEmptyState, CoDirectorErrorState } from "../cards";
import { RetrievalResultCard } from "./RetrievalResultCard";
import { asRetrievalEnvelope, type RetrievalEnvelope } from "./types";

const OVERVIEW_TOOLS = ["project.get_summary", "project.list_blockers"] as const;
const LIBRARY_TOOLS = ["asset.list"] as const;
const PLANS_TOOLS = ["production_plan.list", "proposal.list"] as const;
const BIBLE_TOOLS = ["production_bible.get_summary"] as const;
const JOBS_TOOLS = ["job.list"] as const;

async function runTool(projectId: string, toolId: string): Promise<RetrievalEnvelope | { error: string }> {
  try {
    const inv = await api.runCoDirectorReadTool(projectId, {
      toolId,
      arguments: { limit: 25 },
      requestId: `pc-${toolId}-${Date.now()}`,
    });
    if (inv.status !== "succeeded" || !inv.result) {
      return { error: inv.errorMessage || `${toolId} ${inv.status}` };
    }
    const env = asRetrievalEnvelope(inv.result);
    if (!env) {
      return {
        toolId,
        status: "success",
        summary: `${toolId} completed.`,
        data: inv.result,
        evidence: [],
      };
    }
    return env;
  } catch (err) {
    return { error: err instanceof Error ? err.message : String(err) };
  }
}

export function ProjectRetrievalPanel({
  projectId,
  tools,
  emptyTitle,
  emptyDescription,
  testId,
}: {
  projectId: string;
  tools: readonly string[];
  emptyTitle: string;
  emptyDescription: string;
  testId: string;
}) {
  const [loading, setLoading] = useState(true);
  const [envelopes, setEnvelopes] = useState<RetrievalEnvelope[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      const results: RetrievalEnvelope[] = [];
      let firstError: string | null = null;
      for (const toolId of tools) {
        const out = await runTool(projectId, toolId);
        if (cancelled) return;
        if ("error" in out) {
          firstError = firstError || out.error;
          continue;
        }
        results.push(out);
      }
      if (!cancelled) {
        setEnvelopes(results);
        setError(results.length ? null : firstError);
        setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId, tools]);

  if (loading) {
    return (
      <p className="muted" data-testid={`${testId}-loading`}>
        Loading retrieval…
      </p>
    );
  }

  if (error && !envelopes.length) {
    return <CoDirectorErrorState testId={`${testId}-error`} title="Retrieval unavailable" description={error} />;
  }

  if (!envelopes.length) {
    return <CoDirectorEmptyState testId={`${testId}-empty`} title={emptyTitle} description={emptyDescription} />;
  }

  return (
    <div className="codirector-retrieval-panel" data-testid={testId}>
      {envelopes.map((env) => (
        <RetrievalResultCard key={`${env.toolId}-${env.retrievedAt || env.summary}`} envelope={env} />
      ))}
    </div>
  );
}

export const RETRIEVAL_TOOL_SETS = {
  overview: OVERVIEW_TOOLS,
  library: LIBRARY_TOOLS,
  plans: PLANS_TOOLS,
  bible: BIBLE_TOOLS,
  jobs: JOBS_TOOLS,
};
