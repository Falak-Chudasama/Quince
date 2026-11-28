"""
Layer 4: Desktop Voice Client WS Protocol & Non-Browser Tool Smoke/Validation Suite.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from quince_mcp.tool_tree import TOOL_TREE, root
from quince_mcp.tools.productivity.handlers import (
    _cancel_timer,
    _delete_note,
    _edit_note,
    _list_notes,
    _list_timers,
    _read_note,
    _set_timer,
    _write_note,
)
from quince_mcp.tools.knowledge.handlers import _get_wikipedia_page, _get_wikipedia_summary, _search_wikipedia
from quince_mcp.tools.memory.tools import memory_tool_tree
from quince_mcp.tools.files.handlers import _list_directory, _read_file, _write_file
from quince_mcp.tools.system.handlers import _get_battery_level, _get_os_info, _run_command


# ---------------------------------------------------------------------------
# 1. Desktop Client WS Protocol (rtsi.speak, rtsi.await_user, barge-in)
# ---------------------------------------------------------------------------

def _make_test_client():
    """Construct QuinceClient with mocked audio hardware & hotkey so no mic/speaker is touched."""
    from src.config import Settings

    settings = Settings()
    with (
        patch("src.client.Microphone") as mock_mic_cls,
        patch("src.client.PCMPlayer") as mock_player_cls,
        patch("src.client.PushToTalkHotkey"),
    ):
        mock_mic = MagicMock()
        mock_mic.is_enabled = False
        mock_mic_cls.return_value = mock_mic

        mock_player = MagicMock()
        mock_player_cls.return_value = mock_player

        from src.client import QuinceClient
        client = QuinceClient(settings)
        # Silence Rich console output during tests
        client.status._print_status = MagicMock()
        client.connection = MagicMock()
        client.connection.is_connected = True
        client.connection.send = AsyncMock()
        return client


@pytest.mark.asyncio
async def test_client_rtsi_speak_and_await_user_sends_start_stop_not_cancel():
    client = _make_test_client()
    spoken_lines: list[str] = []
    client.on_llm_final_cb = spoken_lines.append

    # User initiates turn via hotkey start/stop
    await client._start_recording()
    await client._stop_recording()
    sent_types = [json.loads(c.args[0])["type"] for c in client.connection.send.call_args_list]
    assert sent_types == ["start", "stop"]
    assert client._pipeline_busy.is_set()

    # Burst 1: rtsi.speak -> tts.started -> binary audio -> tts.completed
    client.event_handler.handle_text(json.dumps({"type": "rtsi.speak", "data": {"text": "On it."}}))
    client.event_handler.handle_text(json.dumps({"type": "tts.started", "data": "On it."}))
    client.event_handler.handle_binary(b"\x00\x01" * 160, playback_interrupted=client._playback_interrupted.is_set())
    client.event_handler.handle_text(json.dumps({"type": "tts.completed"}))

    # Must NOT reset turn to idle prematurely across TTS bursts
    assert client._pipeline_busy.is_set()
    assert client.status._snapshot.turn == "thinking"
    assert "On it." in spoken_lines

    # Burst 2: rtsi.await_user -> tts.started -> binary -> tts.completed
    client.event_handler.handle_text(json.dumps({
        "type": "rtsi.await_user",
        "data": {"kind": "confirmation", "question": "Should I send this?", "timeout_s": 60},
    }))
    client.event_handler.handle_text(json.dumps({"type": "tts.started", "data": "Should I send this?"}))
    client.event_handler.handle_binary(b"\x02\x03" * 160, playback_interrupted=client._playback_interrupted.is_set())
    if not client._playback_interrupted.is_set():
        client._playback_active.set()
    client.event_handler.handle_text(json.dumps({"type": "tts.completed"}))

    assert client._awaiting_user.is_set()
    assert client.status._snapshot.turn == "awaiting_user"

    # Hotkey reply during awaiting_user must send start + stop, NEVER cancel
    client.connection.send.reset_mock()
    await client._interrupt_and_start_recording()
    await client._stop_recording()

    reply_types = [json.loads(c.args[0])["type"] for c in client.connection.send.call_args_list]
    assert reply_types == ["start", "stop"]
    assert "cancel" not in reply_types
    assert not client._awaiting_user.is_set()

    # Final TTS burst + pipeline.completed -> idle
    client.event_handler.handle_text(json.dumps({"type": "tts.started", "data": "Done."}))
    client.event_handler.handle_text(json.dumps({"type": "tts.completed"}))
    assert client._pipeline_busy.is_set()
    client.event_handler.handle_text(json.dumps({"type": "pipeline.completed"}))
    assert not client._pipeline_busy.is_set()
    assert client.status._snapshot.turn == "idle"


@pytest.mark.asyncio
async def test_client_barge_in_when_not_awaiting_user_sends_cancel():
    client = _make_test_client()
    await client._start_recording()
    await client._stop_recording()
    client._playback_active.set()
    client.connection.send.reset_mock()

    # Mid-turn barge-in (not awaiting_user) must interrupt player AND send cancel before start
    await client._interrupt_and_start_recording()
    client.player.interrupt.assert_called_once()
    sent_types = [json.loads(c.args[0])["type"] for c in client.connection.send.call_args_list]
    assert sent_types == ["cancel", "start"]


def test_client_unknown_additive_ws_events_do_not_crash():
    client = _make_test_client()
    evt = client.event_handler.handle_text(json.dumps({"type": "rtsi.future_telemetry", "data": {"hop": 3}}))
    assert evt is not None and evt.type == "rtsi.future_telemetry"
    bad = client.event_handler.handle_text("not-json{")
    assert bad is None


# ---------------------------------------------------------------------------
# 2. Non-Browser Tool Smoke, Validation & Golden Tree Checks
# ---------------------------------------------------------------------------

def test_productivity_notes_and_timers_smoke_and_validation(tmp_path, monkeypatch):
    import quince_mcp.tools.productivity.handlers as prod_h

    monkeypatch.setattr(prod_h, "NOTES_DIRECTORY", tmp_path)

    # Validation: empty / title-only content rejected
    with pytest.raises(ValueError):
        _write_note("", "Body")
    with pytest.raises(ValueError):
        _write_note("Shopping", "Shopping")

    res_w = _write_note("Shopping List", "- Milk\n- Eggs")
    assert res_w["note_name"] == "Shopping List"
    assert _read_note("Shopping List")["content"] == "- Milk\n- Eggs"
    assert _list_notes()["count"] == 1

    res_e = _edit_note("Shopping List", content="- Bread", operation="append")
    assert "- Bread" in res_e["content"]
    assert _delete_note("Shopping List")["deleted"] is True

    # Timer smoke (mocking threading.Timer so nothing spawns background threads)
    with patch("quince_mcp.tools.productivity.handlers.threading.Timer") as mock_timer:
        t = _set_timer(60, "Tea")
        assert t["duration_seconds"] == 60
        assert len(_list_timers()["timers"]) >= 1
        assert _cancel_timer(t["timer_id"])["cancelled"] is True
        mock_timer.return_value.start.assert_called_once()

    with pytest.raises(ValueError):
        _set_timer(0, "Invalid")


def test_knowledge_and_memory_tools_mocked_network():
    with patch("quince_mcp.tools.knowledge.handlers.wikimedia_client") as mock_wiki:
        mock_wiki.wikipedia_search.return_value = {"query": "Python", "results": [{"title": "Python"}], "count": 1}
        mock_wiki.wikipedia_summary.return_value = {"title": "Python", "extract": "A programming language."}
        mock_wiki.wikipedia_page.return_value = {"title": "Python", "extract": "Long text", "truncated": False}

        assert _search_wikipedia("Python")["count"] == 1
        assert _get_wikipedia_summary("Python")["title"] == "Python"
        assert _get_wikipedia_page("Python")["extract"] == "Long text"

    # Memory tools accept hyphenated memory-id / command-id without crashing
    import asyncio
    del_mem_tool = memory_tool_tree["root--memory--delete-memory"]
    with patch("quince_mcp.apis.basket.basket_client.memory_client") as mock_mem_client:
        mock_mem_client.post = AsyncMock(return_value={"ok": True})
        res = asyncio.run(del_mem_tool.execute({"memory-id": "mem-123"}))
        assert res["ok"] is True
        mock_mem_client.post.assert_called_once()


def test_system_and_files_error_handling():
    assert _get_os_info()["os"]
    with patch("quince_mcp.tools.system.handlers.psutil.sensors_battery", return_value=None):
        bat = _get_battery_level()
        assert bat["available"] is False

    empty_cmd = _run_command("   ")
    assert "error" in empty_cmd

    missing_file = _read_file(str(Path(tempfile.gettempdir()) / "definitely_missing_quince_file_12345.txt"))
    assert missing_file["success"] is False

    missing_dir = _list_directory(str(Path(tempfile.gettempdir()) / "missing_dir_quince_99999"))
    assert missing_dir["success"] is False

    with tempfile.TemporaryDirectory() as td:
        p = str(Path(td) / "sample.txt")
        assert _write_file(p, "hello")["success"] is True
        # Writing without overwrite=True returns error cleanly
        dup = _write_file(p, "world", overwrite=False)
        assert dup["success"] is False


def test_golden_baseline_tool_tree_preserved():
    golden_path = Path(__file__).resolve().parent / "golden" / "baseline_tool_tree.json"
    data = json.loads(golden_path.read_text(encoding="utf-8"))
    baseline_tree = data["tool_tree"]

    # Every tool in the golden baseline must remain present with matching kind & required_arguments
    for tool_id, spec in baseline_tree.items():
        if tool_id == "root":
            # Root now has additive categories (files, web, browser)
            live_child_ids = {c.tool_id for c in root.children}
            for cid in spec["child_ids"]:
                assert cid in live_child_ids, f"Baseline root child missing: {cid}"
            continue

        assert tool_id in TOOL_TREE, f"Baseline tool missing from live TOOL_TREE: {tool_id}"
        live_tool = TOOL_TREE[tool_id]
        assert live_tool.kind == spec["kind"], f"Kind changed for {tool_id}"
        assert live_tool.required_arguments == spec["required_arguments"], (
            f"required_arguments changed for {tool_id}"
        )
        assert live_tool.description.strip(), f"Empty description for {tool_id}"
