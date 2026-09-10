from __future__ import annotations

from pathlib import Path


def file_search_tool(
    file_name: str,
    extension: str | None = None,
    root_path: str = ".",
    max_results: int = 25,
) -> list[str]:
    """Find files below root_path by name and optional extension."""
    root = Path(root_path).expanduser()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Search root does not exist: {root}")

    name = file_name.strip().lower()
    ext = (extension or "").strip().lower()
    if ext and not ext.startswith("."):
        ext = f".{ext}"

    results: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if name and name not in path.name.lower():
            continue
        if ext and path.suffix.lower() != ext:
            continue
        results.append(str(path))
        if len(results) >= max_results:
            break

    return results
