interface Candidate {
  assetId: string;
  url: string;
  label: string;
}

export function CharacterCandidatePanel({
  candidates,
  characterName,
  onSelect,
  onReject,
}: {
  candidates: Candidate[];
  characterName: string;
  onSelect: (assetId: string) => void;
  onReject: () => void;
}) {
  return (
    <div className="character-candidate-panel" data-testid="character-candidates">
      <h4>Casting: {characterName}</h4>
      <div className="character-candidate-grid">
        {candidates.map((c, i) => (
          <div key={c.assetId} className="character-candidate-card" data-testid={`candidate-${i}`}>
            <img src={c.url} alt={c.label} />
            <span className="candidate-label">{c.label}</span>
            <button type="button" onClick={() => onSelect(c.assetId)}>
              Select
            </button>
          </div>
        ))}
      </div>
      <div className="character-candidate-actions">
        <button type="button" className="ghost" onClick={onReject}>
          Reject All
        </button>
      </div>
    </div>
  );
}
