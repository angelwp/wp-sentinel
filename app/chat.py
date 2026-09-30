import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import anthropic
import anyio
import httpx2
from starlette.concurrency import run_in_threadpool
from supabase import Client

from app.guardrails import SYSTEM_GUARDRAILS

# Límites y parámetros de docs/SPEC.md §3, §6, §7.1.
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
MESSAGE_MAX_CHARS = 2000
PROVIDER_RETRY_WAIT_SECONDS = 2
# §7.1: 30 s sin recibir nada del proveedor, antes o después del primer chunk
# (Cambios al spec, 21 sep 2026). Es el timeout de lectura de httpx: cuenta
# entre un pedazo y el siguiente, no el total. Los `ping` del proveedor cuentan
# como "recibir algo".
PROVIDER_TIMEOUT_SECONDS = 30.0
INTERNAL_ERROR_MESSAGE = "Ocurrió un error interno. Intenta de nuevo más tarde."

logger = logging.getLogger(__name__)

_session_locks: dict[str, asyncio.Lock] = {}


def session_lock(session_id: str) -> asyncio.Lock:
    """Lock por sesión: serializa peticiones simultáneas a la misma sesión.

    Se retiene durante todo el stream. Solo protege dentro de un proceso (una
    instancia, un worker de uvicorn; ver CLAUDE.md → Render). Cambio al spec
    del 14 sep 2026, §6 punto 2.
    """
    # Sin await de por medio: en el event loop, leer y escribir el dict es
    # atómico.
    lock = _session_locks.get(session_id)
    if lock is None:
        lock = asyncio.Lock()
        _session_locks[session_id] = lock
    return lock


def build_system_prompt(corpus_text: str) -> list[dict]:
    """Guardrails + corpus en un solo bloque cacheado (SPEC §4.1, §8)."""
    return [
        {
            "type": "text",
            "text": f"{SYSTEM_GUARDRAILS}\n\n{corpus_text}",
            "cache_control": {"type": "ephemeral"},
        }
    ]


def fetch_session(db: Client, session_id: str) -> dict | None:
    result = db.table("sessions").select("*").eq("id", session_id).execute()
    return result.data[0] if result.data else None


def fetch_history(db: Client, session_id: str) -> list[dict]:
    """Historial que se reenvía al proveedor (SPEC §5).

    Una respuesta vacía se persiste, pero ni ella ni su mensaje de usuario
    entran al historial: la API rechaza un mensaje de asistente vacío (Cambios
    al spec, 21 sep 2026, punto 1). Se ordena por `id`, que sigue el orden de
    inserción; `created_at` puede empatar.
    """
    result = (
        db.table("messages")
        .select("role,content")
        .eq("session_id", session_id)
        .order("id")
        .execute()
    )
    history: list[dict] = []
    for row in result.data:
        if row["role"] == "assistant" and row["content"] == "":
            if history and history[-1]["role"] == "user":
                history.pop()
            continue
        history.append({"role": row["role"], "content": row["content"]})
    return history


def _usage_tokens_in(usage: anthropic.types.Usage) -> int:
    """Suma de los tres conteos de entrada (Cambios al spec, 14 sep 2026)."""
    return (
        (usage.input_tokens or 0)
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
    )


class ProviderError(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


# code → mensaje para el usuario (SPEC §7.1).
ERROR_MESSAGES = {
    "busy": "El asesor está saturado en este momento. Intenta de nuevo en un minuto.",
    "provider_down": (
        "El proveedor del asesor no está disponible en este momento. Intenta de"
        " nuevo en unos minutos."
    ),
    "timeout": "El asesor tardó demasiado en responder. Intenta de nuevo.",
    "internal_error": INTERNAL_ERROR_MESSAGE,
}

# Tipo de error que el proveedor manda dentro del stream (`event: error`).
# El SDK lo lanza con el status de la respuesta, que ya era 200, así que el
# código sale del cuerpo y no del status.
_STREAM_ERROR_CODES = {
    "rate_limit_error": "busy",
    "overloaded_error": "provider_down",
    "api_error": "provider_down",
}


def _status_error_code(exc: anthropic.APIStatusError) -> str:
    """§7.1: 429 → busy; 529/5xx → provider_down; otro 4xx → internal_error."""
    if exc.status_code == 429:
        return "busy"
    if exc.status_code >= 500:
        return "provider_down"
    if exc.status_code == 200 and isinstance(exc.body, dict):
        error_type = (exc.body.get("error") or {}).get("type")
        if error_type in _STREAM_ERROR_CODES:
            return _STREAM_ERROR_CODES[error_type]
    return "internal_error"


@dataclass
class Turn:
    """Lo que llegó del proveedor en un intercambio."""

    parts: list[str] = field(default_factory=list)
    started: bool = False  # llegó `message_start`: la entrada ya se cobró
    tokens_in: int = 0
    tokens_out: int | None = None
    stop_reason: str | None = None

    @property
    def text(self) -> str:
        return "".join(self.parts)

    @property
    def truncated(self) -> bool:
        # Completa solo si el proveedor terminó por su cuenta. `max_tokens` y
        # cualquier corte cuentan como truncada (Cambios al spec, 21 sep 2026).
        return self.stop_reason is None or self.stop_reason == "max_tokens"

    @property
    def billed_tokens_out(self) -> int:
        # Sin el conteo final, la cota superior: max_tokens.
        return MAX_TOKENS if self.tokens_out is None else self.tokens_out


async def stream_provider(
    client: anthropic.AsyncAnthropic,
    system: list[dict],
    messages: list[dict],
    turn: Turn,
) -> AsyncIterator[str]:
    """Pedazos de texto del proveedor, con el reintento de SPEC §7.1.

    Solo se reintenta antes de `message_start`: después, la entrada ya se
    cobró (Cambios al spec, 21 sep 2026). Lanza ProviderError si falla; lo
    recibido hasta ahí queda en `turn`.
    """
    for attempt in (1, 2):
        try:
            async with client.messages.stream(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
            ) as stream:
                async for event in stream:
                    if event.type == "message_start":
                        turn.started = True
                        turn.tokens_in = _usage_tokens_in(event.message.usage)
                    elif event.type == "text":
                        turn.parts.append(event.text)
                        yield event.text
                    elif event.type == "message_delta":
                        turn.tokens_out = event.usage.output_tokens
                        turn.stop_reason = event.delta.stop_reason
            if turn.stop_reason is None:
                # El stream se cerró sin decir por qué terminó.
                raise ProviderError("provider_down")
            return
        # APITimeoutError hereda de APIConnectionError: va primero.
        except anthropic.APITimeoutError as exc:
            raise ProviderError("timeout") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError("provider_down") from exc
        # Ya con los headers recibidos, el SDK deja pasar los errores de httpx2
        # sin envolverlos: silencio de más de 30 s o conexión cortada a media
        # respuesta.
        except httpx2.TimeoutException as exc:
            raise ProviderError("timeout") from exc
        except httpx2.TransportError as exc:
            raise ProviderError("provider_down") from exc
        except anthropic.APIStatusError as exc:
            code = _status_error_code(exc)
            if code == "internal_error":
                # Error de configuración propio: no se reintenta ni se reporta
                # como caída del proveedor (Cambios al spec, 21 sep 2026).
                logger.error(
                    "provider_request_rejected status=%s request_id=%s",
                    exc.status_code,
                    exc.request_id,
                )
                raise ProviderError(code) from exc
            if turn.started or attempt == 2:
                raise ProviderError(code) from exc
            await asyncio.sleep(PROVIDER_RETRY_WAIT_SECONDS)
    raise AssertionError("unreachable")


def persist_exchange(
    db: Client, session: dict, user_message: str, turn: Turn
) -> None:
    session_id = session["id"]
    db.table("messages").insert(
        {"session_id": session_id, "role": "user", "content": user_message}
    ).execute()
    db.table("messages").insert(
        {
            "session_id": session_id,
            "role": "assistant",
            "content": turn.text,
            "tokens_in": turn.tokens_in,
            "tokens_out": turn.billed_tokens_out,
            "truncated": turn.truncated,
        }
    ).execute()
    db.table("sessions").update(
        {
            "message_count": session["message_count"] + 1,
            "total_tokens": session["total_tokens"]
            + turn.tokens_in
            + turn.billed_tokens_out,
        }
    ).eq("id", session_id).execute()


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def chat_events(
    db: Client,
    client: anthropic.AsyncAnthropic,
    system: list[dict],
    session: dict,
    history: list[dict],
    message: str,
    messages_per_session: int,
) -> AsyncIterator[str]:
    """Eventos SSE de un intercambio (SPEC §5, §7.1).

    Si llegó `message_start`, el intercambio se persiste pase lo que pase:
    termina bien, se corta, falla el proveedor o el cliente se desconecta
    (Cambios al spec, 21 sep 2026). Sin `message_start` no se persiste ni se
    consume cupo.
    """
    turn = Turn()
    persisted = False

    async def persist() -> None:
        nonlocal persisted
        if turn.started and not persisted:
            persisted = True
            await run_in_threadpool(persist_exchange, db, session, message, turn)

    try:
        error_code = None
        try:
            async for text in stream_provider(
                client, system, [*history, {"role": "user", "content": message}], turn
            ):
                yield sse("delta", {"text": text})
        except ProviderError as exc:
            error_code = exc.code

        await persist()
        if error_code is not None:
            yield sse(
                "error", {"code": error_code, "message": ERROR_MESSAGES[error_code]}
            )
        else:
            yield sse(
                "done",
                {
                    "messages_remaining": messages_per_session
                    - session["message_count"]
                    - 1,
                    "tokens_used": turn.tokens_in + turn.billed_tokens_out,
                },
            )
    except (asyncio.CancelledError, GeneratorExit):
        # El cliente se desconectó. Salir del `async with` del stream ya cerró
        # la conexión con el proveedor; falta guardar lo recibido. Blindado
        # porque la tarea sigue cancelada.
        with anyio.CancelScope(shield=True):
            await persist()
        raise
    except Exception:
        # Con el stream abierto ya no hay status HTTP que cambiar: el error va
        # como evento (SPEC §7.1: el front nunca se queda en blanco). Si la
        # llamada ya se cobró, se persiste igual.
        logger.exception("chat_stream_failed")
        try:
            await persist()
        except Exception:
            logger.exception("chat_persist_failed")
        yield sse(
            "error", {"code": "internal_error", "message": INTERNAL_ERROR_MESSAGE}
        )
