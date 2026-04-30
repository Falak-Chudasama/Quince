import io
import base64
import sys
from PIL import ImageGrab

def get_screen_base64():
    try:
        # Grab screen entirely in RAM
        img = ImageGrab.grab()
        # Resize to keep the base64 payload under Groq's limits
        img.thumbnail((1280, 720))
        
        # Save to byte buffer instead of disk
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=70)
        
        # Encode and print to stdout for Node.js to catch
        b64_string = base64.b64encode(buf.getvalue()).decode('utf-8')
        print(b64_string)
    except Exception as e:
        print(f"ERROR:{str(e)}", file=sys.stderr)

if __name__ == "__main__":
    get_screen_base64()
    