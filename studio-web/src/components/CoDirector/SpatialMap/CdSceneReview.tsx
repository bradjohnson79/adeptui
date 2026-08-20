import { useCallback, useRef, useState } from "react";
import { api } from "../../../api";
import { creatorPerceptionMessage, SCENE_REVIEW_START_FAILED } from "../../../codirector/perception/requestPolicy";

type Fill = {
  id: string;
  kind: "character" | "prop" | "camera";
  label: string;
  tag?: string;
  miniPrompt?: string;
  factStatus?: string;
  characterApproved?: boolean;
};

type Draft = {
  reviewLabel?: string;
  sceneReviewAvailable?: boolean;
  geometryStatus?: string;
  geometryReason?: string;
  canonAvailability?: string;
  canonUnavailableReason?: string;
  proposedFills?: Fill[];
  unusedDetections?: Array<{ label?: string; reason?: string }>;
  zonePhrases?: Array<{ phrase?: string }>;
  relationships?: Array<{ subjectLabel?: string; relation?: string; objectLabel?: string }>;
};

export function CdSceneReview({
  projectId,
  mapId,
  onAccepted,
}: {
  projectId: string;
  mapId: string;
  onAccepted: () => void;
}) {
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [canRetry, setCanRetry] = useState(false);
  const [selected, setSelected] = useState<Record<string, boolean>>({});
  const inFlight = useRef(false);

  const runReview = useCallback(async () => {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setMessage("");
    setCanRetry(false);
    try {
      const res = await api.perception.review(projectId, mapId);
      const next = (res.draft || {}) as Draft;
      setDraft(next);
      const initial: Record<string, boolean> = {};
      for (const fill of next.proposedFills || []) {
        initial[fill.id] = fill.kind === "character" ? !!fill.characterApproved : fill.kind !== "camera" || true;
      }
      setSelected(initial);
    } catch (err) {
      setMessage(creatorPerceptionMessage(err, SCENE_REVIEW_START_FAILED));
      setCanRetry(true);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, [projectId, mapId]);

  const accept = useCallback(async () => {
    if (!draft || inFlight.current) return;
    const items = (draft.proposedFills || [])
      .filter((fill) => selected[fill.id] && fill.factStatus !== "rejected")
      .map((fill) => ({ fillId: fill.id }));
    if (!items.length) {
      setMessage("Choose at least one suggestion to place.");
      setCanRetry(false);
      return;
    }
    inFlight.current = true;
    setBusy(true);
    setMessage("");
    setCanRetry(false);
    try {
      const res = await api.perception.accept(projectId, mapId, items);
      if (res.draft) setDraft(res.draft as Draft);
      if (res.failures?.length) {
        setMessage(res.failures.map((item) => item.message).join(" "));
      } else if (res.acceptedFillIds?.length) {
        setMessage("Placed on the map. You can still move anything by hand.");
        onAccepted();
      }
    } catch (err) {
      setMessage(creatorPerceptionMessage(err, "Could not place those suggestions."));
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }, [draft, selected, projectId, mapId, onAccepted]);

  const reject = useCallback(
    async (fill: Fill) => {
      if (inFlight.current) return;
      inFlight.current = true;
      setBusy(true);
      try {
        const res = await api.perception.correct(projectId, mapId, [
          { factKey: `fill:${(fill.label || fill.id).toLowerCase()}`, action: "reject", value: {} },
        ]);
        if (res.draft) setDraft(res.draft as Draft);
      } catch (err) {
        setMessage(creatorPerceptionMessage(err, "Could not skip that suggestion."));
      } finally {
        inFlight.current = false;
        setBusy(false);
      }
    },
    [projectId, mapId],
  );

  const fills = draft?.proposedFills || [];
  const characters = fills.filter((item) => item.kind === "character");
  const props = fills.filter((item) => item.kind === "prop");
  const cameras = fills.filter((item) => item.kind === "camera");

  return (
    <section className="cd-scene-review" data-testid="cd-scene-review">
      <div className="cd-scene-review__head">
        <h4>CD Scene Review</h4>
        <button
          type="button"
          className="ui-btn ui-btn--primary"
          data-testid="cd-scene-review-run"
          disabled={busy || !mapId}
          onClick={() => void runReview()}
        >
          {busy ? "Reviewing…" : "Review this scene"}
        </button>
      </div>
      <p className="cd-scene-review__hint">
        Co-Director looks at the place and suggests who and what to put on the map. You accept. Slots stay.
      </p>
      {draft?.geometryStatus === "unavailable" ? (
        <p className="cd-scene-review__warn" data-testid="cd-scene-review-geometry-unavailable">
          {draft.geometryReason || "Automatic boxes are unavailable. You can still place people yourself."}
        </p>
      ) : null}
      {draft?.canonAvailability === "unavailable" && draft.canonUnavailableReason ? (
        <p className="cd-scene-review__warn">{draft.canonUnavailableReason}</p>
      ) : null}
      {draft ? (
        <div className="cd-scene-review__body" data-testid="cd-scene-review-draft">
          {characters.length ? (
            <div>
              <p className="cd-scene-review__group">People</p>
              {characters.map((fill) => (
                <label key={fill.id} className="cd-scene-review__row">
                  <input
                    type="checkbox"
                    checked={!!selected[fill.id]}
                    onChange={(e) => setSelected((cur) => ({ ...cur, [fill.id]: e.target.checked }))}
                    data-testid={`cd-scene-review-fill-${fill.id}`}
                  />
                  <span>
                    {fill.label} {fill.miniPrompt ? `— ${fill.miniPrompt}` : ""}
                  </span>
                  <button type="button" className="spatial-map__slot-action" onClick={() => void reject(fill)}>
                    Skip
                  </button>
                </label>
              ))}
            </div>
          ) : null}
          {props.length ? (
            <div>
              <p className="cd-scene-review__group">Important things</p>
              {props.map((fill) => (
                <label key={fill.id} className="cd-scene-review__row">
                  <input
                    type="checkbox"
                    checked={!!selected[fill.id]}
                    onChange={(e) => setSelected((cur) => ({ ...cur, [fill.id]: e.target.checked }))}
                  />
                  <span>{fill.label}</span>
                  <button type="button" className="spatial-map__slot-action" onClick={() => void reject(fill)}>
                    Skip
                  </button>
                </label>
              ))}
            </div>
          ) : null}
          {cameras.length ? (
            <div>
              <p className="cd-scene-review__group">Camera</p>
              {cameras.map((fill) => (
                <label key={fill.id} className="cd-scene-review__row">
                  <input
                    type="checkbox"
                    checked={!!selected[fill.id]}
                    onChange={(e) => setSelected((cur) => ({ ...cur, [fill.id]: e.target.checked }))}
                  />
                  <span>{fill.label}</span>
                </label>
              ))}
            </div>
          ) : null}
          {draft.relationships?.length ? (
            <p className="cd-scene-review__meta" data-testid="cd-scene-review-relationships">
              {draft.relationships
                .slice(0, 6)
                .map((rel) => `${rel.subjectLabel} ${String(rel.relation || "").replace(/_/g, " ").toLowerCase()} ${rel.objectLabel}`)
                .join(" · ")}
            </p>
          ) : null}
          {draft.unusedDetections?.length ? (
            <p className="cd-scene-review__meta" data-testid="cd-scene-review-unused">
              Also noticed, not placed: {draft.unusedDetections.slice(0, 8).map((item) => item.label).filter(Boolean).join(", ")}
            </p>
          ) : null}
          <button
            type="button"
            className="ui-btn ui-btn--primary"
            data-testid="cd-scene-review-accept"
            disabled={busy}
            onClick={() => void accept()}
          >
            Place selected on the map
          </button>
        </div>
      ) : null}
      {message ? (
        <p className="cd-scene-review__message" data-testid="cd-scene-review-message">
          {message}
          {canRetry ? (
            <>
              {" "}
              <button type="button" className="spatial-map__slot-action" data-testid="cd-scene-review-retry" onClick={() => void runReview()}>
                Retry
              </button>
            </>
          ) : null}
        </p>
      ) : null}
    </section>
  );
}
