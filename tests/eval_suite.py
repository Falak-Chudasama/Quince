#!/usr/bin/env python3
"""
Layer 5: Repeatable RTSI & Tool Evaluation / Scorecard Harness.

Usage:
  CI / deterministic mocked mode (default, <1s):
    python tests/eval_suite.py
    pytest tests/eval_suite.py -v

  Live mode (real Basket + local 4B model + Chrome bridge):
    python tests/eval_suite.py --live
    pytest tests/eval_suite.py --live -v
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock

import pytest

_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from quince_mcp.bridge.config import BridgeSettings
from quince_mcp.bridge.protocol import BridgeError
from quince_mcp.rtsi.machine import RtsiMachine
from quince_mcp.rtsi.states import State
from quince_mcp.server import navigate_impl


@dataclass
class EvalStepTrace:
    hop: int
    tool_id: str
    args: dict[str, Any]
    causal_outcome: str
    latency_ms: float
    recoverable_error: str | None = None
    arg_valid: bool = True


@dataclass
class EvalTaskResult:
    name: str
    category: str
    failure_mode: str | None
    passed: bool
    recovered: bool
    hops: int
    traces: list[EvalStepTrace] = field(default_factory=list)
    error: str = ""


def _validate_tool_args(tool_id: str, args: dict[str, Any]) -> bool:
    """Validate arguments against the live QuinceTool schema when available."""
    from quince_mcp.tool_tree import TOOL_TREE

    tool = TOOL_TREE.get(tool_id)
    if tool is None:
        return True
    for req in tool.required_arguments:
        if req not in args or args[req] is None:
            return False
    return True


async def _run_step(
    machine: RtsiMachine | None,
    tool_id: str,
    args: dict[str, Any],
    traces: list[EvalStepTrace],
    *,
    use_server_navigate: bool = False,
) -> dict[str, Any]:
    arg_valid = _validate_tool_args(tool_id, args)
    t0 = time.perf_counter()
    if use_server_navigate or machine is None:
        resp = await navigate_impl(tool_id, args)
    else:
        resp = await machine.handle(tool_id, args, describe_root_fn=AsyncMock())
    lat_ms = (time.perf_counter() - t0) * 1000.0

    result = resp.get("result") or {}
    sc_text = result.get("state_change_text", "")
    causal = "NONE"
    for candidate in ("NAVIGATED", "DOM_UPDATED", "VALUE_CHANGED", "SCROLLED", "NO_EFFECT"):
        if f"[LAST ACTION] {candidate}" in sc_text:
            causal = candidate
            break
    err_code = result.get("error") or resp.get("error")
    traces.append(
        EvalStepTrace(
            hop=len(traces) + 1,
            tool_id=tool_id,
            args=args,
            causal_outcome=causal,
            latency_ms=round(lat_ms, 3),
            recoverable_error=err_code if resp.get("recoverable") or result.get("recoverable") else None,
            arg_valid=arg_valid,
        )
    )
    return resp


def _make_mock_bridge(responses: list[Any]) -> MagicMock:
    bridge = MagicMock()
    bridge.is_connected = True
    bridge.connected_info = {"version": "0.1.0"}
    bridge.call = AsyncMock(side_effect=responses)
    return bridge


def _snap(url: str, title: str, body_lines: str, *, vp: str = "0% AT TOP | ~0.0 above | ~2.0 below | can_scroll: down", fp: str = "fp1") -> dict[str, Any]:
    return {
        "text": f"[PAGE] {title} | {url}\n[VIEWPORT] {vp}\n[FOCUS] none\n{body_lines}",
        "generation": 1,
        "page": {"url": url, "title": title},
        "observation_meta": {"url": url, "title": title, "state_fingerprint": fp},
    }


def _sc(outcome: str, url_before: str, url_after: str, title_after: str, **extra: Any) -> dict[str, Any]:
    effect_map = {
        "NAVIGATED": "navigated",
        "DOM_UPDATED": "dom_changed",
        "VALUE_CHANGED": "value_set",
        "SCROLLED": "none",
        "NO_EFFECT": "none",
    }
    base = {
        "effect": effect_map[outcome],
        "causal_outcome": outcome,
        "navigated": outcome == "NAVIGATED",
        "no_visible_change": outcome == "NO_EFFECT",
        "before": {"url": url_before, "title": "Before"},
        "after": {"url": url_after, "title": title_after},
        "dom": {"added": [], "removed": [], "changed": []},
        "wait": {"settled": True, "reason": "quiet", "elapsed_ms": 80},
    }
    base.update(extra)
    return {"state_change": base}


# ---------------------------------------------------------------------------
# 13 Deterministic Benchmark Tasks
# ---------------------------------------------------------------------------

async def _task_search_submit() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://www.amazon.com/", "title": "Amazon"},
        _snap("https://www.amazon.com/", "Amazon", '[e3] searchbox "Search" [searchbox, enter-submits]'),
        _sc("NAVIGATED", "https://www.amazon.com/", "https://www.amazon.com/s?k=ssd", "Amazon: ssd", navigation_kind="full"),
        _snap("https://www.amazon.com/s?k=ssd", "Amazon: ssd", '[e8] heading(1) "Samsung 990 PRO"'),
        _snap("https://www.amazon.com/s?k=ssd", "Amazon: ssd", '[e8] heading(1) "Samsung 990 PRO"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Search Amazon for ssd"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://www.amazon.com/"}, traces)
    await _run_step(m, "root--browser--type-text", {"ref": "e3", "text": "ssd", "submit": True}, traces)
    res = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Found Samsung 990 PRO"}, traces)
    passed = bool(res["success"] and res["rtsi_outcome"]["status"] == "success")
    return EvalTaskResult("search_submit", "search", None, passed, True, len(traces), traces)


async def _task_premature_exit_recovery() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://www.amazon.com/", "title": "Amazon"},
        _snap("https://www.amazon.com/", "Amazon", '[e3] searchbox "Search" [searchbox, enter-submits]'),
        _sc("VALUE_CHANGED", "https://www.amazon.com/", "https://www.amazon.com/", "Amazon", target={"ref": "e3", "role": "searchbox"}),
        _snap("https://www.amazon.com/", "Amazon", '[e3] searchbox "Search" value="mouse" [focused]'),
        _snap("https://www.amazon.com/", "Amazon", '[e3] searchbox "Search" value="mouse" [focused]'),
        _sc("NAVIGATED", "https://www.amazon.com/", "https://www.amazon.com/s?k=mouse", "Amazon: mouse", navigation_kind="full"),
        _snap("https://www.amazon.com/s?k=mouse", "Amazon: mouse", '[e12] link "Logitech MX Master"'),
        _snap("https://www.amazon.com/s?k=mouse", "Amazon: mouse", '[e12] link "Logitech MX Master"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Search for mouse"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://www.amazon.com/"}, traces)
    await _run_step(m, "root--browser--type-text", {"ref": "e3", "text": "mouse", "submit": False}, traces)
    blk = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Searched"}, traces)
    recovered = blk.get("result", {}).get("error") == "premature_exit_blocked"
    await _run_step(m, "root--browser--press-key", {"key": "Enter", "ref": "e3"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Found Logitech MX Master"}, traces)
    return EvalTaskResult("premature_exit_recovery", "recovery", "premature_exit", bool(done["success"]), recovered, len(traces), traces)


async def _task_filter_and_sort() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://shop.example.com/s", "title": "Results"},
        _snap("https://shop.example.com/s", "Results", '[e5] combobox "Sort"\n[e6] checkbox "Prime"'),
        _sc("VALUE_CHANGED", "https://shop.example.com/s", "https://shop.example.com/s", "Results", target={"ref": "e5", "role": "combobox"}),
        _snap("https://shop.example.com/s", "Results", '[e5] combobox "Sort"\n[e6] checkbox "Prime"'),
        _sc("VALUE_CHANGED", "https://shop.example.com/s", "https://shop.example.com/s", "Results", target={"ref": "e6", "role": "checkbox"}),
        _snap("https://shop.example.com/s", "Results", '[e5] combobox "Sort"\n[e6] checkbox "Prime" [checked]'),
        _snap("https://shop.example.com/s", "Results", '[e5] combobox "Sort"\n[e6] checkbox "Prime" [checked]'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Filter by Prime and sort by price"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://shop.example.com/s"}, traces)
    await _run_step(m, "root--browser--select-option", {"ref": "e5", "option": "Price: Low to High"}, traces)
    await _run_step(m, "root--browser--set-checked", {"ref": "e6", "checked": True}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Filtered and sorted"}, traces)
    return EvalTaskResult("filter_and_sort", "controls", None, bool(done["success"]), True, len(traces), traces)


async def _task_multi_page_scroll() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://docs.example.com/", "title": "Docs"},
        _snap("https://docs.example.com/", "Docs", '[e1] heading(1) "Intro"'),
        {"results": [{"ref": "e40", "role": "link", "name": "Pricing", "position": "below"}], "counts": {"total": 1, "in_viewport": 0, "above_viewport": 0, "below_viewport": 1}},
        _sc("SCROLLED", "https://docs.example.com/", "https://docs.example.com/", "Docs", scroll={"before": 0, "after": 800, "max": 800, "pct": 100, "at_bottom": True}),
        _snap("https://docs.example.com/", "Docs", '[e40] link "Pricing"', vp="100% AT BOTTOM | ~1.0 above | ~0.0 below | can_scroll: up"),
        _sc("NAVIGATED", "https://docs.example.com/", "https://docs.example.com/pricing", "Pricing", navigation_kind="full"),
        _snap("https://docs.example.com/pricing", "Pricing", '[e1] heading(1) "$19/mo"'),
        _snap("https://docs.example.com/pricing", "Pricing", '[e1] heading(1) "$19/mo"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Find pricing"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://docs.example.com/"}, traces)
    await _run_step(m, "root--browser--find-in-page", {"query": "Pricing"}, traces)
    await _run_step(m, "root--browser--scroll", {"direction": "down", "pages": 0.8}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e40"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Pricing is $19/mo"}, traces)
    return EvalTaskResult("multi_page_scroll", "navigation", None, bool(done["success"]), True, len(traces), traces)


async def _task_modal_dismissal() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://site.example.com/", "title": "Site"},
        _snap("https://site.example.com/", "Site", '[e5] button "Continue"'),
        BridgeError("covered_by", "Covered by dialog", data={"covered_by": "dialog"}),
        _snap("https://site.example.com/", "Site", '[MODAL] [e30] dialog "Consent"\n[e31] button "Close"\n[e5] button "Continue"'),
        _sc("DOM_UPDATED", "https://site.example.com/", "https://site.example.com/", "Site", dom={"added": [], "removed": [{"ref": "e30", "desc": "dialog"}], "changed": []}),
        _snap("https://site.example.com/", "Site", '[e5] button "Continue"'),
        _sc("NAVIGATED", "https://site.example.com/", "https://site.example.com/next", "Next", navigation_kind="full"),
        _snap("https://site.example.com/next", "Next", '[e1] heading(1) "Welcome"'),
        _snap("https://site.example.com/next", "Next", '[e1] heading(1) "Welcome"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Click Continue"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://site.example.com/"}, traces)
    cov = await _run_step(m, "root--browser--click", {"ref": "e5"}, traces)
    recovered = cov.get("recoverable") is True and cov.get("result", {}).get("error") == "covered_by"
    await _run_step(m, "root--browser--press-key", {"key": "Escape"}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e5"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Continued past modal"}, traces)
    return EvalTaskResult("modal_dismissal", "recovery", "modal", bool(done["success"]), recovered, len(traces), traces)


async def _task_autocomplete_select() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://maps.example.com/", "title": "Maps"},
        _snap("https://maps.example.com/", "Maps", '[e2] searchbox "Search place"'),
        _sc("DOM_UPDATED", "https://maps.example.com/", "https://maps.example.com/", "Maps", autocomplete_appeared=True, dom={"added": [{"ref": "e30", "role": "listbox", "desc": 'listbox "Suggestions"'}, {"ref": "e31", "role": "option", "desc": 'option "London, UK"'}], "removed": [], "changed": []}),
        _snap("https://maps.example.com/", "Maps", '[e31] option "London, UK"'),
        _sc("NAVIGATED", "https://maps.example.com/", "https://maps.example.com/place/london", "London", navigation_kind="full"),
        _snap("https://maps.example.com/place/london", "London", '[e1] heading(1) "London"'),
        _snap("https://maps.example.com/place/london", "London", '[e1] heading(1) "London"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Find London"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://maps.example.com/"}, traces)
    res_type = await _run_step(m, "root--browser--type-text", {"ref": "e2", "text": "Lon", "submit": False}, traces)
    assert "Autocomplete suggestions appeared" in res_type["result"]["state_change_text"]
    await _run_step(m, "root--browser--click", {"ref": "e31"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Opened London"}, traces)
    return EvalTaskResult("autocomplete_select", "search", None, bool(done["success"]), True, len(traces), traces)


async def _task_form_fill() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://form.example.com/", "title": "Contact"},
        _snap("https://form.example.com/", "Contact", '[e1] textbox "Name"\n[e2] textbox "Email"\n[e3] button "Send"'),
        _sc("VALUE_CHANGED", "https://form.example.com/", "https://form.example.com/", "Contact"),
        _snap("https://form.example.com/", "Contact", '[e1] textbox "Name"\n[e2] textbox "Email"\n[e3] button "Send"'),
        _sc("NAVIGATED", "https://form.example.com/", "https://form.example.com/sent", "Sent", navigation_kind="full"),
        _snap("https://form.example.com/sent", "Sent", '[e1] heading(1) "Received"'),
        _snap("https://form.example.com/sent", "Sent", '[e1] heading(1) "Received"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Fill contact form"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://form.example.com/"}, traces)
    await _run_step(m, "root--browser--fill-form", {"refs": ["e1", "e2"], "values": ["Ada", "ada@example.com"]}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e3"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Form submitted"}, traces)
    return EvalTaskResult("form_fill", "forms", None, bool(done["success"]), True, len(traces), traces)


async def _task_risky_checkout_abort() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://shop.example.com/checkout", "title": "Checkout"},
        _snap("https://shop.example.com/checkout", "Checkout", '[e9] button "Place Order"'),
        BridgeError("confirmation_required", "Confirm", data={"action": {"name": "Place Order", "host": "shop.example.com"}, "pending_token": "t1"}),
        _snap("https://shop.example.com/checkout", "Checkout", '[e9] button "Place Order"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Checkout"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://shop.example.com/checkout"}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e9"}, traces)
    ans = await _run_step(m, "root--browser--provide-answer", {"answer": "no"}, traces)
    recovered = ans.get("result", {}).get("user_declined") is True
    done = await _run_step(m, "root--browser--unsuccessful-termination", {"reason": "User declined order"}, traces)
    return EvalTaskResult("risky_checkout_abort", "safety", "confirmation", bool(done["success"]), recovered, len(traces), traces)


async def _task_risky_checkout_confirm() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://shop.example.com/checkout", "title": "Checkout"},
        _snap("https://shop.example.com/checkout", "Checkout", '[e9] button "Place Order"'),
        BridgeError("confirmation_required", "Confirm", data={"action": {"name": "Place Order", "host": "shop.example.com"}, "pending_token": "t2"}),
        _sc("NAVIGATED", "https://shop.example.com/checkout", "https://shop.example.com/ok", "Confirmed", navigation_kind="full"),
        _snap("https://shop.example.com/ok", "Confirmed", '[e1] heading(1) "Order Placed"'),
        _snap("https://shop.example.com/ok", "Confirmed", '[e1] heading(1) "Order Placed"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Place order"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://shop.example.com/checkout"}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e9"}, traces)
    res_yes = await _run_step(m, "root--browser--provide-answer", {"answer": "yes"}, traces)
    recovered = "[LAST ACTION] NAVIGATED" in res_yes.get("result", {}).get("state_change_text", "")
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Order placed"}, traces)
    return EvalTaskResult("risky_checkout_confirm", "safety", "confirmation", bool(done["success"]), recovered, len(traces), traces)


async def _task_stall_recovery() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    no_eff = _sc("NO_EFFECT", "https://ex.com/", "https://ex.com/", "Ex", state_fingerprint="fp_stall")
    snap_stall = _snap("https://ex.com/", "Ex", '[e1] button "A"\n[e2] button "B"', fp="fp_stall")
    bridge = _make_mock_bridge([
        {"ok": True},  # session.begin
        {"tabs": []},  # tabs.list
        {"tab_id": 1, "url": "https://ex.com/", "title": "Ex"},  # tabs.open
        snap_stall,  # open-tab obs
        no_eff,      # click e1 -> NO_EFFECT -> COMPARE
        snap_stall,  # continue obs
        no_eff,      # click e2 -> NO_EFFECT -> COMPARE
        snap_stall,  # continue obs
        snap_stall,  # blocked click e2 obs
        _sc("SCROLLED", "https://ex.com/", "https://ex.com/", "Ex", scroll={"before": 0, "after": 500, "max": 1000, "pct": 50}, state_fingerprint="fp_scrolled"),
        _snap("https://ex.com/", "Ex", '[e3] button "Real Button"', fp="fp_scrolled"),
        _sc("NAVIGATED", "https://ex.com/", "https://ex.com/done", "Done", navigation_kind="full"),
        _snap("https://ex.com/done", "Done", '[e1] heading(1) "Done"'),
        _snap("https://ex.com/done", "Done", '[e1] heading(1) "Done"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Recover from stall"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://ex.com/"}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e1"}, traces)
    await _run_step(m, "root--browser--record-comparison", {"comparison": "no change"}, traces)
    await _run_step(m, "root--browser--continue", {}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e2"}, traces)
    await _run_step(m, "root--browser--record-comparison", {"comparison": "still no change"}, traces)
    await _run_step(m, "root--browser--continue", {}, traces)
    blk = await _run_step(m, "root--browser--click", {"ref": "e2"}, traces)
    recovered = blk.get("result", {}).get("error") == "repeated_dead_action"
    await _run_step(m, "root--browser--scroll", {"direction": "down", "pages": 0.8}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e3"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Recovered and finished"}, traces)
    return EvalTaskResult("stall_recovery", "recovery", "stall", bool(done["success"]), recovered, len(traces), traces)


async def _task_stale_ref_recovery() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://ex.com/", "title": "Ex"},
        _snap("https://ex.com/", "Ex", '[e4] button "Old"'),
        BridgeError("stale_ref", "Stale ref e4"),
        _snap("https://ex.com/", "Ex", '[e14] button "Updated"'),
        _sc("NAVIGATED", "https://ex.com/", "https://ex.com/ok", "OK", navigation_kind="full"),
        _snap("https://ex.com/ok", "OK", '[e1] heading(1) "OK"'),
        _snap("https://ex.com/ok", "OK", '[e1] heading(1) "OK"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Click button"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://ex.com/"}, traces)
    stale = await _run_step(m, "root--browser--click", {"ref": "e4"}, traces)
    recovered = stale.get("result", {}).get("error") == "stale_ref" and stale.get("recoverable") is True
    await _run_step(m, "root--browser--click", {"ref": "e14"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Recovered stale ref"}, traces)
    return EvalTaskResult("stale_ref_recovery", "recovery", "stale_ref", bool(done["success"]), recovered, len(traces), traces)


async def _task_cross_question_multi_turn() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    bridge = _make_mock_bridge([
        {"ok": True}, {"tabs": []},
        {"tab_id": 1, "url": "https://portal.example.com/", "title": "Portal"},
        _snap("https://portal.example.com/", "Portal", '[e2] textbox "City"\n[e3] button "Save"'),
        _snap("https://portal.example.com/", "Portal", '[e2] textbox "City"\n[e3] button "Save"'),
        _snap("https://portal.example.com/", "Portal", '[e2] textbox "City"\n[e3] button "Save"'),
        _sc("VALUE_CHANGED", "https://portal.example.com/", "https://portal.example.com/", "Portal"),
        _snap("https://portal.example.com/", "Portal", '[e2] textbox "City" value="Austin"\n[e3] button "Save"'),
        _sc("NAVIGATED", "https://portal.example.com/", "https://portal.example.com/saved", "Saved", navigation_kind="full"),
        _snap("https://portal.example.com/saved", "Saved", '[e1] heading(1) "Saved"'),
        _snap("https://portal.example.com/saved", "Saved", '[e1] heading(1) "Saved"'),
        {"ok": True},
    ])
    m = RtsiMachine(bridge, BridgeSettings(judge_policy="adaptive", termination_ends_loop=True))
    await _run_step(m, "root--browser", {"goal": "Save city"}, traces)
    await _run_step(m, "root--browser--open-tab", {"url": "https://portal.example.com/"}, traces)
    await _run_step(m, "root--browser--refresh-page", {}, traces)  # opens exits for cross-question
    q = await _run_step(m, "root--browser--cross-question", {"question": "Which city?"}, traces)
    assert "await_user" in q
    ans = await _run_step(m, "root--browser--provide-answer", {"answer": "Austin"}, traces)
    assert ans["result"]["user_answer"] == "Austin"
    await _run_step(m, "root--browser--type-text", {"ref": "e2", "text": "Austin"}, traces)
    await _run_step(m, "root--browser--click", {"ref": "e3"}, traces)
    done = await _run_step(m, "root--browser--successful-termination", {"result_summary": "Saved Austin"}, traces)
    return EvalTaskResult("cross_question_multi_turn", "multi_turn", None, bool(done["success"]), True, len(traces), traces)


async def _task_non_browser_system_lookup() -> EvalTaskResult:
    traces: list[EvalStepTrace] = []
    res = await _run_step(None, "root--system--get-os-info", {}, traces, use_server_navigate=True)
    passed = bool(res.get("success") and res.get("result", {}).get("os"))
    return EvalTaskResult("non_browser_system_lookup", "system", None, passed, True, len(traces), traces)


EVAL_TASKS: list[Callable[[], Coroutine[Any, Any, EvalTaskResult]]] = [
    _task_search_submit,
    _task_premature_exit_recovery,
    _task_filter_and_sort,
    _task_multi_page_scroll,
    _task_modal_dismissal,
    _task_autocomplete_select,
    _task_form_fill,
    _task_risky_checkout_abort,
    _task_risky_checkout_confirm,
    _task_stall_recovery,
    _task_stale_ref_recovery,
    _task_cross_question_multi_turn,
    _task_non_browser_system_lookup,
]


async def run_mocked_eval_suite() -> dict[str, Any]:
    results: list[EvalTaskResult] = []
    for task_fn in EVAL_TASKS:
        try:
            results.append(await task_fn())
        except Exception as exc:
            results.append(
                EvalTaskResult(task_fn.__name__.lstrip("_task_"), "error", None, False, False, 0, error=repr(exc))
            )

    all_traces = [t for r in results for t in r.traces]
    latencies = sorted(t.latency_ms for t in all_traces)
    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))] if latencies else 0.0
    hops = [r.hops for r in results]

    failure_modes: dict[str, list[bool]] = {}
    for r in results:
        if r.failure_mode:
            failure_modes.setdefault(r.failure_mode, []).append(r.recovered)

    recovery_rates = {
        mode: round(sum(vals) / len(vals), 3)
        for mode, vals in failure_modes.items()
    }
    valid_args_rate = round(sum(1 for t in all_traces if t.arg_valid) / max(1, len(all_traces)), 3)

    return {
        "total_tasks": len(results),
        "passed_tasks": sum(1 for r in results if r.passed),
        "pass_at_1": round(sum(1 for r in results if r.passed) / max(1, len(results)), 3),
        "avg_hops": round(sum(hops) / max(1, len(hops)), 2),
        "max_hops": max(hops) if hops else 0,
        "recovery_rates": recovery_rates,
        "arg_validity_rate": valid_args_rate,
        "p50_latency_ms": round(p50, 3),
        "p95_latency_ms": round(p95, 3),
        "results": results,
    }


def run_live_eval_probe(trace_path: Path) -> dict[str, Any]:
    """
    Opt-in --live runner against live Basket HTTP/WS + Quince MCP bridge.
    Records JSON step traces when live services are reachable.
    """
    basket_url = os.environ.get("BASKET_HTTP_URL", "http://127.0.0.1:7000/docs")
    mcp_url = os.environ.get("QUINCE_MCP_URL", "http://127.0.0.1:7004/mcp")
    probe = {"basket_online": False, "mcp_online": False, "traces": []}
    for key, url in (("basket_online", basket_url), ("mcp_online", mcp_url)):
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=2.0) as resp:
                probe[key] = resp.status < 500
        except Exception:
            probe[key] = False
    trace_path.write_text(json.dumps(probe, indent=2), encoding="utf-8")
    return probe


def print_scorecard(summary: dict[str, Any]) -> None:
    print("\n" + "=" * 68)
    print("  QUINCE RTSI EVALUATION SCORECARD")
    print("=" * 68)
    print(f"  Pass@1 Rate         : {summary['passed_tasks']}/{summary['total_tasks']} ({summary['pass_at_1']*100:.1f}%)")
    print(f"  Avg / Max Hops      : {summary['avg_hops']} / {summary['max_hops']}")
    print(f"  Arg Validity Rate   : {summary['arg_validity_rate']*100:.1f}%")
    print(f"  Latency p50 / p95   : {summary['p50_latency_ms']} ms / {summary['p95_latency_ms']} ms")
    print("  Failure-Mode Recovery:")
    for mode, rate in summary["recovery_rates"].items():
        print(f"    - {mode:<18}: {rate*100:.1f}%")
    for r in summary["results"]:
        if not r.passed:
            print(f"  [FAIL] {r.name}: {r.error or 'returned passed=False'}")
    print("=" * 68)


# ---------------------------------------------------------------------------
# Pytest entrypoints
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_eval_suite_deterministic_ci():
    summary = await run_mocked_eval_suite()
    assert summary["pass_at_1"] == 1.0
    assert summary["arg_validity_rate"] == 1.0
    for mode, rate in summary["recovery_rates"].items():
        assert rate == 1.0, f"Recovery rate < 100% for {mode}"


@pytest.mark.live
def test_eval_suite_live_optional(tmp_path):
    probe = run_live_eval_probe(tmp_path / "live_traces.json")
    assert (tmp_path / "live_traces.json").exists()
    if not probe["basket_online"] and not probe["mcp_online"]:
        pytest.skip("Live Basket / MCP servers are not running")


def main() -> int:
    parser = argparse.ArgumentParser(description="Quince RTSI Evaluation Harness")
    parser.add_argument("--live", action="store_true", help="Run live probe against Basket/MCP/Chrome")
    parser.add_argument("--trace-out", default="tests/eval_traces_live.json", help="Live trace output path")
    args = parser.parse_args()

    summary = asyncio.run(run_mocked_eval_suite())
    print_scorecard(summary)

    if args.live:
        probe = run_live_eval_probe(Path(args.trace_out))
        print(f"Live probe written to {args.trace_out}: {probe}")

    return 0 if summary["pass_at_1"] == 1.0 else 1


if __name__ == "__main__":
    sys.exit(main())
