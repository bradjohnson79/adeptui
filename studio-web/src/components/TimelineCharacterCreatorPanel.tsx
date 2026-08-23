import { useCallback, useEffect, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";
import { Button } from "./ui";

type CharacterListItem = {
  id: string;
  name?: string;
  slug?: string;
  role?: string;
  approval_status?: string;
  status?: string;
};

/**
 * Compact Character Creator rail for Timeline — seed / open full Character Profile.
 * Full editing lives in Character Profile workspace; this is the production entry point.
 */
export function TimelineCharacterCreatorPanel({
  project,
  onChange,
  onOpenCharacterCreator,
}: {
  project: Project;
  onChange: () => void;
  onOpenCharacterCreator: () => void;
}) {
  const [items, setItems] = useState<CharacterListItem[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      const res = await api.listCharacterProfiles(project.id);
      setItems((res.items || []) as CharacterListItem[]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load characters");
      setItems([]);
    }
  }, [project.id]);

  useEffect(() => {
    void load();
  }, [load]);

  const seedKorri = async () => {
    setBusy(true);
    setMsg(null);
    setError(null);
    try {
      const created = await api.seedKorriCanon(project.id);
      setMsg(`Korri ready — ${created.name || "Korri"} (${created.approval_status || "draft"})`);
      await load();
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Seed Korri failed");
    } finally {
      setBusy(false);
    }
  };

  const korri = items.find((c) => (c.slug || "").toLowerCase() === "korri" || (c.name || "").toLowerCase() === "korri");

  return (
    <div className="panel" data-testid="timeline-character-creator">
      <PanelHeading
        title="Character Creator"
        tip="Canonical character identity for this project. Seed Korri or open Character Profile for Motion, Performance Bible, Relationships, and Prompt Package. Attach approved references via the References pane."
      />
      <p className="scene-meta">
        Everything for this character stays in this project’s Library — sheets, voice, and generations do not create new projects.
      </p>

      {error && (
        <p className="error" data-testid="timeline-cc-error">
          {error}
        </p>
      )}
      {msg && (
        <p className="pill" data-testid="timeline-cc-msg">
          {msg}
        </p>
      )}

      {items.length === 0 ? (
        <p data-testid="timeline-cc-empty">No Character Profiles in this project yet.</p>
      ) : (
        <ul data-testid="timeline-cc-list" style={{ listStyle: "none", padding: 0, margin: "0.5rem 0" }}>
          {items.slice(0, 8).map((c) => (
            <li key={c.id} style={{ marginBottom: "0.35rem", fontSize: "0.9rem" }}>
              <strong>{c.name || c.slug || c.id.slice(0, 8)}</strong>
              {c.role ? <span className="muted"> · {c.role}</span> : null}
              <span className="muted"> · {c.approval_status || c.status || "draft"}</span>
            </li>
          ))}
          {items.length > 8 ? <li className="muted">+{items.length - 8} more</li> : null}
        </ul>
      )}

      <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.35rem" }}>
        <Button
          type="button"
          variant="primary"
          disabled={busy}
          onClick={() => void seedKorri()}
          data-testid="timeline-seed-korri"
        >
          {korri ? "Refresh Korri (canon v1)" : "Seed Korri (canon v1)"}
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={busy || !korri}
          onClick={() => {
            if (!korri) return;
            setBusy(true);
            setMsg(null);
            setError(null);
            void api
              .startCharacterVisualSheet(project.id, korri.id, {
                includeDetails: false,
                includePerformance: false,
                candidateCount: 1,
                taskType: "CRS_GENERATION",
                layout: "four_view",
              })
              .then((r) => {
                setMsg(
                  `Visual sheet started · ${r.pack?.status || "GENERATING"}. Use Continue sheet here, or open Character Profile to finish and approve.`,
                );
                onChange();
              })
              .catch((e) => setError(e instanceof Error ? e.message : "Visual sheet failed"))
              .finally(() => setBusy(false));
          }}
          data-testid="timeline-generate-visual-sheet"
        >
          Generate Korri Visual Sheet
        </Button>
        <Button
          type="button"
          variant="primary"
          disabled={busy || !korri}
          onClick={() => {
            if (!korri) return;
            setBusy(true);
            setMsg(null);
            setError(null);
            void api
              .advanceCharacterVisualSheet(project.id, korri.id)
              .then((r) => {
                const status = r.pack?.status || "?";
                const roles = Object.keys(r.pack?.roleAssets || {}).length;
                setMsg(`Sheet advanced · ${status} · ${roles} roles ready`);
                onChange();
              })
              .catch((e) => setError(e instanceof Error ? e.message : "Advance sheet failed"))
              .finally(() => setBusy(false));
          }}
          data-testid="timeline-advance-visual-sheet"
        >
          Continue sheet
        </Button>
        <Button
          type="button"
          variant="ghost"
          disabled={busy}
          onClick={onOpenCharacterCreator}
          data-testid="timeline-open-character-creator"
        >
          Open Character Profile
        </Button>
      </div>
    </div>
  );
}
