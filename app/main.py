from fastapi import FastAPI

from app.corpus import load_corpus

app = FastAPI()

CORPUS_TEXT, CORPUS_FILE_COUNT = load_corpus()


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "corpus_files": CORPUS_FILE_COUNT,
        "corpus_chars": len(CORPUS_TEXT),
    }
