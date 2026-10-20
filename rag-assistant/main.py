import os
import glob
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

app = FastAPI(title="RAG Assistant - Ollama & LangChain")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")
MODEL_NAME = os.getenv("OLLAMA_MODEL", "qwen2.5:0.5b")

# 1. Chargement et découpage des documents avec LangChain
CHUNKS = []
splitter = RecursiveCharacterTextSplitter(chunk_size=450, chunk_overlap=50)

for filepath in glob.glob("/app/docs/*.md"):
    with open(filepath, "r", encoding="utf-8") as f:
        text = f.read()
        CHUNKS.extend(splitter.split_text(text))

vectorizer = TfidfVectorizer()
tfidf_matrix = vectorizer.fit_transform(CHUNKS)

class QueryRequest(BaseModel):
    question: str

def ensure_model_pulled():
    try:
        resp = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models = [m["name"] for m in resp.json().get("models", [])]
            if not any(MODEL_NAME in m for m in models):
                requests.post(f"{OLLAMA_URL}/api/pull", json={"name": MODEL_NAME, "stream": False}, timeout=180)
    except Exception:
        pass

@app.post("/rag/ask")
def ask_assistant(req: QueryRequest):
    # Recherche documentaire RAG sur les chunks LangChain
    query_vec = vectorizer.transform([req.question])
    similarities = cosine_similarity(query_vec, tfidf_matrix).flatten()
    top_indices = similarities.argsort()[-2:][::-1]
    context = "\n---\n".join([CHUNKS[i] for i in top_indices])

    prompt = (
        f"Tu es l'assistant SecOps local du projet RESILIENCE-ALPHA. "
        f"Réponds de façon concise en français uniquement à partir de cette documentation :\n\n"
        f"{context}\n\n"
        f"Question de l'opérateur : {req.question}\nRéponse :"
    )

    try:
        ensure_model_pulled()
        res = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": MODEL_NAME, "prompt": prompt, "stream": False},
            timeout=30
        )
        if res.status_code == 200:
            answer = res.json().get("response", "").strip()
            return {"answer": answer, "context_used": context, "model": MODEL_NAME}
    except Exception:
        pass

    # Réponse de secours instantanée basée sur l'extrait RAG si Ollama est encore en train de télécharger le modèle
    return {
        "answer": f"[Extrait direct de la procédure RAG] :\n{context}",
        "context_used": context,
        "model": f"{MODEL_NAME} (RAG Direct)"
    }