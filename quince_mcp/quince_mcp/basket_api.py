from __future__ import annotations

import httpx
from typing import Any


class BasketAPI:
    """Small async client for Quince-owned operations exposed by Basket."""

    def __init__(self, base_url: str, timeout: float = 15.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _post(self, path: str, payload: dict[str, Any]) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(f"{self.base_url}{path}", json=payload)
            response.raise_for_status()
            return response.json()

    async def _get(self, path: str) -> Any:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}{path}")
            response.raise_for_status()
            return response.json()

    async def memory_store(self, document: str, source: str = "user") -> Any:
        return await self._post("/mcp-api/memory/store", {
            "document": document,
            "source": source,
        })

    async def memory_search(self, query: str, n_result: int = 5) -> Any:
        return await self._post("/mcp-api/memory/search", {
            "query": query,
            "n_result": n_result,
        })

    async def command_add(self, command: str, is_temporary: bool = True) -> Any:
        return await self._post("/mcp-api/commands/add", {
            "command": command,
            "is_temporary": is_temporary,
        })

    async def command_list(self) -> Any:
        return await self._get("/mcp-api/commands")

    async def command_delete(self, command: str) -> Any:
        return await self._post("/mcp-api/commands/delete", {
            "command": command,
        })
