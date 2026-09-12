"""Verifica la conexión a Supabase con una inserción manual (SPEC §13 paso 4).

Inserta una sesión y un mensaje de prueba, confirma que se leen de vuelta,
y borra ambas filas al terminar para no dejar datos de prueba en producción.

Uso: python -m scripts.verify_supabase
"""
import uuid

from dotenv import load_dotenv

load_dotenv()

from app.db import get_supabase  # noqa: E402


def main() -> None:
    db = get_supabase()

    session_id = str(uuid.uuid4())
    session = (
        db.table("sessions")
        .insert({"id": session_id, "ip_hash": "verify-script-test-hash"})
        .execute()
    )
    assert session.data[0]["id"] == session_id
    print(f"sessions: insertada id={session_id}")

    message = (
        db.table("messages")
        .insert(
            {
                "session_id": session_id,
                "role": "user",
                "content": "mensaje de verificación",
                "tokens_in": 0,
                "tokens_out": 0,
            }
        )
        .execute()
    )
    message_id = message.data[0]["id"]
    print(f"messages: insertado id={message_id}")

    read_back = (
        db.table("messages").select("*").eq("id", message_id).execute()
    )
    assert read_back.data[0]["content"] == "mensaje de verificación"
    print("lectura de vuelta: OK")

    db.table("messages").delete().eq("id", message_id).execute()
    db.table("sessions").delete().eq("id", session_id).execute()
    print("limpieza: filas de prueba borradas")

    print("\nVerificación de conexión a Supabase: OK")


if __name__ == "__main__":
    main()
