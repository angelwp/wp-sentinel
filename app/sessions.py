import hashlib
import ipaddress
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import Request
from supabase import Client

# Límites de docs/SPEC.md §6.
MESSAGES_PER_SESSION = 10
SESSIONS_PER_IP = 3
SESSIONS_WINDOW = timedelta(hours=24)


def client_ip(request: Request) -> str:
    """IP del cliente.

    Render pone la IP real como primera entrada de X-Forwarded-For. Sin ese
    header (local), se usa la IP de la conexión.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",")[0].strip()
    else:
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


def create_session(db: Client, ip_hash: str) -> str:
    session_id = str(uuid.uuid4())
    db.table("sessions").insert({"id": session_id, "ip_hash": ip_hash}).execute()
    return session_id
