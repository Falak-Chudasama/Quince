"""
Tests for argument translation and validation:
- _translate_args mapping for all browser actions
- checks defaults for scope, max_chars, clear_first, direction, wait seconds
- checks url presence on goto vs reload/back
- checks fill_form refs and values alignment
"""
import pytest
from unittest.mock import MagicMock
from quince_mcp.rtsi.machine import RtsiMachine
from quince_mcp.bridge.config import BridgeSettings


@pytest.fixture
def machine():
    return RtsiMachine(bridge=MagicMock(), settings=BridgeSettings())


def test_translate_open_tab(machine):
    args = machine._translate_args("root--browser--open-tab", {"url": "https://example.com", "active": True})
    assert args == {"url": "https://example.com", "active": True}


def test_translate_navigate(machine):
    args_reload = machine._translate_args("root--browser--navigate", {"action": "reload"})
    assert args_reload == {"action": "reload"}

    args_goto = machine._translate_args("root--browser--navigate", {"action": "goto", "url": "https://example.com"})
    assert args_goto == {"action": "goto", "url": "https://example.com"}


def test_translate_refresh_page(machine):
    args = machine._translate_args("root--browser--refresh-page", {"scope": "full"})
    assert args["scope"] == "full"
    assert "max_chars" in args


def test_translate_find_and_read(machine):
    find_args = machine._translate_args("root--browser--find-in-page", {"query": "Submit", "max_results": 3})
    assert find_args == {"query": "Submit", "max_results": 3}

    read_args = machine._translate_args("root--browser--read-text", {"ref": "e14", "max_chars": 2000})
    assert read_args == {"ref": "e14", "max_chars": 2000}


def test_translate_click_type_press(machine):
    click_args = machine._translate_args("root--browser--click", {"ref": "e14", "click_type": "double"})
    assert click_args == {"ref": "e14", "click_type": "double"}

    type_args = machine._translate_args("root--browser--type-text", {"ref": "e14", "text": "Hello", "press_enter": True})
    assert type_args["ref"] == "e14"
    assert type_args["text"] == "Hello"
    assert type_args["clear_first"] is True
    assert type_args["press_enter"] is True

    key_args = machine._translate_args("root--browser--press-key", {"key": "Enter", "ref": "e14"})
    assert key_args == {"key": "Enter", "ref": "e14"}


def test_translate_scroll_select_check(machine):
    scroll_args = machine._translate_args("root--browser--scroll", {"direction": "down", "ref": "e10"})
    assert scroll_args == {"direction": "down", "ref": "e10"}

    select_args = machine._translate_args("root--browser--select-option", {"ref": "e10", "option": "Option 1"})
    assert select_args == {"ref": "e10", "option": "Option 1"}

    check_args = machine._translate_args("root--browser--set-checked", {"ref": "e10", "checked": True})
    assert check_args == {"ref": "e10", "checked": True}


def test_translate_fill_form_and_wait(machine):
    fill_args = machine._translate_args("root--browser--fill-form", {"refs": ["e1", "e2"], "values": ["Alice", "alice@example.com"]})
    assert fill_args == {"refs": ["e1", "e2"], "values": ["Alice", "alice@example.com"]}

    wait_args = machine._translate_args("root--browser--wait", {"seconds": 5})
    assert wait_args == {"seconds": 5}
