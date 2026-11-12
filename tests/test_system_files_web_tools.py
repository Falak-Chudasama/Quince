from __future__ import annotations

import os
import tempfile
import pytest

from quince_mcp.tool_tree import TOOL_TREE, root
from quince_mcp.tools.system.handlers import (
    _get_os_info,
    _get_system_uptime,
    _get_ip_info,
    _check_internet,
    _get_wifi_status,
    _run_command,
    _get_env_var,
)
from quince_mcp.tools.files.handlers import (
    _write_file,
    _read_file,
    _append_file,
    _get_file_info,
    _list_directory,
    _search_files,
    _delete_file,
)
from quince_mcp.tools.web.handlers import (
    _clean_html_text,
    _get_weather,
)


def test_tool_tree_structure():
    child_ids = [c.tool_id for c in root.children]
    assert "root--system" in child_ids
    assert "root--files" in child_ids
    assert "root--web" in child_ids
    assert "root--browser" in child_ids
    assert "root--productivity" in child_ids

    # Check key tools exist in TOOL_TREE
    assert "root--system--apps--launch-app" in TOOL_TREE
    assert "root--system--display--take-screenshot" in TOOL_TREE
    assert "root--system--network--get-wifi-status" in TOOL_TREE
    assert "root--system--empty-recycle-bin" in TOOL_TREE
    assert "root--files--list-directory" in TOOL_TREE
    assert "root--files--read-file" in TOOL_TREE
    assert "root--files--write-file" in TOOL_TREE
    assert "root--web--search" in TOOL_TREE
    assert "root--web--get-weather" in TOOL_TREE
    assert "root--web--fetch-webpage" in TOOL_TREE


def test_system_handlers():
    os_info = _get_os_info()
    assert "version" in os_info
    assert "computer_name" in os_info

    uptime = _get_system_uptime()
    assert "uptime_seconds" in uptime
    assert uptime["uptime_seconds"] > 0

    ip_info = _get_ip_info()
    assert "hostname" in ip_info
    assert "local_ips" in ip_info

    net = _check_internet()
    assert "internet_connected" in net

    wifi = _get_wifi_status()
    assert isinstance(wifi, dict)

    env = _get_env_var("PATH")
    assert env["exists"] is True
    assert len(env["value"]) > 0

    cmd = _run_command("Write-Output 'quince_test'")
    assert cmd["success"] is True
    assert "quince_test" in cmd["stdout"]


def test_files_handlers_crud():
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = os.path.join(tmpdir, "test.txt")

        # 1. Write file
        w_res = _write_file(path=test_file, content="Line 1: Hello Quince\n")
        assert w_res["success"] is True
        assert os.path.exists(test_file)

        # 2. Append file
        a_res = _append_file(path=test_file, content="Line 2: System level tools\n")
        assert a_res["success"] is True

        # 3. Read file
        r_res = _read_file(path=test_file)
        assert "Hello Quince" in r_res["content"]
        assert "System level tools" in r_res["content"]

        # 4. Get file info
        info = _get_file_info(path=test_file)
        assert info["exists"] is True
        assert info["is_file"] is True
        assert info["size_bytes"] > 0

        # 5. List directory
        ls = _list_directory(path=tmpdir)
        assert ls["total_items"] == 1
        assert ls["items"][0]["name"] == "test.txt"

        # 6. Search files
        found = _search_files(pattern="*.txt", root_dir=tmpdir)
        assert found["found_count"] == 1

        # 7. Delete file
        del_res = _delete_file(path=test_file)
        assert del_res["success"] is True
        assert not os.path.exists(test_file)



def test_web_handlers():
    raw_html = "<html><body><h1>Title</h1><p>Paragraph with <script>alert(1)</script> details &amp; text.</p></body></html>"
    cleaned = _clean_html_text(raw_html)
    assert "Title" in cleaned
    assert "Paragraph with" in cleaned
    assert "details & text." in cleaned
    assert "alert" not in cleaned
    assert "<script>" not in cleaned

    # Weather test (wttr.in)
    w = _get_weather("London")
    assert "location" in w
