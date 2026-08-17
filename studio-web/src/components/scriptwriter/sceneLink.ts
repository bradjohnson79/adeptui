import type { Scene } from "../../types";

/**
 * CDX-058: linkScene must bind the SELECTED project scene, not project.scenes[0].
 *
 * Pure selection helper — testable without the component. Returns the chosen
 * scene id when it still exists in the project; otherwise falls back to the
 * first scene (the historical default), or undefined when the project has no
 * scenes at all.
 */
export function resolveLinkSceneId(
  scenes: Scene[],
  selectedId: string | undefined | null,
): string | undefined {
  if (selectedId && scenes.some((s) => s.id === selectedId)) return selectedId;
  return scenes[0]?.id;
}
