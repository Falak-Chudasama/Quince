import sys
from pyvda import get_virtual_desktops, VirtualDesktop

def switch_to_desktop(target_number):
    try:
        # User asks for "Desktop 2", which is index 1
        target_index = int(target_number) - 1
        desktops = get_virtual_desktops()
        
        # If the requested desktop doesn't exist, create new ones until it does
        while len(desktops) <= target_index:
            VirtualDesktop.create()
            desktops = get_virtual_desktops()
            
        # Jump to the target desktop
        desktops[target_index].go()
        print(f"SUCCESS: Switched to desktop {target_number}")
        
    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        switch_to_desktop(sys.argv[1])