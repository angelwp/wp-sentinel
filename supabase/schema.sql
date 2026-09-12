-- wp-sentinel — esquema inicial (docs/SPEC.md §4.2)
-- Ejecutar en el SQL editor de Supabase.

create table if not exists sessions (
  id            uuid primary key default gen_random_uuid(),
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
