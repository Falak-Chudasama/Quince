from .httpx_client import HTTPXClient
from quince_mcp.core.configs import BASKET_HOST, BASKET_PORT

base_url = f"http://{BASKET_HOST}:{BASKET_PORT}"
timeout = 5.0

class BasketClient():
    def __init__(self, timeout: float = 5.0):
        self.application = "quince"
        self.base_url = base_url
        self.memory_client = HTTPXClient(f"{base_url}/context/memory", timeout=timeout)
        self.command_client = HTTPXClient(f"{base_url}/context/command", timeout=timeout)

    async def add_memory(self, memory: str, is_temporary: bool = True):
        return await self.memory_client.post(
            url="add",
            args={
                "application": self.application,
                "memory": memory,
                "is_temporary": is_temporary
            })
    
    async def get_all_memory(self):
        return await self.memory_client.post(
            url="get_all",
            args={
                "application": self.application
            })

    async def delete_memory(self, memory_id: str):
        return await self.memory_client.post(
            url="delete",
            args={
                "application": self.application,
                "memory_id": memory_id
            }
        )

    async def delete_all_memory(self):
        return await self.memory_client.post(
            url="delete_all",
            args={
                "application": self.application
            }
        )


    async def add_command(self, command: str, is_temporary: bool = True):
        return await self.command_client.post(
            url="add",
            args={
                "application": self.application,
                "command": command,
                "is_temporary": is_temporary
            })
    
    async def get_all_commands(self):
        return await self.command_client.post(
            url="get_all",
            args={
                "application": self.application
            })

    async def delete_command(self, command_id: str):
        return await self.command_client.post(
            url="delete",
            args={
                "application": self.application,
                "command_id": command_id
            }
        )

    async def delete_all_commands(self):
        return await self.command_client.post(
            url="delete_all",
            args={
                "application": self.application
            }
        )

basket_client = BasketClient(timeout=5.0)