import { useCallback, useEffect, useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";

type Props = {
  project: Project;
  onChange?: () => void;
  embedded?: boolean;
  preferredIdentityId?: string;
};

export function IdentityRegistryWorkspace({ project, embedded, preferredIdentityId }: Props) {
  const [identities, setIdentities] = useState<any[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(preferredIdentityId || null);
  const [versions, setVersions] = useState<any[]>([]);
  const [refs, setRefs] = useState<any[]>([]);
  const [readiness, setReadiness] = useState<any | null>(null);
  const [policy, setPolicy] = useState<any | null>(null);
  const [name, setName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(async () => {
    setError(null);
    const [list, pol] = await Promise.all([
      api.continuity.listIdentities(project.id),
      api.continuity.policy(project.id),
    ]);
    setIdentities(list.items || []);
    setPolicy(pol);
  }, [project.id]);

  const select = useCallback(async (id: string) => {
    setSelectedId(id);
    const [vers, rlist, ready] = await Promise.all([
      api.continuity.listVersions(project.id, id),
      api.continuity.listReferences(project.id, id),
      api.continuity.readiness(project.id, id),
    ]);
    setVersions(vers.items || []);
    setRefs(rlist.items || []);
    setReadiness(ready);
  }, [project.id]);

  useEffect(() => {
    void reload().catch((e) => setError(String(e?.message || e)));
  }, [reload]);

  useEffect(() => {
    if (!preferredIdentityId) return;
    void select(preferredIdentityId).catch(() => undefined);
  }, [preferredIdentityId, project.id, select]);

  const createIdentity = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const created = await api.continuity.createIdentity(project.id, {
        identityType: "character",
        canonicalName: name.trim(),
        displayName: name.trim(),
      });
      setName("");
      await reload();
      if (created.id) await select(String(created.id));
    } catch (e: any) {
      setError(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  const approveVersion = async (versionId: string) => {
    await api.continuity.approveVersion(project.id, versionId);
    if (selectedId) await select(selectedId);
  };

  const togglePolicy = async () => {
    if (!policy) return;
    const next = await api.continuity.updatePolicy(project.id, {
      enabled: !policy.enabled,
      preflightMode: policy.enabled ? "off" : "warn",
      evaluationMode: "manual",
    });
    setPolicy(next);
  };

  return (
    <div
      className={`workspace-root${embedded ? " workspace-root--embedded" : ""}`}
      data-testid="identity-registry-workspace"
    >
      <header className="workspace-header">
        {embedded ? <h3>Identity Registry</h3> : <h1>Identity Registry</h1>}
        <p>
          Project-scoped visual identities. Continuity is optional until policy is enabled.
          Identity Readiness is not an output continuity score.
        </p>
      </header>

      {error ? (
        <div role="alert" className="error-banner">
          {error}
        </div>
      ) : null}

      <section data-testid="continuity-policy-panel" className="glass-section">
        <h2>Continuity Policy</h2>
        <p>
          Enabled: <strong>{policy?.enabled ? "yes" : "no"}</strong> · Preflight:{" "}
          {policy?.preflightMode || "off"} · Evaluation: {policy?.evaluationMode || "manual"}
        </p>
        <button type="button" onClick={() => void togglePolicy()} data-testid="continuity-policy-toggle">
          {policy?.enabled ? "Disable continuity enforcement" : "Enable continuity (warn mode)"}
        </button>
      </section>

      <div className="split-layout" style={{ display: "grid", gridTemplateColumns: "280px 1fr", gap: 16 }}>
        <aside data-testid="identity-list">
          <h2>Identities</h2>
          <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
            <input
              aria-label="New identity name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Canonical name"
              data-testid="identity-name-input"
            />
            <button type="button" disabled={busy} onClick={() => void createIdentity()} data-testid="identity-create">
              Create
            </button>
          </div>
          <ul>
            {identities.length === 0 ? (
              <li data-testid="identity-empty">No identities yet. Create one to begin.</li>
            ) : (
              identities.map((id) => (
                <li key={id.id}>
                  <button
                    type="button"
                    data-testid={`identity-card-${id.id}`}
                    onClick={() => void select(id.id)}
                    aria-current={selectedId === id.id}
                  >
                    {id.displayName || id.canonicalName}{" "}
                    <span>({id.identityType} · {id.status})</span>
                  </button>
                </li>
              ))
            )}
          </ul>
        </aside>

        <main data-testid="identity-detail">
          {!selectedId ? (
            <p>Select an identity to manage versions, references, and readiness.</p>
          ) : (
            <>
              <section data-testid="identity-readiness-panel">
                <h2>Identity Readiness</h2>
                <p className="muted">{readiness?.summary}</p>
                <ul>
                  <li>Approved version: {readiness?.approvedVersionPresent ? "present" : "missing"}</li>
                  <li>Front: {readiness?.referenceCoverage?.front ? "yes" : "missing"}</li>
                  <li>Profile: {readiness?.referenceCoverage?.profile ? "yes" : "missing"}</li>
                  <li>Back: {readiness?.referenceCoverage?.back ? "yes" : "missing"}</li>
                  <li>Full body: {readiness?.referenceCoverage?.fullBody ? "yes" : "missing"}</li>
                  <li>Wardrobe: {readiness?.referenceCoverage?.wardrobe ? "partial/yes" : "missing"}</li>
                </ul>
                {!(readiness?.referenceCoverage?.profile) ? (
                  <p data-testid="missing-profile-ref">
                    No approved profile reference exists for this identity version. Add or approve a
                    registered project asset before requiring profile continuity.
                  </p>
                ) : null}
              </section>

              <section data-testid="identity-version-panel">
                <h2>Versions</h2>
                <ul>
                  {versions.map((v) => (
                    <li key={v.id} data-testid={`identity-version-${v.versionNumber}`}>
                      v{v.versionNumber} · {v.label} · {v.status}
                      {v.status !== "approved" ? (
                        <button type="button" onClick={() => void approveVersion(v.id)}>
                          Approve
                        </button>
                      ) : (
                        <span> (immutable)</span>
                      )}
                    </li>
                  ))}
                </ul>
              </section>

              <section data-testid="reference-role-manager">
                <h2>References</h2>
                {refs.length === 0 ? (
                  <p>No candidate references. Attach a registered project asset — nothing is invented.</p>
                ) : (
                  <ul>
                    {refs.map((r) => (
                      <li key={r.id} data-testid={`reference-${r.id}`}>
                        Asset {r.assetId} · {(r.roles || []).join(", ") || "no roles"} · {r.approvalStatus}
                        {r.approvalStatus === "candidate" || r.approvalStatus === "in_review" ? (
                          <>
                            <button type="button" onClick={() => void api.continuity.approveReference(project.id, r.id).then(() => select(selectedId!))}>
                              Approve
                            </button>
                            <button type="button" onClick={() => void api.continuity.rejectReference(project.id, r.id).then(() => select(selectedId!))}>
                              Reject
                            </button>
                          </>
                        ) : null}
                        {r.approvalStatus === "approved" ? (
                          <>
                            <button
                              type="button"
                              data-testid={`attach-scene-ref-${r.id}`}
                              onClick={() => {
                                const sceneId = project.scenes[0]?.id;
                                if (!sceneId || !selectedId) return;
                                const activeVer = versions.find((v) => v.status === "approved") || versions[0];
                                void api.sceneReferences
                                  .attach(project.id, {
                                    asset_id: r.assetId,
                                    scope_type: "scene",
                                    scope_id: sceneId,
                                    reference_type: "character",
                                    usage_modes: ["identity", "appearance"],
                                    reference_roles: r.roles || ["character"],
                                    identity_id: selectedId,
                                    identity_version_id: activeVer?.id || null,
                                  })
                                  .then(() => select(selectedId));
                              }}
                            >
                              Attach to active scene references
                            </button>
                            <button
                              type="button"
                              onClick={() =>
                                void api.continuity.revokeReference(project.id, r.id, "Incorrect reference").then(() => select(selectedId!))
                              }
                            >
                              Revoke
                            </button>
                          </>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </main>
      </div>
    </div>
  );
}
