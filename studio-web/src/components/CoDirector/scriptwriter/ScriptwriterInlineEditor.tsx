import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import TextAlign from "@tiptap/extension-text-align";
import type { SaveState, ScriptDocument } from "../../scriptwriter/types";
import { IndentKeys, IndentParagraph } from "../../scriptwriter/richTextExtensions";
import { elementsToHtml, isBlankHtml } from "../../scriptwriter/legacyHtml";
import { sanitizeHtml } from "../../scriptwriter/sanitizeHtml";
import { api, ApiError } from "../../../api";
import "./ScriptwriterInline.css";

type Props = {
  projectId: string;
  onOpenFull?: () => void;
};

function resolveInitialHtml(doc: Partial<ScriptDocument> | null): string {
  if (doc?.contentHtml && !isBlankHtml(doc.contentHtml)) return doc.contentHtml;
  if (doc?.elements && doc.elements.length > 0) return elementsToHtml(doc.elements);
  return "<p></p>";
}

export function ScriptwriterInlineEditor({ projectId, onOpenFull }: Props) {
  const [docId, setDocId] = useState<string | null>(null);
  const [title, setTitle] = useState("Untitled Script");
  const [stats, setStats] = useState<Record<string, number>>({});
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [message, setMessage] = useState<string | null>(null);
  const hydrating = useRef(false);
  const saveTimer = useRef<number | null>(null);
  const latestRevisionRef = useRef<number | undefined>(undefined);
  const loadedRef = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ paragraph: false }),
      IndentParagraph,
      Underline,
      TextAlign.configure({ types: ["heading", "paragraph"] }),
      IndentKeys,
    ],
    content: "<p></p>",
    onUpdate: ({ editor: ed }) => {
      if (hydrating.current || !docId) return;
      setSaveState("unsaved");
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void (async () => {
          if (!docId) return;
          try {
            setSaveState("saving");
            const html = sanitizeHtml(ed.getHTML());
            const res = await api.scriptwriter.autosave(projectId, docId, {
              html,
              expectedRevision: latestRevisionRef.current ?? undefined,
            });
            const d = res.document as unknown as { id: string; title: string; revision: number };
            if (d.id) {
              latestRevisionRef.current = d.revision;
              if (d.title) setTitle(d.title);
            }
            setSaveState((res.saveState as SaveState) || "saved");
          } catch (e) {
            if (e instanceof ApiError && e.status === 400 && ((e.code === "SCRIPT_CONFLICT") || (String(e.message || "").includes("CONFLICT")))) {
              try {
                const fresh = await api.scriptwriter.studio(projectId);
                const d = fresh.document as unknown as Partial<ScriptDocument> & { id: string; title: string; revision: number };
                if (d.id) {
                  latestRevisionRef.current = d.revision;
                  setDocId(d.id);
                  if (d.title) setTitle(d.title);
                }
                if (editor) {
                  hydrating.current = true;
                  editor.commands.setContent(resolveInitialHtml(d));
                  hydrating.current = false;
                }
                setSaveState("save_failed");
                setMessage("Document was updated elsewhere. Reloaded latest version.");
              } catch { setSaveState("save_failed"); }
            } else { setSaveState("save_failed"); }
          }
        })();
      }, 700);
    },
  });

  useEffect(() => {
    if (!editor) return;
    let cancelled = false;
    (async () => {
      try {
        const bundle = await api.scriptwriter.studio(projectId);
        if (cancelled) return;
        const d = bundle.document as unknown as Partial<ScriptDocument> & { id: string; title: string; revision: number };
        if (d.id) {
          setDocId(d.id);
          setTitle(d.title);
          latestRevisionRef.current = d.revision;
        }
        setStats((bundle.stats || {}) as Record<string, number>);
        if (editor) {
          hydrating.current = true;
          editor.commands.setContent(resolveInitialHtml(d));
          hydrating.current = false;
          loadedRef.current = true;
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [projectId, editor]);

  const isActive = useCallback(
    (name: string, attrs?: Record<string, unknown>) => editor?.isActive(name, attrs) ?? false,
    [editor],
  );

  const saveLabel = saveState === "saved" ? "Saved" : saveState === "saving" ? "Saving..." : saveState === "save_failed" ? "Save failed" : "";

  return (
    <div className="sw-inline" data-testid="scriptwriter-inline">
      <div className="sw-inline__header">
        <div>
          <h3 className="sw-inline__title">{title || "Untitled Script"}</h3>
          <div className="sw-inline__stats">
            <span className="sw-inline__stat">{(stats.pagesEstimated ?? 0).toFixed(1)} pages</span>
            <span className="sw-inline__stat">{stats.scenes ?? 0} scenes</span>
            <span className="sw-inline__stat">{stats.words ?? 0} words</span>
            {stats.runtimeMinutesEstimated ? (
              <span className="sw-inline__stat">~{Math.round(stats.runtimeMinutesEstimated)} min</span>
            ) : null}
          </div>
        </div>
        <div className="sw-inline__header-right">
          <span className="sw-inline__save-state" data-testid="sw-inline-save-state">{saveLabel}</span>
          <button type="button" className="primary compact" data-testid="sw-inline-open-full" onClick={() => { onOpenFull?.(); }}>
            Open Full
          </button>
        </div>
      </div>

      <div className="sw-inline__toolbar" data-testid="sw-inline-toolbar">
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().toggleBold().run()} disabled={!editor?.can().toggleBold()} data-testid="sw-inline-bold" title="Bold">B</button>
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().toggleItalic().run()} disabled={!editor?.can().toggleItalic()} data-testid="sw-inline-italic" title="Italic">I</button>
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().toggleUnderline().run()} disabled={!editor?.can().toggleUnderline()} data-testid="sw-inline-underline" title="Underline">U</button>
        <span className="sw-inline__tool-sep" />
        <button type="button" className={isActive("heading", { level: 1 }) ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().toggleHeading({ level: 1 }).run()} data-testid="sw-inline-h1" title="Heading 1">H1</button>
        <button type="button" className={isActive("heading", { level: 2 }) ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().toggleHeading({ level: 2 }).run()} data-testid="sw-inline-h2" title="Heading 2">H2</button>
        <span className="sw-inline__tool-sep" />
        <button type="button" className={isActive("bulletList") ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().toggleBulletList().run()} data-testid="sw-inline-bullet" title="Bullet list">•</button>
        <button type="button" className={isActive("orderedList") ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().toggleOrderedList().run()} data-testid="sw-inline-ordered" title="Numbered list">1.</button>
        <span className="sw-inline__tool-sep" />
        <button type="button" className={isActive("textAlign", { textAlign: "left" }) ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().setTextAlign("left").run()} data-testid="sw-inline-align-left" title="Align left">⯇</button>
        <button type="button" className={isActive("textAlign", { textAlign: "center" }) ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().setTextAlign("center").run()} data-testid="sw-inline-align-center" title="Align center">≣</button>
        <button type="button" className={isActive("textAlign", { textAlign: "right" }) ? "sw-inline__tool-btn is-active" : "sw-inline__tool-btn"} onClick={() => editor?.chain().focus().setTextAlign("right").run()} data-testid="sw-inline-align-right" title="Align right">⯈</button>
        <span className="sw-inline__tool-sep" />
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().focus().run() && editor?.commands.updateAttributes("paragraph", { indent: Math.min(Number(editor.getAttributes("paragraph").indent || 0) + 40, 320) })} data-testid="sw-inline-indent" title="Indent">→|</button>
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().focus().run() && editor?.commands.updateAttributes("paragraph", { indent: Math.max(Number(editor.getAttributes("paragraph").indent || 0) - 40, 0) })} data-testid="sw-inline-outdent" title="Outdent">|←</button>
        <span className="sw-inline__tool-sep" />
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().undo().run()} disabled={!editor?.can().undo()} data-testid="sw-inline-undo" title="Undo">↶</button>
        <button type="button" className="sw-inline__tool-btn" onClick={() => editor?.chain().focus().redo().run()} disabled={!editor?.can().redo()} data-testid="sw-inline-redo" title="Redo">↷</button>
      </div>

      {message && <div className="sw-inline__message">{message}</div>}

      <div className="sw-inline__editor" data-testid="sw-inline-editor">
        {editor ? <EditorContent editor={editor} /> : <p className="muted">Loading editor...</p>}
      </div>
    </div>
  );
}
