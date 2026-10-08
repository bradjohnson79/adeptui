import { useState } from "react";
import { beta, download, hero } from "../content";
import { Chapter, SectionHeading } from "./ui";
import {
  configuredDownloadUrl,
  desktopPlatforms,
  downloadState,
  downloads,
  isDesktopOs,
  linuxPackageChooserHref,
  otherPlatforms,
  platformDownloadHref,
  readClientOs,
  readyBuilds,
  releaseActionLabel,
  type ClientOs,
  type DesktopOs,
} from "../downloads";

function PlatformIcon({ id }: { id: DesktopOs }) {
  if (id === "windows") {
    return (
      <svg className="os-icon" viewBox="0 0 16 16" aria-hidden="true">
        <path
          fill="currentColor"
          d="M1 2.25 7.1 1.45v6.05H1V2.25zm6.7-.92L15 0v7.5H7.7V1.33zM1 8.55h6.1v6.05L1 13.7V8.55zm6.7 0H15V16l-7.3-1.15V8.55z"
        />
      </svg>
    );
  }
  if (id === "macos") {
    return (
      <svg className="os-icon" viewBox="0 0 16 16" aria-hidden="true">
        <path
          fill="currentColor"
          d="M11.2 8.4c0-1.7 1.4-2.5 1.46-2.54-.8-1.16-2.04-1.32-2.48-1.34-1.05-.11-2.06.62-2.59.62-.54 0-1.36-.6-2.24-.59-.1 0-1.15.16-1.75.8-1.28 2.22-.33 5.5.92 7.3.61.88 1.33 1.86 2.28 1.83.91-.04 1.26-.59 2.36-.59 1.1 0 1.41.59 2.38.57.98-.02 1.6-.89 2.2-1.78.7-1.01.98-1.99 1-2.04-.02-.01-1.91-.73-1.93-2.9zM9.7 3.7c.5-.61.84-1.46.75-2.3-.72.03-1.6.48-2.11 1.09-.46.54-.87 1.4-.76 2.22.81.06 1.63-.41 2.12-1.01z"
        />
      </svg>
    );
  }
  return (
    <svg className="os-icon" viewBox="0 0 24 24" aria-hidden="true">
      <path
        fill="currentColor"
        d="M12.4 2.2c-1.5.2-2.7 1.1-3.2 2.3-.5.2-1.5.7-1.9 1.5-.6 1-.4 2.3.2 3.3-.8.9-1.2 2.1-1.2 3.6 0 2.3.9 4 2.4 4.8.3 1.2 1.2 2.2 2.4 2.6.3.7.8 1.1 1.5 1.1h.2c.6 0 1.1-.4 1.3-.9.9-.3 1.6-.9 2-1.8 1.6-.7 2.6-2.4 2.6-4.8 0-1.6-.5-2.9-1.4-3.8.6-1 .6-2.3.1-3.3-.4-.8-1.4-1.3-1.9-1.5-.5-1.2-1.6-2.1-3.1-2.1z"
      />
    </svg>
  );
}

function ReleaseButton({
  id,
  prominent = false,
  onSelect,
}: {
  id: DesktopOs;
  prominent?: boolean;
  onSelect?: () => void;
}) {
  const href = downloadState(id) === "available" ? configuredDownloadUrl(id) : null;
  const className = prominent ? "btn btn--primary" : "btn btn--ghost platform-card__action";
  const label = (
    <>
      <PlatformIcon id={id} />
      <span>{releaseActionLabel(id)}</span>
    </>
  );
  const extras = readyBuilds(id).filter((build) => build.url !== href);

  const packageList =
    extras.length > 0 ? (
      <ul className="release__arches">
        {extras.map((build) => (
          <li key={build.installerType ?? build.architecture}>
            <a href={build.url} rel="noopener noreferrer">
              {build.label}
            </a>
          </li>
        ))}
      </ul>
    ) : null;

  if (!href) {
    return (
      <>
        <button type="button" className={`${className} btn--pending`} disabled>
          {label}
        </button>
        {packageList}
      </>
    );
  }

  return (
    <>
      <a className={className} href={href} rel="noopener noreferrer" onClick={onSelect}>
        {label}
      </a>
      {packageList}
    </>
  );
}

function LinuxPackages() {
  const packages = readyBuilds("linux");
  return (
    <div id="linux-packages" className="linux-packages">
      <p className="linux-packages__title">Download Adept UI for Linux</p>
      <ul className="linux-packages__list">
        {packages.map((build) => (
          <li key={build.installerType ?? build.label}>
            <p className="linux-packages__name">{build.audience}</p>
            {build.detail ? <p className="linux-packages__detail">{build.detail}</p> : null}
            <a className="btn btn--ghost platform-card__action" href={build.url} rel="noopener noreferrer">
              {build.label}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function PlatformLinks({ ids }: { ids: DesktopOs[] }) {
  return (
    <>
      {ids.map((id, index) => {
        const href = platformDownloadHref(id);
        const label = releaseActionLabel(id);
        return (
          <span key={id}>
            {index > 0 ? <span aria-hidden="true"> · </span> : null}
            {href ? (
              <a href={href} rel="noopener noreferrer">
                {label}
              </a>
            ) : (
              <span>{label}</span>
            )}
          </span>
        );
      })}
    </>
  );
}

function HeroDownload({ os }: { os: ClientOs }) {
  if (os === "linux") {
    return (
      <div className="download-hero">
        <div className="hero__actions">
          <a className="btn btn--primary" href={linuxPackageChooserHref}>
            <PlatformIcon id="linux" />
            <span>{releaseActionLabel("linux")}</span>
          </a>
          <a className="btn btn--ghost" href={hero.explore.href}>
            {hero.explore.label}
          </a>
        </div>
        <p className="download-hero__note" id="download-hero-status">
          {download.note}
        </p>
        <p className="download-hero__note">{download.linuxPlan}</p>
        <p className="download-hero__others">
          Other platforms: <PlatformLinks ids={otherPlatforms(os)} />
        </p>
      </div>
    );
  }

  if (isDesktopOs(os)) {
    return (
      <div className="download-hero">
        <div className="hero__actions">
          <ReleaseButton id={os} prominent />
          <a className="btn btn--ghost" href={hero.explore.href}>
            {hero.explore.label}
          </a>
        </div>
        <p className="download-hero__note" id="download-hero-status">
          {download.note}
        </p>
        <p className="download-hero__others">
          Other platforms: <PlatformLinks ids={otherPlatforms(os)} />
        </p>
      </div>
    );
  }

  if (os === "ios" || os === "android") {
    return (
      <div className="download-hero">
        <p className="download-hero__mobile">{download.desktopOnly}</p>
        {desktopPlatforms.some((id) => downloadState(id) === "available") ? (
          <p className="download-hero__mobile">{download.choose}</p>
        ) : null}
        <p className="download-hero__others">
          <PlatformLinks ids={desktopPlatforms} />
        </p>
        <div className="hero__actions">
          <a className="btn btn--ghost" href={hero.explore.href}>
            {hero.explore.label}
          </a>
        </div>
      </div>
    );
  }

  return (
    <div className="download-hero">
      <div className="hero__actions">
        <button type="button" className="btn btn--primary btn--pending" disabled>
          {download.unknownLabel}
        </button>
        <a className="btn btn--ghost" href={hero.explore.href}>
          {hero.explore.label}
        </a>
      </div>
      <p className="download-hero__note">{download.note}</p>
      <p className="download-hero__others">
        <PlatformLinks ids={desktopPlatforms} />
      </p>
    </div>
  );
}

export function DownloadSection() {
  return (
    <Chapter id="download" labelledBy="download-title" wide>
      <SectionHeading id="download-title" eyebrow={download.eyebrow} title={download.title} lede={download.lede} />
      <p className="download-channel">{download.channel}</p>
      <DownloadAdeptUI variant="panel" />
      <details className="beta-note">
        <summary>{beta.summary}</summary>
        <p>{beta.body}</p>
      </details>
    </Chapter>
  );
}

export function DownloadAdeptUI({ variant }: { variant: "hero" | "panel" }) {
  const [os] = useState<ClientOs>(() => readClientOs());
  const [selected, setSelected] = useState<DesktopOs | null>(isDesktopOs(os) ? os : null);

  if (variant === "hero") return <HeroDownload os={os} />;

  return (
    <>
      <div className="platforms" role="list">
        {desktopPlatforms.map((id) => {
          const recommended = os === id;
          const active = selected === id;
          const className = ["platform-card", recommended ? "is-recommended" : "", active ? "is-selected" : ""]
            .filter(Boolean)
            .join(" ");
          const version = downloads[id].version;
          return (
            <article key={id} role="listitem" className={className}>
              <div className="platform-card__head">
                <PlatformIcon id={id} />
                <h3>{downloads[id].label}</h3>
              </div>
              {recommended ? <p className="platform-card__flag">{download.recommended}</p> : null}
              {id === "linux" ? <p className="platform-card__plan">{download.linuxPlan}</p> : null}
              {version ? <p className="release__meta">Version {version}</p> : null}
              {id === "linux" ? <LinuxPackages /> : <ReleaseButton id={id} onSelect={() => setSelected(id)} />}
            </article>
          );
        })}
      </div>
      <p id="download-status" className="download-status">
        {download.note}
      </p>
    </>
  );
}
