import type { ReactNode } from "react";
import { useEffect, useRef } from "react";

export function Chapter({
  id,
  labelledBy,
  children,
  wide = false,
  reveal = true,
}: {
  id: string;
  labelledBy: string;
  children: ReactNode;
  wide?: boolean;
  reveal?: boolean;
}) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node || !reveal) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      node.classList.add("is-in");
      return;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          node.classList.add("is-in");
          observer.disconnect();
        }
      },
      { threshold: 0.12 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [reveal]);

  const className = ["chapter", wide ? "chapter--wide" : "", reveal ? "reveal" : ""].filter(Boolean).join(" ");

  return (
    <section id={id} ref={ref} className={className} aria-labelledby={labelledBy}>
      <div className="chapter__inner">{children}</div>
    </section>
  );
}

export function SectionHeading({
  id,
  eyebrow,
  title,
  lede,
}: {
  id: string;
  eyebrow: string;
  title: string;
  lede?: string;
}) {
  return (
    <header className="section-heading">
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
      {lede ? <p className="lede">{lede}</p> : null}
    </header>
  );
}
