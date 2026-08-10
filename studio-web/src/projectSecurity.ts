/** Client-side unlock grant tokens (never store project passwords). */

const STORAGE_KEY = "adept_project_unlock_grants_v1";

type GrantMap = Record<string, { token: string; expiresAt?: string }>;

function load(): GrantMap {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as GrantMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function save(map: GrantMap) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(map));
}

export function getProjectUnlockToken(projectId: string): string {
  const g = load()[projectId];
  if (!g?.token) return "";
  if (g.expiresAt && Date.parse(g.expiresAt) < Date.now()) {
    clearProjectUnlockToken(projectId);
    return "";
  }
  return g.token;
}

export function setProjectUnlockToken(projectId: string, token: string, expiresAt?: string) {
  const map = load();
  map[projectId] = { token, expiresAt };
  save(map);
}

export function clearProjectUnlockToken(projectId: string) {
  const map = load();
  delete map[projectId];
  save(map);
}

export function clearAllProjectUnlockTokens() {
  sessionStorage.removeItem(STORAGE_KEY);
}

/** Extract project id from /api/projects/:id or /api/codirector/projects/:id paths. */
export function projectIdFromApiPath(path: string): string | null {
  const m = path.match(/^\/api\/(?:codirector\/)?projects\/([0-9a-fA-F-]{36})(?:\/|$)/);
  return m?.[1] || null;
}
