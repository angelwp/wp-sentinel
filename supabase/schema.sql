-- wp-sentinel — esquema (docs/SPEC.md §4.2 y "Cambios al spec")
-- Ejecutar en el SQL editor de Supabase. Se puede volver a ejecutar sobre la
-- base existente: agrega lo que falte, quita las columnas retiradas y vuelve a
-- validar las reglas. Todo va en una transacción: si una fila viola una regla,
-- no se aplica nada.

begin;

create table if not exists sessions (
  id            uuid primary key,
  ip_hash       text not null,
  created_at    timestamptz not null default now()
);

-- Columnas de la v1.1. message_count se calcula de messages y total_tokens no
-- lo leía nadie (Cambios al spec, 5 oct 2026). Se aplica solo cuando el código
-- que ya no las usa esté desplegado.
alter table sessions
  drop column if exists message_count,
  drop column if exists total_tokens;

create table if not exists messages (
  id            bigserial primary key,
  session_id    uuid not null references sessions(id),
  role          text not null check (role in ('user','assistant')),
  content       text not null,
  tokens_in     int,
  tokens_out    int,
  truncated     boolean not null default false,
  created_at    timestamptz not null default now()
);

create index if not exists idx_sessions_ip_hash_created_at
  on sessions (ip_hash, created_at);

create index if not exists idx_messages_created_at
  on messages (created_at);

-- Historial de una sesión en orden de inserción (§5).
create index if not exists idx_messages_session_id_id
  on messages (session_id, id);

-- Reglas que la app ya cumple: si un error del código las rompe, la escritura
-- falla en vez de guardar un dato malo (Cambios al spec, 3 oct 2026).
-- `drop ... if exists` + `add` las hace repetibles.
alter table sessions
  drop constraint if exists sessions_ip_hash_sha256,
  add constraint sessions_ip_hash_sha256
    check (ip_hash ~ '^[0-9a-f]{64}$');

alter table messages
  drop constraint if exists messages_tokens_nonnegative,
  add constraint messages_tokens_nonnegative
    check (tokens_in >= 0 and tokens_out >= 0),
  drop constraint if exists messages_tokens_by_role,
  add constraint messages_tokens_by_role
    check (
      (role = 'user' and tokens_in is null and tokens_out is null)
      or (role = 'assistant' and tokens_in is not null and tokens_out is not null)
    ),
  drop constraint if exists messages_truncated_assistant_only,
  add constraint messages_truncated_assistant_only
    check (role = 'assistant' or not truncated),
  -- char_length cuenta code points, igual que len() en Python (§6).
  drop constraint if exists messages_user_content_length,
  add constraint messages_user_content_length
    check (role <> 'user' or char_length(content) between 1 and 2000);

-- Sin políticas: solo entra service_role, que ignora RLS. En producción ya
-- estaba activo; aquí queda explícito para que una base nueva quede igual.
alter table sessions enable row level security;
alter table messages enable row level security;

-- service_role ignora RLS, pero sin estos grants Postgres rechaza cualquier
-- lectura o escritura con 42501 antes de evaluar políticas (SPEC "Cambios al spec").
grant select, insert, update, delete on public.sessions to service_role;
grant select, insert, update, delete on public.messages to service_role;
grant usage, select on all sequences in schema public to service_role;

commit;
