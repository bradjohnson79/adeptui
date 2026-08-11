import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../../api";
import "./story-editor.css";

interface StoryEditorProps {
  projectId: string;
  embedded?: boolean;
}

export function StoryEditor({ projectId, embedded = false }: StoryEditorProps) {
  const [content, setContent] = useState("");
  const [title, setTitle] = useState("Untitled Story");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [wordCount, setWordCount] = useState(0);
  const editorRef = useRef<HTMLTextAreaElement>(null);
  const saveTimerRef = useRef<number | null>(null);
  const loadedRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const doc = await api.storyGet(projectId);
        if (!cancelled) {
          setContent(doc.content || "");
          setTitle(doc.title || "Untitled Story");
          setWordCount(doc.wordCount || 0);
          loadedRef.current = true;
        }
      } catch {
        loadedRef.current = true;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  const scheduleSave = useCallback(
    (newContent: string, newTitle?: string) => {
      if (saveTimerRef.current) clearTimeout(saveTimerRef.current);
      setSaveState("saving");
      saveTimerRef.current = window.setTimeout(async () => {
        try {
          const doc = await api.storySave(projectId, { content: newContent, title: newTitle || title });
          setSaveState("saved");
          setWordCount(doc.wordCount);
          setTimeout(() => setSaveState("idle"), 2000);
        } catch {
          setSaveState("error");
        }
      }, 700);
    },
    [projectId, title],
  );

  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const val = e.target.value;
    setContent(val);
    if (loadedRef.current) scheduleSave(val);
  };

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setTitle(val);
    if (loadedRef.current) scheduleSave(content, val);
  };

  const baseClass = embedded ? "story-editor story-editor--embedded" : "story-editor";

  return (
    <div className={baseClass} data-testid="story-editor">
      <div className="story-editor__header">
        <input
          type="text"
          className="story-editor__title"
          value={title}
          onChange={handleTitleChange}
          placeholder="Story Title"
          data-testid="story-title"
        />
        <span className="story-editor__status" data-testid="story-save-state">
          {saveState === "saving"
            ? "Saving..."
            : saveState === "saved"
              ? "Saved"
              : saveState === "error"
                ? "Save failed"
                : ""}
        </span>
        <span className="story-editor__wordcount">{wordCount} words</span>
      </div>
      <textarea
        ref={editorRef}
        className="story-editor__content"
        value={content}
        onChange={handleChange}
        placeholder={"Write your story here...\n\nDescribe what your film is about. The concept, the characters, the setting, what happens, and how it feels."}
        data-testid="story-content"
      />
    </div>
  );
}
