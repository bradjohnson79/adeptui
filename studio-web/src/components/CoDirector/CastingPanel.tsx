import { useEffect, useState } from "react";
import { api } from "../../api";
import { Button } from "../ui";

type CastRec = {
  characterId: string;
  characterName: string;
  status: string;
  exploratory?: boolean;
  wikiPageId?: string | null;
};

export function CastingPanel({
  projectId,
  focusCharacter,
}: {
  projectId: string;
  focusCharacter?: string | null;
}) {
  const [lifecycle, setLifecycle] = useState<Record<string, unknown> | null>(null);
  const [blockedReason, setBlockedReason] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setError(null);
    try {
      const res = await api.getCoDirectorProductionLifecycle(projectId);
      setLifecycle(res.lifecycle || null);
      setBlockedReason(res.castingBlockedReason || null);
      // Seed casting cards from compiled Wiki characters when empty
      const cast = (res.lifecycle?.characterCasting || []) as CastRec[];
      if (!cast.length) {
        const wiki = await api.getCoDirectorProjectWiki(projectId);
        const chars = (wiki.compiledPages || []).filter((p) => p.pageType === "CHARACTER");
        for (const c of chars.slice(0, 12)) {
          await api.postCoDirectorLifecycleCasting(projectId, {
            characterName: c.title,
            status: "NOT_STARTED",
            exploratory: Boolean(res.castingBlockedReason),
            wikiPageId: c.pageId,
          });
        }
        if (chars.length) {
          const refreshed = await api.getCoDirectorProductionLifecycle(projectId);
          setLifecycle(refreshed.lifecycle || null);
          setBlockedReason(refreshed.castingBlockedReason || null);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  useEffect(() => {
    void load();
  }, [projectId]);

  const casting = (lifecycle?.characterCasting || []) as CastRec[];
  const scriptStatus = String(lifecycle?.scriptStatus || "NONE");

  return (
    <div className="codirector-casting-panel" data-testid="codirector-casting-panel">
      <header style={{ marginBottom: "0.75rem" }}>
        <h3 style={{ margin: 0 }}>Casting</h3>
        <p className="muted" style={{ margin: "0.35rem 0 0" }}>
          How established characters are represented in production — not the character story itself.
        </p>
      </header>

      {blockedReason ? (
        <div
          className="codirector-content-card"
          data-testid="casting-script-required"
          style={{ padding: "0.85rem", marginBottom: "0.75rem" }}
        >
          <strong>Script required</strong>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>
            {blockedReason} You can still explore concepts, but cast lock stays unavailable until the
            script is approved.
          </p>
          <p className="muted" style={{ margin: "0.35rem 0 0" }}>
            Script status: {scriptStatus}
          </p>
        </div>
      ) : (
        <p className="muted" data-testid="casting-ready">
          Casting is open. Script status: {scriptStatus}
        </p>
      )}

      {error ? <p className="muted">{error}</p> : null}

      {!casting.length ? (
        <p className="muted">
          Character casting cards appear when Wiki characters are established.{" "}
          {focusCharacter ? `Looking for ${focusCharacter}.` : null}
        </p>
      ) : (
        <ul style={{ listStyle: "none", padding: 0 }} data-testid="casting-list">
          {casting.map((c) => (
            <li
              key={c.characterId}
              data-testid={`casting-card-${c.characterId}`}
              style={{
                padding: "0.75rem 0",
                borderBottom: "1px solid color-mix(in srgb, currentColor 12%, transparent)",
              }}
            >
              <div style={{ fontWeight: 600 }}>{c.characterName}</div>
              <div className="muted" style={{ fontSize: "0.8rem" }}>
                Status: {c.status.replace(/_/g, " ")}
                {c.exploratory ? " · Exploratory" : ""}
              </div>
              <div className="row" style={{ gap: "0.4rem", marginTop: "0.4rem", flexWrap: "wrap" }}>
                <Button
                  variant="compact"
                  onClick={() =>
                    void api
                      .postCoDirectorLifecycleCasting(projectId, {
                        characterName: c.characterName,
                        status: "CONCEPTING",
                        exploratory: Boolean(blockedReason),
                        wikiPageId: c.wikiPageId || undefined,
                      })
                      .then(() => load())
                  }
                >
                  Concept
                </Button>
                <Button
                  variant="compact"
                  data-testid={`casting-lock-${c.characterId}`}
                  onClick={() =>
                    void api
                      .postCoDirectorLifecycleCasting(projectId, {
                        characterName: c.characterName,
                        status: "CAST_LOCKED",
                        exploratory: false,
                        wikiPageId: c.wikiPageId || undefined,
                      })
                      .then(() => load())
                  }
                >
                  Cast lock
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}

      <Button variant="compact" data-testid="casting-refresh" onClick={() => void load()}>
        Refresh
      </Button>
    </div>
  );
}
