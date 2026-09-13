-- wp-sentinel — esquema inicial (docs/SPEC.md §4.2)
-- Ejecutar en el SQL editor de Supabase.

create table if not exists sessions (
  id            uuid primary key,
  ip_hash       text not null,
  created_at    timestamptz not null default now(),
  message_count int  not null default 0,
  total_tokens  int  not null default 0
);

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

-- RLS activado sin políticas bloquea incluso a service_role sin estos grants.
grant select, insert, update, delete on public.sessions to service_role;
grant select, insert, update, delete on public.messages to service_role;
grant usage, select on all sequences in schema public to service_role;
