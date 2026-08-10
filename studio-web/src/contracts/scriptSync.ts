/** Unified script-link statuses for M4.9 */

export type ScriptLinkStatus =
  | "linked"
  | "script_updated"
  | "override"
  | "conflict"
  | "unlinked";

export const SCRIPT_LINK_LABELS: Record<ScriptLinkStatus, string> = {
  linked: "Linked",
  script_updated: "Script Updated",
  override: "Override",
  conflict: "Conflict",
  unlinked: "Unlinked",
};
