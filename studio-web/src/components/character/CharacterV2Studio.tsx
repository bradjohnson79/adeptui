import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import "./characterV2.css";

type ViewName = "front" | "back" | "closeup";

type ViewSlot = {
  status?: string;
  assetId?: string | null;
  approved?: boolean;
  error?: string | null;
  promptId?: string | null;
};

type V2State = {
  phase?: string;
  atTag?: string;
  productionReady?: boolean;
  jsonRevision?: number;
  sheetAssetId?: string | null;
  visualLock?: { status?: string; error?: string | null };
  revision2?: { status?: string; error?: string | null };
  views?: Record<ViewName, ViewSlot>;
};

type Props = {
  projectId: string;
  characterId: string;
  mode: "express" | "standard";
  saved: boolean;
};

function fileUrl(projectId: string, assetId?: string | null): string {
  if (!assetId) return "";
  return `/api/projects/${encodeURIComponent(projectId)}/assets/${encodeURIComponent(assetId)}/file`;
}

export function CharacterV2Studio({ projectId, characterId, mode, saved }: Props) {
  const [state, setState] = useState<V2State | null>(null);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const pollRef = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    if (!saved) return;
    const next = (await api.getCharacterCreatorV2(projectId, characterId)) as V2State;
    setState(next);
    return next;
  }, [projectId, characterId, saved]);

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [refresh]);

  useEffect(() => {
    const generating = [
      "FRONT_GENERATING",
      "BACK_GENERATING",
      "CLOSEUP_GENERATING",
      "VISION_FRONT",
      "VISION_BOTH_UPDATING_JSON",
    ].includes(String(state?.phase || ""));
    const views = (state?.views ?? {}) as Partial<Record<ViewName, ViewSlot>>;
    const live = Object.values(views).some((v) => ["generating", "queued", "running"].includes(String(v?.status || "")));
    if (!generating && !live) {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
      return;
    }
    if (pollRef.current) return;
    pollRef.current = window.setInterval(() => {
      void refresh().catch(() => undefined);
    }, 2500);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
      pollRef.current = null;
    };
  }, [state?.phase, state?.views, refresh]);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy("");
    }
  };

  if (!saved) {
    return <p className="cc-v2__hint">Save the character first. The profile becomes the character file before any picture is made.</p>;
  }

  const views = (state?.views ?? {}) as Partial<Record<ViewName, ViewSlot>>;
  const lock = state?.visualLock?.status || "none";
  const rev2 = state?.revision2?.status || "none";
  const frontOk = Boolean(views.front?.approved && lock === "ok");
  const sheetReady = frontOk && Boolean(views.back?.approved) && rev2 === "ok";

  const card = (view: ViewName, title: string, helper?: string) => {
    const slot = views[view] || {};
    const img = fileUrl(projectId, slot.assetId);
    return (
      <section className="cc-v2__card" data-testid={`cc-v2-card-${view}`}>
        <h3>{title}</h3>
        {helper ? <p className="cc-v2__hint">{helper}</p> : null}
        {img ? <img className="cc-v2__img" src={img} alt={title} /> : <div className="cc-v2__empty">No image yet</div>}
        <p className="cc-v2__meta">{slot.status || "idle"}{slot.promptId ? ` · ${slot.promptId.slice(0, 8)}` : ""}</p>
        {slot.error ? <p className="cc-v2__error">{slot.error}</p> : null}
        <div className="cc-v2__row">
          <button
            type="button"
            className="cc-v2__btn"
            disabled={!!busy || (view !== "front" && !frontOk)}
            data-testid={`cc-v2-generate-${view}`}
            onClick={() => void run(`create-${view}`, () => api.generateCharacterViewV2(projectId, characterId, view))}
          >
            {view === "front" ? "Create Front View" : view === "back" ? "Create Back View" : "Create Close-up"}
          </button>
          <button
            type="button"
            className="cc-v2__btn cc-v2__btn--primary"
            disabled={!!busy || !slot.assetId}
            data-testid={`cc-v2-approve-${view}`}
            onClick={() => void run(`approve-${view}`, () => api.approveCharacterViewV2(projectId, characterId, view))}
          >
            {view === "front" ? "Approve Front" : view === "back" ? "Approve Back" : "Approve Close-up"}
          </button>
        </div>
      </section>
    );
  };

  return (
    <div className="cc-v2" data-testid="cc-v2-studio" data-mode={mode}>
      <p className="cc-v2__phase" data-testid="cc-v2-phase">{state?.phase || "DRAFT"}</p>
      {state?.productionReady ? (
        <p className="cc-v2__active" data-testid="cc-v2-tag">
          Character Active {state.atTag}
        </p>
      ) : null}
      {lock === "failed" ? (
        <div className="cc-v2__banner">
          <p>Co-Director could not read the front view. Back stays unavailable.</p>
          <button type="button" className="cc-v2__btn" disabled={!!busy} data-testid="cc-v2-retry-vision" onClick={() => void run("vision", () => api.retryCharacterVisionV2(projectId, characterId))}>
            Retry Co-Director Vision
          </button>
        </div>
      ) : null}
      {rev2 === "failed" ? (
        <div className="cc-v2__banner">
          <p>Character details were not updated from both views. The sheet stays unavailable.</p>
          <button type="button" className="cc-v2__btn" disabled={!!busy} data-testid="cc-v2-retry-rev2" onClick={() => void run("rev2", () => api.retryCharacterRevision2V2(projectId, characterId))}>
            Retry Character Detail Update
          </button>
        </div>
      ) : null}
      {lock === "running" || state?.phase === "VISION_FRONT" ? (
        <p className="cc-v2__hint">Co-Director is studying the front view…</p>
      ) : null}
      {state?.phase === "VISION_BOTH_UPDATING_JSON" ? (
        <p className="cc-v2__hint">Co-Director is updating character details from both views…</p>
      ) : null}
      {card("front", "Front view")}
      {card("back", "Back view", frontOk ? undefined : "Available after Front is approved and Co-Director has studied it.")}
      {mode === "standard"
        ? card(
            "closeup",
            "Close-up",
            "Close-up is optional. You do not need it to finish the character or create the Character Sheet. Use it only if you want a clearer facial reference.",
          )
        : null}
      <div className="cc-v2__sheet">
        <button
          type="button"
          className="cc-v2__btn cc-v2__btn--primary"
          disabled={!!busy || !sheetReady}
          data-testid="cc-v2-compose-sheet"
          onClick={() => void run("sheet", () => api.composeCharacterSheetV2(projectId, characterId))}
        >
          Save and Create Character Sheet
        </button>
        {!sheetReady ? <p className="cc-v2__hint">The sheet is available after Front, Back, and the character-detail update.</p> : null}
        {state?.sheetAssetId ? (
          <img className="cc-v2__sheet-img" src={fileUrl(projectId, state.sheetAssetId)} alt="Character sheet" />
        ) : null}
      </div>
      {error ? <p className="cc-v2__error">{error}</p> : null}
      {busy ? <p className="cc-v2__hint">{busy}</p> : null}
    </div>
  );
}
