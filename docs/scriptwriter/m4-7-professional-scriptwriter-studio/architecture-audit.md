# Architecture Audit

Target: unified `workspace=scriptwriter` studio with TipTap screenplay schema, `script-document@1` + `script-transaction@1` + `script-revision@1`.

```text
UI ScriptwriterStudio
  → API /api/projects/{id}/scriptwriter/*
  → ScriptTransaction.commit
  → script_documents / script_elements
  → Co-Director proposals / Bible / Scene sync / Timeline prep
```

Legacy `script_segments` remain readable; migration creates element docs with rollback.
