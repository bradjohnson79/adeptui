import { openTrustedStatusLink, productStatus } from "./productStatus";
import "./beta-notice.css";

type AdeptWindow = Window & {
  adeptDesktop?: { openExternal?: (url: string) => Promise<unknown> };
};

export function BetaNotice() {
  return (
    <aside className="beta-notice" aria-label="Adept UI beta status" data-testid="home-beta-notice">
      <span className="beta-notice__lamp" aria-hidden="true" />
      <p>
        {productStatus.lead} <strong className="beta-notice__mark">{productStatus.mark}</strong>. {productStatus.body}{" "}
        <a
          href={productStatus.bugReportUrl}
          target="_blank"
          rel="noreferrer"
          onClick={(event) => openTrustedStatusLink(event, (window as AdeptWindow).adeptDesktop)}
        >
          {productStatus.linkLabel}
        </a>
        .
      </p>
    </aside>
  );
}
