import { useCallback, useEffect, useRef, useState } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import type { SaveState, ScriptElement } from "../../scriptwriter/types";
import { ScreenplayParagraph, ScreenplayKeys, elementsToDocJson, docJsonToElements } from "../../scriptwriter/screenplayExtension";
import { api, ApiError } from "../../../api";
import "./ScriptwriterInline.css";

export type InlineEditorElementType = "scene_heading" | "action" | "character" | "dialogue" | "parenthetical" | "shot" | "transition" | "general";

const ELEMENT_LABELS: Record<string, string> = {
  scene_heading: "Scene Heading",
  action: "Action",
  character: "Character",
  dialogue: "Dialogue",
  parenthetical: "Parenthetical",
  shot: "Camera / Shot",
  transition: "Transition",
  general: "General Text / Note",
};

const ELEMENT_OPTIONS = [
  "scene_heading", "action", "character", "dialogue",
  "parenthetical", "shot", "transition", "general",
] as const;

type Props = {
  projectId: string;
  onOpenFull?: () => void;
};

export function ScriptwriterInlineEditor({ projectId, onOpenFull }: Props) {
  const [docId, setDocId] = useState<string | null>(null);
  const [title, setTitle] = useState("Untitled Script");
  const [stats, setStats] = useState<Record<string, number>>({});
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [message, setMessage] = useState<string | null>(null);
  const [currentType, setCurrentType] = useState<string>("action");
  const hydrating = useRef(false);
  const saveTimer = useRef<number | null>(null);
  const latestRevisionRef = useRef<number | undefined>(undefined);
  const loadedRef = useRef(false);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({ paragraph: false }),
      ScreenplayParagraph,
      ScreenplayKeys,
    ],
    content: elementsToDocJson([]),
    onUpdate: ({ editor: ed }) => {
      if (hydrating.current || !docId) return;
      setSaveState("unsaved");
      if (saveTimer.current) window.clearTimeout(saveTimer.current);
      saveTimer.current = window.setTimeout(() => {
        void (async () => {
          if (!docId) return;
          try {
            setSaveState("saving");
            const elements = docJsonToElements(ed.getJSON() as { content?: Array<Record<string, unknown>> });
            const res = await api.scriptwriter.autosave(projectId, docId, {
              elements,
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
                const d = fresh.document as unknown as { id: string; title: string; elements?: ScriptElement[]; revision: number };
                if (d.id) {
                  latestRevisionRef.current = d.revision;
                  setDocId(d.id);
                  if (d.title) setTitle(d.title);
                }
                if (editor && d.elements) {
                  hydrating.current = true;
                  editor.commands.setContent(elementsToDocJson(d.elements));
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
    const fn = () => {
      const t = (editor.getAttributes("paragraph").elementType || "action") as string;
      setCurrentType(t);
    };
    editor.on("selectionUpdate", fn);
    return () => { editor.off("selectionUpdate", fn); };
  }, [editor]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const bundle = await api.scriptwriter.studio(projectId);
        if (cancelled) return;
        const d = bundle.document as unknown as { id: string; title: string; elements?: ScriptElement[]; revision: number; updatedAt?: string };
        if (d.id) {
          setDocId(d.id);
          setTitle(d.title);
          latestRevisionRef.current = d.revision;
        }
        setStats((bundle.stats || {}) as Record<string, number>);
        if (editor && d.elements) {
          hydrating.current = true;
          editor.commands.setContent(elementsToDocJson(d.elements));
          hydrating.current = false;
          loadedRef.current = true;
        }
      } catch { /* ignore */ }
    })();
    return () => { cancelled = true; };
  }, [projectId, editor]);

  const normalizeText = (text: string, type: string): string => {
    if (type === "parenthetical" && !(text.startsWith("(") && text.endsWith(")"))) {
      return "(" + text + ")";
    }
    if (type === "shot" && !(text.startsWith("[") && text.endsWith("]"))) {
      return "[" + text + "]";
    }
    return text;
  };

  const handleFormatChange = useCallback((newType: string) => {
    if (!editor) return;
    const { $from } = editor.state.selection;
    const node = $from.parent;
    if (node && node.type.name === "paragraph") {
      const original = node.textContent || "";
      const normalized = normalizeText(original, newType);
      if (normalized !== original) {
        editor
          .chain()
          .focus()
          .updateAttributes("paragraph", { elementType: newType })
          .insertContentAt({ from: $from.start(), to: $from.end() }, normalized)
          .run();
        setCurrentType(newType);
        return;
      }
    }
    editor.chain().focus().updateAttributes("paragraph", { elementType: newType }).run();
    setCurrentType(newType);
  }, [editor]);

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
        <label className="sw-inline__format-label">Element:</label>
        <select
          className="sw-inline__format-select"
          value={currentType}
          onChange={(e) => handleFormatChange(e.target.value)}
          data-testid="sw-inline-format-select"
        >
          {ELEMENT_OPTIONS.map((t) => (
            <option key={t} value={t}>{ELEMENT_LABELS[t] || t}</option>
          ))}
        </select>
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
