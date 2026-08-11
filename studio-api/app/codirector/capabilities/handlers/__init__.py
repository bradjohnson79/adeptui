"""Co-Director capability handlers — execution entry points for capabilities.

Each capability with ``handler_kind == CAPABILITY_HANDLER`` is implemented as
a module here named after the capability id with ``.`` → ``_``. For example,
``image.generate`` → ``capabilities/handlers/image_generate.py``.

Each handler module exposes::

    def handle(db, project_id, plan: ExecutionPlan, context: dict) -> HandlerResult

``HandlerResult`` is duck-typed (object or dict) with ``child_jobs`` and
optional ``planned_steps``, ``collection_id``, ``provider``, ``model``. The
dispatcher merges the result into the plan and persists it.

This package is intentionally minimal — handlers are implemented by
Workstream E. The dispatcher guards the import so missing handlers surface
``CAPABILITY_NOT_IMPLEMENTED`` honestly rather than crashing.
"""
