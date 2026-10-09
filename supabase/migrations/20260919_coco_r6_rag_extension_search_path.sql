-- R6: keep pgvector out of public and pin RAG function resolution.
create schema if not exists extensions;
alter extension vector set schema extensions;
alter function public.rag_hybrid_search(text, extensions.vector, integer, uuid, text, text)
  set search_path = public, extensions, pg_temp;
