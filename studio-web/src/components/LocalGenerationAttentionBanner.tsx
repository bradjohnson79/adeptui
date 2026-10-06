import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../api";
import { clearCacheEntry } from "../runtime/requestCache";
import { useLocalGenerationAttention } from "../hooks/useLocalGenerationAttention";
import { LOCAL_GENERATION_ATTENTION, refreshLocalGenerationAttention } from "../runtime/localGenerationAttention";

export function LocalGenerationAttentionBanner() {
  const snap = useLocalGenerationAttention();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);

  if (!snap.active) return null;

  const cancel = async () => {
    if (!snap.jobId || !snap.cancelable) return;
    setBusy(true);
    try {
      await api.cancelJob(snap.jobId);
      clearCacheEntry("GET", "/api/runtime/local-generation");
    } catch {
      /* hydrate next poll — do not invent success */
    } finally {
      await refreshLocalGenerationAttention();
      setBusy(false);
    }
  };

  const showIt = () => {
    if (snap.projectId) {
      navigate(`/project/${encodeURIComponent(snap.projectId)}`);
    }
  };

  return (
    <div
      className="local-generation-attention-banner"
      data-testid="local-generation-attention-banner"
      role="status"
      aria-live="polite"
    >
      <div className="local-generation-attention-banner__text">
        <strong>Local generation in progress</strong>
        <p data-testid="local-generation-attention-copy">{LOCAL_GENERATION_ATTENTION}</p>
      </div>
      <div className="local-generation-attention-banner__actions">
        {snap.projectId ? (
          <button type="button" data-testid="local-generation-attention-show" onClick={showIt}>
            Show it
          </button>
        ) : null}
        {snap.cancelable && snap.jobId ? (
          <button
            type="button"
            data-testid="local-generation-attention-cancel"
            disabled={busy}
            onClick={() => void cancel()}
          >
            {busy ? "Cancelling…" : "Cancel"}
          </button>
        ) : null}
      </div>
    </div>
  );
}
