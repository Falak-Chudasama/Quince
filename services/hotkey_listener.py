import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os

class AudioRecorder:
    def __init__(self, sample_rate=16000):
        self.sample_rate = sample_rate
        self.is_recording = False
        self.audio_data = []
        self.temp_filename = os.path.abspath("temp_recording.wav")
        self.stream = None

    def start_recording(self):
        self.is_recording = True
        self.audio_data = []
        
        def callback(indata, frames, time, status):
            if self.is_recording:
                self.audio_data.append(indata.copy())

        self.stream = sd.InputStream(samplerate=self.sample_rate, channels=1, callback=callback)
        self.stream.start()

    def stop_recording(self):
        self.is_recording = False
        if self.stream:
            self.stream.stop()
            self.stream.close()
        
        return self.save_audio()

    def save_audio(self):
        if not self.audio_data:
            return None
            
        audio_np = np.concatenate(self.audio_data, axis=0)
        audio_int16 = (audio_np * 32767).astype(np.int16)
        wav.write(self.temp_filename, self.sample_rate, audio_int16)
        
        return self.temp_filename