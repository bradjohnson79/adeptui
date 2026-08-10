/** Named SplitPane / inspector layouts — local only (Phase 4.0.6). */

export type NamedLayoutId = "editing" | "writing" | "generation" | "audio" | "custom";

export type NamedLayout = {
  id: NamedLayoutId | string;
  label: string;
  directorLeft: number;
  directorRight: number;
  inspectorCollapsed?: boolean;
};

const KEY = "adept_ui_named_layouts_v1";
const ACTIVE_KEY = "adept_ui_active_layout_v1";

export const DEFAULT_LAYOUTS: NamedLayout[] = [
  { id: "editing", label: "Editing Layout", directorLeft: 260, directorRight: 300 },
  { id: "writing", label: "Writing Layout", directorLeft: 320, directorRight: 280 },
  { id: "generation", label: "Generation Layout", directorLeft: 240, directorRight: 340 },
  { id: "audio", label: "Audio Layout", directorLeft: 280, directorRight: 320 },
];

export function loadNamedLayouts(): NamedLayout[] {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return DEFAULT_LAYOUTS;
    const parsed = JSON.parse(raw) as NamedLayout[];
    return Array.isArray(parsed) && parsed.length ? parsed : DEFAULT_LAYOUTS;
  } catch {
    return DEFAULT_LAYOUTS;
  }
}

export function saveNamedLayouts(layouts: NamedLayout[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(layouts));
  } catch {
    /* ignore */
  }
}

export function getActiveLayoutId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_KEY);
  } catch {
    return null;
  }
}

export function setActiveLayoutId(id: string): void {
  try {
    localStorage.setItem(ACTIVE_KEY, id);
  } catch {
    /* ignore */
  }
}

export function applyNamedLayout(layout: NamedLayout): void {
  try {
    localStorage.setItem("adept_ui_split_director_left", String(layout.directorLeft));
    /* Inner split primary = center/main width; inspector takes remaining. */
    localStorage.setItem("adept_ui_split_director_right_primary", String(Math.max(360, 1200 - layout.directorRight)));
    setActiveLayoutId(layout.id);
  } catch {
    /* ignore */
  }
}

export function saveCurrentAsLayout(label: string): NamedLayout {
  const left = Number(localStorage.getItem("adept_ui_split_director_left") || 280);
  const main = Number(localStorage.getItem("adept_ui_split_director_right_primary") || 720);
  const right = Math.max(240, 1200 - (Number.isFinite(main) ? main : 720));
  const layout: NamedLayout = {
    id: `custom-${Date.now()}`,
    label,
    directorLeft: Number.isFinite(left) ? left : 280,
    directorRight: Number.isFinite(right) ? right : 300,
  };
  const next = [...loadNamedLayouts(), layout];
  saveNamedLayouts(next);
  setActiveLayoutId(layout.id);
  return layout;
}
