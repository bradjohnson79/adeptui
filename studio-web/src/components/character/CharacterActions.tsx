/**
 * CharacterActions — shared Save / Reset / Delete actions.
 * Delete is only offered for an already-saved character.
 */
type Props = {
  isSaved: boolean;
  canSave: boolean;
  saving?: boolean;
  onSave: () => void;
  onReset: () => void;
  onDelete: () => void;
};

export function CharacterActions({ isSaved, canSave, saving, onSave, onReset, onDelete }: Props) {
  return (
    <div className="character-core__actions">
      <button
        type="button"
        className="character-core__button primary"
        data-testid="character-save"
        disabled={!canSave || saving}
        onClick={onSave}
      >
        {saving ? "Saving…" : "Save Character"}
      </button>
      <button
        type="button"
        className="character-core__button"
        data-testid="character-reset"
        disabled={saving}
        onClick={onReset}
      >
        Reset
      </button>
      {isSaved ? (
        <button
          type="button"
          className="character-core__button danger"
          data-testid="character-delete"
          disabled={saving}
          onClick={onDelete}
        >
          Delete Character
        </button>
      ) : null}
    </div>
  );
}
