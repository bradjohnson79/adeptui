/**
 * PropAdvancedPanel — Express Advanced Prop (DETAILED SET B testids).
 * Wires primary generate/approve + per-angle Qwen Edit to prop-creator advanced APIs.
 * Shares prop-creator-name / PropEntity with Standard; does not rewrite Standard description.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../../api";
import { LibraryQuickPreviewModal, type LibraryQuickPreviewAsset } from "../../library/LibraryQuickPreviewModal";
import { useOpenCoDirector } from "..";
import { CharacterReferenceAssetPicker } from "../characters/CharacterReferenceAssetPicker";
import { propCreatorApi } from "./propCreatorApi";
import {
  ADDITIONAL_VIEWS_HINT,
  ADDITIONAL_VIEWS_TITLE,
  SHEET_COMPOSE_HINT_BLOCKED,
  SHEET_COMPOSE_HINT_READY,
  canComposeAdvancedSheet,
  canApprovePrimary,
  canApproveView,
  primaryPreviewIsPendingReplacement,
  validPrimaryCandidate,
  visiblePrimaryPreviewAssetId,
} from "./propApproval";
import { PropAssetPreview } from "./PropAssetPreview";
import {
  PROP_ADVANCED_ANGLE_KEYS,
  candidateIsFinished,
  displayProgressPercent,
  shouldShowPropProgress,
  surfacedJobProgress,
  type PropAdvancedType,
  type PropAngleKey,
  type PropAngleSlot,
  type PropEntity,
  promptCanonicalPropTag,
} from "./types";

const ADVANCED_TYPES: PropAdvancedType[] = ["spacecraft", "vehicle", "aircraft", "mech", "other"];
const ANGLES = PROP_ADVANCED_ANGLE_KEYS;

export type PropAdvancedPanelProps = {
  projectId: string;
  propId?: string;
  name?: string;
  tagDisplay?: string;
  initialProp?: PropEntity | null;
  onGoTab?: (tab: string, extra?: Record<string, string>) => void;
};

function errMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  if (err && typeof err === "object" && "detail" in err) {
    const d = (err as { detail?: unknown }).detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) return String((d as { message: unknown }).message);
  }
  return err != null ? String(err) : "Request failed.";
}

function primaryStatusLabel(prop: PropEntity | null, named: boolean): string {
  if (!prop) {
    return named
      ? "Upload or generate a Primary look"
      : "Name this Prop, then upload or generate Primary";
  }
  if ((prop.primary_approved_asset_id || "").trim()) {
    return canApprovePrimary(prop)
      ? "New Primary ready — approve to replace identity"
      : "Primary approved";
  }
  const phase = prop.primary_phase || "draft";
  if (phase === "generating") {
    const live = (prop.candidates || []).some((c) => !candidateIsFinished(c));
    return live ? "Generating primary…" : "Primary generating";
  }
  if (canApprovePrimary(prop) || phase === "review") return "Primary ready — approve to lock identity";
  if (phase === "approved") return "Primary approved";
  return "Primary not approved";
}

function primaryGenerating(prop: PropEntity | null, busy: boolean): boolean {
  if (!prop) return Boolean(busy);
  if ((prop.primary_approved_asset_id || "").trim()) return false;
  const cands = prop.candidates || [];
  if (shouldShowPropProgress({ generating: busy || prop.primary_phase === "generating", candidates: cands })) {
    const failedOnly =
      cands.length > 0 && cands.every((c) => candidateIsFinished(c)) && !cands.some((c) => c.status === "complete" && c.asset_id);
    if (failedOnly && prop.primary_phase !== "generating") return false;
    return prop.primary_phase === "generating" || busy || cands.some((c) => !candidateIsFinished(c));
  }
  return false;
}

function primaryProgressPercent(prop: PropEntity | null): number | null {
  if (!prop) return null;
  const cands = prop.candidates || [];
  const job = surfacedJobProgress(cands);
  if (job == null) {
    // No invented smooth % - only show numeric % when Job.progress hydrates.
    return null;
  }
  const pct = displayProgressPercent(cands, Math.max(1, cands.length));
  // Never show 100% before a candidate asset is registered.
  const hasAsset = cands.some((c) => Boolean((c.asset_id || "").trim()) && c.status === "complete");
  if (!hasAsset && pct >= 100) return 99;
  return pct;
}

function primaryStageLabel(prop: PropEntity | null, pct: number | null): string {
  const liveCands = (prop?.candidates || []).filter((c) => !candidateIsFinished(c));
  const live = liveCands[0] || (prop?.candidates || [])[0];
  const msg = String(live?.job_message || "").trim();
  const stage = String(live?.job_stage || "").trim().toLowerCase();
  if (msg) {
    if (pct != null && /sampl/i.test(msg) && !/%/.test(msg)) return `${msg} · ${pct}%`;
    return msg;
  }
  if (stage.includes("load")) return pct != null ? `Loading models · ${pct}%` : "Loading models…";
  if (stage.includes("sampl")) return pct != null ? `Sampling · ${pct}%` : "Sampling…";
  if (stage.includes("complete") || stage.includes("done")) return "Finishing…";
  if (live?.job_id && !String(live.job_id).startsWith("failed")) {
    return pct != null ? `Primary look ${pct}%` : "Queued…";
  }
  return "Queued…";
}

export function PropAdvancedPanel({ projectId, propId, name, tagDisplay, initialProp, onGoTab }: PropAdvancedPanelProps) {
  const [prop, setProp] = useState<PropEntity | null>(initialProp ?? null);
  const [advancedType, setAdvancedType] = useState<PropAdvancedType>("spacecraft");
  const [primaryPrompt, setPrimaryPrompt] = useState("");
  const [busy, setBusy] = useState(false);
  const [anglePending, setAnglePending] = useState<{
    angle: PropAngleKey;
    kind: "generate" | "regenerate" | "approve" | "upload";
  } | null>(null);
  const [angleErrors, setAngleErrors] = useState<Partial<Record<PropAngleKey | "primary", string>>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [previewAsset, setPreviewAsset] = useState<LibraryQuickPreviewAsset | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const saveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const bootRef = useRef<string>("");
  const fileRef = useRef<HTMLInputElement>(null);
  const primaryFileRef = useRef<HTMLInputElement>(null);
  const angleFileRefs = useRef<Partial<Record<PropAngleKey, HTMLInputElement | null>>>({});
  const openCoDirector = useOpenCoDirector();

  const stopPoll = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const applyLocal = useCallback((next: PropEntity) => {
    setProp(next);
    const at = (next.advanced_type || "spacecraft") as PropAdvancedType;
    setAdvancedType(ADVANCED_TYPES.includes(at) ? at : "spacecraft");
    setPrimaryPrompt(next.primary_prompt || "");
  }, []);

  useEffect(() => {
    if (!initialProp) return;
    setProp((prev) => {
      if (!prev || prev.id !== initialProp.id) return initialProp;
      return prev;
    });
  }, [initialProp]);

  const startPoll = useCallback(
    (id: string) => {
      stopPoll();
      const tick = () => {
        void propCreatorApi
          .get(projectId, id)
          .then((res) => {
            applyLocal(res.prop);
            const candLive = (res.prop.candidates || []).some((c) => !candidateIsFinished(c));
            const angles = res.prop.angles || {};
            const angleLive = ANGLES.some((a) => {
              const slot = angles[a] as PropAngleSlot | undefined;
              const st = String(slot?.status || "");
              return st === "queued" || st === "generating";
            });
            const sheetLive = res.prop.advanced_sheet_status === "generating";
            if (!candLive && !angleLive && !sheetLive) stopPoll();
          })
          .catch(() => undefined);
      };
      tick();
      pollRef.current = setInterval(tick, 1000);
    },
    [applyLocal, projectId, stopPoll],
  );

  const ensureAdvanced = useCallback(async (): Promise<PropEntity | null> => {
    const label = (name || prop?.display_label || "").trim();
    if (!label) {
      setError("Name the Prop (shared Name field) before Advanced actions.");
      return null;
    }
    const existingId = propId || prop?.id;
    const res = await propCreatorApi.upsert(projectId, {
      prop_id: existingId,
      name: label,
      // Preserve Standard fields — do not race/clear description or style.
      visual_style: prop?.visual_style || undefined,
      description: prop?.description || undefined,
      mode: "advanced",
      advanced_type: advancedType,
      primary_prompt: primaryPrompt,
      hero_optional: prop?.hero_optional ?? true,
    });
    applyLocal(res.prop);
    return res.prop;
  }, [advancedType, applyLocal, name, primaryPrompt, projectId, prop, propId]);

  // Hydrate + ensure mode=advanced when tab has a named prop.
  useEffect(() => {
    const key = `${projectId}::${propId || ""}::${(name || "").trim()}`;
    if (bootRef.current === key) return;
    bootRef.current = key;
    let cancelled = false;
    (async () => {
      setError(null);
      try {
        if (propId) {
          const res = await propCreatorApi.get(projectId, propId);
          if (cancelled) return;
          applyLocal(res.prop);
          if (res.prop.mode !== "advanced") {
            const label = (name || res.prop.display_label || "").trim();
            if (label) {
              const up = await propCreatorApi.upsert(projectId, {
                prop_id: res.prop.id,
                name: label,
                visual_style: res.prop.visual_style || undefined,
                description: res.prop.description || undefined,
                mode: "advanced",
                advanced_type: (res.prop.advanced_type as PropAdvancedType) || "spacecraft",
                primary_prompt: res.prop.primary_prompt || "",
                hero_optional: res.prop.hero_optional ?? true,
              });
              if (!cancelled) applyLocal(up.prop);
            }
          } else {
            const candLive = (res.prop.candidates || []).some((c) => !candidateIsFinished(c));
            const angles = res.prop.angles || {};
            const angleLive = ANGLES.some((a) => {
              const st = String((angles[a] as PropAngleSlot | undefined)?.status || "");
              return st === "queued" || st === "generating";
            });
            const sheetLive = res.prop.advanced_sheet_status === "generating";
            if (candLive || angleLive || sheetLive) startPoll(res.prop.id);
          }
        } else if (initialProp) {
          if (!cancelled) applyLocal(initialProp);
        }
        // Do not auto-create a new Prop when only a name is typed — Upload /
        // Generate call ensureAdvanced. Avoids duplicate named props.
      } catch (err) {
        if (!cancelled) setError(errMessage(err));
      }
    })();
    return () => {
      cancelled = true;
      // React Strict Mode remounts effects: allow the second run to hydrate.
      if (bootRef.current === key) bootRef.current = "";
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, propId, name]);

  useEffect(() => () => stopPoll(), [stopPoll]);

  const persistMeta = useCallback(
    async (nextType: PropAdvancedType, nextPrompt: string) => {
      const label = (name || prop?.display_label || "").trim();
      const id = propId || prop?.id;
      if (!label || !id) return;
      try {
        const res = await propCreatorApi.upsert(projectId, {
          prop_id: id,
          name: label,
          visual_style: prop?.visual_style || undefined,
          description: prop?.description || undefined,
          mode: "advanced",
          advanced_type: nextType,
          primary_prompt: nextPrompt,
          hero_optional: prop?.hero_optional ?? true,
        });
        applyLocal(res.prop);
      } catch (err) {
        setError(errMessage(err));
      }
    },
    [applyLocal, name, prop, propId, projectId],
  );

  const schedulePersist = useCallback(
    (nextType: PropAdvancedType, nextPrompt: string) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      saveTimerRef.current = setTimeout(() => {
        void persistMeta(nextType, nextPrompt);
      }, 600);
    },
    [persistMeta],
  );

  const setReference = useCallback(
    async (assetId: string | null) => {
      const label = (name || prop?.display_label || "").trim();
      if (!label) {
        setError("Name the Prop (shared Name field) before Advanced actions.");
        setBusy(false);
        return;
      }
      setBusy(true);
      setError(null);
      try {
        const existingId = propId || prop?.id;
        const res = await propCreatorApi.upsert(projectId, {
          prop_id: existingId,
          name: label,
          visual_style: prop?.visual_style || undefined,
          description: prop?.description || undefined,
          mode: "advanced",
          advanced_type: advancedType,
          primary_prompt: primaryPrompt,
          hero_optional: prop?.hero_optional ?? true,
          reference_asset_id: assetId,
          clear_reference: !assetId,
        });
        applyLocal(res.prop);
        setNotice(assetId ? "Reference attached." : "Reference cleared.");
      } catch (err) {
        setError(errMessage(err));
      } finally {
        setBusy(false);
      }
    },
    [advancedType, applyLocal, name, primaryPrompt, projectId, prop, propId],
  );

  const askCoDirectorForReference = useCallback(() => {
    const label = (name || prop?.display_label || "").trim() || "this Advanced Prop";
    const prompt =
      `Please create a Prop Reference for ${label} using Prop Creator. ` +
      `Prefer a clear single-view look sheet suitable as Primary Design Look for this Advanced Prop (${advancedType}). ` +
      `Use the current primary design prompt and any existing reference as identity.`;
    openCoDirector(prompt, { autoSend: false });
  }, [advancedType, name, openCoDirector, prop?.display_label]);

  const onTypeChange = (value: PropAdvancedType) => {
    setAdvancedType(value);
    schedulePersist(value, primaryPrompt);
  };

  const onPromptChange = (value: string) => {
    setPrimaryPrompt(value);
    schedulePersist(advancedType, value);
  };

  const onPromptBlur = () => {
    if (saveTimerRef.current) {
      clearTimeout(saveTimerRef.current);
      saveTimerRef.current = null;
    }
    void persistMeta(advancedType, primaryPrompt);
  };

  const generatePrimary = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const current = await ensureAdvanced();
      if (!current) return;
      if (!(primaryPrompt || current.primary_prompt || "").trim()) {
        setError("Primary design prompt is required.");
        return;
      }
      const res = await propCreatorApi.advancedPrimaryGenerate(projectId, current.id, {
        local_enabled: true,
        api_enabled: false,
        candidate_count: 4,
      });
      applyLocal(res.prop);
      startPoll(res.prop.id);
      setNotice("Generating primary looks.");
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const approvePrimary = async () => {
    if (!prop?.id) return;
    const ready = validPrimaryCandidate(prop);
    if (!ready?.id && !ready?.asset_id) {
      setError("Upload or generate a Primary look first.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const res = await propCreatorApi.advancedPrimaryApprove(projectId, prop.id, {
        candidate_id: ready?.id || "",
        asset_id: ready?.asset_id || "",
      });
      applyLocal(res.prop);
      setNotice("Primary approved. Additional views are optional.");
    } catch (err) {
      setError(errMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const uploadPrimary = async (file: File | undefined) => {
    if (!file) return;
    setBusy(true);
    setError(null);
    setAngleErrors((prev) => ({ ...prev, primary: "" }));
    try {
      const current = await ensureAdvanced();
      if (!current) return;
      const res = await propCreatorApi.advancedPrimaryUpload(projectId, current.id, file);
      applyLocal(res.prop);
      setNotice("Primary upload saved to Library. Approve Primary to lock identity.");
    } catch (err) {
      const message = errMessage(err);
      setAngleErrors((prev) => ({ ...prev, primary: message }));
      setError(message);
    } finally {
      setBusy(false);
    }
  };

  const uploadAngle = async (angle: PropAngleKey, file: File | undefined) => {
    if (!file) return;
    setAngleErrors((prev) => ({ ...prev, [angle]: "" }));
    setError(null);
    setAnglePending({ angle, kind: "upload" });
    try {
      const current = await ensureAdvanced();
      if (!current?.id) {
        setAngleErrors((prev) => ({ ...prev, [angle]: "Name the Prop first." }));
        return;
      }
      const res = await propCreatorApi.advancedAngleUpload(projectId, current.id, angle, file);
      applyLocal(res.prop);
      setNotice(`${angle} upload saved to Library. Approve to make it the canonical view.`);
    } catch (err) {
      const message = errMessage(err);
      setAngleErrors((prev) => ({ ...prev, [angle]: message }));
    } finally {
      setAnglePending(null);
    }
  };

  const previewPrimary = () => {
    const aid =
      visiblePrimaryPreviewAssetId(prop) ||
      prop?.candidates?.find((c) => c.status === "complete" && c.asset_id)?.asset_id ||
      prop?.candidates?.find((c) => c.asset_id)?.asset_id;
    if (!aid) {
      setNotice("No primary image to preview yet.");
      return;
    }
    window.open(api.assetUrl(aid), "_blank", "noopener,noreferrer");
  };

  const runAngle = async (angle: PropAngleKey, kind: "generate" | "regenerate" | "approve" | "remove") => {
    if (!prop?.id) return;
    setError(null);
    setNotice("");
    // Immediate busy label for Generate/Regenerate; optimistic ✓ for Approve.
    setAnglePending({ angle, kind: kind === "remove" ? "approve" : kind });
    if (kind === "approve") {
      const angles = { ...(prop.angles || {}) } as Record<string, PropAngleSlot>;
      const prev = (angles[angle] || {}) as PropAngleSlot;
      angles[angle] = { ...prev, approved: true, status: "approved" };
      applyLocal({ ...prop, angles });
    }
    try {
      const res =
        kind === "generate"
          ? await propCreatorApi.advancedAngleGenerate(projectId, prop.id, angle)
          : kind === "regenerate"
            ? await propCreatorApi.advancedAngleRegenerate(projectId, prop.id, angle)
            : await propCreatorApi.advancedAngleApprove(projectId, prop.id, angle, kind !== "remove");
      applyLocal(res.prop);
      setAnglePending(null);
      if (kind === "approve") {
        setNotice(`${angle} approved.`);
      } else if (kind === "remove") {
        setNotice(`${angle} removed from this Prop.`);
      } else {
        startPoll(res.prop.id);
        // Keep Generating... via slot.status queued/generating (angleBusy).
      }
    } catch (err) {
      setAnglePending(null);
      setError(errMessage(err));
      // Re-sync after failed optimistic approve.
      if ((kind === "approve" || kind === "remove") && prop.id) {
        try {
          const fresh = await propCreatorApi.get(projectId, prop.id);
          applyLocal(fresh.prop);
        } catch {
          /* ignore */
        }
      }
    }
  };



  const sheetBusy = prop?.advanced_sheet_status === "generating";
  const sheetProgress =
    typeof prop?.advanced_sheet_progress === "number" && Number.isFinite(prop.advanced_sheet_progress)
      ? Math.max(0, Math.min(100, Math.round(prop.advanced_sheet_progress * 100)))
      : null;

  const runSheet = async (action: "generate" | "cancel") => {
    if (!projectId || !prop?.id) return;
    setError("");
    setNotice("");
    // Cancel must stay clickable while sheet work runs — do not hold `busy` across compose.
    if (action === "cancel") {
      try {
        const res = await propCreatorApi.advancedReferenceSheetCancel(projectId, prop.id);
        applyLocal(res.prop);
        setNotice("Sheet generation cancelled.");
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
      }
      return;
    }
    // Generate returns immediately (async BE job); poll hydrates advanced_sheet_progress.
    try {
      const res = await propCreatorApi.advancedReferenceSheetGenerate(projectId, prop.id);
      applyLocal(res.prop);
      startPoll(res.prop.id);
      setNotice(
        res.prop.advanced_sheet_status === "complete"
          ? "Advanced Prop Reference Sheet ready."
          : "Sheet generation started.",
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const primaryApproved = Boolean((prop?.primary_approved_asset_id || "").trim());
  const approvePrimaryEnabled = canApprovePrimary(prop);
  const sheetReady = canComposeAdvancedSheet(prop);
  const showPrimaryProgress = primaryGenerating(prop, busy);
  const primaryPct = showPrimaryProgress ? primaryProgressPercent(prop) : null;
  const primaryBarPct = primaryPct == null ? 0 : primaryPct;

  const refId = (prop?.reference_asset_id || "").trim();
  const named = Boolean((name || prop?.display_label || "").trim());
  const refControlsDisabled = busy || !named;
  const tag =
    tagDisplay?.trim() ||
    promptCanonicalPropTag(prop, name) ||
    "%Name";

  const primaryPreviewId = visiblePrimaryPreviewAssetId(prop) || null;
  const primaryPreviewPending = primaryPreviewIsPendingReplacement(prop);

  return (
    <div className="prop-advanced-panel" data-testid="prop-advanced-panel">
      <label className="prop-creator-core__field">
        <span className="prop-creator-core__label">Advanced type</span>
        <select
          data-testid="prop-advanced-type"
          value={advancedType}
          disabled={busy}
          onChange={(e) => onTypeChange(e.target.value as PropAdvancedType)}
        >
          {ADVANCED_TYPES.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      </label>

      <div className="character-core__reference" data-testid="prop-advanced-reference">
        <span className="prop-creator-core__label">Reference</span>
        {refId ? (
          <>
            <div className="character-core__reference-preview">
              <img
                src={api.assetUrl(refId)}
                alt="Prop reference"
                data-testid="prop-advanced-ref-thumb"
              />
            </div>
            <p className="character-core__hint" data-testid="prop-advanced-ref-status">
              Reference: Primary Design Look locked
            </p>
          </>
        ) : null}
        <div className="character-core__reference-actions">
          <button
            type="button"
            className="character-core__button"
            data-testid="prop-advanced-ref-upload"
            disabled={refControlsDisabled}
            onClick={() => fileRef.current?.click()}
          >
            Upload
          </button>
          <button
            type="button"
            className="character-core__button"
            data-testid="prop-advanced-ref-library"
            disabled={refControlsDisabled}
            onClick={() => setPickerOpen(true)}
          >
            Add from Library
          </button>
          <button
            type="button"
            className="character-core__button"
            data-testid="prop-advanced-ref-cd"
            disabled={refControlsDisabled}
            onClick={askCoDirectorForReference}
          >
            Ask Co-Director to create a Prop Reference
          </button>
          {refId ? (
            <button
              type="button"
              className="character-core__button"
              data-testid="prop-advanced-ref-remove"
              disabled={refControlsDisabled}
              onClick={() => void setReference(null)}
            >
              Remove
            </button>
          ) : null}
        </div>
        <input
          ref={fileRef}
          type="file"
          accept="image/*"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (!file) return;
            setBusy(true);
            setError(null);
            void api
              .uploadAsset(projectId, file, "prop_reference", "image")
              .then((asset) => setReference(asset.id))
              .catch((err) => {
                setError(errMessage(err));
                setBusy(false);
              });
          }}
        />
        <CharacterReferenceAssetPicker
          projectId={projectId}
          currentAssetId={refId || null}
          open={pickerOpen}
          busy={busy}
          onCancel={() => setPickerOpen(false)}
          onConfirm={(asset) => {
            setPickerOpen(false);
            void setReference(asset.id);
          }}
        />
      </div>

      <label className="prop-creator-core__field">
        <span className="prop-creator-core__label">Primary design prompt</span>
        <textarea
          className="prop-creator-core__prompt"
          data-testid="prop-advanced-primary-prompt"
          value={primaryPrompt}
          disabled={busy}
          onChange={(e) => onPromptChange(e.target.value)}
          onBlur={onPromptBlur}
          placeholder="Primary design prompt for this Advanced Prop"
        />
      </label>

      <p className="prop-creator-core__label" data-testid="prop-advanced-primary-required-label">
        Primary look (required)
      </p>
      <div className="prop-creator-core__row prop-advanced-panel__primary-actions">
        <button
          type="button"
          className="character-core__button primary"
          data-testid="prop-advanced-primary-generate"
          disabled={busy || !(name || prop?.display_label || "").trim()}
          onClick={() => void generatePrimary()}
        >
          Generate Primary
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="prop-advanced-primary-upload"
          disabled={busy || !(name || prop?.display_label || "").trim()}
          onClick={() => primaryFileRef.current?.click()}
        >
          Upload Primary
        </button>
        <input
          ref={primaryFileRef}
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff"
          hidden
          data-testid="prop-advanced-primary-upload-input"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            void uploadPrimary(file);
          }}
        />
        <button
          type="button"
          className="ghost"
          data-testid="prop-advanced-primary-preview"
          disabled={busy || !primaryPreviewId}
          onClick={previewPrimary}
        >
          Preview
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="prop-advanced-primary-approve"
          disabled={busy || !approvePrimaryEnabled}
          onClick={() => void approvePrimary()}
        >
          Approve Primary
        </button>
        <span className="muted" data-testid="prop-advanced-primary-status">
          {primaryStatusLabel(prop, named)}
        </span>
      </div>

      {showPrimaryProgress ? (
        <div className="character-core__progress" data-testid="prop-advanced-primary-progress">
          <div className="character-core__progress-head">
            <span className="character-core__progress-title">Generating Primary</span>
            {primaryPct != null ? (
              <span className="character-core__progress-pct" data-testid="prop-advanced-primary-progress-pct">
                {primaryPct}%
              </span>
            ) : null}
          </div>
          {primaryPct != null ? (
            <div
              className="character-core__progress-track"
              role="progressbar"
              aria-valuenow={primaryBarPct}
              aria-valuemin={0}
              aria-valuemax={100}
              aria-label="Primary generation progress"
              data-testid="prop-advanced-primary-progress-track"
            >
              <div
                className="character-core__progress-fill"
                data-testid="prop-advanced-primary-progress-fill"
                style={{ width: `${primaryBarPct}%` }}
              />
            </div>
          ) : (
            <div className="character-core__progress-track" data-testid="prop-advanced-primary-progress-waiting" aria-live="polite" />
          )}
          <p className="character-core__progress-label" data-testid="prop-advanced-primary-progress-label">
            {primaryStageLabel(prop, primaryPct)}
          </p>
        </div>
      ) : null}

      {primaryPreviewId ? (
        <div className="prop-advanced-panel__primary-preview" data-testid="prop-advanced-primary-preview-wrap">
          <PropAssetPreview
            assetId={primaryPreviewId}
            projectId={projectId}
            alt="Primary prop"
            className="prop-advanced-panel__primary-thumb"
            testId="prop-advanced-primary-image"
          />
          {primaryPreviewPending ? (
            <p className="muted" data-testid="prop-advanced-primary-preview-pending">
              Showing the new Primary candidate. Approve Primary to lock identity.
            </p>
          ) : null}
        </div>
      ) : null}

      <p className="prop-creator-core__label">
        Tag:{" "}
        <strong data-testid="prop-advanced-tag" className="prop-advanced-panel__tag">
          {tag}
        </strong>
      </p>

      {error ? (
        <p className="prop-creator-core__error" role="alert">
          {error}
        </p>
      ) : null}
      {notice ? <p className="muted">{notice}</p> : null}

      {angleErrors.primary ? (
        <p className="prop-creator-core__error" role="alert" data-testid="prop-advanced-primary-upload-error">
          {angleErrors.primary}
        </p>
      ) : null}

      <div className="prop-advanced-panel__angles-head">
        <p className="prop-creator-core__label" data-testid="prop-advanced-optional-views-title">
          {ADDITIONAL_VIEWS_TITLE}
        </p>
        <p className="muted" data-testid="prop-advanced-optional-views-hint">
          {ADDITIONAL_VIEWS_HINT}
        </p>
      </div>
      <div
        className="prop-advanced-panel__angles"
        data-testid="prop-advanced-angles"
      >
        {ANGLES.map((angle) => {
          const slot = (prop?.angles?.[angle] || null) as PropAngleSlot | null;
          const imgId = slot?.asset_id || null;
          const angleBusy = slot?.status === "queued" || slot?.status === "generating";
          const pendingThis = anglePending?.angle === angle;
          const generatingLabel =
            angleBusy || (pendingThis && (anglePending?.kind === "generate" || anglePending?.kind === "regenerate"));
          const approvePending = pendingThis && anglePending?.kind === "approve";
          const uploadPending = pendingThis && anglePending?.kind === "upload";
          const canApprove = canApproveView(slot, approvePending || uploadPending);
          const cardError = angleErrors[angle] || slot?.error || "";
          const sourceLabel = slot?.source === "uploaded" ? "Uploaded" : slot?.source === "generated" ? "Generated" : "";
          return (
            <div key={angle} className="prop-advanced-panel__angle" data-testid={`prop-advanced-angle-${angle}`}>
              <span className="prop-creator-core__label">
                {angle}
                {slot?.approved ? " [ok]" : ""}
                {angleBusy || uploadPending ? " …" : ""}
                {sourceLabel ? ` · ${sourceLabel}` : ""}
              </span>
              <div className="prop-advanced-panel__angle-img" data-testid={`prop-advanced-angle-${angle}-img`}>
                {imgId ? (
                  <PropAssetPreview
                    assetId={imgId}
                    projectId={projectId}
                    alt={`${angle} view`}
                    testId={`prop-advanced-angle-${angle}-image`}
                    unavailableLabel={`${angle} view unavailable`}
                  />
                ) : null}
              </div>
              {cardError ? (
                <p className="prop-creator-core__error" role="alert" data-testid={`prop-advanced-angle-${angle}-error`}>
                  {cardError}
                </p>
              ) : null}
              <input
                ref={(el) => {
                  angleFileRefs.current[angle] = el;
                }}
                type="file"
                accept="image/png,image/jpeg,image/webp,image/gif,image/bmp,image/tiff,.png,.jpg,.jpeg,.webp,.gif,.bmp,.tif,.tiff"
                hidden
                data-testid={`prop-advanced-angle-${angle}-upload-input`}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  event.target.value = "";
                  void uploadAngle(angle, file);
                }}
              />
              <div className="prop-advanced-panel__angle-actions">
                <button
                  type="button"
                  className="ghost"
                  data-testid={`prop-advanced-angle-${angle}-upload`}
                  disabled={busy || generatingLabel || approvePending || uploadPending || !(name || prop?.display_label || "").trim()}
                  onClick={() => angleFileRefs.current[angle]?.click()}
                >
                  {uploadPending ? "Saving…" : imgId && slot?.source === "uploaded" ? "Replace Upload" : "Upload"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  data-testid={`prop-advanced-angle-${angle}-generate`}
                  disabled={!primaryApproved || generatingLabel || approvePending || uploadPending}
                  aria-busy={generatingLabel || undefined}
                  onClick={() => void runAngle(angle, "generate")}
                >
                  {generatingLabel ? "Generating..." : "Generate"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  data-testid={`prop-advanced-angle-${angle}-regenerate`}
                  disabled={!primaryApproved || generatingLabel || approvePending || uploadPending}
                  aria-busy={generatingLabel || undefined}
                  onClick={() => void runAngle(angle, "regenerate")}
                >
                  {generatingLabel ? "Generating..." : "Regenerate"}
                </button>
                <button
                  type="button"
                  className="ghost"
                  data-testid={`prop-advanced-angle-${angle}-approve`}
                  disabled={!canApprove}
                  aria-pressed={Boolean(slot?.approved) || undefined}
                  onClick={() => void runAngle(angle, "approve")}
                >
                  {slot?.approved ? "Approved" : approvePending ? "Approving..." : "Approve"}
                </button>
                {imgId ? (
                  <button
                    type="button"
                    className="ghost"
                    data-testid={`prop-advanced-angle-${angle}-remove`}
                    disabled={busy || generatingLabel || approvePending || uploadPending}
                    onClick={() => void runAngle(angle, "remove")}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>

      <div className="prop-advanced-panel__sheet" data-testid="prop-advanced-reference-sheet">
        <button
          type="button"
          className="ghost"
          data-testid="prop-advanced-reference-sheet-generate"
          disabled={!sheetReady || sheetBusy}
          title={sheetReady ? SHEET_COMPOSE_HINT_READY : SHEET_COMPOSE_HINT_BLOCKED}
          onClick={() => void runSheet("generate")}
        >
          Generate Advanced Prop Reference Sheet
        </button>
        <button
          type="button"
          className="ghost"
          data-testid="prop-advanced-reference-sheet-cancel"
          disabled={!sheetBusy}
          onClick={() => void runSheet("cancel")}
        >
          Cancel sheet
        </button>
        {sheetBusy ? (
          <div className="character-core__progress" data-testid="prop-advanced-reference-sheet-progress">
            <div className="character-core__progress-head">
              <span className="character-core__progress-title">Composing Advanced Prop Reference Sheet</span>
              {sheetProgress != null ? (
                <span className="character-core__progress-pct" data-testid="prop-advanced-reference-sheet-progress-pct">
                  {sheetProgress}%
                </span>
              ) : null}
            </div>
            {sheetProgress != null ? (
              <div
                className="character-core__progress-track"
                role="progressbar"
                aria-valuenow={sheetProgress}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="Advanced Prop Reference Sheet progress"
                data-testid="prop-advanced-reference-sheet-progress-track"
              >
                <div
                  className="character-core__progress-fill"
                  data-testid="prop-advanced-reference-sheet-progress-fill"
                  style={{ width: `${sheetProgress}%` }}
                />
              </div>
            ) : (
              <div
                className="character-core__progress-track"
                data-testid="prop-advanced-reference-sheet-progress-waiting"
                aria-live="polite"
              />
            )}
            <p className="character-core__progress-label" data-testid="prop-advanced-reference-sheet-status">
              Composing sheet{sheetProgress != null ? ` · ${sheetProgress}%` : "…"}
            </p>
          </div>
        ) : null}
        {prop?.advanced_sheet_status === "complete" && prop.advanced_sheet_asset_id ? (
          <div className="prop-advanced-panel__sheet-preview" data-testid="prop-advanced-reference-sheet-complete">
            <button
              type="button"
              className="prop-advanced-panel__sheet-thumb-btn"
              data-testid="prop-advanced-reference-sheet-preview"
              aria-label="Open Prop Reference Sheet full size"
              onClick={() =>
                setPreviewAsset({
                  id: prop.advanced_sheet_asset_id!,
                  kind: "image",
                  name: "Prop Reference Sheet",
                  filename: prop.display_label || undefined,
                })
              }
            >
              <img
                className="prop-advanced-panel__primary-thumb"
                src={api.assetUrl(prop.advanced_sheet_asset_id)}
                alt="Advanced Prop Reference Sheet"
                data-testid="prop-advanced-reference-sheet-preview-img"
              />
            </button>
            <div
              className="prop-advanced-panel__sheet-success"
              data-testid="prop-advanced-reference-sheet-success"
              role="status"
              aria-live="polite"
            >
              <span className="prop-advanced-panel__sheet-success-check" aria-hidden="true">
                ✓
              </span>
              <span data-testid="prop-advanced-reference-sheet-success-message">
                Prop Reference Sheet has been successfully created
              </span>
            </div>
            <p className="muted" data-testid="prop-advanced-reference-sheet-working">
              Working / universal Adept prop · official PRS bound
            </p>
            <div className="prop-advanced-panel__sheet-actions">
              <button
                type="button"
                className="ghost"
                data-testid="prop-advanced-reference-sheet-open-library"
                onClick={() => onGoTab?.("library")}
              >
                Open in Library
              </button>
              <button
                type="button"
                className="ghost"
                data-testid="prop-advanced-reference-sheet-use-imagegen"
                onClick={() => onGoTab?.("imagegen", { propId: prop.id || "", assetId: prop.advanced_sheet_asset_id || "" })}
              >
                Use in Image Generator
              </button>
            </div>
          </div>
        ) : null}

        {prop?.advanced_sheet_error ? (
          <p className="error" data-testid="prop-advanced-reference-sheet-error">
            {prop.advanced_sheet_error}
          </p>
        ) : null}
      </div>

      <LibraryQuickPreviewModal asset={previewAsset} onClose={() => setPreviewAsset(null)} />

    </div>
  );
}
