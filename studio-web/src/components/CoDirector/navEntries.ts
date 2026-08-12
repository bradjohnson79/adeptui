export type ContentTab =
  | "wiki"
  | "notes"
  | "casting"
  | "library"
  | "bible"
  | "approvals"
  | "plans"
  | "jobs"
  | "vision"
  | "pitch"
  | "scriptwriter"
  | "development"
  | "production"
  | "story"
  | "script"
  | "characters"
  | "spatial_map"
  | "scene_creator";

export type NavTarget =
  | { kind: "content"; tab: ContentTab }
  | { kind: "route"; path: string }
  | { kind: "chat" }
  | { kind: "overflow"; panel: "status" }
  | { kind: "deferred" };

export type NavEntry = {
  id: string;
  label: string;
  target: NavTarget;
  available: boolean;
  deferred?: boolean;
};

export type ContentNavItem =
  | { kind: "tab"; id: ContentTab; label: string }
  | {
      kind: "group";
      id: string;
      label: string;
      children: { id: ContentTab; label: string }[];
    };

/** Creator-facing content navigation — Four Pillars Project Building. */
export const CONTENT_NAV: ContentNavItem[] = [
  { kind: "tab", id: "wiki", label: "Wiki" },
  { kind: "tab", id: "notes", label: "Notes" },
  { kind: "tab", id: "story", label: "Story" },
  { kind: "tab", id: "scriptwriter", label: "Script Writer" },
  { kind: "tab", id: "characters", label: "Character Creator" },
  { kind: "tab", id: "spatial_map", label: "Spatial Map" },
  { kind: "tab", id: "scene_creator", label: "Scene Creator" },
  { kind: "tab", id: "library", label: "Library" },
];

export function buildNavEntries(projectId: string | undefined): NavEntry[] {
  const pid = projectId || "";
  const projectPath = pid ? `/project/${pid}` : "/";
  const entries: NavEntry[] = [
    {
      id: "project",
      label: pid ? "Current Project" : "No Project Selected",
      target: { kind: "route", path: projectPath },
      available: true,
    },
    { id: "wiki", label: "Wiki", target: { kind: "content", tab: "wiki" }, available: true },
    { id: "notes", label: "Notes", target: { kind: "content", tab: "notes" }, available: Boolean(pid) },
    { id: "casting", label: "Casting", target: { kind: "content", tab: "casting" }, available: Boolean(pid) },
    { id: "chat", label: "Conversation", target: { kind: "chat" }, available: true },
    {
      id: "vision",
      label: "Vision",
      target: { kind: "content", tab: "vision" },
      available: Boolean(pid),
    },
    {
      id: "pitch",
      label: "Pitch & Launch",
      target: { kind: "content", tab: "pitch" },
      available: Boolean(pid),
    },
    {
      id: "bible",
      label: "Bible",
      target: { kind: "content", tab: "bible" },
      available: Boolean(pid),
    },
    {
      id: "library",
      label: "Library",
      target: { kind: "content", tab: "library" },
      available: Boolean(pid),
    },
    {
      id: "plans",
      label: "Plans",
      target: { kind: "content", tab: "plans" },
      available: Boolean(pid),
    },
    {
      id: "approvals",
      label: "Approvals",
      target: { kind: "content", tab: "approvals" },
      available: Boolean(pid),
    },
    {
      id: "jobs",
      label: "Jobs",
      target: { kind: "content", tab: "jobs" },
      available: Boolean(pid),
    },
    {
      id: "settings",
      label: "Settings",
      target: { kind: "deferred" },
      available: true,
      deferred: true,
    },
    {
      id: "status",
      label: "System Status",
      target: { kind: "overflow", panel: "status" },
      available: true,
    },
  ];
  return entries;
}
