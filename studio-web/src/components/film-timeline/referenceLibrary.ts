import type { Asset } from "../../types";

/** Insert or replace one classified asset in the shared library list. */
export function upsertClassifiedAsset(items: Asset[], updated: Asset | null | undefined): Asset[] {
  const id = String(updated?.id || "");
  if (!updated || !id) return items;
  const index = items.findIndex((item) => item.id === id);
  if (index < 0) return [{ ...updated }, ...items];
  const next = items.slice();
  next[index] = { ...items[index], ...updated };
  return next;
}

/**
 * Apply a library page without dropping assets the page does not contain.
 * Page rows win for ids they include. Tray assets past the first page stay.
 */
export function mergeLibraryPage(current: Asset[], page: Asset[]): Asset[] {
  const pageIds = new Set(page.map((item) => item.id));
  const kept = current.filter((item) => item.id && !pageIds.has(item.id));
  const prior = new Map(current.map((item) => [item.id, item]));
  const fresh = page.map((item) => {
    const previous = prior.get(item.id);
    return previous ? { ...previous, ...item } : item;
  });
  return [...fresh, ...kept];
}

/** A failed classification leaves the previous list untouched. */
export function libraryAfterClassification(current: Asset[], updated: Asset | null | undefined, ok: boolean): Asset[] {
  if (!ok) return current;
  return upsertClassifiedAsset(current, updated);
}
