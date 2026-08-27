-- Migration 00019: Clean up RLS policies, drop dead tables, remove is_super_admin()

-- 1. DROP DEAD TABLES
DROP TABLE IF EXISTS public.projets CASCADE;
DROP TABLE IF EXISTS public.base_connaissances CASCADE;
DROP TABLE IF EXISTS public.sections_memoire CASCADE;
DROP TABLE IF EXISTS public.criteres_notation CASCADE;
DROP TABLE IF EXISTS public.donnees_chantier CASCADE;

-- 2. UPDATE STORAGE POLICIES TO USE is_superadmin()
DROP POLICY IF EXISTS company_memories_storage_policy ON storage.objects;
DROP POLICY IF EXISTS tenant_storage_access ON storage.objects;

CREATE POLICY company_memories_storage_policy ON storage.objects
    FOR ALL USING (
        bucket_id = 'company-memories' AND (
            is_superadmin() OR
            (storage.foldername(name))[1] = (current_tenant_id())::text OR
            auth.role() = 'authenticated'
        )
    );

CREATE POLICY tenant_storage_access ON storage.objects
    FOR ALL USING (
        is_superadmin() OR (
            bucket_id = ANY (ARRAY['dce-files'::text, 'company-memories'::text, 'generated-docs'::text]) AND
            (storage.foldername(name))[1] = (current_tenant_id())::text
        )
    );

-- 3. DROP OBSOLETE / DUPLICATE POLICIES ON PUBLIC TABLES
DROP POLICY IF EXISTS dce_documents_isolation_policy ON public.dce_documents;
DROP POLICY IF EXISTS dce_documents_superadmin_all ON public.dce_documents;
DROP POLICY IF EXISTS tenant_isolation_dce_documents ON public.dce_documents;

DROP POLICY IF EXISTS dce_embeddings_isolation_policy ON public.dce_embeddings;
DROP POLICY IF EXISTS tenant_isolation_dce_embeddings ON public.dce_embeddings;
DROP POLICY IF EXISTS dce_embeddings_superadmin_all ON public.dce_embeddings;

DROP POLICY IF EXISTS profiles_isolation_policy ON public.profiles;
DROP POLICY IF EXISTS tenant_isolation_profiles ON public.profiles;
DROP POLICY IF EXISTS profiles_superadmin_all ON public.profiles;

DROP POLICY IF EXISTS tenant_documents_isolation ON public.tenant_documents;
DROP POLICY IF EXISTS tenant_isolation_tenant_documents ON public.tenant_documents;
DROP POLICY IF EXISTS tenant_documents_superadmin_all ON public.tenant_documents;

DROP POLICY IF EXISTS tenant_document_chunks_isolation ON public.tenant_document_chunks;
DROP POLICY IF EXISTS tenant_isolation_tenant_document_chunks ON public.tenant_document_chunks;
DROP POLICY IF EXISTS tenant_document_chunks_superadmin_all ON public.tenant_document_chunks;

DROP POLICY IF EXISTS tenants_settings_isolation ON public.tenants_settings;
DROP POLICY IF EXISTS tenant_isolation_tenants_settings ON public.tenants_settings;
DROP POLICY IF EXISTS tenants_settings_superadmin_all ON public.tenants_settings;

DROP POLICY IF EXISTS tenant_isolation_company_assets ON public.company_assets;
DROP POLICY IF EXISTS company_assets_superadmin_all ON public.company_assets;

-- 4. RECREATE CLEAN UNIFIED POLICIES (tenant_id = current_tenant_id() OR auth.role() = 'service_role') + is_superadmin()

-- dce_documents
CREATE POLICY tenant_isolation_dce_documents ON public.dce_documents
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY dce_documents_superadmin_all ON public.dce_documents
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- dce_embeddings
CREATE POLICY tenant_isolation_dce_embeddings ON public.dce_embeddings
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY dce_embeddings_superadmin_all ON public.dce_embeddings
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- profiles
CREATE POLICY tenant_isolation_profiles ON public.profiles
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role' OR id = auth.uid())
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role' OR id = auth.uid());

CREATE POLICY profiles_superadmin_all ON public.profiles
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- tenant_documents
CREATE POLICY tenant_isolation_tenant_documents ON public.tenant_documents
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_documents_superadmin_all ON public.tenant_documents
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- tenant_document_chunks
CREATE POLICY tenant_isolation_tenant_document_chunks ON public.tenant_document_chunks
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY tenant_document_chunks_superadmin_all ON public.tenant_document_chunks
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- tenants_settings
CREATE POLICY tenant_isolation_tenants_settings ON public.tenants_settings
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY tenants_settings_superadmin_all ON public.tenants_settings
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- company_assets
CREATE POLICY tenant_isolation_company_assets ON public.company_assets
    FOR ALL USING (tenant_id = current_tenant_id() OR auth.role() = 'service_role')
    WITH CHECK (tenant_id = current_tenant_id() OR auth.role() = 'service_role');

CREATE POLICY company_assets_superadmin_all ON public.company_assets
    FOR ALL USING (is_superadmin())
    WITH CHECK (is_superadmin());

-- 5. DROP is_super_admin() FUNCTION
DROP FUNCTION IF EXISTS public.is_super_admin();
