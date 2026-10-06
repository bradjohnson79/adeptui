import { describe, expect, it } from "vitest";
import { consumePoseCraftHandoff, posecraftHandoffKey } from "./posecraftHandoff";

describe("PoseCraft CIS handoff", () => {
  it("reads and consumes adept.posecraft.handoff.{projectId}", () => {
    const store = new Map<string, string>();
    const storage = {
      getItem: (k: string) => store.get(k) ?? null,
      setItem: (k: string, v: string) => void store.set(k, v),
      removeItem: (k: string) => void store.delete(k),
    } as Storage;
    storage.setItem(
      posecraftHandoffKey("proj-1"),
      JSON.stringify({ imageAssetId: "snap-asset", snapshotId: "snap-1", honestyLabel: "PoseCraft Snapshot" }),
    );
    const handoff = consumePoseCraftHandoff("proj-1", storage);
    expect(handoff?.imageAssetId).toBe("snap-asset");
    expect(storage.getItem(posecraftHandoffKey("proj-1"))).toBeNull();
  });
});
