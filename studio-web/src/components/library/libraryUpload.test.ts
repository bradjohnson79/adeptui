import { describe, expect, it } from "vitest";
import { inferLibraryUploadKind, libraryUploadTag } from "./libraryUpload";

function fakeFile(name: string, type: string): File {
  return new File(["x"], name, { type });
}

describe("libraryUpload", () => {
  it("infers image, video, and audio from mime or extension", () => {
    expect(inferLibraryUploadKind(fakeFile("korri.png", "image/png"))).toBe("image");
    expect(inferLibraryUploadKind(fakeFile("take.mp4", "video/mp4"))).toBe("video");
    expect(inferLibraryUploadKind(fakeFile("line.wav", "audio/wav"))).toBe("audio");
    expect(inferLibraryUploadKind(fakeFile("still.webp", ""))).toBe("image");
  });

  it("treats unknown files as documents", () => {
    expect(inferLibraryUploadKind(fakeFile("notes.pdf", "application/pdf"))).toBe("document");
  });

  it("builds a short creator tag from the filename", () => {
    expect(libraryUploadTag(fakeFile("Korri Front.png", "image/png"))).toBe("Korri-Front");
  });
});
