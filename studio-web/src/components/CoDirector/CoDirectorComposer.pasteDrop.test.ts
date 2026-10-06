import { describe, expect, it } from "vitest";
import { filesFromClipboardItems, filesFromDataTransfer, isComposerImageFile } from "./CoDirectorComposer";

function fakeFile(name: string, type: string): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type });
}

describe("CoDirectorComposer paste/drop helpers", () => {
  it("accepts png jpeg webp and rejects other files", () => {
    expect(isComposerImageFile(fakeFile("a.png", "image/png"))).toBe(true);
    expect(isComposerImageFile(fakeFile("a.jpg", "image/jpeg"))).toBe(true);
    expect(isComposerImageFile(fakeFile("a.webp", "image/webp"))).toBe(true);
    expect(isComposerImageFile(fakeFile("notes.txt", "text/plain"))).toBe(false);
  });

  it("reads image files from a data transfer", () => {
    const dt = {
      files: [fakeFile("shot.jpg", "image/jpeg"), fakeFile("notes.txt", "text/plain")],
    } as unknown as DataTransfer;
    const files = filesFromDataTransfer(dt);
    expect(files).toHaveLength(1);
    expect(files[0].name).toBe("shot.jpg");
  });

  it("reads image items from a clipboard list", () => {
    const file = fakeFile("clip.png", "image/png");
    const items = [
      { kind: "file", getAsFile: () => file },
      { kind: "string", getAsFile: () => null },
    ] as unknown as DataTransferItemList;
    Object.defineProperty(items, "length", { value: 2 });
    const files = filesFromClipboardItems(items);
    expect(files).toHaveLength(1);
    expect(files[0].type).toBe("image/png");
  });
});
