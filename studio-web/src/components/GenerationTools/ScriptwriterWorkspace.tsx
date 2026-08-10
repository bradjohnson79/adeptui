import { useState } from "react";
import { api } from "../../api";
import type { Project } from "../../types";
import type { EditorTab } from "../../workspacePrefs";
import { PanelHeading } from "../HelpTip";
import { Button } from "../ui";

const DOC_TYPES = [
  "treatment",
  "outline",
  "beat_sheet",
  "scene",
  "screenplay",
  "dialogue_revision",
  "storyboard_brief",
  "shot_breakdown",
  "commercial",
  "trailer",
  "social_video",
] as const;

export function ScriptwriterWorkspace({
  project,
  onChange,
  onGo,
}: {
  project: Project;
  onChange?: () => Promise<void>;
  onGo: (tab: EditorTab) => void;
}) {
  const [documentType, setDocumentType] = useState<(typeof DOC_TYPES)[number]>("treatment");
  const [brief, setBrief] = useState("");
  const [title, setTitle] = useState("");
  const [result, setResult] = useState("");
  const [busy, setBusy] = useState(false);

  const create = async () => {
    setBusy(true);
    setResult("");
    try {
      const res = await api.runGenerationTool(project.id, {
        toolId: "scriptwriter",
        documentType,
        prompt: brief,
        title: title || undefined,
        confirmPaidCloud: false,
      });
      setResult(res.text || "Saved.");
      await onChange?.();
    } catch (e) {
      setResult(e instanceof Error ? e.message : "Failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="page" data-testid="scriptwriter-workspace">
      <PanelHeading
        title="Scriptwriter"
        tip="First-class writing workspace: treatments, outlines, beats, scenes, screenplay, dialogue revisions, storyboard and shot briefs, commercial/trailer/social scripts. Also available through Co-Director and Generation Tools."
      />
      <div className="row-actions">
        <Button variant="ghost" onClick={() => onGo("script")}>
          Open Script / Storyboard
        </Button>
        <Button variant="ghost" onClick={() => onGo("generationtools")}>
          Generation Tools
        </Button>
      </div>
      <label>
        Document type
        <select
          value={documentType}
          onChange={(e) => setDocumentType(e.target.value as (typeof DOC_TYPES)[number])}
          data-testid="scriptwriter-type"
        >
          {DOC_TYPES.map((d) => (
            <option key={d} value={d}>
              {d}
            </option>
          ))}
        </select>
      </label>
      <label>
        Title
        <input value={title} onChange={(e) => setTitle(e.target.value)} data-testid="scriptwriter-title" />
      </label>
      <label>
        Brief
        <textarea rows={4} value={brief} onChange={(e) => setBrief(e.target.value)} data-testid="scriptwriter-brief" />
      </label>
      <Button variant="primary" disabled={busy || !brief.trim()} onClick={() => void create()} data-testid="scriptwriter-create">
        Create & persist
      </Button>
      {result && (
        <pre className="panel" data-testid="scriptwriter-result" style={{ whiteSpace: "pre-wrap" }}>
          {result}
        </pre>
      )}
    </div>
  );
}
