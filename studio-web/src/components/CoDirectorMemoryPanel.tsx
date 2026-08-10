import { useCallback, useRef, useState } from "react";
import type { Project } from "../types";
import { api } from "../api";
import { PanelHeading } from "./HelpTip";

export function CoDirectorMemoryPanel({ project }: { project: Project }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sourcePreview, setSourcePreview] = useState<string | null>(null);
  const importRef = useRef<HTMLInputElement>(null);

  const run = useCallback(
    async (label: string, fn: () => Promise<void>) => {
      setBusy(true);
      setError(null);
      setMessage(null);
      try {
        await fn();
        setMessage(label);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Something went wrong.");
      } finally {
        setBusy(false);
      }
    },
    [],
  );

  const viewSource = () =>
    void run("Memory source loaded.", async () => {
      const bundle = await api.codirectorMemoryExport(project.id);
      setSourcePreview(JSON.stringify(bundle, null, 2));
    });

  const exportMemory = () =>
    void run("Memory exported.", async () => {
      const bundle = await api.codirectorMemoryExport(project.id);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `codirector-memory-${project.id.slice(0, 8)}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });

  const importMemory = (file: File) =>
    void run("Memory imported.", async () => {
      const text = await file.text();
      const bundle = JSON.parse(text) as Record<string, unknown>;
      await api.codirectorMemoryImport(project.id, bundle);
      setSourcePreview(null);
    });

  const compactIfLong = () =>
    void run("Conversation summarized.", async () => {
      const convo = await api.codirectorGetConversation(project.id);
      const count = convo.messages?.length ?? 0;
      if (count < 8) {
        setMessage("Conversation is still short — no summary needed yet.");
        return;
      }
      const beforeSequence = Math.max(0, count - 4);
      await api.codirectorCompactConversation(project.id, {
        beforeSequence,
        summaryText: "Earlier conversation summarized to save space.",
      });
    });

  const runAudit = () =>
    void run("Memory check complete.", async () => {
      const audit = await api.codirectorConversationAudit(project.id);
      setSourcePreview(JSON.stringify(audit, null, 2));
    });

  return (
    <div className="panel" data-testid="codirector-memory-panel">
      <PanelHeading
        title="Co-Director Memory"
        tip="View, back up, or restore what Co-Director remembers for this project."
      />
      <p className="muted">Keep your story context safe. Summarize long chats when they grow.</p>
      <div className="row-actions" style={{ flexWrap: "wrap", gap: "0.5rem" }}>
        <button type="button" className="ghost" disabled={busy} data-testid="memory-view-source" onClick={viewSource}>
          View memory
        </button>
        <button type="button" className="ghost" disabled={busy} data-testid="memory-export" onClick={exportMemory}>
          Export backup
        </button>
        <button
          type="button"
          className="ghost"
          disabled={busy}
          data-testid="memory-import"
          onClick={() => importRef.current?.click()}
        >
          Import backup
        </button>
        <input
          ref={importRef}
          type="file"
          accept="application/json,.json"
          hidden
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void importMemory(file);
            e.target.value = "";
          }}
        />
        <button type="button" className="ghost" disabled={busy} data-testid="memory-compact" onClick={compactIfLong}>
          Summarize long chat
        </button>
        <button type="button" className="ghost" disabled={busy} data-testid="memory-audit" onClick={runAudit}>
          Check memory health
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      {message && <p className="scene-meta">{message}</p>}
      {sourcePreview && (
        <pre className="muted" style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem", maxHeight: 240, overflow: "auto" }}>
          {sourcePreview}
        </pre>
      )}
    </div>
  );
}
