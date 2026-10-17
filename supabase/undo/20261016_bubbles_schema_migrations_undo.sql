-- Undo of 20261016_bubbles_schema_migrations.sql: removes the register only (nothing else depends on it; the app falls back to "unknown").
drop table if exists public.bubbles_schema_migrations;
