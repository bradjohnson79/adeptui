import type { NavigateFunction } from "react-router-dom";

export const PROJECT_LIBRARY_HASH = "projects-library";
export const PROJECT_LIBRARY_ID = "projects-library";

/** Scroll Home to the project library grid (search / open / manage). */
export function focusProjectLibrary(): void {
  const el = document.getElementById(PROJECT_LIBRARY_ID);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "start" });
  const search = el.querySelector<HTMLInputElement>('input[aria-label="Search projects"]');
  search?.focus({ preventScroll: true });
}

/** Navigate to Generation Studio home (project library landing). */
export function goHome(navigate: NavigateFunction): void {
  navigate({ pathname: "/" });
}

/**
 * Open the full project library. When already on Home, scroll instead of a no-op navigate("/").
 */
export function browseAllProjects(navigate: NavigateFunction): void {
  const onHome = window.location.pathname === "/" || window.location.pathname === "";
  if (onHome) {
    if (window.location.hash !== `#${PROJECT_LIBRARY_HASH}`) {
      // Preserve React Router history state markers (idx/key).
      window.history.replaceState(window.history.state, "", `/#${PROJECT_LIBRARY_HASH}`);
    }
    requestAnimationFrame(() => focusProjectLibrary());
    return;
  }
  navigate({ pathname: "/", hash: PROJECT_LIBRARY_HASH });
}
