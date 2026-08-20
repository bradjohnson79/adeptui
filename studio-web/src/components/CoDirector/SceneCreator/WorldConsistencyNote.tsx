import { useEffect, useState } from "react";
import { api } from "../../../api";

type Advisory = {
  advisoryText: string | null;
  canMarkIntentional: boolean;
  packet: Record<string, unknown> | null;
};

export function WorldConsistencyNote({
  projectId,
  sceneId,
  assetId,
}: {
  projectId: string;
  sceneId?: string;
  assetId?: string;
}) {
  const [advisory, setAdvisory] = useState<Advisory | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    let cancelled = false;
    void api.worldIntelligence
      .advisory(projectId, sceneId, assetId)
      .then((row) => {
        if (!cancelled) setAdvisory(row);
      })
      .catch(() => {
        if (!cancelled) setAdvisory(null);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, sceneId, assetId]);

  if (!advisory?.advisoryText) return null;

  const markIntentional = async () => {
    const packet = advisory.packet || {};
    const comparisons = (packet.comparisons as Array<Record<string, unknown>> | undefined) || [];
    const fromId = String(comparisons[0]?.referenceAssetId || "");
    const toId = String(assetId || comparisons[0]?.observedAssetId || "");
    if (!fromId || !toId) return;
    setBusy(true);
    try {
      await api.worldIntelligence.markIntentional(projectId, fromId, toId, sceneId);
      setAdvisory({
        ...advisory,
        advisoryText: "This world change is marked as intentional.",
        canMarkIntentional: false,
      });
    } catch {
      /* keep the current note */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="world-consistency-note" data-testid="world-consistency-note">
      <p className="scene-creator-profile__caption" data-testid="world-consistency-text">
        {advisory.advisoryText}
      </p>
      {advisory.canMarkIntentional ? (
        <button
          type="button"
          className="ghost"
          data-testid="world-consistency-intentional"
          disabled={busy}
          onClick={() => void markIntentional()}
        >
          This change is on purpose
        </button>
      ) : null}
    </div>
  );
}
