"""Pytest configuration for separating deterministic CI tests from --live benchmarks."""
from __future__ import annotations

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run live Chrome / Basket / 4B LLM integration benchmarks",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--live"):
        return
    skip_live = pytest.mark.skip(reason="need --live option to run live Chrome/LLM tests")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
