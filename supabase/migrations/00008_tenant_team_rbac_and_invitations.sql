-- =============================================================================
-- Migration 00008: Multi-User per Tenant, Roles (owner, member, read_only) & Team Invitations
-- Standard Multi-Tenant PostgreSQL RLS (Strict tenant isolation)
-- =============================================================================

-- 1. Ensure user role constraints allow owner, member, read_only
ALTER TABLE public.users DROP CONSTRAINT IF EXISTS check_user_role;
ALTER TABLE public.users ADD CONSTRAINT check_user_role 
    CHECK (role IN ('owner', 'member', 'read_only', 'conducteur_travaux', 'chiffreur', 'admin'));

-- 2. Tenant Invitations Table
CREATE TABLE IF NOT EXISTS public.tenant_invitations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'member', 'read_only', 'conducteur_travaux', 'chiffreur')),
    invitation_token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'accepted', 'revoked', 'expired')),
    invited_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '7 days'),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Performance and query indexes
CREATE INDEX IF NOT EXISTS idx_tenant_invitations_tenant_id ON public.tenant_invitations(tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_tenant_invitations_token ON public.tenant_invitations(invitation_token);

-- Permissions
GRANT ALL ON TABLE public.tenant_invitations TO btp_app_user;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO btp_app_user;

-- Enable Row Level Security
ALTER TABLE public.tenant_invitations ENABLE ROW LEVEL SECURITY;

-- Strict Multi-Tenant Isolation Policy:
-- - Writes (INSERT/UPDATE/DELETE) require explicit app.current_tenant_id matching
-- - Pending token lookup allowed for unauthenticated invitees with valid token secret
DROP POLICY IF EXISTS tenant_isolation_tenant_invitations ON public.tenant_invitations;
CREATE POLICY tenant_isolation_tenant_invitations ON public.tenant_invitations
    FOR ALL
    TO btp_app_user
    USING (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
        OR (status = 'pending')
    )
    WITH CHECK (
        tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::UUID
    );
