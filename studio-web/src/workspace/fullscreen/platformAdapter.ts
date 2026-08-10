import type { FullscreenPlatformAdapter } from "./types";

/** Browser Fullscreen API adapter. Desktop shells can swap this without rewriting editors. */
export const browserFullscreenAdapter: FullscreenPlatformAdapter = {
  async requestFullscreen(element: HTMLElement) {
    const anyEl = element as HTMLElement & {
      webkitRequestFullscreen?: () => Promise<void> | void;
      msRequestFullscreen?: () => Promise<void> | void;
    };
    if (typeof element.requestFullscreen === "function") {
      await element.requestFullscreen();
      return;
    }
    if (typeof anyEl.webkitRequestFullscreen === "function") {
      await Promise.resolve(anyEl.webkitRequestFullscreen());
      return;
    }
    if (typeof anyEl.msRequestFullscreen === "function") {
      await Promise.resolve(anyEl.msRequestFullscreen());
      return;
    }
    throw new Error("Fullscreen API is not available in this browser.");
  },
  async exitFullscreen() {
    const doc = document as Document & {
      webkitExitFullscreen?: () => Promise<void> | void;
      msExitFullscreen?: () => Promise<void> | void;
    };
    if (!getFullscreenElement()) return;
    if (typeof document.exitFullscreen === "function") {
      await document.exitFullscreen();
      return;
    }
    if (typeof doc.webkitExitFullscreen === "function") {
      await Promise.resolve(doc.webkitExitFullscreen());
      return;
    }
    if (typeof doc.msExitFullscreen === "function") {
      await Promise.resolve(doc.msExitFullscreen());
    }
  },
  getFullscreenElement() {
    return getFullscreenElement();
  },
};

function getFullscreenElement(): Element | null {
  const doc = document as Document & {
    webkitFullscreenElement?: Element | null;
    msFullscreenElement?: Element | null;
  };
  return document.fullscreenElement || doc.webkitFullscreenElement || doc.msFullscreenElement || null;
}

let activeAdapter: FullscreenPlatformAdapter = browserFullscreenAdapter;

export function getFullscreenAdapter(): FullscreenPlatformAdapter {
  return activeAdapter;
}

/** Electron / desktop shell can register a native adapter here. */
export function setFullscreenAdapter(adapter: FullscreenPlatformAdapter) {
  activeAdapter = adapter;
}
