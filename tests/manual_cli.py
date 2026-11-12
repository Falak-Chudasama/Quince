"""
manual_cli.py — Basket-less interactive CLI to drive Quince RTSI with your Chrome browser.

Usage:
  python -m tests.manual_cli
"""
import asyncio
import json
from quince_mcp.server import navigate_impl


async def main():
    print("=" * 60)
    print("  QUINCE RTSI MANUAL CLI")
    print("=" * 60)
    print("Ensure the Quince extension is loaded and connected in Chrome.\n")

    # Step 1: Enter root--browser
    print("[1] Navigating to root--browser...")
    res = await navigate_impl("root--browser", {})
    
    if not res.get("success"):
        print(f"\n[-] Error: {res.get('message')}")
        print("    Did you install the extension in Chrome and paste the token from:")
        print("    quince_mcp/bridge/.bridge_token ?")
        return

    print("\n[+] Success! Browser session started.")
    print(f"    Session ID: {res['result'].get('session_id')}")
    tabs = res["result"].get("tabs", [])
    print(f"    Open Tabs: {len(tabs)}")
    for t in tabs[:5]:
        print(f"      - [{t.get('tab_id')}] {t.get('title')} ({t.get('url')})")

    # Interactive Loop
    while True:
        children = res.get("children", [])
        valid_tools = [c["tool_id"] for c in children if "tool_id" in c]

        print("\n" + "-" * 60)
        print("AVAILABLE OPTIONS:")
        for idx, tool_id in enumerate(valid_tools):
            print(f"  [{idx + 1}] {tool_id}")

        choice = input("\nSelect an option number (or 'q' to quit): ").strip()
        if choice.lower() in ("q", "quit", "exit"):
            print("Ending session...")
            await navigate_impl("terminate", {})
            break

        if not choice.isdigit() or int(choice) < 1 or int(choice) > len(valid_tools):
            print("Invalid selection. Try again.")
            continue

        selected_tool = valid_tools[int(choice) - 1]
        args = {}

        if selected_tool == "root--browser--open-tab":
            url = input("Enter URL to open: ").strip()
            args["url"] = url or "https://example.com"
        elif selected_tool == "root--browser--click":
            ref = input("Enter element ref (e.g. e1): ").strip()
            args["ref"] = ref
        elif selected_tool == "root--browser--type-text":
            ref = input("Enter element ref (e.g. e1): ").strip()
            text = input("Enter text to type: ").strip()
            args["ref"] = ref
            args["text"] = text
        elif selected_tool == "root--browser--record-comparison":
            comp = input("Enter short comparison notes: ").strip()
            args["comparison"] = comp
        elif selected_tool == "root--browser--successful-termination":
            summary = input("Enter result summary: ").strip()
            args["result_summary"] = summary or "Done"

        print(f"\n--> Calling {selected_tool}...")
        res = await navigate_impl(selected_tool, args)

        print(f"Status: {'Success' if res.get('success') else 'Failed'}")
        print(f"Message: {res.get('message')}")
        if res.get("result"):
            print("\nResult Data:")
            print(json.dumps(res["result"], indent=2))

        if res.get("terminate"):
            print("\n[!] Session completed or terminated.")
            break


if __name__ == "__main__":
    asyncio.run(main())
