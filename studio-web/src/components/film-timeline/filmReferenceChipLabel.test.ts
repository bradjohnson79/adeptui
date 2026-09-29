import { describe, expect, it } from "vitest";
import { filmReferenceChipLabel } from "./filmReferenceChipLabel";

describe("filmReferenceChipLabel", () => {
  it("keeps a single @ when tag already includes @", () => {
    expect(filmReferenceChipLabel({ type: "character", tag: "@Renkoka" })).toBe("@Renkoka");
  });
  it("collapses @@ double prefix on character chips", () => {
    expect(filmReferenceChipLabel({ type: "character", tag: "@@Renkoka" })).toBe("@Renkoka");
  });
  it("keeps a single # when tag already includes #", () => {
    expect(filmReferenceChipLabel({ type: "environment", tag: "#Abode" })).toBe("#Abode");
  });
  it("collapses ## double prefix on environment chips", () => {
    expect(filmReferenceChipLabel({ type: "environment", tag: "##Abode" })).toBe("#Abode");
  });
  it("adds prefix when label has none", () => {
    expect(filmReferenceChipLabel({ type: "character", label: "Renkoka" })).toBe("@Renkoka");
    expect(filmReferenceChipLabel({ type: "environment", label: "Abode" })).toBe("#Abode");
    expect(filmReferenceChipLabel({ type: "prop", label: "Blade" })).toBe("%Blade");
    expect(filmReferenceChipLabel({ type: "video", label: "Take1" })).toBe("*Take1");
    expect(filmReferenceChipLabel({ type: "audio", label: "VO" })).toBe("&VO");
  });
  it("prefers tag over label", () => {
    expect(filmReferenceChipLabel({ type: "character", tag: "@Renkoka", label: "Other" })).toBe("@Renkoka");
  });
});
