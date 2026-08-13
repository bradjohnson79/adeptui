import { Extension } from "@tiptap/core";
import Paragraph from "@tiptap/extension-paragraph";
import { mergeAttributes } from "@tiptap/core";

const INDENT_STEP = 40;
const MAX_INDENT = 320;

function currentIndent(attrs: { indent?: number | null } | undefined): number {
  const v = Number(attrs?.indent);
  return Number.isFinite(v) && v > 0 ? Math.min(v, MAX_INDENT) : 0;
}

export const IndentParagraph = Paragraph.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      indent: {
        default: 0,
        parseHTML: (el) => {
          const raw = (el as HTMLElement).getAttribute("data-indent");
          const n = raw ? Number(raw) : 0;
          return Number.isFinite(n) && n > 0 ? Math.min(n, MAX_INDENT) : 0;
        },
        renderHTML: (attrs) => {
          const n = currentIndent(attrs as { indent?: number | null });
          return n > 0 ? { "data-indent": String(n) } : {};
        },
      },
    };
  },
  renderHTML({ HTMLAttributes }) {
    const n = currentIndent(HTMLAttributes as { indent?: number | null });
    const style = n > 0 ? `margin-left: ${n}px` : null;
    const merged = mergeAttributes(HTMLAttributes, style ? { style } : {});
    return ["p", merged, 0];
  },
});

export const IndentKeys = Extension.create({
  name: "indentKeys",
  addKeyboardShortcuts() {
    return {
      Tab: ({ editor }) => {
        if (!editor.isActive("paragraph")) return false;
        const attrs = editor.getAttributes("paragraph") as { indent?: number | null };
        const next = Math.min(currentIndent(attrs) + INDENT_STEP, MAX_INDENT);
        editor.commands.updateAttributes("paragraph", { indent: next });
        return true;
      },
      "Shift-Tab": ({ editor }) => {
        if (!editor.isActive("paragraph")) return false;
        const attrs = editor.getAttributes("paragraph") as { indent?: number | null };
        const cur = currentIndent(attrs);
        if (cur <= 0) return true;
        const next = Math.max(cur - INDENT_STEP, 0);
        editor.commands.updateAttributes("paragraph", { indent: next });
        return true;
      },
    };
  },
});

export { INDENT_STEP, MAX_INDENT };
