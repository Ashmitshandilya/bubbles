-- COCO RAG foundation: source-aware evidence corpus + pgvector hybrid retrieval.
create extension if not exists vector with schema extensions;

create table if not exists public.rag_documents (
  id uuid primary key default gen_random_uuid(),
  title text not null,
  source_name text not null,
  source_url text,
  publisher text,
  evidence_level text not null default 'unknown',
  country text,
  population text,
  publication_date date,
  retrieved_at timestamptz not null default now(),
  topic_tags text[] not null default '{}',
  scope text not null default 'global' check (scope in ('global','user')),
  owner_user_id uuid references auth.users(id) on delete cascade,
  document_type text not null default 'guideline',
  content_hash text not null unique,
  created_at timestamptz not null default now()
);

create table if not exists public.rag_chunks (
  id bigint generated always as identity primary key,
  document_id uuid not null references public.rag_documents(id) on delete cascade,
  chunk_index integer not null,
  content text not null,
  fts tsvector generated always as (to_tsvector('english', content)) stored,
  embedding extensions.vector(384),
  metadata jsonb not null default '{}'::jsonb,
  created_at timestamptz not null default now(),
  unique(document_id, chunk_index)
);

create index if not exists rag_chunks_fts_idx on public.rag_chunks using gin(fts);
create index if not exists rag_chunks_embedding_idx on public.rag_chunks using hnsw (embedding vector_cosine_ops);
create index if not exists rag_documents_scope_idx on public.rag_documents(scope, owner_user_id);
create index if not exists rag_documents_topic_idx on public.rag_documents using gin(topic_tags);

alter table public.rag_documents enable row level security;
alter table public.rag_chunks enable row level security;

-- Users may read global evidence and their own private evidence.
drop policy if exists "Read accessible RAG documents" on public.rag_documents;
create policy "Read accessible RAG documents" on public.rag_documents
for select to authenticated
using (scope = 'global' or owner_user_id = auth.uid());

drop policy if exists "Read accessible RAG chunks" on public.rag_chunks;
create policy "Read accessible RAG chunks" on public.rag_chunks
for select to authenticated
using (
  exists (
    select 1 from public.rag_documents d
    where d.id = rag_chunks.document_id
      and (d.scope = 'global' or d.owner_user_id = auth.uid())
  )
);

-- Trusted backend performs ingestion; clients never write the evidence corpus.
revoke insert, update, delete on public.rag_documents from authenticated;
revoke insert, update, delete on public.rag_chunks from authenticated;

create or replace function public.rag_hybrid_search(
  query_text text,
  query_embedding extensions.vector(384) default null,
  match_count integer default 8,
  request_user_id uuid default null,
  topic_filter text default null,
  country_filter text default null
)
returns table (
  chunk_id bigint,
  document_id uuid,
  title text,
  source_name text,
  source_url text,
  publisher text,
  evidence_level text,
  content text,
  lexical_rank integer,
  semantic_rank integer,
  fused_score numeric
)
language sql
stable
as $$
  with lexical as (
    select c.id, row_number() over(order by ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) desc) as rank
    from public.rag_chunks c
    join public.rag_documents d on d.id = c.document_id
    where c.fts @@ websearch_to_tsquery('english', query_text)
      and (d.scope = 'global' or (d.scope = 'user' and d.owner_user_id = request_user_id))
      and (topic_filter is null or topic_filter = any(d.topic_tags))
      and (country_filter is null or d.country is null or d.country = country_filter)
    order by ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) desc
    limit greatest(match_count * 4, 20)
  ),
  semantic as (
    select c.id, row_number() over(order by c.embedding <=> query_embedding) as rank
    from public.rag_chunks c
    join public.rag_documents d on d.id = c.document_id
    where query_embedding is not null
      and c.embedding is not null
      and (d.scope = 'global' or (d.scope = 'user' and d.owner_user_id = request_user_id))
      and (topic_filter is null or topic_filter = any(d.topic_tags))
      and (country_filter is null or d.country is null or d.country = country_filter)
    order by c.embedding <=> query_embedding
    limit greatest(match_count * 4, 20)
  ),
  fused as (
    select coalesce(l.id, s.id) as id,
           l.rank as lexical_rank,
           s.rank as semantic_rank,
           (case when l.rank is not null then 1.0 / (60 + l.rank) else 0 end +
            case when s.rank is not null then 1.0 / (60 + s.rank) else 0 end) as score
    from lexical l full outer join semantic s on s.id = l.id
  )
  select c.id, d.id, d.title, d.source_name, d.source_url, d.publisher,
         d.evidence_level, c.content, f.lexical_rank::integer, f.semantic_rank::integer,
         f.score::numeric
  from fused f
  join public.rag_chunks c on c.id = f.id
  join public.rag_documents d on d.id = c.document_id
  order by f.score desc
  limit match_count;
$$;

revoke execute on function public.rag_hybrid_search(text, extensions.vector, integer, uuid, text, text) from anon;
grant execute on function public.rag_hybrid_search(text, extensions.vector, integer, uuid, text, text) to authenticated;
