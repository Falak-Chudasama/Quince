from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions
from faster_whisper import WhisperModel
import pyttsx3
import os

app = FastAPI()

print("\n[Local AI Server] Booting offline models into RAM... Please wait.")

# 1. RAG MEMORY SETUP
print("[Memory] Loading BGE-Large-1.5...")
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-en-v1.5")
client = chromadb.PersistentClient(path="./quince_memory")
COLLECTION_NAME = "session_memory"

# 2. STT (SPEECH TO TEXT) SETUP
print("[Ear] Loading Faster-Whisper...")
try:
    stt_model = WhisperModel("large-v3", device="cuda", compute_type="int8")
except Exception:
    print("      -> CUDA failed, falling back to CPU. (Using 'base' model for speed)")
    stt_model = WhisperModel("base", device="cpu", compute_type="int8")

# 3. TTS (TEXT TO SPEECH) SETUP
print("[Voice] Initializing pyttsx3...")
tts_engine = pyttsx3.init()
tts_engine.setProperty('rate', 175)

class RAGItem(BaseModel):
    role: str = ""
    text: str

class AudioItem(BaseModel):
    path: str

class TTSItem(BaseModel):
    text: str
    output_path: str

# --- API ENDPOINTS ---

@app.post("/rag/flush")
def flush_memory():
    try: client.delete_collection(name=COLLECTION_NAME)
    except: pass
    client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    return {"status": "Memory flushed."}

@app.post("/rag/add")
def add_memory(item: RAGItem):
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    collection.add(documents=[item.text], metadatas=[{"role": item.role}], ids=[f"msg_{collection.count() + 1}"])
    return {"status": "Added."}

@app.post("/rag/query")
def query_memory(item: RAGItem):
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    if collection.count() == 0: return {"context": ""}
    results = collection.query(query_texts=[item.text], n_results=min(collection.count(), 3))
    context = [f"[{meta['role'].upper()}]: {doc}" for doc, meta in zip(results['documents'][0], results['metadatas'][0])]
    return {"context": "\n".join(context)}

@app.post("/stt")
def transcribe_audio(item: AudioItem):
    segments, _ = stt_model.transcribe(item.path, beam_size=5, language="en")
    text = "".join([segment.text for segment in segments])
    return {"text": text.strip()}

@app.post("/tts")
def synthesize_speech(item: TTSItem):
    tts_engine.save_to_file(item.text, item.output_path)
    tts_engine.runAndWait()
    return {"success": True}

if __name__ == "__main__":
    import uvicorn
    print("\n[Local AI Server] Ready on http://127.0.0.1:8001")
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")