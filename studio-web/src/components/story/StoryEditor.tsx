import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { Placeholder } from "@tiptap/extension-placeholder";
import { api } from "../../api";
import "./story-editor.css";

interface StoryEditorProps {
  projectId: string;
  embedded?: boolean;
}

export function StoryEditor({ projectId, embedded = false }: StoryEditorProps) {
  const [title, setTitle] = useState("Untitled Story");
  const [saveState, setSaveState] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [wordCount, setWordCount] = useState(0);
  const saveTimerRef = useRef<number | null>(null);
  const loadedRef = useRef(false);

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

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
        strike: false,
        code: false,
        blockquote: false,
        horizontalRule: false,
      }),
      Placeholder.configure({
        placeholder:
          "Write your story here...\n\nDescribe what your film is about. The concept, the characters, the setting, what happens, and how it feels.",
      }),
    ],
    content: "",
  });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const doc = await api.storyGet(projectId);
        if (!cancelled && editor) {
          editor.commands.setContent(doc.content || "");
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
  }, [projectId, editor]);

  useEffect(() => {
    if (!editor) return;
    const onUpdate = () => {
      if (!loadedRef.current) return;
      scheduleSave(editor.getHTML());
    };
    editor.on("update", onUpdate);
    return () => {
      editor.off("update", onUpdate);
      editor.destroy();
    };
  }, [editor, scheduleSave]);

  const handleTitleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value;
    setTitle(val);
    if (loadedRef.current) scheduleSave(editor?.getHTML() || "", val);
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
      {editor ? (
        <div className="story-editor__toolbar" data-testid="story-toolbar">
          <button
            type="button"
            className={editor.isActive("bold") ? "is-active" : ""}
            data-testid="story-btn-bold"
            onClick={() => editor.chain().focus().toggleBold().run()}
            aria-label="Bold"
          >
            B
          </button>
          <button
            type="button"
            className={editor.isActive("italic") ? "is-active" : ""}
            data-testid="story-btn-italic"
            onClick={() => editor.chain().focus().toggleItalic().run()}
            aria-label="Italic"
          >
            I
          </button>
          <button
            type="button"
            className={editor.isActive("heading", { level: 1 }) ? "is-active" : ""}
            data-testid="story-btn-h1"
            onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
            aria-label="Heading 1"
          >
            H1
          </button>
          <button
            type="button"
            className={editor.isActive("heading", { level: 2 }) ? "is-active" : ""}
            data-testid="story-btn-h2"
            onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
            aria-label="Heading 2"
          >
            H2
          </button>
          <button
            type="button"
            className={editor.isActive("bulletList") ? "is-active" : ""}
            data-testid="story-btn-bullet"
            onClick={() => editor.chain().focus().toggleBulletList().run()}
            aria-label="Bullet list"
          >
            •
          </button>
          <button
            type="button"
            className={editor.isActive("orderedList") ? "is-active" : ""}
            data-testid="story-btn-numbered"
            onClick={() => editor.chain().focus().toggleOrderedList().run()}
            aria-label="Numbered list"
          >
            1.
          </button>
          <button
            type="button"
            disabled={!editor.can().undo()}
            data-testid="story-btn-undo"
            onClick={() => editor.chain().focus().undo().run()}
            aria-label="Undo"
          >
            ↶
          </button>
          <button
            type="button"
            disabled={!editor.can().redo()}
            data-testid="story-btn-redo"
            onClick={() => editor.chain().focus().redo().run()}
            aria-label="Redo"
          >
            ↷
          </button>
        </div>
      ) : null}
      <div className="story-editor__content" data-testid="story-content">
        <EditorContent editor={editor} />
      </div>
    </div>
  );
}
