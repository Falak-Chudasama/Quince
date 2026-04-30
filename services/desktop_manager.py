import sys
import json
import re
from pyvda import get_virtual_desktops, VirtualDesktop

def switch_to_desktop(query):
    try:
        desktops = get_virtual_desktops()
        query_lower = query.lower().strip()
        target_desktop = None
        
        # 1. Exact Name Match (e.g., "Work", "Gaming")
        for d in desktops:
            if d.name and d.name.lower() == query_lower:
                target_desktop = d
                break
                
        # 2. Partial Name Match
        if not target_desktop:
            for d in desktops:
                if d.name and (query_lower in d.name.lower() or d.name.lower() in query_lower):
                    target_desktop = d
                    break
                    
        # 3. Number/Index Match (e.g., "2", "Desktop 2")
        if not target_desktop:
            match = re.search(r'\d+', query)
            if match:
                idx = int(match.group()) - 1
                if 0 <= idx < len(desktops):
                    target_desktop = desktops[idx]
                elif idx >= len(desktops):
                    # Create desktops until we reach the requested index
                    while len(get_virtual_desktops()) <= idx:
                        VirtualDesktop.create()
                    target_desktop = get_virtual_desktops()[idx]

        # 4. Execute Switch
        if target_desktop:
            target_desktop.go()
            desktop_name = target_desktop.name if target_desktop.name else f"Desktop {target_desktop.number}"
            print(json.dumps({"success": True, "message": f"Switched to {desktop_name}"}))
        else:
            print(json.dumps({"success": False, "message": f"Could not find a desktop matching '{query}'"}))
            
    except Exception as e:
        print(json.dumps({"success": False, "message": str(e)}))

if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Join arguments to support multi-word desktop names (e.g., "Side Project")
        switch_to_desktop(" ".join(sys.argv[1:]))
    else:
        print(json.dumps({"success": False, "message": "No query provided."}))