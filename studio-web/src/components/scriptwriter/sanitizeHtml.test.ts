import assert from "node:assert/strict";
import test from "node:test";
import { SANITIZE_POLICY } from "./sanitizeHtml";

/**
 * sanitizeHtml — pure-logic unit tests for the sanitize policy.
 *
 * DOMPurify.sanitize requires a live DOM, so no jsdom harness exists in this
 * repo. These tests cover the exported SANITIZE_POLICY data: which tags / attrs
 * are allowed or forbidden, and which URI schemes are permitted. Full sanitization
 * behavior is covered by the Playwright E2E suite that runs against a real
 * browser DOM.
 */

test("sanitize policy allows prose and structural tags", () => {
  for (const tag of ["p", "strong", "em", "u", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "li", "blockquote", "hr"]) {
    assert.ok(
      SANITIZE_POLICY.ALLOWED_TAGS.includes(tag),
      `expected ${tag} to be allowed`,
    );
  }
});

test("sanitize policy blocks script and iframe", () => {
  for (const tag of ["script", "iframe"]) {
    assert.ok(
      SANITIZE_POLICY.FORBID_TAGS.includes(tag),
      `expected ${tag} to be forbidden`,
    );
    assert.ok(
      !SANITIZE_POLICY.ALLOWED_TAGS.includes(tag),
      `expected ${tag} to NOT be in ALLOWED_TAGS`,
    );
  }
});

test("sanitize policy blocks other dangerous embed/object/form tags", () => {
  for (const tag of ["object", "embed", "form", "input", "style", "link", "meta"]) {
    assert.ok(
      SANITIZE_POLICY.FORBID_TAGS.includes(tag),
      `expected ${tag} to be forbidden`,
    );
  }
});

test("sanitize policy forbids inline event handlers (on*)", () => {
  for (const attr of ["onerror", "onload", "onclick", "onmouseover", "onfocus", "onblur", "onchange", "onsubmit"]) {
    assert.ok(
      SANITIZE_POLICY.FORBID_ATTR.includes(attr),
      `expected ${attr} to be forbidden`,
    );
    assert.ok(
      !SANITIZE_POLICY.ALLOWED_ATTR.includes(attr),
      `expected ${attr} to NOT be allowed`,
    );
  }
});

test("sanitize policy blocks javascript: URIs", () => {
  assert.ok(
    !SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("javascript:alert(1)"),
    "javascript: scheme must be rejected",
  );
  assert.ok(
    !SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("JaVaScRiPt:alert(1)"),
    "javascript: scheme must be rejected case-insensitively",
  );
});

test("sanitize policy blocks data: URIs", () => {
  assert.ok(
    !SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("data:text/html,<script>alert(1)</script>"),
    "data: scheme must be rejected",
  );
});

test("sanitize policy blocks vbscript: URIs", () => {
  assert.ok(
    !SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("vbscript:msgbox(1)"),
    "vbscript: scheme must be rejected",
  );
});

test("sanitize policy allows safe http(s) and relative URIs", () => {
  assert.ok(SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("https://example.com/img.png"));
  assert.ok(SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("/media/asset-1.png"));
  assert.ok(SANITIZE_POLICY.ALLOWED_URI_REGEXP.test("relative/path.png"));
});

test("sanitize policy does not allow data-* attributes", () => {
  assert.equal(SANITIZE_POLICY.ALLOW_DATA_ATTR, false);
  assert.ok(!SANITIZE_POLICY.ALLOWED_ATTR.includes("data-testid"));
});

test("sanitize policy allows a limited set of presentation attributes", () => {
  for (const attr of ["style", "align", "class"]) {
    assert.ok(
      SANITIZE_POLICY.ALLOWED_ATTR.includes(attr),
      `expected ${attr} to be allowed`,
    );
  }
});
