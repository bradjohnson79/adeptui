import assert from "node:assert/strict";
import test from "node:test";
import type { Project } from "../../types";
import {
  buildBrandCheck,
  collectBrandResults,
  createDefaultCampaign,
  parseBrandStudioState,
  serializeBrandStudioState,
} from "./brandStudioModel";

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "proj-brand",
    name: "Spark Cola",
    engine_default: "auto",
    global_prompt: "",
    negative_prompt: "",
    width: 1024,
    height: 1024,
    fps: 24,
    seed: 1,
    preset: "quality",
    vram_gb: 24,
    spatial_map_json: "{}",
    render_safety_json: "",
    learning_json: "",
    learning_enabled_json: "",
    preview_settings_json: "",
    description: "",
    company: "",
    director_name: "",
    version: "1.0",
    tags_json: "[]",
    archived: 0,
    defaults_json: "",
    settings_json: "",
    primary_project_type: "commercial",
    project_traits_json: "[]",
    resolved_profile_json: "{}",
    project_type_version: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    scenes: [],
    assets: [],
    ...overrides,
  };
}

test("brand studio state merges defaults with saved settings", () => {
  const project = makeProject({
    settings_json: JSON.stringify({
      brandStudio: {
        version: 1,
        activeCampaign: {
          brief: "Make it pop.",
          campaignType: "social",
          brandKit: {
            requiredWording: "Zero sugar",
          },
        },
        results: [],
      },
    }),
  });

  const state = parseBrandStudioState(project);
  assert.equal(state.activeCampaign.brief, "Make it pop.");
  assert.equal(state.activeCampaign.campaignType, "social");
  assert.equal(state.activeCampaign.brandKit.requiredWording, "Zero sugar");
  assert.equal(state.activeCampaign.heroFormat, "Square 1:1");
});

test("brand studio state serializes without dropping other settings", () => {
  const project = makeProject({
    settings_json: JSON.stringify({
      somethingElse: { ok: true },
    }),
  });
  const state = parseBrandStudioState(project);
  state.activeCampaign.name = "Holiday Burst";
  const saved = JSON.parse(serializeBrandStudioState(project.settings_json, state));
  assert.equal(saved.somethingElse.ok, true);
  assert.equal(saved.brandStudio.activeCampaign.name, "Holiday Burst");
});

test("brand results group saved brand assets and approved items", () => {
  const project = makeProject({
    assets: [
      {
        id: "asset-1",
        project_id: "proj-brand",
        tag: "Launch concept",
        kind: "image",
        filename: "launch.png",
        path: "C:/tmp/launch.png",
        comfy_name: "",
        created_at: "2026-08-01T10:00:00.000Z",
        prompt_meta_json: JSON.stringify({
          op: "brand_generate",
          brandStudio: {
            campaignId: "brand-campaign-proj-brand",
            title: "Launch concept",
            heroFormat: "Story 9:16",
            resultLane: "formats",
          },
        }),
      },
    ],
  });
  const campaign = createDefaultCampaign(project);
  campaign.approvedAssetIds = ["asset-1"];
  const results = collectBrandResults(project, campaign, []);
  assert.equal(results.length, 1);
  assert.equal(results[0].lane, "approved");
  assert.equal(results[0].format, "Story 9:16");
});

test("brand check counts visual locks and canon guidance", () => {
  const campaign = createDefaultCampaign(makeProject());
  campaign.brandKit.logoAssetId = "logo-1";
  campaign.brandKit.productAssetId = "product-1";
  campaign.brandKit.requiredWording = "New limited drop";
  campaign.brandKit.bibleSummary = "Crisp neon youth culture with playful confidence.";
  const summary = buildBrandCheck(campaign);
  assert.equal(summary.total, 5);
  assert.equal(summary.ready, 5);
});
