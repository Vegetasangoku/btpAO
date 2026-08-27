-- Critical fix: match_company_knowledge and match_dce_chunks are SECURITY DEFINER
-- functions owned by `postgres` (rolbypassrls=true), so they bypass RLS on
-- knowledge_vectors/dce_embeddings entirely. They take p_tenant_id as a plain
-- caller-supplied argument with no internal check tying it to the caller's real
-- identity. Both were EXECUTE-able by `anon` (fully unauthenticated) and
-- `authenticated` (any tenant) via PostgREST RPC, meaning anyone with the public
-- anon key could pass any tenant_id and read that tenant's private company
-- knowledge / DCE document chunks. Restrict EXECUTE to the trusted backend
-- roles only; the FastAPI backend is the sole place that verifies a caller's
-- JWT and its real tenant_id before ever reaching this data.
--
-- Applied live to the project on 2026-08-23 (Claude, direct fix). This file
-- exists so the fix is tracked in version control and reproduced on any
-- fresh environment, per project convention (see supabase/migrations/00019+).

REVOKE EXECUTE ON FUNCTION public.match_company_knowledge(uuid, text, vector, double precision, integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.match_company_knowledge(uuid, text, vector, double precision, integer) FROM anon;
REVOKE EXECUTE ON FUNCTION public.match_company_knowledge(uuid, text, vector, double precision, integer) FROM authenticated;

REVOKE EXECUTE ON FUNCTION public.match_dce_chunks(uuid, uuid, vector, double precision, integer) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION public.match_dce_chunks(uuid, uuid, vector, double precision, integer) FROM anon;
REVOKE EXECUTE ON FUNCTION public.match_dce_chunks(uuid, uuid, vector, double precision, integer) FROM authenticated;

GRANT EXECUTE ON FUNCTION public.match_company_knowledge(uuid, text, vector, double precision, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.match_company_knowledge(uuid, text, vector, double precision, integer) TO btp_app_user;

GRANT EXECUTE ON FUNCTION public.match_dce_chunks(uuid, uuid, vector, double precision, integer) TO service_role;
GRANT EXECUTE ON FUNCTION public.match_dce_chunks(uuid, uuid, vector, double precision, integer) TO btp_app_user;
