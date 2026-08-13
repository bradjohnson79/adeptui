/**
 * PropsWorkspace — creator-first "Props & Accessories" panel for a character.
 *
 * Max 4 props per character (enforced in the backend; mirrored in the UI).
 * Each slot has a name, description, optional reference, a Generate button,
 * and once an image exists: a thumbnail + Approve / Remove. Approved props
 * are shown as saved.
 *
 * Props remain CHARACTER-ASSOCIATED LIBRARY ASSETS: a prop image is saved via
 * the existing character_props backend, which registers/assigns it to the
 * project Library with entity_type=character, entity_id=characterId. No
 * duplicate binaries, no hidden media store.
 *
 * Disabled entirely until the character is saved (needs a real characterId).
 *
 * Reuses the shared character-core CSS classes for buttons/fields/hints and a
 * small matching stylesheet (propsWorkspace.css) for prop-specific layout.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import "./characterCore.css";
import "./propsWorkspace.css";

const MAX_PROPS = 4;

export type PropSlot = {
  id: string;
  name: string;
  prop_type?: string;
  description?: string;
  library_asset_id?: string | null;
  approval_status?: string;
  generation_job_id?: string | null;
};

type Props = {
  projectId: string;
  /** Real character id — when empty, the workspace is disabled. */
  characterId: string;
};

export function PropsWorkspace({ projectId, characterId }: Props) {
  const [props, setProps] = useState<PropSlot[]>([]);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  // Per-slot draft state for name/description before creation.
  const [drafts, setDrafts] = useState<Record<string, { name: string; description: string }>>({});
  // Per-slot in-flight generation flag.
  const [generating, setGenerating] = useState<Record<string, boolean>>({});
  const pollingRef = useRef<Record<string, boolean>>({});

  const saved = !!characterId;

  const refresh = useCallback(async () => {
    if (!projectId || !characterId) {
      setProps([]);
      return;
    }
    setLoading(true);
    setError("");
    try {
      const res = await api.listCharacterProps(projectId, characterId);
      setProps((res.items || []) as PropSlot[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load props.");
    } finally {
      setLoading(false);
    }
  }, [projectId, characterId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const draftKey = (slotId: string) => slotId;

  const getDraft = useCallback(
    (slotId: string): { name: string; description: string } => {
      return (
        drafts[draftKey(slotId)] || {
          name: "",
          description: "",
        }
      );
    },
    [drafts],
  );

  const setDraft = useCallback((slotId: string, patch: Partial<{ name: string; description: string }>) => {
    setDrafts((prev) => ({
      ...prev,
      [draftKey(slotId)]: { ...(prev[draftKey(slotId)] || { name: "", description: "" }), ...patch },
    }));
  }, []);

  const canAdd = saved && props.length < MAX_PROPS;

  const handleAdd = useCallback(async () => {
    if (!canAdd) return;
    setNotice("");
    setError("");
    try {
      const created = (await api.createCharacterProp(projectId, characterId, {
        name: "New Prop",
        description: "",
      })) as PropSlot;
      setProps((prev) => [...prev, created]);
      setDraft(created.id, { name: "New Prop", description: "" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not add a prop slot.");
    }
  }, [canAdd, projectId, characterId, setDraft]);

  const handleSaveField = useCallback(
    async (slot: PropSlot, field: "name" | "description", value: string) => {
      // Optimistic local update.
      setProps((prev) => prev.map((p) => (p.id === slot.id ? { ...p, [field]: value } : p)));
      try {
        await api.patchCharacterProp(projectId, characterId, slot.id, { [field]: value });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not save prop.");
        void refresh();
      }
    },
    [projectId, characterId, refresh],
  );

  const pollStatus = useCallback(
    async (slot: PropSlot, attemptsLeft: number) => {
      if (attemptsLeft <= 0) {
        pollingRef.current[slot.id] = false;
        setGenerating((prev) => ({ ...prev, [slot.id]: false }));
        return;
      }
      try {
        const status = await api.getCharacterPropStatus(projectId, characterId, slot.id);
        setProps((prev) =>
          prev.map((p) =>
            p.id === slot.id
              ? {
                ...p,
                library_asset_id: status.library_asset_id ?? p.library_asset_id,
                approval_status: status.approval_status ?? p.approval_status,
                generation_job_id: status.jobId ?? p.generation_job_id,
              }
              : p,
          ),
        );
        if (status.library_asset_id || status.jobStatus === "done") {
          pollingRef.current[slot.id] = false;
          setGenerating((prev) => ({ ...prev, [slot.id]: false }));
          return;
        }
        if (status.jobStatus === "failed" || status.jobStatus === "cancelled") {
          pollingRef.current[slot.id] = false;
          setGenerating((prev) => ({ ...prev, [slot.id]: false }));
          setError(`Prop image generation failed. Try again.`);
          return;
        }
      } catch {
        // transient; keep polling
      }
      setTimeout(() => void pollStatus(slot, attemptsLeft - 1), 2000);
    },
    [projectId, characterId],
  );

  const handleGenerate = useCallback(
    async (slot: PropSlot) => {
      if (!saved) return;
      setNotice("");
      setError("");
      if (pollingRef.current[slot.id]) return;
      setGenerating((prev) => ({ ...prev, [slot.id]: true }));
      try {
        await api.generateCharacterProp(projectId, characterId, slot.id);
        pollingRef.current[slot.id] = true;
        void pollStatus(slot, 120);
      } catch (e) {
        setGenerating((prev) => ({ ...prev, [slot.id]: false }));
        setError(e instanceof Error ? e.message : "Could not start prop generation.");
      }
    },
    [saved, projectId, characterId, pollStatus],
  );

  const handleApprove = useCallback(
    async (slot: PropSlot) => {
      setNotice("");
      setError("");
      try {
        await api.approveCharacterProp(projectId, characterId, slot.id);
        setProps((prev) =>
          prev.map((p) => (p.id === slot.id ? { ...p, approval_status: "approved" } : p)),
        );
        setNotice(`${slot.name || "Prop"} saved to the character.`);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not approve prop.");
      }
    },
    [projectId, characterId],
  );

  const handleRemove = useCallback(
    async (slot: PropSlot) => {
      const confirmed = window.confirm(
        `Remove ${slot.name || "this prop"}? The image stays in your project Library.`,
      );
      if (!confirmed) return;
      setNotice("");
      setError("");
      try {
        await api.deleteCharacterProp(projectId, characterId, slot.id);
        setProps((prev) => prev.filter((p) => p.id !== slot.id));
        setDrafts((prev) => {
          const next = { ...prev };
          delete next[draftKey(slot.id)];
          return next;
        });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Could not remove prop.");
      }
    },
    [projectId, characterId],
  );

  if (!saved) {
    return (
      <div className="props-workspace" data-testid="props-workspace">
        <div className="props-workspace__header">
          <h3 className="props-workspace__header-title">Props &amp; Accessories</h3>
          <span className="props-workspace__header-count">0 of {MAX_PROPS}</span>
        </div>
        <p className="props-workspace__disabled-banner" data-testid="props-disabled">
          Save the character first, then add up to {MAX_PROPS} props here.
        </p>
      </div>
    );
  }

  return (
    <div className="props-workspace" data-testid="props-workspace">
      <div className="props-workspace__header">
        <h3 className="props-workspace__header-title">Props &amp; Accessories</h3>
        <span className="props-workspace__header-count">
          {props.length} of {MAX_PROPS}
        </span>
      </div>

      {loading && props.length === 0 ? (
        <p className="props-workspace__empty">Loading props…</p>
      ) : null}

      {props.length === 0 && !loading ? (
        <p className="props-workspace__empty">
          No props yet. Add a prop below — like a staff, a pendant, or a keepsake.
        </p>
      ) : null}

      <div className="props-workspace__slots">
        {props.map((slot) => {
          const draft = getDraft(slot.id);
          const hasImage = !!slot.library_asset_id;
          const isApproved = slot.approval_status === "approved";
          const isGenerating = !!generating[slot.id];
          const src = slot.library_asset_id ? api.assetUrl(slot.library_asset_id) : "";
          return (
            <div
              key={slot.id}
              className={`props-workspace__slot${isApproved ? " is-approved" : ""}`}
              data-testid={`prop-slot-${slot.id}`}
            >
              <div className="props-workspace__slot-media">
                {src ? (
                  <img src={src} alt={slot.name || "Prop"} loading="lazy" />
                ) : (
                  <div className="props-workspace__slot-placeholder">
                    {isGenerating ? "Generating prop image…" : "No image yet — describe and generate."}
                  </div>
                )}
              </div>

              <div className="character-core__field">
                <label className="character-core__label" htmlFor={`prop-name-${slot.id}`}>
                  Name
                </label>
                <input
                  id={`prop-name-${slot.id}`}
                  type="text"
                  value={draft.name || slot.name || ""}
                  placeholder="e.g. Korri's Staff"
                  onChange={(e) => setDraft(slot.id, { name: e.target.value })}
                  onBlur={(e) => void handleSaveField(slot, "name", e.target.value)}
                />
              </div>

              <div className="character-core__field">
                <label className="character-core__label" htmlFor={`prop-desc-${slot.id}`}>
                  Description{" "}
                  <span className="character-core__optional">(what it looks like)</span>{" "}
                  <span className="character-core__tip" title="Describe the prop. The character's approved look is used as the visual reference, so the prop stays on-style.">
                    (?)
                  </span>
                </label>
                <textarea
                  id={`prop-desc-${slot.id}`}
                  value={draft.description ?? slot.description ?? ""}
                  placeholder="A carved wooden staff with sun-glyph inlays…"
                  onChange={(e) => setDraft(slot.id, { description: e.target.value })}
                  onBlur={(e) => void handleSaveField(slot, "description", e.target.value)}
                />
              </div>

              {isApproved ? (
                <span className="props-workspace__slot-badge" data-testid={`prop-saved-${slot.id}`}>
                  Saved
                </span>
              ) : null}

              <div className="props-workspace__slot-actions">
                <button
                  type="button"
                  className="character-core__button primary"
                  data-testid={`prop-generate-${slot.id}`}
                  disabled={isGenerating || !slot.name?.trim()}
                  onClick={() => void handleGenerate(slot)}
                >
                  {isGenerating ? "Generating…" : hasImage ? "Regenerate" : "Generate"}
                </button>
                <button
                  type="button"
                  className="character-core__button"
                  data-testid={`prop-approve-${slot.id}`}
                  disabled={!hasImage || isApproved}
                  onClick={() => void handleApprove(slot)}
                >
                  {isApproved ? "Saved" : "Approve"}
                </button>
                <button
                  type="button"
                  className="character-core__button danger"
                  data-testid={`prop-remove-${slot.id}`}
                  onClick={() => void handleRemove(slot)}
                >
                  Remove
                </button>
              </div>
            </div>
          );
        })}
      </div>

      <div className="props-workspace__add">
        <button
          type="button"
          className="character-core__button"
          data-testid="prop-add"
          disabled={!canAdd}
          onClick={() => void handleAdd()}
        >
          + Add Prop
        </button>
      </div>

      {notice ? (
        <p className="character-core__hint" data-testid="props-notice">
          {notice}
        </p>
      ) : null}
      {error ? (
        <p className="character-core__hint" style={{ color: "#f08787" }} data-testid="props-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
