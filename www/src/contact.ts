/**
 * Public contact copy. Delivery settings stay on the server.
 * There is no privacy-policy page yet, so the form does not invent a link.
 */

export const contactCategories = [
  {
    id: "general",
    label: "General Inquiry",
    help: "Questions about Adept UI, the project, features or availability.",
    success: "Thanks — your message has been sent.",
    subject: (subject: string) => `[Adept UI] General Inquiry — ${subject}`,
  },
  {
    id: "bug",
    label: "Report a Bug",
    help: "Tell us what happened, what you expected, and how to reproduce it if possible.",
    success: "Thanks for reporting the issue.",
    subject: (subject: string) => `[Adept UI Bug] ${subject}`,
  },
  {
    id: "media",
    label: "Media Request",
    help: "Press, interviews, demonstrations, project information or other media requests.",
    success: "Thanks — your media request has been received.",
    subject: (subject: string) => `[Adept UI Media] ${subject}`,
  },
] as const;

export type ContactCategoryId = (typeof contactCategories)[number]["id"];

export const contactFailure = "We couldn't send your message right now. Please try again.";

export const contactPrivacy = "Information submitted through this form is used to respond to your message.";

export function contactCategory(id: string) {
  return contactCategories.find((item) => item.id === id) ?? null;
}

/** Reads a fixed category id from the page address. Unknown values stay on General Inquiry. */
export function categoryFromSearch(search: string): ContactCategoryId {
  const query = search.startsWith("?") ? search.slice(1) : search;
  const raw = new URLSearchParams(query).get("category")?.trim().toLowerCase() ?? "";
  return contactCategory(raw)?.id ?? "general";
}
