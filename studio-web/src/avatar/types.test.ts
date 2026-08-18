import { describe, expect, it } from "vitest";
import {
  applyApprovedIdentityToSession,
  avatarGenerateBlockers,
  canGenerateAvatarSession,
  claimsLiveAvatarVideo,
  emptyAvatarSession,
  pickApprovedCharacterStill,
  validateAvatarSession,
} from "./types";

function scriptSession() {
  const session = emptyAvatarSession("proj-1", "Korri Presenter");
  session.character_profile_id = "char-korri";
  session.character_name = "Korri";
  session.dialogue_original = "Welcome to the briefing.";
  session.input_mode = "script";
  return session;
}

describe("pickApprovedCharacterStill", () => {
  it("binds an approved hero still instead of name-only identity", () => {
    const picked = pickApprovedCharacterStill({
      profile: { id: "char-korri", name: "Korri" },
      references: [
        { id: "ref-name", reference_role: "notes", approval_status: "approved" },
        {
          id: "ref-hero",
          asset_id: "ast-hero-1",
          reference_role: "hero_identity",
          approval_status: "approved",
          canonical: true,
        },
        {
          id: "ref-sheet",
          asset_id: "ast-sheet-1",
          reference_role: "character_sheet",
          approval_status: "pending",
        },
      ],
    });
    expect(picked).toEqual({ assetId: "ast-hero-1", role: "hero_identity" });
  });

  it("falls back to an approved sheet when no hero still exists", () => {
    const picked = pickApprovedCharacterStill({
      profile: { id: "char-korri", name: "Korri" },
      references: [
        {
          id: "ref-sheet",
          asset_id: "ast-sheet-9",
          reference_role: "character_sheet",
          approval_status: "approved",
        },
      ],
    });
    expect(picked?.assetId).toBe("ast-sheet-9");
  });

  it("does not invent a still from the character name", () => {
    expect(
      pickApprovedCharacterStill({
        profile: { id: "char-korri", name: "Korri" },
        references: [],
      }),
    ).toBeNull();
  });
});

describe("applyApprovedIdentityToSession", () => {
  it("sets source_still_asset_id from the approved still", () => {
    const next = applyApprovedIdentityToSession(scriptSession(), {
      characterId: "char-korri",
      characterName: "Korri",
      stillAssetId: "ast-hero-1",
      stillRole: "hero_identity",
    });
    expect(next.source_still_asset_id).toBe("ast-hero-1");
    expect(next.character_name).toBe("Korri");
    expect(next.look.portrait_asset_id).toBe("ast-hero-1");
  });
});

describe("canGenerate matches validate + not-installed", () => {
  const experimental = { id: "infinitetalk-local", name: "InfiniteTalk", label: "Experimental" as const };
  const missing = { id: "infinitetalk-local", name: "InfiniteTalk", label: "Not Installed" as const };

  it("allows script planning without audio when the runtime is present", () => {
    const session = scriptSession();
    const issues = validateAvatarSession(session);
    expect(issues.some((item) => item.level === "bad")).toBe(false);
    expect(issues.some((item) => item.text.includes("script mode can still plan"))).toBe(true);
    expect(canGenerateAvatarSession(session, { ...experimental, certifiedReady: true })).toBe(true);
  });

  it("disables generate when the badge is Not Installed", () => {
    const session = scriptSession();
    const blockers = avatarGenerateBlockers(session, missing);
    expect(canGenerateAvatarSession(session, missing)).toBe(false);
    expect(blockers.some((item) => item.text.includes("not installed"))).toBe(true);
  });

  it("keeps Approved Voice strict", () => {
    const session = scriptSession();
    session.input_mode = "approved_voice";
    session.dialogue_original = "";
    const blockers = avatarGenerateBlockers(session, experimental);
    expect(canGenerateAvatarSession(session, experimental)).toBe(false);
    expect(blockers.some((item) => item.text.includes("Approved Voice"))).toBe(true);
  });

  it("requires source video for Existing Video Dubbing", () => {
    const session = scriptSession();
    session.mode = "existing_video_lipsync";
    const blockers = avatarGenerateBlockers(session, {
      id: "musetalk-1-5-local",
      name: "MuseTalk 1.5",
      label: "Experimental",
    });
    expect(blockers.some((item) => item.text.includes("Source video"))).toBe(true);
  });

  it("does not treat Experimental as a fake live-gen success", () => {
    const session = scriptSession();
    const blockers = avatarGenerateBlockers(session, experimental);
    expect(canGenerateAvatarSession(session, experimental)).toBe(false);
    expect(blockers.some((item) => item.text.includes("needs repair — Open Runtime Setup"))).toBe(true);
    expect(
      claimsLiveAvatarVideo({
        status: "failed",
        lastError: { code: "AVATAR_SECTION_PROVIDER_NOT_CERTIFIED", message: "not certified" },
        sections: [{ outputVideoAssetId: null, errorCode: "AVATAR_SECTION_PROVIDER_NOT_CERTIFIED" }],
      }),
    ).toBe(false);
  });
});

describe("session Save Draft / New Session do not overwrite", () => {
  it("emptyAvatarSession creates a new id instead of mutating the current one", () => {
    const current = scriptSession();
    current.id = "avs-current";
    current.dialogue_original = "Keep this draft.";
    const created = emptyAvatarSession(current.project_id, "Presenter 2");
    expect(created.id).not.toBe(current.id);
    expect(current.dialogue_original).toBe("Keep this draft.");
    expect(created.dialogue_original).toBe("");
  });

  it("applying identity to a new session leaves the previous session object unchanged", () => {
    const current = scriptSession();
    current.id = "avs-current";
    current.source_still_asset_id = "ast-old";
    const created = applyApprovedIdentityToSession(emptyAvatarSession(current.project_id, "Presenter 2"), {
      characterId: "char-korri",
      characterName: "Korri",
      stillAssetId: "ast-hero-1",
      stillRole: "hero_identity",
    });
    expect(created.id).not.toBe(current.id);
    expect(current.source_still_asset_id).toBe("ast-old");
    expect(created.source_still_asset_id).toBe("ast-hero-1");
  });
});
