from quince_mcp.basket_api import BasketAPI
from quince_mcp.file_system.file_system import file_root
from quince_mcp.menu_node import MenuNode
from quince_mcp.quince_tools import build_quince_root


def build_root(basket_api_url: str) -> MenuNode:
    root = MenuNode("root", "root", "Root level")
    root.add_child(file_root)
    root.add_child(build_quince_root(BasketAPI(basket_api_url)))
    return root
