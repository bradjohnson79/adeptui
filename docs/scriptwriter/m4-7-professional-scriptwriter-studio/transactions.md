# Script Transactions (`script-transaction@1`)

All multi-element operations commit as named undoable transactions:

`insert_scene`, `delete_scene`, `move_scene`, `apply_codirector_proposal`, `restore_revision`, `import_document`, `convert_outline_to_scenes`, `apply_timeline_prep_metadata`.

```ts
type ScriptTransaction = {
  id: string;
  documentId: string;
  kind: string;
  source: "creator" | "codirector" | "migration" | "import" | "system";
  beforeRevision: number;
  afterRevision: number;
  affectedElementIds: string[];
  createdAt: string;
  reversible: boolean;
};
```

Payload/snapshot refs enable reverse when `reversible: true`.
