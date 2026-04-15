from faster_whisper import WhisperModel

class STTService:
    def __init__(self):
        try:
            self.model = WhisperModel("large-v3", device="cuda", compute_type="int8")
        except Exception as e:
            print(f"CUDA initialization failed, falling back to CPU: {e}", flush=True)
            try:
                self.model = WhisperModel("large-v3", device="cpu", compute_type="int8")
            except Exception as e2:
                print(f"int8 failed, falling back to float32: {e2}", flush=True)
                self.model = WhisperModel("large-v3", device="cpu", compute_type="float32")

    def transcribe(self, audio_path):
        segments, _ = self.model.transcribe(
            audio_path,
            beam_size=5,
            language="en",
            vad_filter=False,
            vad_parameters=dict(min_silence_duration_ms=500)
        )
        text = "".join([segment.text for segment in segments])
        print(f"Raw transcription: '{text}'", flush=True)
        return text.strip()