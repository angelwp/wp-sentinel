import hashlib
import ipaddress
import threading
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from supabase import Client

# Límites de docs/SPEC.md §6.
MESSAGES_PER_SESSION = 10
SESSIONS_PER_IP = 3
SESSIONS_WINDOW = timedelta(hours=24)

_create_lock = threading.Lock()


def client_ip(request: Request) -> str:
    """IP del cliente.

    En Render, Cloudflare va delante y escribe CF-Connecting-IP con la IP que
    ve en su borde, pisando cualquier valor que mande el cliente. No se usa
    X-Forwarded-For: Render conserva lo que mande el cliente y solo le agrega
    entradas, así que es falseable. Sin CF-Connecting-IP (local), se usa la IP
    de la conexión.
    """
    ip = request.headers.get("cf-connecting-ip", "").strip()
    if not ip:
        ip = request.client.host if request.client else ""
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return ip


def hash_ip(ip: str, salt: str) -> str:
    """SHA-256 de la IP con sal. La IP en claro nunca se guarda (SPEC §6)."""
    return hashlib.sha256(f"{salt}{ip}".encode()).hexdigest()


def count_recent_sessions(db: Client, ip_hash: str) -> int:
    since = (datetime.now(timezone.utc) - SESSIONS_WINDOW).isoformat()
    result = (
        db.table("sessions")
        .select("id", count="exact", head=True)
        .eq("ip_hash", ip_hash)
        .gte("created_at", since)
        .execute()
    )
    return result.count or 0


def create_session_if_allowed(db: Client, ip_hash: str) -> str | None:
    """Crea la sesión si la IP no llegó al límite; si llegó, devuelve None.

    Contar e insertar va bajo un lock para que peticiones simultáneas no pasen
    el límite. Solo protege dentro de un proceso: supone una instancia con un
    worker, como está hoy en Render (CLAUDE.md).
    """
    with _create_lock:
        if count_recent_sessions(db, ip_hash) >= SESSIONS_PER_IP:
            return None
        session_id = str(uuid.uuid4())
        db.table("sessions").insert({"id": session_id, "ip_hash": ip_hash}).execute()
        return session_id
