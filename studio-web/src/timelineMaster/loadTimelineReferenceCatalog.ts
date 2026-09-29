import { api } from "../api";
import { isRealBindingId, type ReferenceBindingView } from "../sceneReferences/referenceTokens";

export function collectPromptBindingIds(
  segments?:
    | Array<{
        reference_binding_ids?: string[] | null;
        reference_name_bindings?: Array<{ binding_id?: string } | null> | null;
      }>
    | null,
): string[] {
  const ids = new Set<string>();
  for (const seg of segments || []) {
    for (const id of seg.reference_binding_ids || []) {
      const token = String(id || "").trim();
      if (token) ids.add(token);
    }
    for (const row of seg.reference_name_bindings || []) {
      const token = String(row?.binding_id || "").trim();
      if (token) ids.add(token);
    }
  }
  return [...ids];
}

export function resolveTimelineReference(
  bindingId: string,
  catalog: ReferenceBindingView[],
): ReferenceBindingView | undefined {
  const token = String(bindingId || "").trim();
  if (!token) return undefined;
  return catalog.find((item) => item.id === token);
}

export async function loadTimelineReferenceCatalog(args: {
  projectId: string;
  sceneId?: string | null;
  bindingIds?: string[];
}): Promise<ReferenceBindingView[]> {
  const sceneId = String(args.sceneId || "").trim();
  const res = await api.sceneReferences.list(
    args.projectId,
    sceneId
      ? { scopeType: "scene", scopeId: sceneId, includeInherited: true, sceneId }
      : { scopeType: "project", scopeId: args.projectId, includeInherited: true },
  );
  const byId = new Map<string, ReferenceBindingView>();
  for (const item of (res.items || []) as ReferenceBindingView[]) {
    if (item?.id) byId.set(item.id, item);
  }
  const missing = (args.bindingIds || []).filter((id) => isRealBindingId(id) && !byId.has(id));
  await Promise.all(
    missing.map(async (id) => {
      try {
        const row = (await api.sceneReferences.get(args.projectId, id)) as ReferenceBindingView;
        if (row?.id) byId.set(row.id, row);
      } catch {
        // Deleted / unknown binding stays absent so Timed Prompt can mark it missing.
      }
    }),
  );
  return [...byId.values()];
}
