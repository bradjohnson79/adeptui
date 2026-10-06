import { describe, expect, it } from "vitest";
import {
  IG_CARDINALITY,
  IG_GENERIC_MAX,
  applyAuthoritySelection,
  filterCatalogForAutocomplete,
  igTokenAtCaret,
  insertChipAtCaret,
  parseIgPromptTokens,
  poseCraftChip,
  resolvePromptAgainstCatalog,
  type IgCatalogOption,
} from "./igPromptTokens";
import type { CisAuthorityRef } from "./cisAuthorityTypes";

const catalogs: IgCatalogOption[] = [
  {
    key: "character:korri",
    kind: "character",
    assetId: "a-korri",
    name: "Korri",
    chip: "@Korri",
    label: "@Korri",
  },
  {
    key: "character:anadriya",
    kind: "character",
    assetId: "a-ana",
    name: "Anadriya",
    chip: "@Anadriya",
    label: "@Anadriya",
  },
  {
    key: "prop:mug",
    kind: "prop",
    assetId: "a-mug",
    name: "Coffee Mug",
    chip: "%CoffeeMug",
    label: "%CoffeeMug",
  },
  {
    key: "environment:venture",
    kind: "environment",
    assetId: "a-env",
    name: "Venture Corridor",
    chip: "#VentureCorridor",
    label: "#VentureCorridor",
  },
  {
    key: "environment:old",
    kind: "environment",
    assetId: "a-old",
    name: "Old Hall",
    chip: "#OldHall",
    label: "#OldHall",
  },
  {
    key: "posecraft:stand",
    kind: "posecraft",
    assetId: "a-pose",
    name: "Standing Guard",
    chip: poseCraftChip("Standing Guard"),
    label: "Standing Guard",
  },
  {
    key: "library:mood",
    kind: "other",
    assetId: "a-mood",
    name: "Mood Board",
    chip: "~MoodBoard",
    label: "~MoodBoard",
  },
];

describe("IG prompt-native parser boundaries", () => {
  it("parses tokens with trailing punctuation (not space-split)", () => {
    const tokens = parseIgPromptTokens("@Korri, walks with @Anadriya. #VentureCorridor; mood ~MoodBoard");
    expect(tokens.map((t) => t.raw)).toEqual([
      "@Korri",
      "@Anadriya",
      "#VentureCorridor",
      "~MoodBoard",
    ]);
  });

  it("does not treat mid-word @ as a token", () => {
    const tokens = parseIgPromptTokens("email brad@example.com and @Korri");
    expect(tokens.map((t) => t.raw)).toEqual(["@Korri"]);
  });

  it("recognizes PoseCraft under ~ namespace", () => {
    const chip = poseCraftChip("Standing Guard");
    expect(chip).toBe("~PoseCraft_StandingGuard");
    const tokens = parseIgPromptTokens(`pose ${chip} now`);
    expect(tokens).toHaveLength(1);
    expect(tokens[0].isPoseCraft).toBe(true);
    expect(tokens[0].sigil).toBe("~");
  });

  it("igTokenAtCaret finds partial query", () => {
    const text = "hello @Kor";
    const at = igTokenAtCaret(text, text.length);
    expect(at).toMatchObject({ sigil: "@", query: "Kor", start: 6 });
  });

  it("insertChipAtCaret replaces partial token and avoids blind duplicates", () => {
    const partial = insertChipAtCaret("see @Ko", 7, "@Korri");
    expect(partial.text).toBe("see @Korri");
    const dup = insertChipAtCaret("see @Korri there", 4, "@Korri");
    expect(dup.alreadyPresent).toBe(true);
    expect(dup.text).toBe("see @Korri there");
  });
});

describe("IG cardinality laws", () => {
  it("allows multi characters and props", () => {
    expect(IG_CARDINALITY.character.mode).toBe("multi");
    expect(IG_CARDINALITY.prop.mode).toBe("multi");
    let refs: CisAuthorityRef[] = [];
    refs = applyAuthoritySelection(refs, {
      key: "character:korri",
      kind: "character",
      assetId: "a-korri",
      name: "Korri",
      chip: "@Korri",
    }).refs;
    refs = applyAuthoritySelection(refs, {
      key: "character:anadriya",
      kind: "character",
      assetId: "a-ana",
      name: "Anadriya",
      chip: "@Anadriya",
    }).refs;
    expect(refs).toHaveLength(2);
  });

  it("replaces environment and PoseCraft (ONE each)", () => {
    let refs: CisAuthorityRef[] = [
      {
        key: "environment:old",
        kind: "environment",
        assetId: "a-old",
        name: "Old Hall",
        chip: "#OldHall",
      },
    ];
    const env = applyAuthoritySelection(refs, {
      key: "environment:venture",
      kind: "environment",
      assetId: "a-env",
      name: "Venture Corridor",
      chip: "#VentureCorridor",
    });
    expect(env.refs.filter((r) => r.kind === "environment")).toHaveLength(1);
    expect(env.refs[0].chip).toBe("#VentureCorridor");
    expect(env.replaced?.chip).toBe("#OldHall");

    refs = applyAuthoritySelection([], {
      key: "posecraft:a",
      kind: "posecraft",
      assetId: "p1",
      name: "A",
      chip: poseCraftChip("A"),
    }).refs;
    const pose = applyAuthoritySelection(refs, {
      key: "posecraft:b",
      kind: "posecraft",
      assetId: "p2",
      name: "B",
      chip: poseCraftChip("B"),
    });
    expect(pose.refs.filter((r) => r.kind === "posecraft")).toHaveLength(1);
    expect(IG_CARDINALITY.posecraft.max).toBe(1);
  });

  it("caps generic ~ refs", () => {
    let refs: CisAuthorityRef[] = [];
    for (let i = 0; i < IG_GENERIC_MAX; i++) {
      refs = applyAuthoritySelection(refs, {
        key: `library:${i}`,
        kind: "other",
        assetId: `g${i}`,
        name: `G${i}`,
        chip: `~G${i}`,
      }).refs;
    }
    const blocked = applyAuthoritySelection(refs, {
      key: "library:extra",
      kind: "other",
      assetId: "extra",
      name: "Extra",
      chip: "~Extra",
    });
    expect(blocked.refs).toHaveLength(IG_GENERIC_MAX);
    expect(blocked.blockedReason).toMatch(/At most/);
  });
});

describe("resolve + autocomplete catalogs", () => {
  it("activates mentioned prompt tags and flags unresolved", () => {
    const active: CisAuthorityRef[] = [];
    const result = resolvePromptAgainstCatalog(
      "@Korri in #VentureCorridor with @Nobody",
      catalogs,
      active,
    );
    expect(result.toActivate.map((r) => r.chip).sort()).toEqual(["#VentureCorridor", "@Korri"]);
    expect(result.unresolved[0]?.raw).toBe("@Nobody");
    expect(result.unresolved[0]?.suggestions.length).toBeGreaterThan(0);
  });

  it("warns when prompt still has inactive #OldEnv after env replace", () => {
    const active: CisAuthorityRef[] = [
      {
        key: "environment:venture",
        kind: "environment",
        assetId: "a-env",
        name: "Venture Corridor",
        chip: "#VentureCorridor",
      },
    ];
    const result = resolvePromptAgainstCatalog(
      "still shows #OldHall and #VentureCorridor",
      catalogs,
      active,
    );
    expect(result.staleEnvTags).toContain("#OldHall");
    expect(result.staleEnvTags).not.toContain("#VentureCorridor");
  });

  it("filters autocomplete by sigil", () => {
    const chars = filterCatalogForAutocomplete(catalogs, "@", "ko");
    expect(chars.every((c) => c.kind === "character")).toBe(true);
    expect(chars.some((c) => c.chip === "@Korri")).toBe(true);
    const poses = filterCatalogForAutocomplete(catalogs, "~", "PoseCraft_");
    expect(poses.some((c) => c.kind === "posecraft")).toBe(true);
  });
});
