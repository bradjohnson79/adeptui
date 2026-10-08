/**
 * One place for the public product-status notice on Home.
 * The bug-report address is fixed. It is never built from user input.
 */

export const productStatus = {
  status: "beta",
  lead: "Adept UI is currently in",
  mark: "BETA",
  body: "Features are actively evolving and you may encounter bugs.",
  linkLabel: "Report any bugs here",
  bugReportUrl: "https://adeptui.org/contact?category=bug",
} as const;

type DesktopBridge = {
  openExternal?: (url: string) => Promise<unknown>;
};

export function openTrustedStatusLink(
  event: { preventDefault: () => void },
  desktop: DesktopBridge | null | undefined,
): void {
  if (!desktop?.openExternal) return;
  event.preventDefault();
  void desktop.openExternal(productStatus.bugReportUrl);
}
