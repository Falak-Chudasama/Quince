import sys
import json
import threading
import time
import keyboard
import soundfile as sf
import sounddevice as sd
from hotkey_listener import AudioRecorder

def send_to_node(msg_type, data):
    payload = json.dumps({"type": msg_type, "data": data})
    print(payload, flush=True)

def play_audio_file(file_path):
    try:
        data, fs = sf.read(file_path)
        sd.play(data, fs)
        sd.wait()
    except Exception as e:
        send_to_node("error", f"Audio play error: {e}")

def listen_for_node_commands():
    for line in sys.stdin:
        try:
            message = json.loads(line.strip())
            if message.get("type") == "play_audio":
                audio_path = message.get("data")
                send_to_node("status", "Playing response...")
                play_audio_file(audio_path)
        except Exception:
            pass

def main():
    recorder = AudioRecorder()
    threading.Thread(target=listen_for_node_commands, daemon=True).start()

    send_to_node("status", "Python Audio I/O Ready. Hold Ctrl+Shift+Q to speak.")

    while True:
        try:
            if keyboard.is_pressed('ctrl+shift+q'):
                send_to_node("status", "Listening...")
                recorder.start_recording()

                while keyboard.is_pressed('ctrl+shift+q'):
                    time.sleep(0.05)

                send_to_node("status", "Sending audio to Brain...")
                audio_file = recorder.stop_recording()

                if audio_file:
                    # Send the file path to Node.js for Groq API processing
                    send_to_node("audio_ready", audio_file)
            time.sleep(0.05)
        except KeyboardInterrupt:
            break
        except Exception as e:
            send_to_node("error", str(e))

if __name__ == "__main__":
    main()