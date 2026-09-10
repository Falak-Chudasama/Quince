# Quince + hierarchical MCP

This repository is intentionally a single Quince project with one virtual environment:

```text
quince/
├── .venv/
├── src/              # Quince voice client
├── quince_mcp/       # Quince MCP capability layer/server
├── run.py            # starts the client; MCP starts with it
└── .env
```

`src` and `quince_mcp` are sibling Python packages and therefore share the same `.venv` and interpreter. No second MCP process is required for normal operation.

## Runtime

```text
Quince process
├── voice client ──WS──> Basket
└── MCP server  <──WS── Basket
                     │
                     └──HTTP──> Basket controllers
```

The MCP server starts inside `QuinceClient.run()` and listens on `MCP_HOST:MCP_PORT`.

## Capability tree

```text
root
├── file_system
│   └── search_files
└── quince
    ├── long_term_memory
    │   ├── store
    │   └── search
    └── command_management
        ├── add
        ├── list
        └── delete
```

Only `file_system` and `quince` are exposed initially. Selecting a branch returns `EXPLORE` and exposes only that branch's children. Terminal nodes return `EXECUTE`.

## Configuration

Quince reads `.env` from the project root. Defaults are:

```env
BASKET_WS_URL=ws://127.0.0.1:7000/ws
BASKET_API_URL=http://127.0.0.1:7000
MCP_HOST=127.0.0.1
MCP_PORT=7100
```

## Run on Windows

From the `quince` directory:

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
```

Basket remains a separate process using its normal startup command.

`quince_mcp.run_mcp` exists only as a development-only standalone MCP runner; normal Quince startup should use `python run.py`, which starts the MCP server itself.
