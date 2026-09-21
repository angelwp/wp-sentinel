import logging
import uuid
from functools import lru_cache

import anthropic
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

load_dotenv()

from app.chat import (  # noqa: E402
    INTERNAL_ERROR_MESSAGE,
    MESSAGE_MAX_CHARS,
    PROVIDER_TIMEOUT_SECONDS,
    ProviderError,
    build_system_prompt,
    call_provider,
    fetch_history,
    fetch_session,
    persist_exchange,
    session_lock,
)
from app.config import get_settings  # noqa: E402
from app.corpus import load_corpus  # noqa: E402
from app.db import get_supabase  # noqa: E402
from app.sessions import (  # noqa: E402
    MESSAGES_PER_SESSION,
    SESSIONS_PER_IP,
    client_ip,
    create_session_if_allowed,
    hash_ip,
)


class _HideClientAddr(logging.Filter):
    """Quita la IP del access log de uvicorn, que la pone como primer argumento.

    La IP nunca va en claro a los logs (SPEC §6). Va en código y no como
    --no-access-log porque el start command de Render se capturó a mano.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple) and record.args:
            record.args = ("-", *record.args[1:])
        return True


logging.getLogger("uvicorn.access").addFilter(_HideClientAddr())

app = FastAPI()

CORPUS_TEXT, CORPUS_FILE_COUNT = load_corpus()
SYSTEM_PROMPT = build_system_prompt(CORPUS_TEXT)
get_supabase()  # valida credenciales de Supabase al arrancar (SPEC §11)


@lru_cache
def get_anthropic() -> anthropic.Anthropic:
    # max_retries=0: los únicos reintentos son los de SPEC §7.1 (app/chat.py).
    return anthropic.Anthropic(
        api_key=get_settings().anthropic_api_key,
        max_retries=0,
        timeout=PROVIDER_TIMEOUT_SECONDS,
    )


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"code": code, "message": message}
    )


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> JSONResponse:
    # SPEC §7.1: todo error termina en un mensaje legible, con el mismo cuerpo
    # {"code","message"}. Starlette vuelve a lanzar la excepción después de
    # responder, así que el traceback sigue llegando al log.
    return _error(500, "internal_error", INTERNAL_ERROR_MESSAGE)


_INVALID_REQUEST = "La petición no tiene el formato esperado."


def _is_storable(text: str) -> bool:
    """Postgres no guarda NUL en `text`, y un surrogate suelto no se codifica
    en UTF-8. Se rechazan antes de llamar al proveedor: si no, la llamada se
    cobra y la inserción falla después, sin consumir cupo."""
    if "\x00" in text:
        return False
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "corpus_files": CORPUS_FILE_COUNT,
        "corpus_chars": len(CORPUS_TEXT),
    }


@app.post("/api/session", status_code=201)
def new_session(request: Request):
    ip_hash = hash_ip(client_ip(request), get_settings().ip_hash_salt)
    session_id = create_session_if_allowed(get_supabase(), ip_hash)

    if session_id is None:
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

    return {"session_id": session_id, "messages_remaining": MESSAGES_PER_SESSION}


@app.post("/api/chat")
async def chat(request: Request):
    try:
        body = await request.json()
    except Exception:
        return _error(422, "invalid_request", _INVALID_REQUEST)

    if not isinstance(body, dict):
        return _error(422, "invalid_request", _INVALID_REQUEST)

    session_id = body.get("session_id")
    message = body.get("message")

    if not isinstance(session_id, str) or not isinstance(message, str):
        return _error(422, "invalid_request", _INVALID_REQUEST)
    # uuid.UUID() acepta varias grafías del mismo UUID (mayúsculas, sin guiones,
    # llaves, urn:uuid:). Se sigue con la canónica: Postgres no acepta todas, y
    # cada sesión debe tener un solo lock.
    try:
        session_id = str(uuid.UUID(session_id))
    except ValueError:
        return _error(422, "invalid_request", _INVALID_REQUEST)
    if len(message) == 0 or not _is_storable(message):
        return _error(422, "invalid_request", _INVALID_REQUEST)
    if len(message) > MESSAGE_MAX_CHARS:
        return _error(
            422,
            "message_too_long",
            f"El mensaje supera los {MESSAGE_MAX_CHARS} caracteres permitidos.",
        )

    # Supabase y Anthropic son clientes síncronos: correrlos aquí bloquearía
    # el event loop y, con un solo worker, a todo el servidor. El lock por
    # sesión también es de threading, así que todo va al threadpool.
    return await run_in_threadpool(_chat_turn, session_id, message)


def _chat_turn(session_id: str, message: str):
    db = get_supabase()

    with session_lock(session_id):
        session = fetch_session(db, session_id)
        if session is None:
            return _error(404, "session_not_found", "Esa sesión no existe.")

        if session["message_count"] >= MESSAGES_PER_SESSION:
            return _error(
                429,
                "session_limit",
                f"Esta conversación llegó a su límite de {MESSAGES_PER_SESSION} "
                "mensajes. Abre una sesión nueva para seguir.",
            )

        history = fetch_history(db, session_id)
        history.append({"role": "user", "content": message})

        try:
            text, tokens_in, tokens_out = call_provider(
                get_anthropic(), SYSTEM_PROMPT, history
            )
        except ProviderError as exc:
            return _error(exc.status_code, exc.code, exc.message)

        persist_exchange(db, session, message, text, tokens_in, tokens_out)

    return {
        "text": text,
        "messages_remaining": MESSAGES_PER_SESSION - session["message_count"] - 1,
        "tokens_used": tokens_in + tokens_out,
    }
