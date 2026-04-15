import pyttsx3

class TTSService:
    def __init__(self):
        self.engine = pyttsx3.init()
        # Clean up the robotic voice slightly by adjusting rate
        self.engine.setProperty('rate', 175) 
        
        # Optional: Set to a specific Windows voice if desired
        # voices = self.engine.getProperty('voices')
        # self.engine.setProperty('voice', voices[1].id) # Usually a female voice

    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()