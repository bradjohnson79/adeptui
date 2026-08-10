import { useState, type ReactNode } from "react";
import {
  CoDirectorAssetCard,
  CoDirectorContentCard,
  CoDirectorEmptyState,
  CoDirectorEntityCard,
  CoDirectorErrorState,
  CoDirectorJobCard,
  CoDirectorPlanCard,
  CoDirectorWarningCard,
} from "../cards";
import type { RetrievalEnvelope, RetrievalEvidence } from "./types";

function EvidenceList({ evidence }: { evidence: RetrievalEvidence[] }) {
  if (!evidence.length) return null;
  return (
    <details className="codirector-retrieval-evidence" data-testid="codirector-retrieval-evidence">
      <summary>Evidence ({evidence.length})</summary>
      <ul>
        {evidence.map((e, i) => (
          <li key={`${e.sourceType}-${e.sourceId}-${i}`}>
            <strong>{e.sourceType}</strong> · {e.sourceName || e.sourceId}
            <span className="muted"> via {e.repository}</span>
          </li>
        ))}
      </ul>
    </details>
  );
}

function CardShell({
  toolId,
  children,
  title,
  meta,
  footer,
  testId,
}: {
  toolId: string;
  children?: ReactNode;
  title: string;
  meta?: string;
  footer?: ReactNode;
  testId?: string;
}) {
  if (toolId.startsWith("asset.") || toolId.includes("library")) {
    return (
      <CoDirectorAssetCard title={title} meta={meta} footer={footer} testId={testId}>
        {children}
      </CoDirectorAssetCard>
    );
  }
  if (toolId.startsWith("job.")) {
    return (
      <CoDirectorJobCard title={title} meta={meta} footer={footer} testId={testId}>
        {children}
      </CoDirectorJobCard>
    );
  }
  if (toolId.startsWith("production_plan.") || toolId.includes("plan")) {
    return (
      <CoDirectorPlanCard title={title} meta={meta} footer={footer} testId={testId}>
        {children}
      </CoDirectorPlanCard>
    );
  }
  if (toolId.startsWith("character.") || toolId.startsWith("scene.") || toolId.startsWith("production_bible.")) {
    return (
      <CoDirectorEntityCard title={title} meta={meta} footer={footer} testId={testId}>
        {children}
      </CoDirectorEntityCard>
    );
  }
  return (
    <CoDirectorContentCard title={title} meta={meta} footer={footer} testId={testId}>
      {children}
    </CoDirectorContentCard>
  );
}

function dataPreview(data: unknown): string {
  if (data == null) return "No payload.";
  if (typeof data === "string") return data.slice(0, 280);
  try {
    return JSON.stringify(data, null, 2).slice(0, 600);
  } catch {
    return String(data).slice(0, 280);
  }
}

export function RetrievalResultCard({
  envelope,
  testId = "codirector-retrieval-card",
}: {
  envelope: RetrievalEnvelope;
  testId?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const evidence = envelope.evidence || [];
  const warnings = envelope.warnings || [];

  if (envelope.status === "failed") {
    return (
      <CoDirectorErrorState
        testId={testId}
        title="Retrieval failed"
        description={envelope.summary || `Tool ${envelope.toolId} failed.`}
      />
    );
  }

  if (envelope.status === "empty") {
    return (
      <div data-testid={testId}>
        <CoDirectorEmptyState
          kind="no-results"
          title="Nothing found"
          description={envelope.summary || `No records from ${envelope.toolId}.`}
        />
        <EvidenceList evidence={evidence} />
      </div>
    );
  }

  if (envelope.status === "partial") {
    return (
      <div data-testid={testId}>
        <CoDirectorWarningCard
          title="Partial retrieval"
          meta={envelope.toolId}
          footer={<EvidenceList evidence={evidence} />}
        >
          <p>{envelope.summary}</p>
          {warnings.map((w) => (
            <p key={w.code} className="muted">
              {w.message}
            </p>
          ))}
          {(envelope.unavailableSections || []).length > 0 ? (
            <p className="muted">Unavailable: {(envelope.unavailableSections || []).join(", ")}</p>
          ) : null}
          <button type="button" className="linkish" onClick={() => setExpanded((v) => !v)}>
            {expanded ? "Hide details" : "Show details"}
          </button>
          {expanded ? <pre className="codirector-retrieval-json">{dataPreview(envelope.data)}</pre> : null}
        </CoDirectorWarningCard>
      </div>
    );
  }

  return (
    <CardShell
      toolId={envelope.toolId}
      title={envelope.summary || envelope.toolId}
      meta={`${envelope.toolId}${envelope.retrievedAt ? ` · ${envelope.retrievedAt}` : ""}`}
      testId={testId}
      footer={<EvidenceList evidence={evidence} />}
    >
      {warnings.map((w) => (
        <p key={w.code} className="muted">
          {w.message}
        </p>
      ))}
      <button type="button" className="linkish" onClick={() => setExpanded((v) => !v)}>
        {expanded ? "Hide details" : "Show details"}
      </button>
      {expanded ? <pre className="codirector-retrieval-json">{dataPreview(envelope.data)}</pre> : null}
    </CardShell>
  );
}
