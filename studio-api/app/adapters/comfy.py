"""ComfyUI adapter boundary and behavior-preserving legacy wrapper."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from ..comfy_client import ComfyClient


class ComfyAdapter(Protocol):
    async def health(self) -> dict[str, Any]: ...

    async def queue_prompt(self, workflow: dict[str, Any]) -> str: ...

    async def get_history(self, prompt_id: str) -> dict[str, Any]: ...

    async def get_queue(self) -> dict[str, Any]: ...

    async def interrupt(self) -> None: ...

    async def upload_image(
        self, src: Path, filename: str | None = None, subfolder: str = "studio"
    ) -> str: ...

    async def upload_file_copy(
        self, src: Path, filename: str | None = None, subfolder: str = "studio"
    ) -> str: ...

    async def wait_for_prompt(
        self,
        prompt_id: str,
        timeout_sec: float | None = None,
        on_progress: Any = None,
    ) -> dict[str, Any]: ...

    def find_output_files(self, history_entry: dict[str, Any]) -> list[Path]: ...


class ExistingComfyClientAdapter:
    """Delegate to the current client without altering calls or results."""

    def __init__(self, client: ComfyClient) -> None:
        self._client = client

    async def health(self) -> dict[str, Any]:
        return await self._client.health()

    async def queue_prompt(self, workflow: dict[str, Any]) -> str:
        return await self._client.queue_prompt(workflow)

    async def get_history(self, prompt_id: str) -> dict[str, Any]:
        return await self._client.get_history(prompt_id)

    async def get_queue(self) -> dict[str, Any]:
        return await self._client.get_queue()

    async def interrupt(self) -> None:
        await self._client.interrupt()

    async def upload_image(
        self, src: Path, filename: str | None = None, subfolder: str = "studio"
    ) -> str:
        return await self._client.upload_image(src, filename, subfolder)

    async def upload_file_copy(
        self, src: Path, filename: str | None = None, subfolder: str = "studio"
    ) -> str:
        return await self._client.upload_file_copy(src, filename, subfolder)

    async def wait_for_prompt(
        self,
        prompt_id: str,
        timeout_sec: float | None = None,
        on_progress: Any = None,
    ) -> dict[str, Any]:
        return await self._client.wait_for_prompt(
            prompt_id, timeout_sec, on_progress
        )

    def find_output_files(self, history_entry: dict[str, Any]) -> list[Path]:
        return self._client.find_output_files(history_entry)
