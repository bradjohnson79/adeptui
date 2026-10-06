import { useEffect, useRef } from "react";
import { useEditor, EditorContent } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import { Placeholder } from "@tiptap/extension-placeholder";
import { sanitizeHtml } from "../scriptwriter/sanitizeHtml";
import { toEditorHtml } from "./canonicalStory";

const STORY_PLACEHOLDER =
  "Write the story here — synopsis, world, characters, and arcs. Scene dialogue belongs in Script.";

type Props = {
  html: string;
  onChange: (html: string) => void;
  placeholder?: string;
  testId?: string;
  compact?: boolean;
};

/** Formatted story-treatment body. Not screenplay formatting. */
export function StoryRichBody({
  html,
  onChange,
  placeholder = STORY_PLACEHOLDER,
  testId = "story-rich-body",
  compact = false,
}: Props) {
  const hydrating = useRef(true);
  const lastSent = useRef(html);

  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        codeBlock: false,
        code: false,
        strike: false,
      }),
      Underline,
      Placeholder.configure({ placeholder }),
    ],
    content: toEditorHtml(html),
    onUpdate: ({ editor: ed }) => {
      if (hydrating.current) return;
      const next = sanitizeHtml(ed.getHTML());
      lastSent.current = next;
      onChange(next);
    },
  });

  useEffect(() => {
    if (!editor) return;
    hydrating.current = false;
  }, [editor]);

  useEffect(() => {
    if (!editor) return;
    if (html === lastSent.current) return;
    hydrating.current = true;
    editor.commands.setContent(toEditorHtml(html));
    lastSent.current = html;
    hydrating.current = false;
  }, [editor, html]);

  if (!editor) return null;

  return (
    <div className={compact ? "story-rich-body story-rich-body--compact" : "story-rich-body"} data-testid={testId}>
      <div className="sw-richtext-toolbar" data-testid={`${testId}-toolbar`}>
        <button type="button" className="sw-rt-btn" onClick={() => editor.chain().focus().toggleBold().run()} title="Bold">
          B
        </button>
        <button type="button" className="sw-rt-btn" onClick={() => editor.chain().focus().toggleItalic().run()} title="Italic">
          I
        </button>
        <button type="button" className="sw-rt-btn" onClick={() => editor.chain().focus().toggleUnderline().run()} title="Underline">
          U
        </button>
        <span className="sw-rt-sep" />
        <button
          type="button"
          className={editor.isActive("heading", { level: 1 }) ? "sw-rt-btn is-active" : "sw-rt-btn"}
          onClick={() => editor.chain().focus().toggleHeading({ level: 1 }).run()}
          title="Heading"
        >
          H1
        </button>
        <button
          type="button"
          className={editor.isActive("heading", { level: 2 }) ? "sw-rt-btn is-active" : "sw-rt-btn"}
          onClick={() => editor.chain().focus().toggleHeading({ level: 2 }).run()}
          title="Subheading"
        >
          H2
        </button>
        <span className="sw-rt-sep" />
        <button
          type="button"
          className={editor.isActive("bulletList") ? "sw-rt-btn is-active" : "sw-rt-btn"}
          onClick={() => editor.chain().focus().toggleBulletList().run()}
          title="List"
        >
          •
        </button>
        <button
          type="button"
          className={editor.isActive("orderedList") ? "sw-rt-btn is-active" : "sw-rt-btn"}
          onClick={() => editor.chain().focus().toggleOrderedList().run()}
          title="Numbered list"
        >
          1.
        </button>
      </div>
      <EditorContent editor={editor} />
    </div>
  );
}
