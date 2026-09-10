from mcp.server.mcpserver import MCPServer

mcp = MCPServer("Quince")

@mcp.tool()
def chat():
    """
    Normal Chat if NO agentic calls required
    """