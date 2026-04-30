from fastapi import FastAPI
from pydantic import BaseModel
import chromadb
from chromadb.utils import embedding_functions

app = FastAPI()

print("[Memory] Loading BGE-Large-1.5 Model into RAM...")
# Load this ONCE
ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="BAAI/bge-large-en-v1.5")
client = chromadb.PersistentClient(path="./quince_memory")
COLLECTION_NAME = "session_memory"

class MemoryItem(BaseModel):
    role: str = ""
    text: str

@app.post("/flush")
def flush():
    try: 
        client.delete_collection(name=COLLECTION_NAME)
    except: 
        pass
    client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    return {"status": "Memory flushed."}

@app.post("/add")
def add(item: MemoryItem):
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    doc_id = f"msg_{collection.count() + 1}"
    collection.add(documents=[item.text], metadatas=[{"role": item.role}], ids=[doc_id])
    return {"status": "Added."}

@app.post("/query")
def query(item: MemoryItem):
    collection = client.get_or_create_collection(name=COLLECTION_NAME, embedding_function=ef)
    if collection.count() == 0:
        return {"context": ""}
        
    results = collection.query(query_texts=[item.text], n_results=min(collection.count(), 3))
    context = []
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        context.append(f"[{meta['role'].upper()}]: {doc}")
        
    return {"context": "\n".join(context)}

if __name__ == "__main__":
    import uvicorn
    # Runs locally on port 8001
    uvicorn.run(app, host="127.0.0.1", port=8001, log_level="error")