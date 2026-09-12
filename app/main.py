from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.corpus import load_corpus  # noqa: E402
from app.db import get_supabase  # noqa: E402

app = FastAPI()

CORPUS_TEXT, CORPUS_FILE_COUNT = load_corpus()
get_supabase()  # valida credenciales de Supabase al arrancar (SPEC §11)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "corpus_files": CORPUS_FILE_COUNT,
        "corpus_chars": len(CORPUS_TEXT),
    }
