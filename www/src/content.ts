/**
 * Public-site copy. Claims are limited to creator-facing Adept UI surfaces
 * confirmed in the application source during the website audit.
 * SceneCraft spatial work is a later release. WAN is not a current engine.
 * No price, ship date, or license is stated because none is published.
 */

export const site = {
  name: "Adept UI",
  kicker: "AI-Powered Film Production",
  title: "Adept UI Beta — AI Filmmaking & Video Production Software",
  description:
    "Adept UI is in Beta. It is a unified AI filmmaking environment for character creation, storyboarding, image and video generation, voice, editing, and finished production using local and API models.",
} as const;

export const beta = {
  label: "Beta",
  hero: "Adept UI is currently in Beta and under active development. Features, model support, and workflows may continue to evolve during the Beta period.",
  summary: "What does Beta mean?",
  body: "Adept UI is actively being developed. During Beta, features may change, some workflows may still require refinement, and users may encounter bugs. Feedback and bug reports help improve the platform.",
} as const;

export const nav = [
  { href: "#ai-filmmaking", label: "Overview" },
  { href: "#co-director", label: "Co-Director" },
  { href: "#workflow", label: "Workflow" },
  { href: "#production", label: "Production" },
  { href: "#models", label: "Models" },
  { href: "/docs", label: "Docs" },
  { href: "#about", label: "About" },
  { href: "/contact", label: "Contact" },
] as const;

export const cta = {
  label: "Download",
  href: "#download",
} as const;

export const hero = {
  eyebrow: "Open AI filmmaking ecosystem",
  pillars: ["Create", "Direct", "Generate", "Edit", "Finish"],
  title: "Create an Entire Film Inside One AI Production Environment.",
  support: "From characters and storyboards to generation, editing and final delivery.",
  body: "Adept UI is a unified AI filmmaking and video production environment. Character creation, storyboarding, image and video generation, voice, editing, and finishing stay in one workspace, using local engines or hosted models you choose.",
  beta: beta.hero,
  explore: { label: "Explore the Platform", href: "#workspace" },
  pills: [
    "Characters",
    "Image Generation",
    "Storyboard",
    "AI Video",
    "Voice",
    "Scriptwriting",
    "Editing",
    "Production Management",
    "Local AI Models",
    "API Models",
  ],
} as const;

export const why = {
  eyebrow: "Why Adept UI",
  title: "AI Filmmaking Shouldn't Feel Like Ten Different Applications.",
  lede: "AI film production is often split across generators that never meet. A still is made in one place, a shot in another, a voice somewhere else, and the cut in a timeline that never met the character. Adept UI is the production workflow that holds those pieces together.",
  beforeTitle: "Disconnected tools.",
  before: [
    "Image generators",
    "Video generators",
    "Character references",
    "Prompt documents",
    "Voice systems",
    "Editors",
    "File managers",
    "Timelines",
    "Model interfaces",
    "External automation",
  ],
  afterTitle: "One connected production environment.",
  after: [
    "Characters",
    "Worlds",
    "Scenes",
    "Storyboard",
    "Images",
    "Video",
    "Voice",
    "Scripts",
    "Editing",
    "Models",
  ],
} as const;

export const workspace = {
  eyebrow: "Unified production",
  title: "One Workspace. The Entire Production.",
  lede: "Adept UI is the production environment where development, image and video generation, direction, and finishing stay attached to the same film.",
  core: "Adept UI",
  nodes: [
    "Characters",
    "Worlds",
    "Scenes",
    "Storyboard",
    "Images",
    "Video",
    "Voice",
    "Scripts",
    "Editing",
    "Production",
    "Models",
  ],
} as const;

export const coDirector = {
  eyebrow: "Production intelligence",
  title: "Meet Co-Director",
  lede: "Production intelligence across the filmmaking workflow, not a separate chat window.",
  body: "Co-Director sits across the filmmaking ecosystem rather than living as a detached chatbot. It is an orchestration and production layer: it works from the project in front of you, talks through creative decisions, and can coordinate tasks the current Adept UI systems support.",
  relations: ["Characters", "Storyboard", "Timeline", "MAGI", "Voice", "Production"],
  caption: "Co-Director with the project wiki, characters, and working session.",
  points: [
    "Understands production context.",
    "Works across supported Adept UI systems.",
    "Helps plan scenes and productions.",
    "Assists with visual direction.",
    "Helps prepare generation instructions.",
    "Understands characters, environments, and assets.",
    "Supports production continuity.",
    "Converses naturally about creative decisions.",
    "Can coordinate supported production tasks.",
  ],
  stages: [
    {
      index: "01",
      title: "Conversation",
      body: "Talk about the scene, the character, or the problem in ordinary creative language. Co-Director is meant to follow the production, not a blank prompt box.",
    },
    {
      index: "02",
      title: "Planning",
      body: "Shape scenes, shots, and direction with the characters, environments, and assets already in the project.",
    },
    {
      index: "03",
      title: "Production",
      body: "Carry that plan into the systems that hold references, storyboards, scripts, voices, and generation settings.",
    },
    {
      index: "04",
      title: "Execution",
      body: "Coordinate supported production tasks without silently swapping the model, the asset, or the project you chose.",
    },
  ],
} as const;

export const workflow = {
  eyebrow: "Filmmaking workflow",
  title: "From Idea to Finished Production.",
  lede: "Five stages, one environment. Nothing in the chain is a separate application you have to reintroduce the production to.",
  steps: [
    {
      index: "01",
      title: "Develop",
      items: ["Characters", "Worlds", "Scripts", "Scenes"],
    },
    {
      index: "02",
      title: "Visualize",
      items: ["Reference images", "Storyboard", "Shot planning"],
    },
    {
      index: "03",
      title: "Generate",
      items: ["Images", "Video", "Voice", "Performance"],
    },
    {
      index: "04",
      title: "Assemble",
      items: ["Timeline", "Scene continuity", "Production structure"],
    },
    {
      index: "05",
      title: "Finish",
      items: ["MAGI", "Editing", "Upscaling", "Color", "Delivery"],
    },
  ],
} as const;

export type SystemCard = {
  name: string;
  body: string;
  span: "wide" | "half" | "third" | "bar";
  note?: string;
};

export const systems: { eyebrow: string; title: string; lede: string; cards: SystemCard[] } = {
  eyebrow: "Core production systems",
  title: "The Rooms of the Production.",
  lede: "These are the working areas of Adept UI. Each one belongs to the open project. Spatial reconstruction is named only where it is not yet a current release.",
  cards: [
    {
      name: "Co-Director",
      body: "Production intelligence and orchestration across the systems Adept UI currently supports.",
      span: "bar",
    },
    {
      name: "Character System",
      body: "Character references, identity, appearance, wardrobe, and voice, kept with the production.",
      span: "half",
    },
    {
      name: "Storyboard Studio",
      body: "Plan the shot, the beat, and the sequence before a frame is generated. The board stays in the project.",
      span: "half",
    },
    {
      name: "Image Creation",
      body: "Generate stills, keyframes, character references, and environment art with a local or hosted image model you select.",
      span: "third",
    },
    {
      name: "AI Video",
      body: "Generate the shot with a supported local engine or a hosted video model. Adept UI orchestrates that choice. It is not itself a video foundation model, and it does not swap the model you selected.",
      span: "third",
    },
    {
      name: "Voice",
      body: "Direct a character voice and performance in Voice Studio. Music, ambience, and Foley live in Audio Studio.",
      span: "third",
    },
    {
      name: "Scriptwriting",
      body: "Develop dialogue, scenes, and production material in Scriptwriter.",
      span: "third",
    },
    {
      name: "Timeline",
      body: "Build shots and scenes into sequences, with retakes, references, and continuation on the production timeline.",
      span: "third",
    },
    {
      name: "MAGI",
      body: "Finish generated picture and sound: color grade, upscale, overlays, and production export.",
      span: "half",
    },
    {
      name: "Worlds and Props",
      body: "Environment Creator builds locations and sets. Prop Creator builds reusable objects.",
      note: "SceneCraft spatial reconstruction is planned for a later release. It is not part of the current production set.",
      span: "half",
    },
    {
      name: "Project Management",
      body: "Assets, scenes, library files, and generations stay inside the project you have open.",
      span: "half",
    },
  ],
};

export const continuity = {
  eyebrow: "Characters",
  title: "Characters Built for the Production.",
  lede: "Character creation here keeps identity, references, appearance, and voice with the production, so a later scene can continue from the same person.",
  voice: "Voice Studio directs that character's voice and performance. The voice stays with the person, not with a loose audio file.",
  points: [
    { title: "Character references", body: "Identity, appearance, and voice stay attached to the character, not to a single prompt." },
    { title: "Props and environments", body: "Objects, locations, and sets can be developed once and reused across scenes." },
    { title: "Reference roles", body: "A picture can be a character, a style, a start frame, an end frame, or motion — and that role is explicit." },
    { title: "Scene assets", body: "What a scene is using remains with that scene inside the project library." },
    { title: "Shot continuity", body: "Later shots are designed to inherit the production's references instead of starting from a blank generator." },
    { title: "Production context", body: "Co-Director and the timeline read the work that already exists, so direction has something to hold onto." },
  ],
} as const;

export const models = {
  eyebrow: "Image and video models",
  title: "Use the Right AI Model for the Shot.",
  lede: "Adept UI is a multi-model production environment. It runs the image or video model you select, local or hosted, and does not silently substitute another one. The workflow around that choice — references, storyboard, timeline, and finish — stays in Adept UI.",
  qualifier:
    "A model is available when it is installed locally or connected in Setup. Names below are the current creator-facing video engines, plus still-image families present in Adept UI's model setup.",
  localTitle: "Local",
  localVideo: ["MiniMax H3", "LTX 2.5", "Hunyuan 1.5 Distilled"],
  localImage: ["Illustrious XL", "Qwen-Image", "Z-Image", "Flux"],
  apiTitle: "API",
  apiVideo: [
    "Seedance 2.0",
    "Seedance 2.5",
    "Kling 2.5 Turbo Pro",
    "Kling 3.0",
    "Veo 3.1",
    "Runway Gen-3 Turbo",
    "Flux 3.0",
    "Happy Horse 1.0",
    "Google Gemini Omni",
  ],
  apiNote: "Hosted video engines connect through fal.ai. Hosted stills can include Flux, Krea 2, and other image models configured in Setup.",
} as const;

export const timeline = {
  eyebrow: "Timeline",
  title: "Generation Becomes Production.",
  lede: "Video generation meets the cut here. A shot is ordered, reviewed, and retaken on the timeline instead of leaving the process as an isolated clip.",
  points: [
    { title: "Cinematic sequencing", body: "Shots sit in order on a timeline so a scene can be read as a sequence, not a pile of clips." },
    { title: "Continuation", body: "A later shot can be developed from the production already in progress." },
    { title: "Reference-driven generation", body: "Character, style, start-frame, end-frame, and motion references have explicit roles." },
    { title: "Retakes", body: "A new take is a deliberate generation. Opening the timeline does not restart an abandoned render." },
    { title: "Scene assembly", body: "Shots, picture, and sound come together as production structure." },
    { title: "Visual review", body: "You can look at the sequence in the same environment that made it." },
  ],
  caveat:
    "The timeline is designed to preserve continuity. It does not guarantee that every third-party model will match the previous frame.",
} as const;

export const magi = {
  eyebrow: "MAGI",
  title: "Finish the Shot.",
  lede: "MAGI is the post-generation finishing environment. Generation makes the shot. MAGI is where that media is graded, scaled, composed, and prepared for delivery.",
  points: [
    "Color grade, including exposure and grade presets.",
    "Upscale, with GPU upscaling when that path is available.",
    "Overlay composition for titles and picture elements.",
    "Production export through final render.",
  ],
  caveat:
    "Dissolves and stabilization are not finishing engines in the current release. Delivery uses the tools MAGI actually runs.",
} as const;

export const localApi = {
  eyebrow: "Local and API",
  title: "Local When You Want It. Cloud When You Need It.",
  lede: "Run a supported model on your own machine, or connect a hosted generator when the shot needs it. Local open-weight models are tools you install. They are not a license for Adept UI itself.",
  localTitle: "Local AI",
  local: [
    "Local model execution for supported engines.",
    "Control over the model files you install.",
    "Private local workflows for those tools.",
    "Use of the hardware you already run.",
    "No mandatory cloud-only path for supported local tools.",
  ],
  apiTitle: "API AI",
  api: [
    "Access to advanced hosted models.",
    "A wider set of generation choices.",
    "No local install for those providers.",
    "A different system when the shot asks for it.",
  ],
  comfy: {
    heading: "Built on ComfyUI Workflows",
    body: "Adept UI uses ComfyUI workflow infrastructure behind supported local AI generation while providing a unified AI filmmaking workflow for characters, images, video, voice, scenes, and production.",
    points: [
      "ComfyUI-powered local generation workflows.",
      "Adept UI handles the filmmaking production experience.",
      "Normal workflows do not require operating node graphs.",
      "Supported local models run through curated ComfyUI workflows.",
    ],
    docsLabel: "Learn how Adept UI uses ComfyUI workflows",
    docsHref: "/docs/local-ai/comfyui-and-the-local-runtime",
  },
} as const;

export const control = {
  eyebrow: "Built for control",
  title: "Your Production. Your Models. Your Workflow.",
  lede: "Adept UI is a production environment with selectable models, not a single generator with a fixed look.",
  points: [
    { title: "Production ownership", body: "The open project holds the characters, scenes, library, and generations." },
    { title: "Modular model support", body: "Local engines and hosted APIs are choices. One is not silently swapped for the other." },
    { title: "Project organization", body: "Assets stay with the production instead of scattering across separate tools." },
    { title: "Configurable workflows", body: "Develop, visualize, generate, assemble, and finish without leaving the environment." },
    { title: "Persistent assets", body: "References and reusable elements are kept so the next scene can use them." },
    { title: "One interface", body: "The creator works in Adept UI. Runtimes stay behind that workspace." },
  ],
  privacy:
    "Supported local jobs run on your machine. A hosted model sends that provider the request it requires. This page does not make a legal privacy certification.",
} as const;

export const audience = {
  eyebrow: "Who it is for",
  title: "Made for People Building Pictures.",
  lede: "Adept UI is for independent filmmakers and small teams who need characters, shots, and the cut to hold together.",
  people: [
    "AI Filmmakers",
    "Independent Directors",
    "Animators",
    "Previsualization Artists",
    "Content Studios",
    "Storytellers",
    "Creative Technologists",
    "Small Production Teams",
  ],
} as const;

export const platform = {
  eyebrow: "Platform",
  title: "The Whole Production, in One Place.",
  columns: [
    { title: "Develop", items: ["Characters", "Scripts", "Worlds", "Scenes"] },
    { title: "Design", items: ["References", "Storyboards", "Shot Planning"] },
    { title: "Generate", items: ["Images", "Video", "Voice"] },
    { title: "Direct", items: ["Co-Director", "Scene Context", "Creative Guidance"] },
    { title: "Assemble", items: ["Timeline", "Sequences", "Continuity"] },
    { title: "Finish", items: ["MAGI", "Editing", "Upscale", "Delivery"] },
  ],
} as const;

export const finale = {
  titleLead: "Build More Than a Generation.",
  titleRest: "Build the Production.",
  body: "Adept UI brings creative development, AI generation, production intelligence and finishing together inside one filmmaking environment.",
  cta: { label: "Explore the Platform", href: "#production" },
  note: "Availability, pricing, and licensing will be announced with the release.",
} as const;

export const storyboard = {
  eyebrow: "Storyboard Studio",
  title: "Plan the Shot Before You Generate It.",
  lede: "Storyboarding and shot planning live in the same project as the images and video those frames will become.",
  caption: "Storyboard Studio, in the open project.",
} as const;

export const shots = {
  home: {
    src: "/product/adept-ui-home.webp",
    alt: "Adept UI home, introducing the filmmaking workspace and Co-Director",
    caption: "The Adept UI workspace.",
  },
  codirector: {
    src: "/product/adept-ui-co-director.webp",
    alt: "Adept UI Co-Director with the project wiki, characters, and a working session",
    caption: "Co-Director across the open production.",
  },
  storyboard: {
    src: "/product/adept-ui-ai-storyboard-studio.webp",
    alt: "Adept UI Storyboard Studio with aspect controls and panels ready for frames",
    caption: "Storyboard Studio, before the shot is generated.",
  },
  character: {
    src: "/product/adept-ui-ai-character-creator.webp",
    alt: "Adept UI Character Creator with a profile, appearance fields, and a reference image",
    caption: "Character identity, appearance, and reference.",
  },
  voice: {
    src: "/product/adept-ui-ai-voice-studio.webp",
    alt: "Adept UI Voice Studio with an approved character voice and performance directions",
    caption: "Voice stays with the character.",
  },
  timeline: {
    src: "/product/adept-ui-ai-filmmaking-timeline.webp",
    alt: "Adept UI timeline with a generated shot, inspector, and library references",
    caption: "A shot on the production timeline.",
  },
  magi: {
    src: "/product/adept-ui-magi.webp",
    alt: "Adept UI MAGI editor comparing a shot with the project library and timeline",
    caption: "MAGI, where the shot is finished.",
  },
} as const;

export const film = {
  director: {
    src: "/film/film-color-suite.webp",
    alt: "A filmmaker reviewing a grade on a monitor in a dark color suite",
    caption: "Finishing is part of the production, not a separate errand.",
  },
  camera: {
    src: "/film/film-camera-on-set.webp",
    alt: "A cinema camera and reference monitor on a dark set",
    caption: "Built for film production.",
  },
} as const;

export const download = {
  eyebrow: "Beta",
  title: "Download Adept UI Beta.",
  lede: "Adept UI is desktop filmmaking software for Windows, macOS, and Linux. These builds are Beta. Choose your platform and bring the production environment to your workstation.",
  channel: "Current release · Beta",
  note: "Beta installers for Windows, macOS, and Linux.",
  unavailable: "The installer will be published with the release.",
  linuxPlan: "Choose the Linux package for your distribution. Ubuntu and Debian-based systems use the .deb package. Fedora and compatible RPM-based systems use the .rpm package. A portable AppImage is also available.",
  desktopOnly: "Adept UI is available for desktop.",
  choose: "Choose your desktop platform:",
  recommended: "Recommended for your device",
  unknownLabel: "Coming soon",
} as const;

export const footer = {
  links: [
    { href: "#ai-filmmaking", label: "Overview" },
    { href: "#co-director", label: "Co-Director" },
    { href: "#production", label: "Production" },
    { href: "/docs", label: "Docs" },
    { href: "#download", label: "Download" },
    { href: "/contact", label: "Contact" },
    { href: "#faq", label: "Questions" },
  ],
} as const;

export const faq = {
  eyebrow: "Questions",
  title: "What Adept UI Is, and What It Is Not.",
  items: [
    {
      q: "What is Adept UI?",
      a: "Adept UI is AI filmmaking software: one production environment for characters, storyboards, images, video, voice, the timeline, and finishing. It is not a single chat box, and it is not a single video model.",
    },
    {
      q: "What can I create with Adept UI?",
      a: "A project can hold characters and references, storyboards, still images, generated shots, character voices, scripts, and sequences you assemble and finish. SceneCraft spatial reconstruction is planned for a later release and is not part of the current production set.",
    },
    {
      q: "Does Adept UI support AI video generation?",
      a: "Yes. You generate shots with a model you select. Local video engines are MiniMax H3, LTX 2.5, and Hunyuan 1.5 Distilled. Hosted video can include Seedance, Kling, Veo, Runway, Flux, Happy Horse, and Google Gemini Omni when that connection is configured. Adept UI orchestrates those engines and does not replace the one you chose.",
    },
    {
      q: "Can Adept UI generate AI images?",
      a: "Yes. Stills, keyframes, character references, and storyboard frames can be made with an installed local image family, including Illustrious XL, Qwen-Image, Z-Image, and Flux, or with a hosted image model configured in Setup.",
    },
    {
      q: "Does Adept UI support AI voice generation?",
      a: "Yes. Voice Studio designs a character voice and directs performance. Music, ambience, and Foley live in Audio Studio.",
    },
    {
      q: "Can Adept UI run AI models locally?",
      a: "Supported local engines run on your machine when they are installed, and you keep those model files. A local open-weight model is a model you run. It is not a license for the Adept UI application.",
    },
    {
      q: "Does Adept UI support cloud AI models?",
      a: "Yes. Hosted video connects through fal.ai, kie.ai, and wavespeed.ai when those providers' API keys are added in the Setup Wizard. Local and hosted are explicit choices.",
    },
    {
      q: "Is Adept UI available for Windows, macOS, and Linux?",
      a: "The desktop application is in Beta for Windows, macOS, and Linux.",
    },
    {
      q: "Is Adept UI free?",
      a: "Yes. Adept UI 1.1 is a free application. There will be a paid Cloud version of Adept UI available in the near future with more features, community participation and an online marketplace for artists to offer their services through the platform. More updates will be coming soon.",
    },
    {
      q: "Is Adept UI in Beta?",
      a: "Yes. Adept UI is in Beta and under active development. Features may change, some workflows may still need refinement, and you may encounter bugs.",
    },
    {
      q: "Is Adept UI open source?",
      a: "No. Adept UI 1.1 is free AI filmmaking software built around an open AI ecosystem. It is not open-source software. A public source repository is not permission to fork, rebrand, or redistribute Adept UI. Support for local models, including open-weight models, is not a license for the Adept UI application. Each model and provider keeps its own license, terms, and any usage cost.",
    },
  ],
} as const;

export const sectionIds = [
  "ai-filmmaking",
  "why",
  "workspace",
  "co-director",
  "storyboard",
  "workflow",
  "production",
  "continuity",
  "ai-voice",
  "models",
  "timeline",
  "ai-video",
  "magi",
  "local-ai",
  "about",
  "audience",
  "platform",
  "download",
  "faq",
  "cta",
] as const;
