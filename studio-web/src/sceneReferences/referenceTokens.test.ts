import assert from "node:assert/strict";
import test from "node:test";
import {
  bindingAcceptedOnTrack,
  displayToken,
  formatAutocompleteRow,
  parseTokenQuery,
  remapBindingIdsToSceneScope,
  resolveBinding,
  sanitizeAlias,
  sortBindingsForTrack,
  tokenSummary,
} from "./referenceTokens.ts";

test("sanitizeAlias strips prefix and spaces", () => {
  assert.equal(sanitizeAlias("*Korri Pose Video"), "KorriPoseVideo");
  assert.equal(sanitizeAlias("@Korri"), "Korri");
  assert.equal(sanitizeAlias("#Schnick Counter"), "SchnickCounter");
});

test("displayToken uses typed prefixes", () => {
  assert.equal(displayToken("Korri", "entity"), "@Korri");
  assert.equal(displayToken("SchnickCounterWide", "image"), "#SchnickCounterWide");
  assert.equal(displayToken("KorriPoseVideo", "video"), "*KorriPoseVideo");
});

test("autocomplete rows include token and type", () => {
  assert.equal(
    formatAutocompleteRow({
      id: "1",
      asset_id: "a",
      alias: "KorriPoseVideo",
      media_kind: "video",
      reference_type: "video",
      duration_sec: 4.8,
    }),
    "*KorriPoseVideo · Video · 4.8s",
  );
  assert.equal(
    formatAutocompleteRow({
      id: "2",
      asset_id: "b",
      alias: "Korri",
      media_kind: "entity",
      reference_type: "character",
    }),
    "@Korri · Character",
  );
});

test("wrong type is rejected per track", () => {
  const video = {
    id: "v",
    asset_id: "vid",
    alias: "KorriPoseVideo",
    media_kind: "video" as const,
    reference_type: "video",
  };
  const image = {
    id: "i",
    asset_id: "img",
    alias: "SchnickCounterWide",
    media_kind: "image" as const,
    reference_type: "image",
  };
  assert.equal(bindingAcceptedOnTrack(video, "videoReference"), true);
  assert.equal(bindingAcceptedOnTrack(image, "videoReference"), false);
  assert.equal(bindingAcceptedOnTrack(video, "imageReference"), false);
  assert.equal(bindingAcceptedOnTrack(image, "imageReference"), true);
  assert.equal(bindingAcceptedOnTrack(video, "prompt"), true);
  assert.equal(bindingAcceptedOnTrack(image, "prompt"), true);
  assert.equal(bindingAcceptedOnTrack(video, "camera"), true);
  assert.equal(bindingAcceptedOnTrack(image, "camera"), false);
  assert.equal(bindingAcceptedOnTrack({ ...image, media_kind: "entity", reference_type: "character", alias: "Korri" }, "camera"), true);
  assert.equal(bindingAcceptedOnTrack({ ...image, media_kind: "entity", reference_type: "prop", alias: "Cup" }, "camera"), true);
  assert.equal(bindingAcceptedOnTrack({ ...image, media_kind: "entity", reference_type: "character", alias: "Korri" }, "lipsyncSpeaker"), true);
  assert.equal(bindingAcceptedOnTrack({ ...image, media_kind: "entity", reference_type: "prop", alias: "Cup" }, "lipsyncSpeaker"), false);
  assert.equal(parseTokenQuery("*Kor").prefix, "*");
});

test("token summary stays compact and flags missing bindings", () => {
  const korri = {
    id: "k",
    asset_id: "ak",
    alias: "Korri",
    media_kind: "entity" as const,
    reference_type: "character",
  };
  const bar = {
    id: "b",
    asset_id: "ab",
    alias: "Bar",
    media_kind: "image" as const,
    reference_type: "image",
  };
  assert.equal(tokenSummary(["k", "b", "missing", "x", "y"], [korri, bar]), "@Korri #Bar Broken Reference +2");
});

test("camera autocomplete lists characters before videos", () => {
  const video = {
    id: "v",
    asset_id: "vid",
    alias: "Macarena",
    media_kind: "video" as const,
    reference_type: "video",
  };
  const korri = {
    id: "k",
    asset_id: "ak",
    alias: "Korri",
    media_kind: "entity" as const,
    reference_type: "character",
  };
  const cup = {
    id: "p",
    asset_id: "ap",
    alias: "Cup",
    media_kind: "entity" as const,
    reference_type: "prop",
  };
  const sorted = sortBindingsForTrack([video, cup, korri], "camera");
  assert.deepEqual(sorted.map((item) => item.alias), ["Korri", "Cup", "Macarena"]);
});

test("sibling-scope project id resolves to scene-scope row by asset_id", () => {
  const sceneRow = {
    id: "scene-bind",
    asset_id: "asset-k",
    alias: "KorriPoseVideo",
    media_kind: "video" as const,
    reference_type: "video",
    scope_type: "scene",
  };
  const projectRow = {
    id: "project-bind",
    asset_id: "asset-k",
    alias: "KorriDanceMotion",
    media_kind: "video" as const,
    reference_type: "video",
    scope_type: "project",
  };
  const resolved = resolveBinding("project-bind", [sceneRow], [projectRow]);
  assert.equal(resolved?.id, "scene-bind");
  assert.equal(resolved?.alias, "KorriPoseVideo");
  assert.deepEqual(
    remapBindingIdsToSceneScope(["project-bind"], [sceneRow], [projectRow]),
    ["scene-bind"],
  );
  assert.equal(tokenSummary(["project-bind"], [sceneRow], 3, [projectRow]), "*KorriPoseVideo");
});
