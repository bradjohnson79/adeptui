"""Tool handlers, grouped by the subsystem they read from or propose against.

Read handlers are `async def handler(ctx, args) -> dict` and only ever query.
Mutating handlers come in pairs — `preview(ctx, args) -> ToolPreview` and
`apply(ctx, args) -> dict` — and `apply` is reachable only from
`ToolExecutionService.execute_approved_proposal`, never from a chat turn.
"""
