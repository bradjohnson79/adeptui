"""Closed toolset over the existing registry. Shelved tools are not registered."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic_ai import RunContext
from pydantic_ai.toolsets import FunctionToolset

from .deps import TurnDeps

TOOLSET_ID = "adept_cd_closed_registry"


class ToolArguments(BaseModel):
    model_config = ConfigDict(extra="allow")


class ClosedRegistryToolset(FunctionToolset[TurnDeps]):
    """One stable toolset. Membership at run time is the admitted id list."""

    async def get_tools(self, ctx: RunContext[TurnDeps]):
        tools = await super().get_tools(ctx)
        allowed = set(ctx.deps.exposed_tool_ids)
        return {name: tool for name, tool in tools.items() if name in allowed}


def _describe(definition) -> str:
    names = ", ".join(param.name for param in definition.parameters) or "none"
    return f"{definition.description} Arguments: {names}."


def _bind(tool_id: str):
    from dbos import DBOS

    async def _run(ctx: RunContext[TurnDeps], arguments: ToolArguments) -> str:
        from ...db import SessionLocal
        from .execute import run_admitted_tool
        from .models import AuthorityEnvelope

        envelope = AuthorityEnvelope.model_validate(ctx.deps.envelope)
        with SessionLocal() as db:
            result = run_admitted_tool(
                db,
                envelope,
                tool_id=tool_id,
                arguments=arguments.model_dump(exclude_none=True),
                tool_call_id=tool_id,
            )
        return result.model_dump_json()

    _run.__name__ = "cd_tool_" + tool_id.replace(".", "_")
    return DBOS.step()(_run)


def build_toolset() -> ClosedRegistryToolset:
    from ..tools.exposure import is_shelved_tool
    from ..tools.registry import all_definitions

    toolset = ClosedRegistryToolset(id=TOOLSET_ID)
    for definition in all_definitions():
        if is_shelved_tool(definition.tool_id):
            continue
        toolset.add_function(
            _bind(definition.tool_id),
            name=definition.tool_id,
            takes_ctx=True,
            description=_describe(definition),
        )
    return toolset
