/** Plain-language approval copy. Technical ids stay out of the default card. */

export type ApprovalDetail = { label: string; value: string };

export type ApprovalSummary = {
  wants: string;
  details: ApprovalDetail[];
};

type Args = Record<string, unknown>;

function text(value: unknown, limit = 220): string {
  const raw = String(value || "").replace(/\s+/g, " ").trim();
  if (!raw) return "";
  return raw.length > limit ? `${raw.slice(0, limit - 1)}…` : raw;
}

function voiceBriefPhrase(value: unknown): string {
  if (typeof value !== "string" || !value.trim().startsWith("{")) return "";
  try {
    const brief = JSON.parse(value) as Record<string, unknown>;
    return text(brief.delivery || brief.tone || brief.additionalDirection, 180);
  } catch {
    return "";
  }
}

function sceneLine(value: unknown): string {
  return text(String(value || "").replace(/^\[[^\]]+\]\s*/, ""));
}

function named(args: Args, key: string): string {
  return text(args[key], 80);
}

function pushNamed(details: ApprovalDetail[], label: string, value: string): void {
  if (value) details.push({ label, value });
}

export function approvalSummary(toolId: string, args: Args): ApprovalSummary {
  if (toolId === "character_creator.create_from_brief") {
    const name = text(args.name, 80) || "a new character";
    const brief = text(args.brief || args.description);
    return {
      wants: `Create a new character named ${name}.`,
      details: brief ? [{ label: "Character", value: brief }] : [],
    };
  }
  if (toolId === "character_creator.propose_visual_sheet") {
    const name = text(args.characterName || args.name, 80) || "this character";
    const profile = text(args.profileSummary);
    const usingExisting = Boolean(args.heroAssetId);
    const details: ApprovalDetail[] = [
      {
        label: "Using",
        value: args.heroAssetId
          ? `${name}'s current Character Profile and uploaded reference.`
          : `${name}'s current Character Profile.`,
      },
    ];
    if (profile) details.push({ label: "Profile", value: profile });
    details.push({
      label: "Result",
      value: usingExisting
        ? "The sheet uses the existing image."
        : "The front reference will be created in Character Creator.",
    });
    return {
      wants: usingExisting
        ? `Create the front reference for ${name} using the existing image.`
        : "There isn’t an existing character image, so I’ll create the front reference first and use that as the character’s visual identity.",
      details,
    };
  }
  if (toolId === "create_scene" || toolId === "references.attach") {
    const scene = sceneLine(args.prompt || args.text || args.description);
    const ratio = text(args.aspectRatio, 12);
    const details: ApprovalDetail[] = [];
    if (scene) details.push({ label: "Scene", value: scene });
    pushNamed(details, "Character", named(args, "characterName"));
    pushNamed(details, "Prop", named(args, "propName"));
    pushNamed(details, "Environment", named(args, "environmentName"));
    if (ratio) details.push({ label: "Format", value: ratio });
    details.push({ label: "Result", value: "Nothing will be created until you approve." });
    return {
      wants:
        toolId === "references.attach"
          ? "Attach a character reference in Timeline."
          : "Create a new scene in Timeline.",
      details,
    };
  }
  if (toolId === "timeline.propose_add_prompt_segment") {
    const seconds = args.sceneDurationSec ?? args.durationSec;
    const ratio = text(args.aspectRatio, 12);
    const scene = sceneLine(args.text);
    const details: ApprovalDetail[] = [];
    if (scene) details.push({ label: "Scene", value: scene });
    pushNamed(details, "Character", named(args, "characterName"));
    pushNamed(details, "Prop", named(args, "propName"));
    pushNamed(details, "Environment", named(args, "environmentName"));
    if (ratio) details.push({ label: "Format", value: ratio });
    details.push({ label: "Result", value: "Nothing will be placed until you approve." });
    const length = typeof seconds === "number" || typeof seconds === "string" ? `${seconds}` : "";
    return {
      wants: length ? `Add a ${length}-second timed prompt to Timeline.` : "Add a timed prompt to Timeline.",
      details,
    };
  }
  if (toolId === "propose_image_generate") {
    const ratio = text(args.aspectRatio, 12);
    const prompt = text(args.prompt);
    const details: ApprovalDetail[] = [];
    if (args.referenceAssetId) details.push({ label: "Using", value: "The approved reference." });
    if (prompt) details.push({ label: "View", value: prompt });
    return {
      wants: ratio ? `Generate a ${ratio} still image.` : "Generate a still image.",
      details,
    };
  }
  if (toolId === "character_creator.generate_voice_candidates" || toolId === "character_creator.preview_voice_design") {
    const name = text(args.characterName || args.name, 40) || "this character";
    const line = text(args.testLine, 220);
    const performance = text(args.performance, 180) || voiceBriefPhrase(args.designBriefJson);
    const details: ApprovalDetail[] = [];
    if (line) details.push({ label: "Line", value: line });
    if (performance) details.push({ label: "Performance", value: performance });
    details.push({
      label: "Result",
      value: line
        ? "A new voice clip will be generated in Voice Studio."
        : "A voice will be prepared in Voice Studio.",
    });
    return {
      wants: line ? `Create a voice performance for ${name}.` : `Give ${name} a voice in Voice Studio.`,
      details,
    };
  }
  if (toolId === "audio.generate_ambience" || toolId === "audio.generate_sfx" || toolId === "audio.generate_music") {
    const sound = text(args.prompt, 220);
    const ambience = toolId === "audio.generate_ambience";
    const music = toolId === "audio.generate_music";
    const details: ApprovalDetail[] = [];
    if (sound) details.push({ label: "Sound", value: sound });
    details.push({
      label: "Result",
      value: ambience
        ? "A new ambience clip will be created in Audio Studio."
        : music
          ? "A new music cue will be created in Audio Studio."
          : "A new sound effect will be created in Audio Studio.",
    });
    return {
      wants: ambience
        ? "Create background ambience for this scene."
        : music
          ? "Create a music cue for this scene."
          : "Create a sound effect for this scene.",
      details,
    };
  }
  if (toolId === "prop_creator.generate_view") {
    const subject = text(args.name || args.propName || args.description, 120) || "a prop";
    return {
      wants: `Generate a prop image of ${subject}.`,
      details: [
        {
          label: "Result",
          value: "The generated image will be added to the Library and can be used in Prop Creator.",
        },
      ],
    };
  }
  return {
    wants: "Make this change.",
    details: [],
  };
}

export function handleApprovalChoice(
  choice: "approve" | "revise" | "reject",
  handlers: { onApprove: () => void; onRevise: () => void; onReject: () => void },
): void {
  if (choice === "approve") handlers.onApprove();
  else if (choice === "revise") handlers.onRevise();
  else handlers.onReject();
}
