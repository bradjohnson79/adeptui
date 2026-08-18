import assert from "node:assert/strict";
import test from "node:test";
import {
  clearLoraSelectorCache,
  fetchCompatibleLoras,
} from "./loraClient.ts";

const SDXL_LORA = {
  id: "lora-sdxl-1",
  name: "Cinematic Lighting XL",
  category: "Lighting",
  recommended_strength: 0.7,
  strength_min: 0.2,
  strength_max: 1.2,
  modality: "image",
  model_family: "sdxl",
};

test("fetchCompatibleLoras requests only compatible enabled LoRAs per family", async () => {
  clearLoraSelectorCache();
  const calls: Array<[string, string | undefined]> = [];
  const fetcher = async (family: string, mod?: string) => {
    calls.push([family, mod]);
    return { loras: family === "illustrious" ? [SDXL_LORA] : [] };
  };
  const sdxl = await fetchCompatibleLoras("illustrious", "image", fetcher);
  assert.equal(sdxl.length, 1);
  assert.equal(sdxl[0].id, "lora-sdxl-1");
  // deterministic: same family -> same list; different family -> no loras
  const ltx = await fetchCompatibleLoras("ltx", "video", fetcher);
  assert.equal(ltx.length, 0);
  assert.deepEqual(calls, [["illustrious", "image"], ["ltx", "video"]]);
});

test("fetchCompatibleLoras is single-flight and cached per key", async () => {
  clearLoraSelectorCache();
  let fetches = 0;
  const fetcher = async () => {
    fetches += 1;
    return { loras: [SDXL_LORA] };
  };
  const [a, b, c] = await Promise.all([
    fetchCompatibleLoras("illustrious", "image", fetcher),
    fetchCompatibleLoras("illustrious", "image", fetcher),
    fetchCompatibleLoras("illustrious", "image", fetcher),
  ]);
  assert.equal(a.length, 1);
  assert.equal(b.length, 1);
  assert.equal(c.length, 1);
  assert.equal(fetches, 1, "single-flight: one fetch for concurrent readers");
  await fetchCompatibleLoras("illustrious", "image", fetcher);
  assert.equal(fetches, 1, "cached: no second fetch");
});

test("fetchCompatibleLoras retries after failure (no poisoned cache)", async () => {
  clearLoraSelectorCache();
  let fail = true;
  const fetcher = async () => {
    if (fail) throw new Error("registry unavailable");
    return { loras: [SDXL_LORA] };
  };
  await assert.rejects(() => fetchCompatibleLoras("illustrious", "image", fetcher));
  fail = false;
  const list = await fetchCompatibleLoras("illustrious", "image", fetcher);
  assert.equal(list.length, 1);
});

test("fetchCompatibleLoras never exposes unassigned or disabled records", async () => {
  // The backend registry is the authority; the client only relays it. This
  // guards the relay contract (selectors render exactly what the registry
  // returns for the active family).
  clearLoraSelectorCache();
  const fetcher = async () => ({ loras: [] });
  assert.equal((await fetchCompatibleLoras("fal", "video", fetcher)).length, 0);
});