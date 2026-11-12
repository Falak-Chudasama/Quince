from __future__ import annotations

import os
import shutil
import glob
from datetime import datetime
from pathlib import Path
from typing import Any


def _resolve_path(raw_path: str | None) -> Path:
    if not raw_path or raw_path.strip() in ("", ".", "~"):
        return Path(os.environ.get("USERPROFILE", os.path.expanduser("~")))

    raw_path = raw_path.strip()
    # Resolve common shortcuts
    shortcuts = {
        "desktop": Path(os.environ.get("USERPROFILE", ".")) / "Desktop",
        "downloads": Path(os.environ.get("USERPROFILE", ".")) / "Downloads",
        "documents": Path(os.environ.get("USERPROFILE", ".")) / "Documents",
        "pictures": Path(os.environ.get("USERPROFILE", ".")) / "Pictures",
        "music": Path(os.environ.get("USERPROFILE", ".")) / "Music",
        "videos": Path(os.environ.get("USERPROFILE", ".")) / "Videos",
    }
    lower = raw_path.lower()
    if lower in shortcuts:
        return shortcuts[lower]

    expanded = os.path.expandvars(os.path.expanduser(raw_path))
    return Path(expanded).resolve()


def _list_directory(path: str | None = None, include_hidden: bool = False) -> dict[str, Any]:
    target_path = _resolve_path(path)

    if not target_path.exists():
        return {"error": f"Path '{target_path}' does not exist.", "success": False}

    if not target_path.is_dir():
        return {"error": f"Path '{target_path}' is a file, not a directory.", "success": False}

    items = []
    try:
        for entry in os.scandir(target_path):
            if not include_hidden and entry.name.startswith("."):
                continue

            try:
                stat = entry.stat()
                is_dir = entry.is_dir()
                mod_time = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                items.append({
                    "name": entry.name,
                    "is_dir": is_dir,
                    "size_bytes": stat.st_size if not is_dir else 0,
                    "modified": mod_time,
                })
            except Exception:
                continue

        # Sort directories first, then alphabetically
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

        return {
            "success": True,
            "path": str(target_path),
            "total_items": len(items),
            "items": items[:100],  # cap to top 100 entries for prompt efficiency
        }
    except Exception as exc:
        return {"error": f"Failed to list directory: {exc}", "success": False}


def _read_file(path: str, max_chars: int = 4000, start_line: int = 1) -> dict[str, Any]:
    file_path = _resolve_path(path)

    if not file_path.exists():
        return {"error": f"File '{file_path}' does not exist.", "success": False}

    if not file_path.is_file():
        return {"error": f"Path '{file_path}' is a directory, not a file.", "success": False}

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        slice_lines = lines[max(0, start_line - 1):]
        content = "".join(slice_lines)

        truncated = len(content) > max_chars
        if truncated:
            content = content[:max_chars]

        return {
            "success": True,
            "path": str(file_path),
            "total_lines": total_lines,
            "start_line": start_line,
            "content": content,
            "truncated": truncated,
        }
    except Exception as exc:
        return {"error": f"Failed to read file: {exc}", "success": False}


def _write_file(path: str, content: str, overwrite: bool = False) -> dict[str, Any]:
    file_path = _resolve_path(path)

    if file_path.exists() and not overwrite:
        return {
            "error": f"File '{file_path}' already exists. Pass overwrite=True to overwrite.",
            "success": False,
        }

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "path": str(file_path),
            "size_bytes": len(content.encode("utf-8")),
            "overwritten": overwrite and file_path.exists(),
        }
    except Exception as exc:
        return {"error": f"Failed to write file: {exc}", "success": False}


def _append_file(path: str, content: str) -> dict[str, Any]:
    file_path = _resolve_path(path)

    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(content)

        return {
            "success": True,
            "path": str(file_path),
            "appended_chars": len(content),
            "total_size_bytes": file_path.stat().st_size,
        }
    except Exception as exc:
        return {"error": f"Failed to append to file: {exc}", "success": False}


def _search_files(pattern: str, root_dir: str | None = None, max_results: int = 25) -> dict[str, Any]:
    base = _resolve_path(root_dir)
    pattern = pattern.strip()

    if not base.exists() or not base.is_dir():
        return {"error": f"Search directory '{base}' does not exist.", "success": False}

    matches = []
    # Search with glob recursion
    glob_pattern = str(base / "**" / pattern)

    try:
        for p in glob.iglob(glob_pattern, recursive=True):
            try:
                item = Path(p)
                matches.append({
                    "name": item.name,
                    "path": str(item),
                    "is_dir": item.is_dir(),
                    "size_bytes": item.stat().st_size if item.is_file() else 0,
                })
                if len(matches) >= max_results:
                    break
            except Exception:
                continue

        return {
            "success": True,
            "root_dir": str(base),
            "pattern": pattern,
            "found_count": len(matches),
            "matches": matches,
        }
    except Exception as exc:
        return {"error": f"Search failed: {exc}", "success": False}


def _get_file_info(path: str) -> dict[str, Any]:
    file_path = _resolve_path(path)

    if not file_path.exists():
        return {"error": f"'{file_path}' does not exist.", "success": False, "exists": False}

    stat = file_path.stat()
    return {
        "success": True,
        "exists": True,
        "name": file_path.name,
        "path": str(file_path),
        "is_file": file_path.is_file(),
        "is_dir": file_path.is_dir(),
        "size_bytes": stat.st_size if file_path.is_file() else 0,
        "created": datetime.fromtimestamp(stat.st_ctime).strftime("%Y-%m-%d %H:%M:%S"),
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
        "extension": file_path.suffix,
    }



def _make_directory(path: str) -> dict[str, Any]:
    target_path = _resolve_path(path)

    try:
        target_path.mkdir(parents=True, exist_ok=True)
        return {"success": True, "path": str(target_path), "created": True}
    except Exception as exc:
        return {"error": f"Failed to create directory: {exc}", "success": False}


def _copy_file(source: str, destination: str) -> dict[str, Any]:
    src = _resolve_path(source)
    dst = _resolve_path(destination)

    if not src.exists():
        return {"error": f"Source '{src}' does not exist.", "success": False}

    try:
        if src.is_dir():
            shutil.copytree(src, dst)
        else:
            if dst.is_dir():
                dst = dst / src.name
            shutil.copy2(src, dst)
        return {"success": True, "source": str(src), "destination": str(dst)}
    except Exception as exc:
        return {"error": f"Copy failed: {exc}", "success": False}


def _move_file(source: str, destination: str) -> dict[str, Any]:
    src = _resolve_path(source)
    dst = _resolve_path(destination)

    if not src.exists():
        return {"error": f"Source '{src}' does not exist.", "success": False}

    try:
        shutil.move(str(src), str(dst))
        return {"success": True, "source": str(src), "destination": str(dst)}
    except Exception as exc:
        return {"error": f"Move failed: {exc}", "success": False}


def _delete_file(path: str) -> dict[str, Any]:
    target = _resolve_path(path)

    if not target.exists():
        return {"error": f"Path '{target}' does not exist.", "success": False}

    try:
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()
        return {"success": True, "path": str(target), "deleted": True}
    except Exception as exc:
        return {"error": f"Delete failed: {exc}", "success": False}
