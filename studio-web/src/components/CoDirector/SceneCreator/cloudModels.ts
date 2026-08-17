/**
 * Cloud generator offering truth for the Scene Creator (CDX-080).
 *
 * Discovery rows carry adapterAvailable / executable / selectable flags.
 * A row the catalog marks adapterAvailable=False or executable=False (e.g.
 * flux-kontext-fal) must never be rendered as a selectable cloud generator —
 * the backend would fail or refuse at execution. This helper is the single
 * filter the Cloud Generators dropdown applies, and the pure unit under test.
 */

export type CloudGeneratorRow = {
  id?: string;
  modelId?: string;
  label?: string;
  name?: string;
  providerId?: string;
  selectable?: boolean;
  executable?: boolean;
  adapterAvailable?: boolean;
  [key: string]: unknown;
};

export function cloudGeneratorSelectable(row: CloudGeneratorRow): boolean {
  return (
    row.adapterAvailable !== false &&
    row.executable !== false &&
    row.selectable !== false
  );
}

export function selectableCloudModels(
  rows: CloudGeneratorRow[] | null | undefined,
): CloudGeneratorRow[] {
  return (rows || []).filter(cloudGeneratorSelectable);
}
