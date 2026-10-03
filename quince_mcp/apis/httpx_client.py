import httpx
from typing import Any

class HTTPXClient:
    def __init__(self, base_url: str, timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)

    async def get(self, url: str):
        response = await self.client.get(f"{self.base_url}/{url}", timeout=self.timeout)
        response.raise_for_status()
        return response.json()
    
    async def post(self, url: str, args: dict[str, Any]):
        response = await self.client.post(
            f"{self.base_url}/{url}",
            timeout=self.timeout,
            json=args
        )

        response.raise_for_status()
        return response.json()