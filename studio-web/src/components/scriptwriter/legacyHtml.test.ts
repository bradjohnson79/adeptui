import assert from "node:assert/strict";
import test from "node:test";
import { elementsToHtml, isBlankHtml } from "./legacyHtml";
import type { ScriptElement } from "./types";

/**
 * legacyHtml — pure-logic unit tests for the legacy elements→HTML converter
 * and the blank-HTML detector. No DOM required.
 */

function mkEl(overrides: Partial<ScriptElement> & Pick<ScriptElement, "id" | "type" | "text" | "order">): ScriptElement {
  return { ...overrides };
}

test("elementsToHtml returns an empty paragraph for an empty array", () => {
  assert.equal(elementsToHtml([]), "<p></p>");
  assert.equal(elementsToHtml(undefined as unknown as ScriptElement[]), "<p></p>");
});

test("elementsToHtml converts a small elements array to HTML with paragraph breaks", () => {
  const elements: ScriptElement[] = [
    mkEl({ id: "e1", type: "scene_heading", text: "INT. CAFE - DAY", order: 0 }),
    mkEl({ id: "e2", type: "action", text: "Rain on glass.", order: 1 }),
    mkEl({ id: "e3", type: "character", text: "KORRI", order: 2 }),
    mkEl({ id: "e4", type: "parenthetical", text: "quietly", order: 3 }),
    mkEl({ id: "e5", type: "dialogue", text: "We keep going.", order: 4 }),
    mkEl({ id: "e6", type: "transition", text: "CUT TO:", order: 5 }),
    mkEl({ id: "e7", type: "shot", text: "CLOSE ON KORRI", order: 6 }),
  ];
  const html = elementsToHtml(elements);

  // scene heading -> h1
  assert.ok(html.includes("<h1>INT. CAFE - DAY</h1>"), "scene_heading must be an h1");
  // action -> <p>
  assert.ok(html.includes("<p>Rain on glass.</p>"), "action must be a plain <p>");
  // character -> uppercased + indented <p>
  assert.ok(html.includes("text-transform: uppercase;"), "character must be uppercased");
  assert.ok(html.includes("KORRI"), "character text must be present");
  // parenthetical -> italic <p>
  assert.ok(html.includes("font-style: italic;"), "parenthetical must be italic");
  assert.ok(html.includes("quietly"));
  // dialogue -> indented <p>
  assert.ok(html.includes("We keep going."), "dialogue text must be present");
  // transition -> right-aligned upper <p>
  assert.ok(html.includes("text-align: right;"), "transition must be right-aligned");
  assert.ok(html.includes("CUT TO:"));
  // shot -> uppercased + bold <p>
  assert.ok(html.includes("CLOSE ON KORRI"), "shot text must be present");
});

test("elementsToHtml escapes HTML-unsafe text", () => {
  const elements: ScriptElement[] = [
    mkEl({ id: "e1", type: "action", text: "5 < 10 & 2 > 1", order: 0 }),
  ];
  const html = elementsToHtml(elements);
  assert.ok(html.includes("&lt;"), "< must be escaped");
  assert.ok(html.includes("&gt;"), "> must be escaped");
  assert.ok(html.includes("&amp;"), "& must be escaped");
  assert.ok(!html.includes("5 < 10"), "raw < must not survive");
});

test("elementsToHtml emits elements in array order", () => {
  // The TS converter does not re-sort by `order`; it emits in array order.
  // Callers are expected to pre-sort. Verify the array order is preserved.
  const elements: ScriptElement[] = [
    mkEl({ id: "e1", type: "scene_heading", text: "FIRST", order: 0 }),
    mkEl({ id: "e2", type: "action", text: "second", order: 1 }),
  ];
  const html = elementsToHtml(elements);
  const firstIdx = html.indexOf("FIRST");
  const secondIdx = html.indexOf("second");
  assert.ok(firstIdx > -1 && secondIdx > -1);
  assert.ok(firstIdx < secondIdx, "array order must be preserved");
});

test("round-trip preserves text content via tags", () => {
  const elements: ScriptElement[] = [
    mkEl({ id: "e1", type: "scene_heading", text: "INT. CAFE - DAY", order: 0 }),
    mkEl({ id: "e2", type: "action", text: "Rain on glass.", order: 1 }),
  ];
  const html = elementsToHtml(elements);
  // Strip tags and confirm the text content survives intact.
  const stripped = html.replace(/<[^>]*>/g, "");
  assert.equal(stripped, "INT. CAFE - DAYRain on glass.");
});

test("isBlankHtml detects empty / whitespace-only HTML", () => {
  assert.equal(isBlankHtml(""), true);
  assert.equal(isBlankHtml(null), true);
  assert.equal(isBlankHtml(undefined), true);
  assert.equal(isBlankHtml("<p></p>"), true);
  assert.equal(isBlankHtml("   <p>   </p>   "), true);
  assert.equal(isBlankHtml("<p><br></p>"), true, "<br> with no text is blank");
});

test("isBlankHtml returns false for HTML with text content", () => {
  assert.equal(isBlankHtml("<p>Rain on glass.</p>"), false);
  assert.equal(isBlankHtml("<h1>Title</h1>"), false);
  assert.equal(isBlankHtml("<p>  text  </p>"), false);
});
