from quince_mcp.menu_node import MenuNode
from quince_mcp.file_system.file_system import file_root

root = MenuNode("root","root","Root level")
root.add_child(file_root)