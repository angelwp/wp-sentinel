import logging
import threading
import time

import anthropic
from supabase import Client

from app.guardrails import SYSTEM_GUARDRAILS

# Límites y parámetros de docs/SPEC.md §3, §6, §7.1.
MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
MESSAGE_MAX_CHARS = 2000
PROVIDER_RETRY_WAIT_SECONDS = 2
# §7.1: timeout a los 30 s. Sin streaming, la respuesta llega de una vez, así
# que el timeout de lectura de httpx equivale a "30 s sin primer chunk". El
# default del SDK es 600 s y retendría el lock de la sesión todo ese tiempo.
PROVIDER_TIMEOUT_SECONDS = 30.0
INTERNAL_ERROR_MESSAGE = "Ocurrió un error interno. Intenta de nuevo más tarde."

logger = logging.getLogger(__name__)

_session_locks: dict[str, threading.Lock] = {}
_session_locks_guard = threading.Lock()


def session_lock(session_id: str) -> threading.Lock:
    """Lock por sesión: serializa peticiones simultáneas a la misma sesión.

    Solo protege dentro de un proceso (una instancia, un worker de uvicorn;
    ver CLAUDE.md → Render). Cambio al spec del 14 sep 2026, §6 punto 2.
    """
    with _session_locks_guard:
        lock = _session_locks.get(session_id)
        if lock is None:
            lock = threading.Lock()
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
    result = (
        db.table("messages")
        .select("role,content")
        .eq("session_id", session_id)
        .order("created_at")
        .execute()
    )
    return [{"role": row["role"], "content": row["content"]} for row in result.data]


def _usage_tokens_in(usage: anthropic.types.Usage) -> int:
    """Suma de los tres conteos de entrada (Cambios al spec, 14 sep 2026)."""
    return (
        (usage.input_tokens or 0)
        + (usage.cache_creation_input_tokens or 0)
        + (usage.cache_read_input_tokens or 0)
    )


class ProviderError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(code)


# code → (status HTTP, mensaje para el usuario).
_PROVIDER_ERRORS = {
    "busy": (
        503,
        "El asesor está saturado en este momento. Intenta de nuevo en un minuto.",
    ),
    "provider_down": (
        503,
        "El proveedor del asesor no está disponible en este momento. Intenta de"
        " nuevo en unos minutos.",
    ),
    "timeout": (504, "El asesor tardó demasiado en responder. Intenta de nuevo."),
    "internal_error": (500, INTERNAL_ERROR_MESSAGE),
}


def _provider_error(code: str) -> ProviderError:
    status_code, message = _PROVIDER_ERRORS[code]
    return ProviderError(status_code, code, message)


def _is_retryable(exc: anthropic.APIStatusError) -> bool:
    """§7.1: solo 429, 529 y 5xx se reintentan."""
    return exc.status_code == 429 or exc.status_code >= 500


def call_provider(
    client: anthropic.Anthropic, system: list[dict], messages: list[dict]
) -> tuple[str, int, int]:
    """Llama al proveedor con un reintento en 429/529/5xx (SPEC §7.1).

    Devuelve (texto, tokens_in, tokens_out). Lanza ProviderError si falla.
    El resto de los errores de estado (400, 401, 403, 404…) son de
    configuración: no se reintentan ni se reportan como caída del proveedor.
    """
    for attempt in (1, 2):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=messages,
            )
            return (
                "".join(
                    block.text for block in response.content if block.type == "text"
                ),
                _usage_tokens_in(response.usage),
                response.usage.output_tokens,
            )
        # APITimeoutError hereda de APIConnectionError: va primero.
        except anthropic.APITimeoutError as exc:
            raise _provider_error("timeout") from exc
        except anthropic.APIConnectionError as exc:
            raise _provider_error("provider_down") from exc
        except anthropic.APIStatusError as exc:
            if not _is_retryable(exc):
                logger.error(
                    "provider_request_rejected status=%s request_id=%s",
                    exc.status_code,
                    exc.request_id,
                )
                raise _provider_error("internal_error") from exc
            if attempt == 2:
                code = "busy" if exc.status_code == 429 else "provider_down"
                raise _provider_error(code) from exc
            time.sleep(PROVIDER_RETRY_WAIT_SECONDS)
    raise AssertionError("unreachable")


def persist_exchange(
    db: Client,
    session: dict,
    user_message: str,
    assistant_text: str,
    tokens_in: int,
    tokens_out: int,
) -> None:
    session_id = session["id"]
    db.table("messages").insert(
        {"session_id": session_id, "role": "user", "content": user_message}
    ).execute()
    db.table("messages").insert(
        {
            "session_id": session_id,
            "role": "assistant",
            "content": assistant_text,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        }
    ).execute()
    tokens_used = tokens_in + tokens_out
    db.table("sessions").update(
        {
            "message_count": session["message_count"] + 1,
            "total_tokens": session["total_tokens"] + tokens_used,
        }
    ).eq("id", session_id).execute()
