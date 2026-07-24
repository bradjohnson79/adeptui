import { useEffect, useState } from "react";
import { api } from "../api";
import type { Asset, Project, Scene } from "../types";
import {
  REFERENCE_ROLES,
  STRENGTH_PRESET_VALUES,
  type ReferenceCapabilities,
  type ReferenceContinuityPreset,
  type ReferenceIngredient,
  type ReferenceIngredientRole,
  type ReferenceMethod,
  type ReferenceSheet,
  type StrengthPreset,
} from "../references/types";

export function VisualReferencesPanel({
  project,
  scene,
  assets,
  onChange,
}: {
  project: Project;
  scene: Scene;
  assets: Asset[];
  onChange?: () => void;
}) {
  const [caps, setCaps] = useState<ReferenceCapabilities | null>(null);
  const [method, setMethod] = useState<ReferenceMethod>("none");
  const [ingredients, setIngredients] = useState<ReferenceIngredient[]>([]);
  const [sheet, setSheet] = useState<ReferenceSheet | null>(null);
  const [presets, setPresets] = useState<ReferenceContinuityPreset[]>([]);
  const [strengthPreset, setStrengthPreset] = useState<StrengthPreset>("balanced");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [strengthValue, setStrengthValue] = useState(1.4);
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [pickerAssetId, setPickerAssetId] = useState("");
  const [pickerRole, setPickerRole] = useState<ReferenceIngredientRole>("character");
  const [subjectName, setSubjectName] = useState("");
  const [presetName, setPresetName] = useState("");
  const [validation, setValidation] = useState<{ errors: any[]; warnings: any[] } | null>(null);

  const refresh = async () => {
    const [c, ings, pr] = await Promise.all([
      api.referenceCapabilities(project.id),
      api.listReferenceIngredients(project.id),
      api.listReferencePresets(project.id),
    ]);
    setCaps(c);
    setIngredients(ings.items || []);
    setPresets(pr.items || []);
  };

  useEffect(() => {
    refresh().catch((e) => setMsg(String(e)));
    // Restore method from director timeline if present
    api.getDirector(project.id, scene.id).then((d) => {
      const ref = d?.reference || d?.ic_lora;
      if (ref?.method === "ingredients_ic_lora" || ref?.reference_method === "ingredients_ic_lora") {
        setMethod("ingredients_ic_lora");
        if (ref.strength_preset) setStrengthPreset(ref.strength_preset);
        if (typeof ref.strength === "number") setStrengthValue(ref.strength);
        if (ref.sheet_id) {
          api.getReferenceSheet(project.id, ref.sheet_id).then(setSheet).catch(() => undefined);
        }
      }
    }).catch(() => undefined);
  }, [project.id, scene.id]);

  useEffect(() => {
    setStrengthValue(STRENGTH_PRESET_VALUES[strengthPreset]);
  }, [strengthPreset]);

  const persistDirectorRef = async (patch: Record<string, unknown>) => {
    const d = await api.getDirector(project.id, scene.id);
    const next = {
      ...d,
      reference: {
        ...(d.reference || {}),
        method,
        reference_method: method,
        enabled: method === "ingredients_ic_lora",
        model_id: "ltx23_ic_lora_ingredients",
        strength_preset: strengthPreset,
        strength: strengthValue,
        sheet_id: sheet?.id,
        ...patch,
      },
    };
    await api.putDirector(project.id, scene.id, next);
  };

  const addIngredient = async () => {
    if (!pickerAssetId) return;
    setBusy(true);
    setMsg(null);
    try {
      await api.upsertReferenceIngredient(project.id, {
        asset_id: pickerAssetId,
        role: pickerRole,
        subject_name: subjectName || undefined,
        priority: "primary",
        include: true,
        label: subjectName || undefined,
      });
      setSubjectName("");
      await refresh();
      onChange?.();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const buildSheet = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const built = await api.buildReferenceSheet(project.id, {
        ingredient_ids: ingredients.filter((i) => i.include).map((i) => i.id),
        layout: "auto",
        scene_id: scene.id,
      });
      setSheet(built);
      await persistDirectorRef({ sheet_id: built.id });
      const v = await api.validateReferenceSheet(project.id, built.id);
      setValidation(v);
      setMsg("Reference sheet built.");
      onChange?.();
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const savePreset = async () => {
    if (!presetName.trim() || !sheet) return;
    setBusy(true);
    try {
      await api.saveReferencePreset(project.id, {
        name: presetName.trim(),
        sheet_id: sheet.id,
        reference_sheet_asset_id: sheet.composite_asset_id || undefined,
        source_reference_ids: sheet.source_ingredient_ids || [],
        subjects: ingredients
          .filter((i) => i.include)
          .map((i) => ({
            name: i.subject_name || i.label || i.role,
            role: i.role,
            asset_ids: [i.asset_id],
          })),
        strength_preset: strengthPreset,
        strength_value: strengthValue,
      });
      setPresetName("");
      await refresh();
      setMsg("Continuity preset saved.");
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const reusePreset = async (presetId: string) => {
    setBusy(true);
    try {
      const reused = await api.reuseReferencePreset(project.id, presetId);
      setMethod("ingredients_ic_lora");
      if (reused.sheet) setSheet(reused.sheet);
      if (reused.strength_preset) setStrengthPreset(reused.strength_preset);
      if (typeof reused.strength_value === "number") setStrengthValue(reused.strength_value);
      await persistDirectorRef({
        method: "ingredients_ic_lora",
        sheet_id: reused.sheet?.id,
        strength_preset: reused.strength_preset,
        strength: reused.strength_value,
      });
      setMsg(`Reused preset: ${reused.preset?.name || presetId}`);
    } catch (e) {
      setMsg(String(e));
    } finally {
      setBusy(false);
    }
  };

  const selectMethod = async (next: ReferenceMethod) => {
    if (next === "identity_id_lora") return;
    if (next === "ingredients_ic_lora" && caps && !caps.ic_lora_option_enabled) {
      setMsg(caps.blockers?.[0] || "Ingredients IC-LoRA is not available.");
      return;
    }
    setMethod(next);
    try {
      await persistDirectorRef({ method: next, reference_method: next, enabled: next === "ingredients_ic_lora" });
    } catch (e) {
      setMsg(String(e));
    }
  };

  const imageAssets = assets.filter((a) => a.kind === "image");
  const blocker =
    method === "ingredients_ic_lora" && caps && !caps.ic_lora_option_enabled
      ? caps.blockers?.[0] || caps.model_message || "Ingredients IC-LoRA unavailable"
      : null;

  return (
    <section className="visual-references" aria-label="Visual References" style={{ marginTop: "0.75rem" }}>
      <h3 style={{ margin: "0 0 0.35rem" }}>Visual References</h3>
      <p className="muted" style={{ marginTop: 0, fontSize: "0.85rem" }}>
        Guide LTX 2.3 with a composite Ingredients reference sheet (IC-LoRA).
      </p>

      <fieldset style={{ border: "none", padding: 0, margin: "0 0 0.75rem" }}>
        <legend className="scene-meta">Reference method</legend>
        {(
          [
            ["none", "None"],
            ["start_frame", "Start Frame"],
            ["first_last_frame", "First / Last Frame"],
            ["ingredients_ic_lora", "Ingredients Reference — IC-LoRA"],
            ["identity_id_lora", "Identity Reference — ID-LoRA"],
          ] as const
        ).map(([value, label]) => {
          const disabled =
            value === "identity_id_lora" ||
            (value === "ingredients_ic_lora" && !!caps && !caps.ic_lora_option_enabled);
          return (
            <label key={value} className="scene-meta" style={{ display: "block", opacity: disabled ? 0.55 : 1 }}>
              <input
                type="radio"
                name="reference-method"
                checked={method === value}
                disabled={disabled}
                onChange={() => selectMethod(value)}
              />{" "}
              {label}
              {value === "identity_id_lora" ? " (not available yet)" : ""}
            </label>
          );
        })}
      </fieldset>

      {blocker && (
        <p className="pill" style={{ background: "rgba(180,80,40,0.15)" }}>
          {blocker}
        </p>
      )}
      {caps?.vram_warning && method === "ingredients_ic_lora" && (
        <p className="muted" style={{ fontSize: "0.8rem" }}>
          {caps.vram_warning}
        </p>
      )}

      {method === "ingredients_ic_lora" && (
        <>
          <div className="row" style={{ gap: "0.5rem", flexWrap: "wrap", alignItems: "end" }}>
            <label className="scene-meta">
              Asset
              <select value={pickerAssetId} onChange={(e) => setPickerAssetId(e.target.value)}>
                <option value="">Select…</option>
                {imageAssets.map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.tag || a.filename}
                  </option>
                ))}
              </select>
            </label>
            <label className="scene-meta">
              Role
              <select
                value={pickerRole}
                onChange={(e) => setPickerRole(e.target.value as ReferenceIngredientRole)}
              >
                {REFERENCE_ROLES.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </label>
            <label className="scene-meta">
              Subject
              <input value={subjectName} onChange={(e) => setSubjectName(e.target.value)} placeholder="Barnes" />
            </label>
            <button type="button" disabled={busy || !pickerAssetId} onClick={addIngredient}>
              Add reference
            </button>
          </div>

          <ul className="home-list" style={{ marginTop: "0.5rem" }}>
            {ingredients.length === 0 && <li className="empty">No references yet — pick assets and assign roles.</li>}
            {ingredients.map((ing) => (
              <li key={ing.id}>
                <strong>{ing.subject_name || ing.label || ing.role}</strong> · {ing.role} · {ing.priority}
                {!ing.include ? " (excluded)" : ""}
              </li>
            ))}
          </ul>

          <div className="row" style={{ gap: "0.5rem", marginTop: "0.5rem", flexWrap: "wrap" }}>
            <button type="button" disabled={busy || ingredients.length === 0} onClick={buildSheet}>
              Build Reference Sheet
            </button>
            <label className="scene-meta">
              Reference influence
              <select
                value={strengthPreset}
                onChange={(e) => setStrengthPreset(e.target.value as StrengthPreset)}
              >
                <option value="subtle">Subtle</option>
                <option value="balanced">Balanced</option>
                <option value="strong">Strong</option>
              </select>
            </label>
            <button type="button" className="linkish" onClick={() => setAdvancedOpen((v) => !v)}>
              Advanced {advancedOpen ? "▾" : "▸"}
            </button>
          </div>
          {advancedOpen && (
            <label className="scene-meta" style={{ display: "block", marginTop: "0.35rem" }}>
              Strength value
              <input
                type="number"
                step="0.05"
                min={0}
                max={2}
                value={strengthValue}
                onChange={(e) => setStrengthValue(Number(e.target.value))}
              />
            </label>
          )}

          {sheet?.preview_url && (
            <div style={{ marginTop: "0.75rem" }}>
              <p className="scene-meta">Composite preview · v{sheet.version}</p>
              <img
                src={sheet.preview_url}
                alt="Ingredients reference sheet"
                style={{ maxWidth: "100%", borderRadius: 4, background: "#000" }}
              />
            </div>
          )}

          {validation && (
            <div style={{ marginTop: "0.5rem" }}>
              {validation.errors?.map((e, i) => (
                <p key={`e-${i}`} className="pill" style={{ background: "rgba(180,60,40,0.18)" }}>
                  {e.message}
                </p>
              ))}
              {validation.warnings?.map((w, i) => (
                <p key={`w-${i}`} className="muted" style={{ fontSize: "0.8rem" }}>
                  {w.message}
                </p>
              ))}
            </div>
          )}

          <div className="row" style={{ gap: "0.5rem", marginTop: "0.75rem", flexWrap: "wrap" }}>
            <input
              value={presetName}
              onChange={(e) => setPresetName(e.target.value)}
              placeholder="Continuity preset name"
            />
            <button type="button" disabled={busy || !sheet || !presetName.trim()} onClick={savePreset}>
              Save continuity preset
            </button>
          </div>
          {presets.length > 0 && (
            <ul className="home-list" style={{ marginTop: "0.35rem" }}>
              {presets.map((p) => (
                <li key={p.id}>
                  {p.name}{" "}
                  <button type="button" className="linkish" onClick={() => reusePreset(p.id)}>
                    Reuse
                  </button>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      {msg && <p className="muted" style={{ marginTop: "0.5rem" }}>{msg}</p>}
    </section>
  );
}
