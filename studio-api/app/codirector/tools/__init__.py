"""Co-Director M2.2: bounded tool registry and approved project actions.

Two kinds of tools, and nothing else:

- **read** tools execute immediately when the model asks for them. They have no write path —
  their handlers only ever query. Their results are sanitized and size-capped before they
  re-enter the model's context or reach the browser.
- **mutating** tools can only ever *propose*. The model never executes one; it produces a
  durable `tool_call` proposal that a human must approve, at which point the *server* — not
  the model — runs the recorded arguments through `ToolExecutionService`.

The registry is deliberately closed: every tool is declared in `definitions.py` with an
explicit argument schema and an explicit capability requirement. There is no generic
"run this handler" escape hatch, no shell, no filesystem, and no SQL surface.

See `docs/architecture/CODIRECTOR_TOOL_REGISTRY.md` and
`docs/architecture/CODIRECTOR_TOOL_SECURITY.md`.
"""
