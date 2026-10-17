from fastapi import FastAPI

app = FastAPI(title="RAG Assistant")


@app.get("/health")
def health():
    return {"status": "ok"}