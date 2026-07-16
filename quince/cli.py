from __future__ import annotations

import sys
from pathlib import Path

from .agent import QuinceAgent
from .config import load_settings
from .prompts import load_preferences_file

def main() -> int:
    settings = load_settings()
    preferences_text = load_preferences_file(settings.preferences_path)
    agent = QuinceAgent(settings, preferences_text)
    agent.start()

    print("\nQuince is ready. Type a task and press Enter.")
    print("Type 'exit' to quit. Type 'reload prefs' after editing preferences.txt.\n")

    try:
        while True:
            task = input("quince> ").strip()
            if not task:
                continue
            if task.lower() in {"exit", "quit"}:
                break
            if task.lower() == "reload prefs":
                preferences_text = load_preferences_file(settings.preferences_path)
                agent.reload_preferences(preferences_text)
                print("Preferences reloaded.")
                continue
            result = agent.run(task)
            print(f"quince: {result}\n")
    finally:
        agent.stop()

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
