import { isImageAsset, type LibraryAsset } from "../library/assetModel";

export const ENVIRONMENT_PICKER_PAGE_SIZE = 200;
const MAX_PAGES = 10;

type LibraryPage = {
  items?: LibraryAsset[];
  totalMatches?: number;
};

export type LibraryPageLoader = (
  projectId: string,
  opts: { q?: string; limit: number; offset: number },
) => Promise<LibraryPage>;

function classificationFolder(asset: LibraryAsset): string {
  const classification = asset.classification || {};
  return String(
    (classification as { target_folder?: string }).target_folder ||
      (classification as { subtype?: string }).subtype ||
      "",
  );
}

function haystack(asset: LibraryAsset): string {
  return [asset.tag, asset.filename, asset.title, asset.libraryPath, classificationFolder(asset)]
    .map((value) => String(value || "").toLowerCase())
    .join(" ");
}

export function environmentPickerRank(asset: LibraryAsset): number {
  const text = haystack(asset);
  if (text.includes("atlas")) return 3;
  if (text.includes("background") || text.includes("environment")) return 2;
  if (text.includes("scene")) return 1;
  return 0;
}

export function rankEnvironmentPickerAssets(assets: LibraryAsset[]): LibraryAsset[] {
  return [...assets].sort((a, b) => {
    const rankDelta = environmentPickerRank(b) - environmentPickerRank(a);
    if (rankDelta !== 0) return rankDelta;
    return String(a.filename || a.tag || a.id).localeCompare(String(b.filename || b.tag || b.id));
  });
}

export function matchEnvironmentPickerQuery(asset: LibraryAsset, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return haystack(asset).includes(q);
}

export async function loadEnvironmentPickerImages(
  listLibrary: LibraryPageLoader,
  projectId: string,
  query = "",
): Promise<LibraryAsset[]> {
  const q = query.trim() || undefined;
  const images: LibraryAsset[] = [];
  let offset = 0;
  for (let page = 0; page < MAX_PAGES; page += 1) {
    const payload = await listLibrary(projectId, {
      q,
      limit: ENVIRONMENT_PICKER_PAGE_SIZE,
      offset,
    });
    const items = Array.isArray(payload?.items) ? payload.items : [];
    images.push(...items.filter(isImageAsset));
    const total = Number(payload?.totalMatches ?? items.length);
    offset += items.length;
    if (items.length === 0 || offset >= total) break;
  }
  return rankEnvironmentPickerAssets(images);
}
