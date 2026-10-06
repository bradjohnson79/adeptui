import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import { CharacterGenerationProgress } from "./CharacterGenerationProgress";
import { characterMediaUrl } from "./characterMediaUrl";
import {
  openCharacterSheetInImageGenerator,
  openCharacterSheetInLibrary,
  type GoTab,
} from "./characterSheetDestinations";
import "./characterV2.css";

type ViewName = "front" | "closeup";
type AngleName = "side" | "three_quarter" | "back";

type ViewSlot = {
  status?: string;
  assetId?: string | null;
  assetUrl?: string | null;
  approved?: boolean;
  source?: "uploaded" | "generated" | string | null;
  error?: string | null;
  promptId?: string | null;
  progress?: { percent?: number | null; stage?: string; label?: string; source?: string };
};

type V2State = {
  phase?: string;
  atTag?: string;
  productionReady?: boolean;
  jsonRevision?: number;
  sheetAssetId?: string | null;
  sheet?: {
    status?: string;
    assetId?: string | null;
    assetUrl?: string | null;
    progress?: { percent?: number | null; stage?: string; label?: string };
  };
  visualLock?: { status?: string; error?: string | null };
  views?: Record<string, ViewSlot>;
  multiView?: {
    status?: string;
    engine?: string;
    error?: string | null;
    angles?: Record<string, ViewSlot>;
  };
  sheetGate?: {
    ready?: boolean;
    missing?: string[];
    nextAction?: string;
    approvedFrontAssetId?: string | null;
    approvedSideAssetId?: string | null;
    approvedThreeQuarterAssetId?: string | null;
    approvedBackAssetId?: string | null;
  };
  engine?: { available?: boolean; status?: string; creatorMessage?: string; code?: string };
};

type GeneratorRow = {
  id?: string;
  label?: string;
  display?: string;
};

type Props = {
  projectId: string;
  characterId: string;
  mode: "express" | "standard";
  saved: boolean;
  editable?: boolean;
  frontEpoch?: number;
  onGoTab?: GoTab;
};

const ANGLES: { name: AngleName; label: string }[] = [
  { name: "side", label: "Side" },
  { name: "three_quarter", label: "3/4" },
  { name: "back", label: "Back" },
];

function slotImage(slot?: ViewSlot): string {
  return characterMediaUrl(slot?.assetUrl);
}

function visionLockHint(error?: string | null): string {
  const raw = String(error || "").trim();
  if (/not authorized to use this model/i.test(raw)) {
    return "Co-Director Vision cannot use the current studio key with this reading model.";
  }
  if (raw && raw !== "vlm_error") return raw;
  return "";
}

function anglesRuntimeHint(message?: string | null): string {
  const raw = String(message || "").trim();
  if (/preparing qwen/i.test(raw)) return "Preparing Qwen Image Edit…";
  if (/port conflict|another image program/i.test(raw)) {
    return "Another image program is using the local picture engine. Adept will not take it over.";
  }
  if (/object_info|winerror|connection refused|urlopen|actively refused|comfy/i.test(raw)) {
    return "The local image runtime is offline. Pictures already made stay as they are.";
  }
  return raw;
}

export function CharacterV2Studio({ projectId, characterId, mode, saved, editable = true, frontEpoch = 0, onGoTab }: Props) {
  const [state, setState] = useState<V2State | null>(null);
  const [busy, setBusy] = useState("");
  const [sheetTick, setSheetTick] = useState(0);
  const [error, setError] = useState("");
  const [angleErrors, setAngleErrors] = useState<Partial<Record<AngleName, string>>>({});
  const [uploadOpen, setUploadOpen] = useState(false);
  const [family, setFamily] = useState("auto");
  const [generators, setGenerators] = useState<GeneratorRow[]>([]);
  const [hasReference, setHasReference] = useState(false);
  const pollRef = useRef<number | null>(null);
  const fileRefs = useRef<Partial<Record<AngleName, HTMLInputElement | null>>>({});

  const refresh = useCallback(async () => {
    if (!saved || !editable) return;
    const next = (await api.getCharacterCreatorV2(projectId, characterId)) as V2State;
    setState(next);
    return next;
  }, [projectId, characterId, saved, editable, frontEpoch]);

  useEffect(() => {
    void refresh().catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [refresh]);

  useEffect(() => {
    if (!saved) return;
    if (!editable) return;
    void api
      .listCharacterCreatorGenerators(projectId, characterId)
      .then((inv) => {
        const rows = Array.isArray((inv as { generators?: GeneratorRow[] }).generators)
          ? ((inv as { generators?: GeneratorRow[] }).generators as GeneratorRow[])
          : [];
        setGenerators(rows.filter((row) => !/wonder3d|krea/i.test(String(row.label || row.id || ""))));
        setHasReference(Boolean((inv as { hasReference?: boolean }).hasReference));
      })
      .catch(() => undefined);
  }, [projectId, characterId, saved, editable, frontEpoch, state?.views?.front?.assetId]);

  const views = state?.views || {};
  const angles = state?.multiView?.angles || {};
  const liveStatuses = ["generating", "queued", "running", "starting"];
  const angleLive = Object.values(angles).some((v) => liveStatuses.includes(String(v?.status || "")));
  const generating = ["FRONT_GENERATING", "CLOSEUP_GENERATING", "VISION_FRONT", "ANGLES_GENERATING"].includes(
    String(state?.phase || ""),
  );

  useEffect(() => {
    const live = generating || angleLive || liveStatuses.includes(String(views.front?.status || ""));
    if (!live) {
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
  }, [generating, angleLive, views.front?.status, refresh]);

  useEffect(() => {
    if (busy !== "sheet") {
      setSheetTick(0);
      return;
    }
    setSheetTick(8);
    const timer = window.setInterval(() => {
      setSheetTick((prev) => (prev >= 90 ? 90 : prev + 8));
    }, 180);
    return () => window.clearInterval(timer);
  }, [busy]);

  const run = async (label: string, fn: () => Promise<unknown>) => {
    setBusy(label);
    if (label === "sheet") setSheetTick(8);
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

  if (!editable) {
    return (
      <p className="cc-v2__hint" data-testid="cc-v2-ownership">
        Global characters can only be edited from the project that created them.
      </p>
    );
  }

  const lock = state?.visualLock?.status || "none";
  const frontApproved = Boolean(views.front?.approved && String(views.front?.assetId || "").trim());
  const frontOk = Boolean(frontApproved && lock === "ok");
  const anglesApproved = ANGLES.every((row) => Boolean(angles[row.name]?.approved && angles[row.name]?.assetId));
  const anglesStage = !state?.engine
    ? "Checking whether Character Angles are ready…"
    : !frontApproved
      ? "Approve Front before making Side, 3/4, and Back."
      : anglesApproved
        ? "Side, 3/4, and Back are ready."
        : lock === "failed"
          ? "You can upload Side, 3/4, and Back. Generate Character Angles stays unavailable until Co-Director can read the Front."
          : !frontOk
            ? "You can upload Side, 3/4, and Back. Generate Character Angles uses the approved Front after Co-Director reads it."
        : state.engine.available === false
          ? anglesRuntimeHint(state.engine.creatorMessage) || "Character Angles need the local image runtime ready."
          : "Ready to make Side, 3/4, and Back from the approved Front, or upload your own.";
  const sheetGate = state?.sheetGate || { ready: false, missing: [] };
  const sheetReady = Boolean(
    sheetGate.ready &&
      sheetGate.approvedFrontAssetId &&
      sheetGate.approvedSideAssetId &&
      sheetGate.approvedThreeQuarterAssetId &&
      sheetGate.approvedBackAssetId,
  );
  const sheetStale = String(state?.sheet?.status || "") === "stale";
  const sheetLabel = state?.sheet?.assetUrl && sheetStale ? "Rebuild Character Sheet" : "Save and Create Character Sheet";
  const frontAsset = String(views.front?.assetId || "").trim();
  const referenceSignature = frontAsset || (hasReference ? "reference" : "");
  const viewOpAvailable = (view: string) => view === "front" || (view === "closeup" && frontOk);

  const frontHint = hasReference || frontAsset
    ? "Front will be created from the reference picture"
    : "Front will be created from the Character Profile description";

  const jobActive = Boolean(busy) || generating || angleLive;

  const renderProgress = (view: string, slot?: ViewSlot, fallbackLabel?: string) => (
    <CharacterGenerationProgress
      view={view}
      status={slot?.status}
      progress={slot?.progress?.percent}
      stage={slot?.progress?.stage}
      label={slot?.progress?.label || (slot?.status === "queued" ? "Waiting its turn…" : fallbackLabel)}
      error={slot?.error}
    />
  );

  const card = (view: ViewName, title: string, helper?: string) => {
    const slot = views[view] || {};
    const img = slotImage(slot);
    const available = viewOpAvailable(view);
    return (
      <section className="cc-v2__card" data-testid={`cc-v2-card-${view}`}>
        <h3>{title}</h3>
        {helper ? <p className="cc-v2__hint">{helper}</p> : null}
        {img ? (
          <img className="cc-v2__img" data-testid={`cc-v2-img-${view}`} src={img} alt={title} />
        ) : (
          <div className="cc-v2__empty">No image yet</div>
        )}
        {renderProgress(view, slot)}
        {!available ? (
          <p className="cc-v2__hint" data-testid={`cc-v2-unavailable-${view}`}>
            Available after Front is approved.
          </p>
        ) : null}
        <div className="cc-v2__row">
          <button
            type="button"
            className="cc-v2__btn"
            disabled={!!busy || jobActive || !available}
            data-testid={`cc-v2-generate-${view}`}
            onClick={() =>
              void run(`create-${view}`, () =>
                api.generateCharacterViewV2(projectId, characterId, view, { family: family === "auto" ? undefined : family }),
              )
            }
          >
            {view === "front" ? "Create Front View" : "Create Close-up"}
          </button>
          <button
            type="button"
            className="cc-v2__btn cc-v2__btn--primary"
            disabled={!!busy || !img || Boolean(slot.approved)}
            data-testid={`cc-v2-approve-${view}`}
            onClick={() => void run(`approve-${view}`, () => api.approveCharacterViewV2(projectId, characterId, view))}
          >
            {slot.approved ? "Approved" : view === "front" ? "Approve Front" : "Approve Close-up"}
          </button>
        </div>
      </section>
    );
  };

  const uploadAngle = async (angle: AngleName, file: File | undefined) => {
    if (!file) return;
    setAngleErrors((prev) => ({ ...prev, [angle]: "" }));
    setBusy(`upload-${angle}`);
    setError("");
    try {
      await api.uploadCharacterAngle(projectId, characterId, angle, file);
      await refresh();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Upload failed";
      setAngleErrors((prev) => ({ ...prev, [angle]: message }));
    } finally {
      setBusy("");
    }
  };

  const angleCard = (angle: AngleName, label: string) => {
    const slot = angles[angle] || {};
    const img = slotImage(slot);
    const approved = Boolean(slot.approved);
    const uploaded = String(slot.source || "") === "uploaded";
    const cardError = angleErrors[angle] || (busy === `upload-${angle}` ? "" : slot.error);
    return (
      <section className="cc-v2__card" data-testid={`cc-v2-card-${angle}`}>
        <h3>{label}</h3>
        {img ? (
          <img className="cc-v2__img" data-testid={`cc-v2-img-${angle}`} src={img} alt={label} />
        ) : (
          <div className="cc-v2__empty">No image yet</div>
        )}
        {renderProgress(angle, slot, busy === `upload-${angle}` ? "Saving to Library…" : undefined)}
        {cardError ? (
          <p className="cc-v2__error" data-testid={`cc-v2-upload-error-${angle}`}>
            {cardError}
          </p>
        ) : null}
        <input
          ref={(el) => {
            fileRefs.current[angle] = el;
          }}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff"
          hidden
          data-testid={`cc-v2-upload-input-${angle}`}
          onChange={(event) => {
            const file = event.target.files?.[0];
            event.target.value = "";
            void uploadAngle(angle, file);
          }}
        />
        <div className="cc-v2__row">
          <button
            type="button"
            className="cc-v2__btn"
            disabled={!!busy}
            data-testid={`cc-v2-upload-${angle}`}
            onClick={() => fileRefs.current[angle]?.click()}
          >
            {img && uploaded ? "Replace Upload" : "Upload"}
          </button>
          <button
            type="button"
            className="cc-v2__btn cc-v2__btn--primary"
            disabled={!!busy || !img || approved}
            data-testid={`cc-v2-approve-${angle}`}
            onClick={() => void run(`approve-${angle}`, () => api.approveCharacterAngle(projectId, characterId, angle, true))}
          >
            {approved ? "Approved" : "Approve"}
          </button>
          <button
            type="button"
            className="cc-v2__btn"
            disabled={!!busy || jobActive || !frontOk || !state?.engine?.available}
            data-testid={`cc-v2-regen-${angle}`}
            onClick={() => void run(`regen-${angle}`, () => api.regenerateCharacterAngle(projectId, characterId, angle))}
          >
            Regenerate
          </button>
          {img ? (
            <button
              type="button"
              className="cc-v2__btn"
              disabled={!!busy}
              data-testid={`cc-v2-reject-${angle}`}
              onClick={() => {
                if (!window.confirm(`Remove this ${label} picture?`)) return;
                void run(`reject-${angle}`, () => api.approveCharacterAngle(projectId, characterId, angle, false));
              }}
            >
              Remove
            </button>
          ) : null}
        </div>
      </section>
    );
  };

  const sheetImg = characterMediaUrl(state?.sheet?.assetUrl);
  const sheetAssetId = String(state?.sheet?.assetId || state?.sheetAssetId || "").trim();

  return (
    <div className="cc-v2" data-testid="cc-v2-studio" data-mode={mode}>
      <p className="cc-v2__phase" data-testid="cc-v2-phase">{state?.phase || "DRAFT"}</p>
      {state?.productionReady ? (
        <p className="cc-v2__active" data-testid="cc-v2-tag">
          Character Active {state.atTag}
        </p>
      ) : null}
      {lock === "failed" ? (
        <div className="cc-v2__banner" data-testid="cc-v2-vision-failed">
          <p>Co-Director could not read the front view. Character Angles stay unavailable.</p>
          {visionLockHint(state?.visualLock?.error) ? (
            <p className="cc-v2__hint" data-testid="cc-v2-vision-error">
              {visionLockHint(state?.visualLock?.error)}
            </p>
          ) : null}
          <button type="button" className="cc-v2__btn" disabled={!!busy} data-testid="cc-v2-retry-vision" onClick={() => void run("vision", () => api.retryCharacterVisionV2(projectId, characterId))}>
            Retry Co-Director Vision
          </button>
        </div>
      ) : null}
      <label className="cc-v2__hint" htmlFor="cc-v2-generator-select">
        Front generator
        <span className="cc-v2__tip" title="This only makes the Front picture. Side, 3/4, and Back come from Character Angles."> (?)</span>
      </label>
      <select
        id="cc-v2-generator-select"
        className="cc-v2__select"
        data-testid="cc-v2-generator-select"
        value={family}
        onChange={(e) => setFamily(e.target.value)}
        disabled={!!busy}
      >
        <option value="auto">Auto</option>
        {generators.map((row) => (
          <option key={row.id} value={row.id}>
            {row.display || row.label || row.id}
          </option>
        ))}
      </select>
      {card("front", "Front view", frontHint)}
      <section className="cc-v2__card" data-testid="cc-v2-angles">
        <h3>Character Angles</h3>
        <p className="cc-v2__hint">
          Side, 3/4, and Back can be generated from the approved Front, or you can upload your own pictures.
        </p>
        {angleLive ? <p className="cc-v2__hint" data-testid="cc-v2-multiview-live">Character Angles are running…</p> : null}
        {!angleLive ? (
          <p
            className={
              !anglesApproved && (state?.engine?.available === false || lock === "failed")
                ? "cc-v2__error"
                : "cc-v2__hint"
            }
            data-testid="cc-v2-angles-stage"
          >
            {anglesStage}
          </p>
        ) : null}
        <div className="cc-v2__row">
          <button
            type="button"
            className="cc-v2__btn cc-v2__btn--primary"
            disabled={!!busy || jobActive || !frontOk || !state?.engine?.available}
            data-testid="cc-v2-generate-multiview"
            onClick={() => void run("angles", () => api.generateCharacterAngles(projectId, characterId))}
          >
            Generate Character Angles
          </button>
          <span className="cc-v2__tip" title="Uses the approved Front picture to make Side, 3/4, and Back."> (?)</span>
          <button
            type="button"
            className="cc-v2__btn"
            disabled={!!busy}
            data-testid="cc-v2-upload-angles"
            onClick={() => setUploadOpen((open) => !open)}
          >
            Upload Angles
          </button>
          <span className="cc-v2__tip" title="Add your own Side, 3/4, or Back picture. You do not have to upload all three."> (?)</span>
        </div>
        {uploadOpen ? (
          <div className="cc-v2__row" data-testid="cc-v2-upload-angles-panel">
            {ANGLES.map((row) => (
              <button
                key={`upload-panel-${row.name}`}
                type="button"
                className="cc-v2__btn"
                disabled={!!busy}
                data-testid={`cc-v2-upload-panel-${row.name}`}
                onClick={() => fileRefs.current[row.name]?.click()}
              >
                Upload {row.label}
              </button>
            ))}
          </div>
        ) : null}
        <div className="cc-v2__angles">
          {ANGLES.map((row) => (
            <Fragment key={row.name}>{angleCard(row.name, row.label)}</Fragment>
          ))}
        </div>
      </section>
      {mode === "standard" || frontOk
        ? card(
            "closeup",
            mode === "express" ? "Close-up — Optional" : "Close-up",
            "Close-up is optional. You do not need it to finish the character or create the Character Sheet.",
          )
        : null}
      <div className="cc-v2__sheet">
        <div className="cc-v2__row">
        <button
          type="button"
          className="cc-v2__btn cc-v2__btn--primary"
          disabled={!!busy || !sheetReady}
          data-testid="cc-v2-compose-sheet"
          onClick={() => void run("sheet", () => api.composeCharacterSheetV2(projectId, characterId))}
        >
          {sheetLabel}
        </button>
        {sheetImg ? (
          <button
            type="button"
            className="cc-v2__btn"
            disabled={!!busy || !sheetReady}
            data-testid="cc-v2-regen-sheet"
            onClick={() =>
              void run("sheet", () => api.composeCharacterSheetV2(projectId, characterId, { regenerate: true }))
            }
          >
            Regenerate
          </button>
        ) : null}
        </div>
        {!sheetReady ? (
          <p className="cc-v2__hint" data-testid="cc-v2-sheet-hint">
            {(sheetGate.missing || []).join(" · ") || "Approve Front"}
          </p>
        ) : (
          <p className="cc-v2__hint" data-testid="cc-v2-sheet-hint">
            {sheetStale
              ? "Uses the current approved Front, Side, 3/4, and Back."
              : sheetGate.nextAction || "Character Sheet ready to create."}
          </p>
        )}
        {sheetImg ? (
          <div className="cc-v2__sheet-result">
            <button
              type="button"
              className="cc-v2__sheet-open"
              data-testid="cc-v2-open-full-size"
              onClick={() => window.open(sheetImg, "_blank", "noopener,noreferrer")}
            >
              <img className="cc-v2__sheet-img" data-testid="cc-v2-img-sheet" src={sheetImg} alt="Character sheet" />
            </button>
            <button
              type="button"
              className="cc-v2__btn"
              data-testid="cc-v2-open-full-size-btn"
              onClick={() => window.open(sheetImg, "_blank", "noopener,noreferrer")}
            >
              Open Full Size
            </button>
            {onGoTab && sheetAssetId ? (
              <div className="cc-v2__row" data-testid="cc-v2-sheet-destinations">
                <button
                  type="button"
                  className="cc-v2__btn"
                  data-testid="cc-v2-open-library"
                  onClick={() => openCharacterSheetInLibrary(onGoTab, sheetAssetId)}
                >
                  Open in Library
                </button>
                <button
                  type="button"
                  className="cc-v2__btn cc-v2__btn--primary"
                  data-testid="cc-v2-use-imagegen"
                  onClick={() =>
                    openCharacterSheetInImageGenerator(onGoTab, { characterId, assetId: sheetAssetId })
                  }
                >
                  Use in Image Generator
                </button>
              </div>
            ) : null}
          </div>
        ) : null}
        <CharacterGenerationProgress
          view="sheet"
          status={busy === "sheet" ? "generating" : state?.sheet?.status}
          progress={busy === "sheet" ? sheetTick : state?.sheet?.progress?.percent ?? (sheetImg ? 100 : null)}
          stage={busy === "sheet" ? "composing" : state?.sheet?.progress?.stage}
          label={
            busy === "sheet"
              ? "Creating Character Sheet…"
              : state?.sheet?.progress?.label || (sheetImg ? "Character Sheet Ready" : undefined)
          }
        />
      </div>
      {error ? <p className="cc-v2__error">{error}</p> : null}
      <span hidden>{referenceSignature}</span>
    </div>
  );
}
