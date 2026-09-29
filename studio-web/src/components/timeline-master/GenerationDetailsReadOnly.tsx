import { useMemo } from "react";
import type { SceneTimelineMaster } from "../../timelineMaster/contracts";
import { formatBatchStatus } from "../../timelineMaster/contracts";
import { executionWindowSpans } from "../../timelineMaster/resolveExecutionWindowForPrompt";

type Props = {
  master: SceneTimelineMaster | null | undefined;
};

/**
 * Read-only Generation Details - CD/rematerialize-owned associations.
 * Not a Batch track; no create/drag/resize/delete/duplicate.
 */
export function GenerationDetailsReadOnly({ master }: Props) {
  const rows = useMemo(() => executionWindowSpans(master?.batchBlocks), [master?.batchBlocks]);
  if (!rows.length) {
    return (
      <div className="timeline-inspector__section" data-testid="timeline-generation-details">
        <h4>Generation Details</h4>
        <p className="scene-meta">No generation associations yet. They appear after rematerialize from the Co-Director plan.</p>
      </div>
    );
  }
  return (
    <div className="timeline-inspector__section" data-testid="timeline-generation-details">
      <h4>Generation Details</h4>
      <p className="scene-meta">Read-only. Associations are owned by Co-Director and rematerialize - not edited here.</p>
      <ul className="timeline-master-batches" aria-label="Generation Details">
        {rows.map(({ batch, start, end }, index) => {
          const takeCount = batch.candidateVersions?.length ?? 0;
          const takeLabel = takeCount === 0 ? "" : " - " + takeCount + (takeCount === 1 ? " take" : " takes");
          return (
            <li
              key={batch.id}
              className="timeline-master-batch"
              data-testid={"timeline-generation-detail-" + batch.id}
            >
              <div className="timeline-master-batch__row">
                <strong>
                  Region {index + 1}: {start.toFixed(2)}s-{end.toFixed(2)}s
                </strong>
                <span>{formatBatchStatus(batch.status)}</span>
              </div>
              <div className="timeline-master-batch__meta">
                {batch.generatorId || "No generator"}
                {takeLabel}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}