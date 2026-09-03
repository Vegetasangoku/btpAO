-- ==============================================================================
-- 00033_sharepoint_connectors.sql
-- Connecteur SharePoint (Microsoft Graph) par tenant, avec synchronisation
-- incrémentale par delta-query : seuls les fichiers nouveaux ou modifiés depuis
-- le dernier passage sont retéléchargés et réindexés (jamais un scan complet
-- répété -- c'est le principal levier anti-dérapage de coût OCR/embeddings pour
-- ce connecteur). Un connecteur = une App Registration Azure AD (client_id +
-- client_secret, credentials fournis par l'IT du client, jamais par btpAO) avec
-- accès en lecture seule à un Drive/dossier SharePoint précis choisi par le
-- client -- jamais tout le tenant Microsoft 365.
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.sharepoint_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL UNIQUE REFERENCES public.tenants(id) ON DELETE CASCADE,
    ms_tenant_id TEXT NOT NULL,               -- Azure AD tenant ID du CLIENT (jamais le nôtre)
    client_id TEXT NOT NULL,                  -- App Registration (client credentials flow)
    client_secret_encrypted TEXT NOT NULL,    -- chiffré via app.core.crypto_vault (AES-256-GCM)
    site_url TEXT NOT NULL,                   -- ex. https://contoso.sharepoint.com/sites/AppelsOffres
    drive_id TEXT,                            -- résolu au premier appel Graph réussi
    selected_folder_path TEXT NOT NULL DEFAULT '/',  -- limite volontaire du périmètre indexé
    allowed_extensions TEXT[] NOT NULL DEFAULT ARRAY['pdf','docx','xlsx'],
    max_file_size_bytes BIGINT NOT NULL DEFAULT 52428800, -- 50 Mo, aligné sur MAX_FILE_SIZE_BYTES
    status TEXT NOT NULL DEFAULT 'pending_verification', -- pending_verification | connected | error | disconnected
    last_error TEXT,
    delta_link TEXT,                          -- curseur Microsoft Graph /delta -- coeur du sync incrémental
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.sharepoint_connections ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_sharepoint_connections" ON public.sharepoint_connections;
CREATE POLICY "tenant_isolation_sharepoint_connections" ON public.sharepoint_connections
    FOR ALL USING (
        tenant_id = public.current_tenant_id()
        OR auth.role() = 'service_role'
    );

CREATE INDEX IF NOT EXISTS idx_sharepoint_connections_tenant ON public.sharepoint_connections(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sharepoint_connections_status ON public.sharepoint_connections(status) WHERE status = 'connected';

GRANT ALL ON public.sharepoint_connections TO postgres, authenticated, anon, service_role, btp_app_user;

-- Un enregistrement par fichier SharePoint déjà traité : permet de ne réindexer
-- QUE les fichiers nouveaux ou dont le contenu a changé (comparaison de
-- file_hash), même si Microsoft Graph renvoie l'item dans un delta (un simple
-- déplacement/renommage ne doit pas redéclencher OCR + embeddings).
CREATE TABLE IF NOT EXISTS public.sharepoint_sync_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES public.tenants(id) ON DELETE CASCADE,
    connection_id UUID NOT NULL REFERENCES public.sharepoint_connections(id) ON DELETE CASCADE,
    graph_item_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    file_hash TEXT,
    size_bytes BIGINT,
    company_asset_id UUID REFERENCES public.company_assets(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'indexed',   -- indexed | skipped_type | skipped_size | skipped_quota | failed | deleted_upstream
    status_detail TEXT,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_sharepoint_sync_items_item UNIQUE (connection_id, graph_item_id)
);

ALTER TABLE public.sharepoint_sync_items ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "tenant_isolation_sharepoint_sync_items" ON public.sharepoint_sync_items;
CREATE POLICY "tenant_isolation_sharepoint_sync_items" ON public.sharepoint_sync_items
    FOR ALL USING (
        tenant_id = public.current_tenant_id()
        OR auth.role() = 'service_role'
    );

CREATE INDEX IF NOT EXISTS idx_sharepoint_sync_items_tenant ON public.sharepoint_sync_items(tenant_id);
CREATE INDEX IF NOT EXISTS idx_sharepoint_sync_items_connection ON public.sharepoint_sync_items(connection_id);

GRANT ALL ON public.sharepoint_sync_items TO postgres, authenticated, anon, service_role, btp_app_user;

COMMENT ON TABLE public.sharepoint_connections IS
'Un connecteur SharePoint par tenant (Microsoft Graph, client-credentials flow). delta_link porte le curseur de synchronisation incrémentale -- voir app/services/sharepoint_service.py.';
COMMENT ON TABLE public.sharepoint_sync_items IS
'Historique des fichiers SharePoint déjà synchronisés, utilisé pour ignorer les fichiers inchangés (comparaison file_hash) même quand Microsoft Graph les renvoie dans un delta.';
