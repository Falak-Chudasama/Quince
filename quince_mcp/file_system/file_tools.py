from __future__ import annotations

from pathlib import Path
from typing import Any


def file_search_tool(
    file_name: str,
    extension: str = "",
    root_path: str = ".",
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Search recursively for files by name and optional extension."""
    root = Path(root_path).expanduser().resolve()
    if not root.exists():
        raise ValueError(f"Search root does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Search root is not a directory: {root}")

    extension = extension.strip()
    if extension and not extension.startswith("."):
        extension = "." + extension

    needle = file_name.strip().lower()
    if not needle:
        raise ValueError("file_name cannot be empty")

    if max_results < 1:
        raise ValueError("max_results must be at least 1")

    results: list[dict[str, Any]] = []
    for path in root.rglob("*"):
        if len(results) >= max_results:
            break
        if not path.is_file():
            continue
        if needle not in path.name.lower():
            continue
        if extension and path.suffix.lower() != extension.lower():
            continue
        results.append({
            "name": path.name,
            "path": str(path),
        })

    return results
