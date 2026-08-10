import { useEffect, useState } from "react";
import { api } from "../../api";

/** Optional Continuity controls for Generate Studio — policy-aware, no fake readiness. */
export function GenerateContinuitySection({ projectId }: { projectId: string }) {
  const [policy, setPolicy] = useState<any>(null);
  const [identities, setIdentities] = useState<any[]>([]);
  const [identityId, setIdentityId] = useState("");
  const [preview, setPreview] = useState<any>(null);

  useEffect(() => {
    void Promise.all([
      api.continuity.policy(projectId),
      api.continuity.listIdentities(projectId),
    ]).then(([p, ids]) => {
      setPolicy(p);
      setIdentities(ids.items || []);
    }).catch(() => {
      /* continuity optional */
    });
  }, [projectId]);

  const runPreview = async () => {
    if (!identityId) return;
    const r = await api.continuity.preflight(projectId, {
      bindings: [{ identityId, expectedVisibility: "fully_visible" }],
      workflowSupportsReferences: true,
    });
    setPreview(r);
  };

  return (
    <section className="glass-section" data-testid="generate-continuity-section">
      <h3>Continuity</h3>
      <p className="muted">
        Optional. Project policy enabled: {policy?.enabled ? "yes" : "no"} (preflight {policy?.preflightMode || "off"}).
        When the workflow cannot consume references, continuity remains prompt-guided — we do not claim refs were used.
      </p>
      <label>
        Attach identity
        <select
          aria-label="Attach identity"
          value={identityId}
          onChange={(e) => setIdentityId(e.target.value)}
          data-testid="generate-continuity-identity"
        >
          <option value="">None</option>
          {identities.map((i) => (
            <option key={i.id} value={i.id}>
              {i.displayName || i.canonicalName}
            </option>
          ))}
        </select>
      </label>
      <button type="button" disabled={!identityId} onClick={() => void runPreview()} data-testid="generate-continuity-preflight">
        Preview Continuity Packet
      </button>
      {preview ? (
        <p data-testid="generate-continuity-packet-id">
          Status {preview.status} · packet {preview.packetId || "none"} · bindings {preview.bindingCount ?? 0}
        </p>
      ) : null}
    </section>
  );
}
