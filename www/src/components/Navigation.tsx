import { useEffect, useState } from "react";
import { beta, cta, nav } from "../content";
import { ExternalIconLink } from "./ExternalLinks";
import { KoFiButton } from "./KoFiButton";

function onHome() {
  const path = window.location.pathname.replace(/\/+$/, "");
  return path === "";
}

function hrefFor(href: string) {
  if (onHome() || !href.startsWith("#")) return href;
  return `/${href}`;
}

const spy: { id: string; href: string }[] = [
  { id: "ai-filmmaking", href: "#ai-filmmaking" },
  { id: "why", href: "#ai-filmmaking" },
  { id: "workspace", href: "#ai-filmmaking" },
  { id: "co-director", href: "#co-director" },
  { id: "storyboard", href: "#workflow" },
  { id: "workflow", href: "#workflow" },
  { id: "production", href: "#production" },
  { id: "continuity", href: "#production" },
  { id: "models", href: "#models" },
  { id: "timeline", href: "#production" },
  { id: "magi", href: "#production" },
  { id: "local-ai", href: "#models" },
  { id: "about", href: "#about" },
  { id: "audience", href: "#about" },
  { id: "platform", href: "" },
  { id: "download", href: "" },
  { id: "faq", href: "" },
  { id: "cta", href: "" },
];

export function Navigation() {
  const [solid, setSolid] = useState(false);
  const [open, setOpen] = useState(false);
  const [current, setCurrent] = useState("#ai-filmmaking");

  useEffect(() => {
    const onScroll = () => setSolid(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const nodes = spy
      .map((item) => document.getElementById(item.id))
      .filter((node): node is HTMLElement => Boolean(node));
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
        if (!visible) return;
        const match = spy.find((item) => item.id === visible.target.id);
        if (match) setCurrent(match.href);
      },
      { rootMargin: "-45% 0px -45% 0px", threshold: [0.1, 0.25] },
    );
    nodes.forEach((node) => observer.observe(node));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  return (
    <header className={open ? "nav is-solid is-open" : solid ? "nav is-solid" : "nav"}>
      <div className="nav__inner">
        <a className="brand" href={onHome() ? "#ai-filmmaking" : "/"} onClick={() => setOpen(false)}>
          <img src="/brand/adept-ui-emblem.webp" alt="" width={640} height={640} />
          <span className="brand__name">ADEPT UI</span>
          <span className="beta-badge">{beta.label}</span>
        </a>
        <button
          className="nav__toggle"
          type="button"
          aria-expanded={open}
          aria-controls="site-nav"
          onClick={() => setOpen((value) => !value)}
        >
          {open ? "Close" : "Menu"}
        </button>
        <ul id="site-nav" className="nav__links">
          {nav.map((item) => (
            <li key={item.href}>
              <a
                href={hrefFor(item.href)}
                aria-current={
                  item.href === "/contact"
                    ? window.location.pathname.replace(/\/+$/, "") === "/contact"
                      ? "page"
                      : undefined
                    : onHome() && current === item.href
                      ? "location"
                      : undefined
                }
                onClick={() => setOpen(false)}
              >
                {item.label}
              </a>
            </li>
          ))}
          <li className="nav__support-item">
            <KoFiButton />
          </li>
        </ul>
        <div className="nav__external">
          <ExternalIconLink kind="github" />
          <ExternalIconLink kind="huggingFace" />
        </div>
        <div className="nav__support">
          <KoFiButton />
        </div>
        <a className="btn btn--primary nav__cta" href={hrefFor(cta.href)} onClick={() => setOpen(false)}>
          {cta.label}
        </a>
      </div>
    </header>
  );
}
