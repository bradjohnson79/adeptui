import { useLayoutEffect, useRef, useState } from "react";
import { measureFirstRowHeight, threeRowLibraryMaxHeight } from "./libraryRowBounds";

export type HomeLibraryBounds = {
  height: number;
  rowHeight: number;
  gap: number;
};

export function useHomeLibraryBounds(view: "grid" | "list", itemCount: number) {
  const resultsRef = useRef<HTMLDivElement>(null);
  const gridFootprintRef = useRef<number | null>(null);
  const lastKeyRef = useRef("");
  const [bounds, setBounds] = useState<HomeLibraryBounds | undefined>(undefined);

  useLayoutEffect(() => {
    const root = resultsRef.current;
    if (!root || itemCount <= 0) {
      setBounds(undefined);
      return;
    }

    const apply = (next: HomeLibraryBounds) => {
      setBounds((prev) => {
        if (
          prev &&
          Math.abs(prev.height - next.height) < 0.5 &&
          Math.abs(prev.rowHeight - next.rowHeight) < 0.5 &&
          Math.abs(prev.gap - next.gap) < 0.5
        ) {
          return prev;
        }
        return next;
      });
    };

    const measure = () => {
      const grid = root.querySelector<HTMLElement>(".project-library-grid");
      const cards = [...root.querySelectorAll<HTMLElement>(".project-cover-card")];
      if (!grid || !cards.length) return;
      const styles = getComputedStyle(grid);
      const gap = parseFloat(styles.rowGap || styles.gap || "16") || 16;
      const key = `${Math.round(root.clientWidth)}:${view}`;

      if (view === "list") {
        grid.style.removeProperty("--home-library-row-height");
        const listRow = cards[0].getBoundingClientRect().height;
        const height = gridFootprintRef.current ?? threeRowLibraryMaxHeight(listRow, gap);
        apply({ height, rowHeight: listRow, gap });
        return;
      }

      if (lastKeyRef.current !== key) {
        grid.style.removeProperty("--home-library-row-height");
        void grid.offsetHeight;
        lastKeyRef.current = key;
      }

      const rowHeight = measureFirstRowHeight(
        cards.map((card) => {
          const box = card.getBoundingClientRect();
          return { top: box.top, height: box.height };
        }),
      );
      if (rowHeight <= 0) return;
      const height = threeRowLibraryMaxHeight(rowHeight, gap);
      grid.style.setProperty("--home-library-row-height", `${rowHeight}px`);
      gridFootprintRef.current = height;
      apply({ height, rowHeight, gap });
    };

    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    const grid = root.querySelector(".project-library-grid");
    if (grid) observer.observe(grid);
    cardsToObserve(root).forEach((card) => observer.observe(card));
    return () => observer.disconnect();
  }, [view, itemCount]);

  return { resultsRef, bounds };
}

function cardsToObserve(root: HTMLElement): Element[] {
  const cards = [...root.querySelectorAll(".project-cover-card")];
  const first = cards[0];
  if (!first) return [];
  const firstTop = Math.round(first.getBoundingClientRect().top);
  return cards.filter((card) => Math.abs(Math.round(card.getBoundingClientRect().top) - firstTop) <= 1);
}
