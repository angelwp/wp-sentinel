import asyncio
import logging
import uuid
from functools import lru_cache

import anthropic
import anyio
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.concurrency import run_in_threadpool
from starlette.types import Receive, Scope, Send

load_dotenv()

from app.chat import (  # noqa: E402
    INTERNAL_ERROR_MESSAGE,
    MESSAGE_MAX_CHARS,
    PROVIDER_TIMEOUT_SECONDS,
    build_system_prompt,
    chat_events,
    fetch_history,
    fetch_session,
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
def get_anthropic() -> anthropic.AsyncAnthropic:
    # max_retries=0: los únicos reintentos son los de SPEC §7.1 (app/chat.py).
    return anthropic.AsyncAnthropic(
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

    lock = session_lock(session_id)
    await lock.acquire()
    try:
        # Supabase es síncrono: al threadpool, para no bloquear el event loop.
        db = get_supabase()
        session = await run_in_threadpool(fetch_session, db, session_id)
        if session is None:
            lock.release()
            return _error(404, "session_not_found", "Esa sesión no existe.")

        if session["message_count"] >= MESSAGES_PER_SESSION:
            lock.release()
            return _error(
                429,
                "session_limit",
                f"Esta conversación llegó a su límite de {MESSAGES_PER_SESSION} "
                "mensajes. Abre una sesión nueva para seguir.",
            )

        history = await run_in_threadpool(fetch_history, db, session_id)
    except BaseException:
        lock.release()
        raise

    # Desde aquí el lock es de la respuesta: lo suelta al terminar el stream.
    return _SessionStream(
        chat_events(
            db,
            get_anthropic(),
            SYSTEM_PROMPT,
            session,
            history,
            message,
            MESSAGES_PER_SESSION,
        ),
        lock,
    )


class _SessionStream(StreamingResponse):
    """SSE (SPEC §5) que retiene el lock de la sesión hasta terminar.

    El lock no se suelta dentro del generador: si el cliente se desconecta
    antes de que empiece a iterar, su código nunca corre. Al terminar, pase
    lo que pase, se cierra el generador (así corre su limpieza, que persiste
    lo recibido) y después se suelta el lock.
    """

    def __init__(self, content, lock: asyncio.Lock):
        super().__init__(
            content,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )
        self._lock = lock

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            with anyio.CancelScope(shield=True):
                try:
                    await self.body_iterator.aclose()
                finally:
                    self._lock.release()
