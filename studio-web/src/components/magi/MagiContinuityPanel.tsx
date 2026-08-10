import { useState } from "react";
import { api } from "../../api";

type Props = {
  projectId: string;
  sourceAssetId: string | null;
};

/** MAGI Continuity drawer — corrections only via ImageEditIntent path. */
export function MagiContinuityPanel({ projectId, sourceAssetId }: Props) {
  const [msg, setMsg] = useState<string | null>(null);
  const [correction, setCorrection] = useState<any | null>(null);
  const [busy, setBusy] = useState(false);

  const propose = async () => {
    if (!sourceAssetId) {
      setMsg("Select a source asset first.");
      return;
    }
    setBusy(true);
    setMsg(null);
    try {
      const c = await api.continuity.proposeCorrection(projectId, {
        sourceAssetId,
        dimensions: ["overall_identity"],
        prompt: "Restore approved visual identity from Continuity Packet references.",
      });
      setCorrection(c);
      setMsg(`${c.certificationLabel || c.status}: ${c.disclosure || ""}`);
    } catch (e: any) {
      setMsg(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  const enqueue = async () => {
    if (!correction?.id || !correction.certified) {
      setMsg("Only Certified corrections can enqueue. Deferred/Blocked never enqueue.");
      return;
    }
    setBusy(true);
    try {
      const r = await api.continuity.enqueueCorrection(projectId, String(correction.id));
      setCorrection(r);
      setMsg(`Enqueued via ImageEditIntent. Source preserved: ${String(r.sourcePreserved)}`);
    } catch (e: any) {
      setMsg(String(e?.message || e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div data-testid="magi-continuity-panel">
      <p className="magi-group-label">Expected Identity</p>
      <p className="magi-empty">Open Continuity Workspace for multi-binding packet review.</p>
      <p className="magi-group-label">Correction</p>
      <div className="magi-actions">
        <button type="button" className="magi-chip" disabled={busy} onClick={() => void propose()}>
          Propose correction
        </button>
        <button
          type="button"
          className="magi-primary"
          disabled={busy || !correction?.certified}
          onClick={() => void enqueue()}
          data-testid="magi-continuity-enqueue"
        >
          Approve enqueue
        </button>
      </div>
      {correction ? (
        <p data-testid="magi-continuity-cert-label">
          {correction.certificationLabel} · workflow {correction.workflowKey}
        </p>
      ) : null}
      {msg ? <p className="magi-empty">{msg}</p> : null}
      <p className="magi-empty">
        Compare modes: output vs reference, prior approved, adjacent Timeline shot, before/after correction.
        No second MAGI correction runtime.
      </p>
    </div>
  );
}
