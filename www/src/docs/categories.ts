import type { DocCategory } from "./types";

export const docCategories: DocCategory[] = [
  {
    id: "getting-started",
    title: "Getting started",
    summary: "What Adept UI is, how a project is organized, and the path from an empty project to a shot you can keep.",
    group: "start",
  },
  {
    id: "installation",
    title: "Installation",
    summary: "Desktop platforms, what is published today, and what this site will not invent about hardware or installers.",
    group: "start",
  },
  {
    id: "setup-manager",
    title: "Setup",
    summary: "Adept Setup checks whether the studio is ready and prepares components. Guided, AI-Guided, and Manual are different ways through the same setup.",
    group: "start",
  },
  {
    id: "update-manager",
    title: "Updates",
    summary: "What can be said about updates before a public installer and update channel exist.",
    group: "start",
  },
  {
    id: "co-director",
    title: "Co-Director",
    summary: "Co-Director is production intelligence across the open project. It is not a separate chatbot with no memory of the film.",
    group: "create",
  },
  {
    id: "characters",
    title: "Characters",
    summary: "A character is an identity the production can reuse: profile, references, appearance, and voice, kept with the project.",
    group: "create",
  },
  {
    id: "storyboard",
    title: "Storyboard",
    summary: "Storyboard Studio is where you plan panels before you spend a video generation on a shot you have not looked at.",
    group: "create",
  },
  {
    id: "image-generation",
    title: "Image generation",
    summary: "Stills, keyframes, and reference art are generated with an image model you select, then kept in the project library.",
    group: "create",
  },
  {
    id: "video-generation",
    title: "Video generation",
    summary: "Adept UI runs a video model you choose. It is the production environment around that model, not a video model of its own.",
    group: "create",
  },
  {
    id: "voice-audio",
    title: "Voice and audio",
    summary: "Voice Studio directs a character's voice. Audio Studio is where music, ambience, and Foley live.",
    group: "create",
  },
  {
    id: "timeline",
    title: "Timeline",
    summary: "Timeline is where a generated shot becomes part of a scene: ordered, reviewed, continued, or retaken on purpose.",
    group: "finish",
  },
  {
    id: "magi",
    title: "MAGI",
    summary: "MAGI is the finishing room. Generation makes the shot. MAGI grades, scales, composes, and prepares it for delivery.",
    group: "finish",
  },
  {
    id: "scenecraft",
    title: "SceneCraft",
    summary: "SceneCraft spatial reconstruction is planned for a later release. It is not part of the current production set.",
    group: "finish",
  },
  {
    id: "models",
    title: "Models",
    summary: "Local engines and hosted APIs are choices. The model you select is the model that runs.",
    group: "systems",
  },
  {
    id: "local-ai",
    title: "Local AI",
    summary: "Supported local models run on your machine when they are installed. Open-weight models are not a license for Adept UI.",
    group: "systems",
  },
  {
    id: "api-models",
    title: "API models",
    summary: "Hosted generators are available when their connection is configured. A hosted job sends that provider the request it requires.",
    group: "systems",
  },
  {
    id: "projects",
    title: "Projects",
    summary: "One open project holds the characters, scenes, library, and generations. A new image should not become a new project.",
    group: "systems",
  },
  {
    id: "workflows",
    title: "Workflows",
    summary: "End-to-end paths through the rooms you already have: develop, visualize, generate, assemble, finish.",
    group: "help",
  },
  {
    id: "troubleshooting",
    title: "Troubleshooting",
    summary: "What a failed or stuck generation usually means, and what not to do while you find out.",
    group: "help",
  },
  {
    id: "developer",
    title: "Developer",
    summary: "A public view of how the product is shaped. It is not an internal runbook and it does not include secrets.",
    group: "help",
  },
  {
    id: "reference",
    title: "Reference",
    summary: "Short definitions and the local services a developer may see. Creators are not asked to operate those services by hand.",
    group: "help",
  },
];

export const categoryById = new Map(docCategories.map((category) => [category.id, category]));
