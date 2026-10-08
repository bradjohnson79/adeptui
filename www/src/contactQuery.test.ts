import { describe, expect, it } from "vitest";
import { categoryFromSearch } from "./contact";

describe("contact category deep link", () => {
  it("preselects only the known categories", () => {
    expect(categoryFromSearch("?category=bug")).toBe("bug");
    expect(categoryFromSearch("?category=general")).toBe("general");
    expect(categoryFromSearch("?category=media")).toBe("media");
    expect(categoryFromSearch("?category=BUG")).toBe("bug");
  });

  it("ignores unknown values instead of following them", () => {
    expect(categoryFromSearch("?category=https://evil.example")).toBe("general");
    expect(categoryFromSearch("?category=bug&next=https://evil.example")).toBe("bug");
    expect(categoryFromSearch("")).toBe("general");
    expect(categoryFromSearch("?category=")).toBe("general");
  });
});
