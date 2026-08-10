import { Extension, mergeAttributes } from "@tiptap/core";
import Paragraph from "@tiptap/extension-paragraph";
import type { ScriptElement, ScriptElementType } from "./types";

const ENTER_NEXT: Record<string, ScriptElementType> = {
  scene_heading: "action",
  action: "action",
  character: "dialogue",
  dialogue: "action",
  parenthetical: "dialogue",
  transition: "scene_heading",
};

const TAB_CYCLE: ScriptElementType[] = [
  "scene_heading",
  "action",
  "character",
  "parenthetical",
  "dialogue",
  "transition",
];

/** Keep node name `paragraph` so StarterKit Document content (`paragraph block*`) resolves. */
export const ScreenplayParagraph = Paragraph.extend({
  addAttributes() {
    return {
      ...this.parent?.(),
      elementType: {
        default: "action",
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-element-type") || "action",
        renderHTML: (attrs) => ({ "data-element-type": attrs.elementType }),
      },
      elementId: {
        default: null,
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-element-id"),
        renderHTML: (attrs) => (attrs.elementId ? { "data-element-id": attrs.elementId } : {}),
      },
      sceneNumber: {
        default: null,
        parseHTML: (el) => (el as HTMLElement).getAttribute("data-scene-number"),
        renderHTML: (attrs) => (attrs.sceneNumber ? { "data-scene-number": attrs.sceneNumber } : {}),
      },
    };
  },
  renderHTML({ HTMLAttributes }) {
    const t = HTMLAttributes.elementType || "action";
    return ["p", mergeAttributes(HTMLAttributes, { class: `sp-el sp-el--${t}`, "data-element-type": t }), 0];
  },
});

export const ScreenplayKeys = Extension.create({
  name: "screenplayKeys",
  addKeyboardShortcuts() {
    return {
      Enter: ({ editor }) => {
        const type = (editor.getAttributes("paragraph").elementType || "action") as ScriptElementType;
        const next = ENTER_NEXT[type] || "action";
        editor.commands.splitBlock();
        editor.commands.updateAttributes("paragraph", {
          elementType: next,
          elementId: crypto.randomUUID(),
          sceneNumber: null,
        });
        return true;
      },
      Tab: ({ editor }) => {
        const type = (editor.getAttributes("paragraph").elementType || "action") as ScriptElementType;
        const idx = TAB_CYCLE.indexOf(type);
        const next = TAB_CYCLE[(idx < 0 ? 0 : idx + 1) % TAB_CYCLE.length];
        editor.commands.updateAttributes("paragraph", { elementType: next });
        return true;
      },
      "Shift-Tab": ({ editor }) => {
        const type = (editor.getAttributes("paragraph").elementType || "action") as ScriptElementType;
        const idx = TAB_CYCLE.indexOf(type);
        const next = TAB_CYCLE[(idx < 0 ? 0 : idx - 1 + TAB_CYCLE.length) % TAB_CYCLE.length];
        editor.commands.updateAttributes("paragraph", { elementType: next });
        return true;
      },
      "Mod-1": ({ editor }) => {
        editor.commands.updateAttributes("paragraph", { elementType: "scene_heading" });
        return true;
      },
      "Mod-2": ({ editor }) => {
        editor.commands.updateAttributes("paragraph", { elementType: "action" });
        return true;
      },
      "Mod-3": ({ editor }) => {
        editor.commands.updateAttributes("paragraph", { elementType: "character" });
        return true;
      },
      "Mod-4": ({ editor }) => {
        editor.commands.updateAttributes("paragraph", { elementType: "dialogue" });
        return true;
      },
      "Mod-5": ({ editor }) => {
        editor.commands.updateAttributes("paragraph", { elementType: "parenthetical" });
        return true;
      },
      "Mod-6": ({ editor }) => {
        editor.commands.updateAttributes("paragraph", { elementType: "transition" });
        return true;
      },
    };
  },
});

export function elementsToDocJson(elements: ScriptElement[]) {
  return {
    type: "doc",
    content: (elements.length ? elements : [{ id: crypto.randomUUID(), type: "action" as const, text: "", order: 0 }]).map(
      (el) => ({
        type: "paragraph",
        attrs: {
          elementType: el.type,
          elementId: el.id,
          sceneNumber: el.sceneNumber || null,
        },
        content: el.text ? [{ type: "text", text: el.text }] : [],
      }),
    ),
  };
}

export function docJsonToElements(json: { content?: Array<Record<string, unknown>> }): ScriptElement[] {
  const content = json.content || [];
  return content.map((node, order) => {
    const attrs = (node.attrs || {}) as Record<string, unknown>;
    const texts: string[] = [];
    const walk = (n: Record<string, unknown>) => {
      if (n.type === "text" && typeof n.text === "string") texts.push(n.text);
      const kids = n.content as Array<Record<string, unknown>> | undefined;
      kids?.forEach(walk);
    };
    walk(node);
    return {
      id: String(attrs.elementId || crypto.randomUUID()),
      type: (attrs.elementType as ScriptElementType) || "action",
      text: texts.join(""),
      order,
      sceneNumber: (attrs.sceneNumber as string) || null,
    };
  });
}
