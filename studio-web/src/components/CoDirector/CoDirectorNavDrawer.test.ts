import assert from "node:assert/strict";
import test from "node:test";
import { buildNavEntries } from "./navEntries.ts";

test("nav entries omit mis-aliased Storyboards / Props / Exports", () => {
  const entries = buildNavEntries("proj-1");
  const ids = entries.map((e) => e.id);
  assert.ok(ids.includes("scripts"));
  assert.ok(ids.includes("characters"));
  assert.ok(ids.includes("approvals"));
  assert.ok(ids.includes("plans"));
  assert.ok(ids.includes("wiki"));
  assert.equal(entries.find((e) => e.id === "wiki")?.label, "Wiki");
  assert.equal(entries.find((e) => e.id === "content")?.label, "Project Focus");
  assert.ok(!ids.includes("storyboards"));
  assert.ok(!ids.includes("props"));
  assert.ok(!ids.includes("exports"));
});

test("jobs entry stays available when project bound", () => {
  const jobs = buildNavEntries("proj-1").find((e) => e.id === "jobs");
  assert.ok(jobs);
  assert.equal(jobs?.deferred, undefined);
  assert.equal(jobs?.target.kind, "content");
  if (jobs?.target.kind === "content") {
    assert.equal(jobs.target.tab, "jobs");
  }
});

test("no-project nav stays honest", () => {
  const entries = buildNavEntries(undefined);
  assert.equal(entries.find((e) => e.id === "project")?.label, "No Project Selected");
  assert.ok(!entries.some((e) => e.id === "approvals"));
});
