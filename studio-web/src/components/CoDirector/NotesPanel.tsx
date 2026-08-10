import { useEffect, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";

type Note = {
  id: string;
  text: string;
  category?: string;
  source?: string;
  promotionStatus?: string;
  confidence?: number;
};

export function NotesPanel({ projectId }: { projectId: string }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.getCoDirectorProjectNotes(projectId);
      setNotes((res.notes || []) as Note[]);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  return (
    <div className="codirector-notes-panel" data-testid="codirector-notes-panel">
      <header style={{ marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Notes</h3>
        <p className="muted" style={{ margin: "0.35rem 0 0" }}>
          Working memory — messy, provisional, and not the Wiki. Promote facts when they belong in
          the Project Bible.
        </p>
      </header>
      <div className="row" style={{ gap: "0.5rem", marginBottom: "0.75rem" }}>
        <Button variant="compact" data-testid="notes-refresh" onClick={() => void load()} disabled={busy}>
          Refresh
        </Button>
      </div>
      {error ? <p className="muted">{error}</p> : null}
      {!notes.length && !busy ? (
        <p className="muted" data-testid="notes-empty">
          Notes will gather here as Co-Director listens, reads scripts, and explores ideas.
        </p>
      ) : (
        <ul className="codirector-notes-list" data-testid="notes-list" style={{ listStyle: "none", padding: 0 }}>
          {notes.map((note) => (
            <li
              key={note.id}
              data-testid={`note-row-${note.id}`}
              style={{
                padding: "0.65rem 0",
                borderBottom: "1px solid color-mix(in srgb, currentColor 12%, transparent)",
              }}
            >
              <div className="muted" style={{ fontSize: "0.75rem", marginBottom: "0.25rem" }}>
                {[note.category, note.source, note.promotionStatus].filter(Boolean).join(" · ")}
              </div>
              <div>{note.text}</div>
              {note.promotionStatus !== "PROMOTED" ? (
                <Button
                  variant="compact"
                  data-testid={`note-promote-${note.id}`}
                  style={{ marginTop: "0.35rem" }}
                  onClick={() => {
                    void api
                      .promoteCoDirectorWiki(projectId, {
                        noteId: note.id,
                        text: note.text,
                        destination: note.category === "Character" ? "character" : "story",
                      })
                      .then(() => load());
                  }}
                >
                  Add to Wiki
                </Button>
              ) : (
                <span className="muted" style={{ fontSize: "0.75rem" }}>
                  Promoted to Wiki
                </span>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
