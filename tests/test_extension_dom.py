"""
Layer 1: Chrome Extension TypeScript build & DOM/action unit test runner integration.
Executes `npx tsc --noEmit`, `npm run build`, and `npm test` (node --test) inside `extension/`.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
import pytest


EXT_DIR = Path(__file__).resolve().parent.parent / "extension"


def _npm_cmd() -> str:
    return shutil.which("npm.cmd") or shutil.which("npm") or "npm"


def _npx_cmd() -> str:
    return shutil.which("npx.cmd") or shutil.which("npx") or "npx"


def test_extension_typescript_check_and_build():
    if shutil.which("node") is None:
        pytest.skip("Node.js not installed")

    tsc = subprocess.run(
        [_npx_cmd(), "tsc", "--noEmit"],
        cwd=str(EXT_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert tsc.returncode == 0, f"tsc failed:\n{tsc.stdout}\n{tsc.stderr}"

    build = subprocess.run(
        [_npm_cmd(), "run", "build"],
        cwd=str(EXT_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert build.returncode == 0, f"esbuild failed:\n{build.stdout}\n{build.stderr}"
    assert (EXT_DIR / "dist" / "content.js").exists()
    assert (EXT_DIR / "dist" / "background.js").exists()


def test_extension_dom_and_action_suite():
    if shutil.which("node") is None:
        pytest.skip("Node.js not installed")

    res = subprocess.run(
        [_npm_cmd(), "test"],
        cwd=str(EXT_DIR),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert res.returncode == 0, f"extension tests failed:\n{res.stdout}\n{res.stderr}"
