-- 0001_init.sql
-- Initial schema for paper-companion: papers, chunks, notes, RLS policies, pgvector.
-- Run order: extensions → tables → indexes → triggers → RLS policies.

-- ============================================================
-- Extensions
-- ============================================================

create extension if not exists vector;        -- embeddings
create extension if not exists pgcrypto;      -- gen_random_uuid()

-- ============================================================
-- Tables
-- ============================================================

-- papers: a user's saved paper (uploaded PDF or fetched arXiv/HAL link)
create table papers (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references auth.users(id) on delete cascade,
  title       text not null,
  source      text not null check (source in ('pdf', 'arxiv', 'hal', 'url')),
  source_url  text,
  language    text not null check (language in ('en', 'fr', 'mixed', 'unknown')),
  page_count  int,
  status      text not null default 'uploaded'
              check (status in ('uploaded', 'processing', 'ready', 'failed')),
  error       text,
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- chunks: chunked, embedded passages from a paper.
-- user_id is denormalized from papers to keep RLS policy expressions index-friendly.
create table chunks (
  id           uuid primary key default gen_random_uuid(),
  paper_id     uuid not null references papers(id) on delete cascade,
  user_id      uuid not null references auth.users(id) on delete cascade,
  content      text not null,
  page_number  int,
  section      text,                -- predicted by bilingual-section-classifier; nullable until that ships
  chunk_index  int  not null,
  embedding    vector(1024),        -- multilingual-e5-large output dim
  token_count  int,
  created_at   timestamptz not null default now()
);

-- notes: user-written notes attached to a paper
create table notes (
  id          uuid primary key default gen_random_uuid(),
  paper_id    uuid not null references papers(id) on delete cascade,
  user_id     uuid not null references auth.users(id) on delete cascade,
  content     text not null,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

-- ============================================================
-- Indexes
-- ============================================================

create index papers_user_idx   on papers(user_id);
create index papers_status_idx on papers(status) where status <> 'ready';

create index chunks_paper_idx on chunks(paper_id);
create index chunks_user_idx  on chunks(user_id);

-- IVFFlat vector index for cosine similarity. lists=100 is a starting point;
-- tune to roughly sqrt(rows) once corpus size is known (revisit in week 3).
create index chunks_embedding_idx
  on chunks using ivfflat (embedding vector_cosine_ops)
  with (lists = 100);

create index notes_paper_idx on notes(paper_id);
create index notes_user_idx  on notes(user_id);

-- ============================================================
-- Triggers
-- ============================================================

create or replace function set_updated_at()
returns trigger as $$
begin
  new.updated_at := now();
  return new;
end;
$$ language plpgsql;

create trigger papers_updated_at
  before update on papers
  for each row execute function set_updated_at();

create trigger notes_updated_at
  before update on notes
  for each row execute function set_updated_at();

-- ============================================================
-- Row-Level Security
-- A user can only see and modify their own papers, chunks, and notes.
-- ============================================================

alter table papers enable row level security;
alter table chunks enable row level security;
alter table notes  enable row level security;

create policy papers_owner on papers
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy chunks_owner on chunks
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);

create policy notes_owner on notes
  for all
  using      (auth.uid() = user_id)
  with check (auth.uid() = user_id);
