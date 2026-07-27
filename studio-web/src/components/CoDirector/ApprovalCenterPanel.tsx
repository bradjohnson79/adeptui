import { useEffect, useState } from "react";
import { api } from "../../api";

export function ApprovalCenterPanel({ projectId }: { projectId: string }) {
  const [data, setData] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const res = await api.m214Approvals({
        projectId,
        pending: {
          story: { status: "pending", items: [{ id: "story-1", label: "Storyteller handoff" }] },
          media: { status: "pending", items: [{ id: "media-1", label: "Mocked hitchhiker card" }] },
        },
      });
      if (!cancelled) setData(res);
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  return (
    <section className="m214-approval-center" data-testid="m214-approval-center" aria-label="Approval Center">
      <h3>Approval Center</h3>
      <p>Pending: {String(data?.pendingCount ?? "…")}</p>
      <p className="m214-primary-action">{String(data?.primaryNextAction || "")}</p>
      <ul>
        {((data?.categories as Array<{ category: string; status: string }>) || []).map((c) => (
          <li key={c.category}>
            <span className={`m214-status m214-status-${c.status}`} aria-label={`${c.category} ${c.status}`}>
              {c.category}: {c.status}
            </span>
          </li>
        ))}
      </ul>
      <p className="eyebrow">No silent approvals</p>
    </section>
  );
}
