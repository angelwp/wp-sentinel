from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

load_dotenv()

from app.config import get_settings  # noqa: E402
from app.corpus import load_corpus  # noqa: E402
from app.db import get_supabase  # noqa: E402
from app.sessions import (  # noqa: E402
    MESSAGES_PER_SESSION,
    SESSIONS_PER_IP,
    client_ip,
    count_recent_sessions,
    create_session,
    hash_ip,
)

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


@app.post("/api/session", status_code=201)
def new_session(request: Request):
    db = get_supabase()
    ip_hash = hash_ip(client_ip(request), get_settings().ip_hash_salt)

    if count_recent_sessions(db, ip_hash) >= SESSIONS_PER_IP:
        return JSONResponse(
            status_code=429,
            content={
                "code": "ip_limit",
                "message": (
                    f"Ya abriste {SESSIONS_PER_IP} conversaciones desde esta "
                    "conexión en las últimas 24 horas, que es el máximo del "
                    "demo. Podrás abrir otra más tarde."
                ),
            },
        )

    session_id = create_session(db, ip_hash)
    return {"session_id": session_id, "messages_remaining": MESSAGES_PER_SESSION}
