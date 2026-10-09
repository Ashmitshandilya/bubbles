-- R5: service-only RAG RPC. Backend authenticates the user first and supplies user_id.
create or replace function public.rag_hybrid_search(
  query_text text, query_embedding public.vector(384) default null, match_count integer default 8,
  request_user_id uuid default null, topic_filter text default null, country_filter text default null
)
returns table (chunk_id bigint, document_id uuid, title text, source_name text, source_url text, publisher text,
  evidence_level text, content text, lexical_rank integer, semantic_rank integer, fused_score numeric)
language sql stable security definer set search_path = public, pg_temp
as $$
  with lexical as (
    select c.id, row_number() over(order by ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) desc) rank
    from public.rag_chunks c join public.rag_documents d on d.id=c.document_id
    where c.fts @@ websearch_to_tsquery('english', query_text)
      and (d.scope='global' or (d.scope='user' and d.owner_user_id=request_user_id))
      and (topic_filter is null or topic_filter=any(d.topic_tags))
      and (country_filter is null or d.country is null or d.country=country_filter)
    order by ts_rank_cd(c.fts, websearch_to_tsquery('english', query_text)) desc
    limit least(greatest(match_count*4,20),100)
  ), semantic as (
    select c.id, row_number() over(order by c.embedding <=> query_embedding) rank
    from public.rag_chunks c join public.rag_documents d on d.id=c.document_id
    where query_embedding is not null and c.embedding is not null
      and (d.scope='global' or (d.scope='user' and d.owner_user_id=request_user_id))
      and (topic_filter is null or topic_filter=any(d.topic_tags))
      and (country_filter is null or d.country is null or d.country=country_filter)
    order by c.embedding <=> query_embedding
    limit least(greatest(match_count*4,20),100)
  ), fused as (
    select coalesce(l.id,s.id) id,l.rank lexical_rank,s.rank semantic_rank,
      (case when l.rank is not null then 1.0/(60+l.rank) else 0 end + case when s.rank is not null then 1.0/(60+s.rank) else 0 end) score
    from lexical l full outer join semantic s on s.id=l.id
  )
  select c.id,d.id,d.title,d.source_name,d.source_url,d.publisher,d.evidence_level,c.content,
    f.lexical_rank::integer,f.semantic_rank::integer,f.score::numeric
  from fused f join public.rag_chunks c on c.id=f.id join public.rag_documents d on d.id=c.document_id
  order by f.score desc limit least(greatest(match_count,1),100)
$$;
revoke execute on function public.rag_hybrid_search(text, public.vector, integer, uuid, text, text) from anon, authenticated;
grant execute on function public.rag_hybrid_search(text, public.vector, integer, uuid, text, text) to service_role;
