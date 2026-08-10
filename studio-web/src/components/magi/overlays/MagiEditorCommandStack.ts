export type MagiEditorCommandSnapshot<TState> = {
  type: string;
  label: string;
  undo: TState;
  redo: TState;
};

export class MagiEditorCommandStack<TState> {
  private undoStack: Array<MagiEditorCommandSnapshot<TState>> = [];
  private redoStack: Array<MagiEditorCommandSnapshot<TState>> = [];
  private coalesce: { type: string; started: number } | null = null;

  canUndo() {
    return this.undoStack.length > 0;
  }
  canRedo() {
    return this.redoStack.length > 0;
  }

  push(type: string, label: string, before: TState, after: TState) {
    const now = Date.now();
    if (
      type === "overlay.text.update" &&
      this.coalesce?.type === type &&
      now - this.coalesce.started < 800 &&
      this.undoStack.length
    ) {
      const last = this.undoStack[this.undoStack.length - 1];
      last.redo = structuredClone(after);
      last.label = label;
      this.redoStack = [];
      return;
    }
    this.undoStack.push({
      type,
      label,
      undo: structuredClone(before),
      redo: structuredClone(after),
    });
    if (this.undoStack.length > 100) this.undoStack.shift();
    this.redoStack = [];
    this.coalesce = type === "overlay.text.update" ? { type, started: now } : null;
  }

  undo(current: TState): TState | null {
    const cmd = this.undoStack.pop();
    if (!cmd) return null;
    this.redoStack.push({ ...cmd, undo: structuredClone(current), redo: cmd.redo });
    this.coalesce = null;
    return structuredClone(cmd.undo);
  }

  redo(current: TState): TState | null {
    const cmd = this.redoStack.pop();
    if (!cmd) return null;
    this.undoStack.push({ ...cmd, undo: structuredClone(current), redo: cmd.redo });
    return structuredClone(cmd.redo);
  }
}
