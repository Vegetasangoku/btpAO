'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  Building2,
  ArrowLeft,
  ShieldAlert,
  Cpu,
  Sliders,
  DollarSign,
  Users,
  FileText,
  CheckCircle2,
  Trash2,
  Save,
  Loader2,
  Percent,
  Calendar,
  BookOpen,
  BrainCircuit,
  Upload,
  FileUp,
  HardDrive,
  AlertTriangle,
  Palette,
  Eye,
  Download,
  ExternalLink,
  X,
} from 'lucide-react';

import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { LLM_MODEL_TIERS } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';
import { DismissibleNotice } from '@/components/ui/dismissible-notice';

interface TenantDetail {
  id: string;
  name: string;
  slug?: string;
  plan: string;
  siret?: string;
  contact_email?: string;
  monthly_limit?: number;
  used_this_month?: number;
  llm_provider?: string;
  llm_model?: string;
  llm_model_tier?: string;
  llm_fallback_tier?: string;
  branding_config?: any;
  model_routing_config?: {
    extraction_gonogo?: { provider: string; model: string };
    redaction_memoire?: { provider: string; model: string };
    analyse_prix?: { provider: string; model: string };
  };
  created_at?: string;
}

interface TenantSettings {
  custom_system_prompt?: string;
  system_prompt_memory?: string;
  taux_inflation_pct?: number;
  marge_cible_pct?: number;
  taux_horaires?: { ouvrier?: number; conducteur?: number };
}

interface TenantDocument {
  id: string;
  file_name: string;
  title?: string;
  category?: string;
  file_path: string;
  file_type: string;
  file_size: number;
  status: string;
  source?: string;
  can_download?: boolean;
  created_at: string;
}

export default function TenantDetailPage() {
  const { t } = useTranslation();
  const router = useRouter();
  const params = useParams();
  const rawId = params?.id;

  const tenantId = Array.isArray(rawId) ? rawId[0] : (rawId as string);

  const [activeTab, setActiveTab] = useState<'info' | 'routing' | 'rag' | 'memory' | 'economic'>('routing');
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [settings, setSettings] = useState<TenantSettings | null>(null);
  const [modelTier, setModelTier] = useState<string>('inherit');
  // Palier de repli propre a ce tenant (03/09) -- 'inherit' = suit le reglage
  // plateforme (lui-meme automatique si rien n'est configure la non plus).
  const [modelFallbackTier, setModelFallbackTier] = useState<string>('inherit');
  const [documents, setDocuments] = useState<TenantDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [openingDocId, setOpeningDocId] = useState<string | null>(null);
  const [previewDoc, setPreviewDoc] = useState<{ title: string; url: string; isPdf: boolean } | null>(null);
  const [notice, setNotice] = useState<{ message: string; detail?: string; variant?: 'error' | 'success' } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Visualiser / Aperçu immédiat d'un document
  async function handleViewDocument(doc: TenantDocument) {
    setOpeningDocId(doc.id);
    try {
      let url = '';
      if (doc.source === 'tenant_documents' && doc.file_path && !doc.file_path.startsWith('tenants/')) {
        const { data, error } = await supabase.storage.from('company-memories').createSignedUrl(doc.file_path, 3600);
        if (error) throw error;
        url = data.signedUrl;
      } else {
        url = await api.getAdminTenantDocumentBlobUrl(tenantId, doc.id, true);
      }

      const isPdf = (doc.file_name || doc.title || '').toLowerCase().endsWith('.pdf') || (doc.file_type || '').includes('pdf');
      if (isPdf) {
        setPreviewDoc({ title: doc.file_name || doc.title || 'Document', url, isPdf: true });
      } else {
        window.open(url, '_blank');
      }
    } catch (err: any) {
      alert("Impossible de prévisualiser ce document : " + (err.message || 'Erreur inconnue'));
    } finally {
      setOpeningDocId(null);
    }
  }

  // Téléchargement direct d'un document
  async function handleDownloadDocument(doc: TenantDocument) {
    setOpeningDocId(doc.id);
    try {
      let url = '';
      if (doc.source === 'tenant_documents' && doc.file_path && !doc.file_path.startsWith('tenants/')) {
        const { data, error } = await supabase.storage.from('company-memories').createSignedUrl(doc.file_path, 3600);
        if (error) throw error;
        url = data.signedUrl;
      } else {
        url = await api.getAdminTenantDocumentBlobUrl(tenantId, doc.id, false);
      }

      const a = document.createElement('a');
      a.href = url;
      a.download = doc.file_name || doc.title || 'document';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    } catch (err: any) {
      alert("Erreur lors du téléchargement : " + (err.message || 'Erreur inconnue'));
    } finally {
      setOpeningDocId(null);
    }
  }

  useEffect(() => {
    async function loadData() {
      if (!tenantId) return;
      setLoading(true);
      try {
        console.log('[TenantDetailPage] Loading data for tenantId:', tenantId);
        // 1. Tenant info from backend API with fallback
        let loadedTenant: any = null;
        try {
          loadedTenant = await api.getTenantDetail(tenantId);
          console.log('[TenantDetailPage] api.getTenantDetail result:', loadedTenant);
        } catch (apiErr) {
          console.warn('[TenantDetailPage] api.getTenantDetail failed:', apiErr);
          try {
            const { data: tenantData } = await supabase
              .from('tenants')
              .select('*')
              .eq('id', tenantId)
              .maybeSingle();
            loadedTenant = tenantData;
          } catch {}
        }

        if (loadedTenant) {
          setTenant(loadedTenant);
          setModelTier(loadedTenant.llm_model_tier || loadedTenant.branding_config?.llm_model_tier || 'inherit');
          setModelFallbackTier(loadedTenant.llm_fallback_tier || loadedTenant.branding_config?.llm_fallback_tier || 'inherit');
        } else {
          setNotice({ message: t('admin.tenant_detail.err_load_data'), variant: 'error' });
        }

        // 2. Settings & Memory (resilient fallback)
        try {
          const { data: settingsData } = await supabase
            .from('tenants_settings')
            .select('*')
            .eq('tenant_id', tenantId)
            .maybeSingle();

          if (settingsData) {
            setSettings(settingsData);
          } else {
            setSettings({
              custom_system_prompt: `Vous êtes l'ingénieur d'études BTP principal de ${loadedTenant?.name || 'l\'entreprise'}.`,
              system_prompt_memory: `- Mettre en avant la certification Qualibat.\n- Majorer de 5% pour Île-de-France.`,
              taux_inflation_pct: 3.5,
              marge_cible_pct: 12.0,
            });
          }
        } catch {}

        // 3. Documents unifiés (Savoir-faire Entreprise, Templates et Archives)
        try {
          const unifiedDocs = await api.getAdminTenantDocuments(tenantId);
          if (unifiedDocs && unifiedDocs.length > 0) {
            setDocuments(unifiedDocs as any);
          } else {
            // Fallback : lecture directe des tables Supabase
            const { data: assetsData } = await supabase
              .from('company_assets')
              .select('*')
              .eq('tenant_id', tenantId)
              .order('created_at', { ascending: false });

            const { data: legacyDocs } = await supabase
              .from('tenant_documents')
              .select('*')
              .eq('tenant_id', tenantId)
              .order('created_at', { ascending: false });

            const merged: TenantDocument[] = [
              ...(assetsData || []).map((a: any) => ({
                id: a.id,
                file_name: a.metadata_json?.file_name || a.title,
                title: a.title,
                category: a.category,
                file_path: a.s3_url || '',
                file_type: a.metadata_json?.content_type || 'document',
                file_size: a.metadata_json?.file_size || 0,
                status: a.status || 'Prêt',
                source: 'company_knowledge',
                created_at: a.created_at,
                can_download: true,
              })),
              ...(legacyDocs || []).map((d: any) => ({
                ...d,
                source: 'tenant_documents',
                can_download: true,
              })),
            ];
            setDocuments(merged);
          }
        } catch {
          // Fallback legacy
          try {
            const { data: docsData } = await supabase
              .from('tenant_documents')
              .select('*')
              .eq('tenant_id', tenantId)
              .order('created_at', { ascending: false });

            setDocuments(docsData || []);
          } catch {}
        }
      } catch (err) {
        console.error('Erreur chargement client:', err);
      } finally {
        setLoading(false);
      }
    }

    if (tenantId) loadData();
  }, [tenantId]);


  async function handleAdminFileUpload(files: FileList | null) {
    if (!files || files.length === 0 || !tenantId) return;
    setUploading(true);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const cleanName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
        const storagePath = `${tenantId}/${Date.now()}_${cleanName}`;

        const { error: uploadErr } = await supabase.storage
          .from('company-memories')
          .upload(storagePath, file, { upsert: true });

        if (uploadErr) throw uploadErr;

        const fileType = file.name.endsWith('.docx') ? 'memoire_word' : file.name.endsWith('.pdf') ? 'memoire_pdf' : 'certification';
        const { data: newDoc, error: dbErr } = await supabase
          .from('tenant_documents')
          .insert({
            tenant_id: tenantId,
            file_name: file.name,
            file_path: storagePath,
            file_type: fileType,
            file_size: file.size,
            status: 'En cours de traitement OCR...',
          })
          .select()
          .single();

        if (dbErr) throw dbErr;
        if (newDoc) {
          setDocuments(prev => [newDoc, ...prev]);

          fetch('/api/process-document', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              documentId: newDoc.id,
              filePath: storagePath,
              tenantId: tenantId,
              fileName: file.name,
            }),
          }).then(res => res.json()).then(json => {
            if (json.success) {
              setDocuments(prev => prev.map(d => d.id === newDoc.id ? { ...d, status: 'Prêt - Indexé' } : d));
            }
          }).catch(err => console.error('Erreur process-document admin:', err));
        }
      }
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setNotice({ message: t('admin.tenant_detail.err_upload'), detail: err.message, variant: 'error' });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleDeleteDocument(docId: string, filePath: string) {
    if (!confirm(t('admin.tenant_detail.confirm_delete_doc'))) return;
    try {
      await supabase.storage.from('company-memories').remove([filePath]);
      await supabase.from('tenant_documents').delete().eq('id', docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err: any) {
      setNotice({ message: t('admin.tenant_detail.err_delete_doc'), detail: err.message, variant: 'error' });
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    if (!tenant) return;
    setSaving(true);

    try {
      // 1. Update tenants table & model tier via API
      try {
        await api.updateTenant(tenantId, {
          name: tenant.name,
          siret: tenant.siret,
          contact_email: tenant.contact_email,
          plan: tenant.plan,
          llm_model_tier: modelTier,
          llm_fallback_tier: modelFallbackTier,
          branding_config: {
            ...(tenant.branding_config || {}),
            llm_model_tier: modelTier,
            llm_fallback_tier: modelFallbackTier,
            model_routing_config: tenant.model_routing_config,
          },
        });
      } catch (apiErr) {
        const { error: tErr } = await supabase
          .from('tenants')
          .update({
            name: tenant.name,
            siret: tenant.siret,
            contact_email: tenant.contact_email,
            plan: tenant.plan,
            monthly_limit: tenant.monthly_limit,
            model_routing_config: tenant.model_routing_config,
            branding_config: {
              ...(tenant.branding_config || {}),
              llm_model_tier: modelTier,
              llm_fallback_tier: modelFallbackTier,
            },
          })
          .eq('id', tenantId);

        if (tErr) throw tErr;
      }


      // 2. Update tenants_settings & Memory
      if (settings) {
        const { error: sErr } = await supabase
          .from('tenants_settings')
          .upsert({
            tenant_id: tenantId,
            custom_system_prompt: settings.custom_system_prompt,
            system_prompt_memory: settings.system_prompt_memory,
            taux_inflation_pct: settings.taux_inflation_pct,
            marge_cible_pct: settings.marge_cible_pct,
            mis_a_jour_le: new Date().toISOString(),
          }, { onConflict: 'tenant_id' });

        if (sErr) throw sErr;
      }

      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } catch (err: any) {
      setNotice({ message: t('admin.tenant_detail.err_save'), detail: err.message, variant: 'error' });
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm(t('admin.tenant_detail.confirm_delete_tenant', { name: tenant?.name || '' }))) return;
    try {
      await api.deleteTenant(tenantId);
      router.push('/admin/tenants');
    } catch (err: any) {
      setNotice({ message: t('admin.tenant_detail.err_delete_tenant'), detail: String(err?.message || err), variant: 'error' });
    }
  }

  function formatBytes(bytes: number) {
    if (bytes === 0) return '0 ' + t('admin.tenant_detail.rag.unit_kb');
    const k = 1024;
    const sizes = [t('admin.tenant_detail.rag.unit_bytes'), t('admin.tenant_detail.rag.unit_kb'), t('admin.tenant_detail.rag.unit_mb'), t('admin.tenant_detail.rag.unit_gb')];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  if (loading) {
    return (
      <div className="p-16 text-center space-y-3">
        <Loader2 className="w-8 h-8 text-hl animate-spin mx-auto" />
        <p className="text-xs text-muted-foreground">{t('admin.tenant_detail.loading')}</p>
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="p-12 text-center space-y-4">
        <h2 className="text-base font-bold text-foreground font-heading">{t('admin.tenant_detail.not_found_title')}</h2>
        <Link href="/admin/tenants" className="text-xs text-hl hover:underline">
          {t('admin.tenant_detail.not_found_back')}
        </Link>
        {notice && (
          <div className="max-w-md mx-auto text-left">
            <DismissibleNotice
              message={notice.message}
              detail={notice.detail}
              variant={notice.variant}
              onDismiss={() => setNotice(null)}
            />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      {/* Back link & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link
          href="/admin/tenants"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t('admin.tenant_detail.back_link')}</span>
        </Link>

        <div className="flex items-center gap-3">
          {saveSuccess && (
            <div className="px-3 py-1.5 rounded-xl bg-positive/10 border border-positive/30 text-positive text-xs font-bold flex items-center gap-1.5 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4" />
              <span>{t('admin.tenant_detail.save_success')}</span>
            </div>
          )}

          <button
            onClick={handleDelete}
            className="p-2 rounded-xl text-slate-500 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
            title={t('admin.tenant_detail.delete_title')}
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {notice && (
        <DismissibleNotice
          message={notice.message}
          detail={notice.detail}
          variant={notice.variant}
          onDismiss={() => setNotice(null)}
        />
      )}

      {/* Main Info Card */}
      <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line shadow-xs space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-hl/10 text-hl font-bold text-sm flex items-center justify-center border border-hl/20">
              {tenant.name.substring(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded-full bg-hl/10 text-hl border border-hl/20 uppercase">
                  {t('admin.tenant_detail.plan_badge', { plan: tenant.plan })}
                </span>
                <span className="text-xs text-muted-foreground font-mono">{t('admin.tenant_detail.id_label', { id: tenant.id })}</span>
              </div>
              <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight mt-0.5">{tenant.name}</h1>
            </div>
          </div>

          <div className="text-right">
            <p className="text-xs text-muted-foreground font-mono">{t('admin.tenant_detail.monthly_quota')}</p>
            <p className="text-lg font-bold text-foreground font-mono">
              {tenant.used_this_month || 0} <span className="text-xs text-muted-foreground font-normal">/ {tenant.monthly_limit || 15} DCE</span>
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap border-b border-line gap-1.5">
        {[
          { id: 'rag', label: t('admin.tenant_detail.tab_rag'), icon: BookOpen },
          { id: 'memory', label: t('admin.tenant_detail.tab_memory'), icon: BrainCircuit },
          { id: 'routing', label: t('admin.tenant_detail.tab_routing'), icon: Cpu },
          { id: 'economic', label: t('admin.tenant_detail.tab_economic'), icon: Sliders },
          { id: 'info', label: t('admin.tenant_detail.tab_info'), icon: Building2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-3.5 py-2.5 border-b-2 text-xs transition-all font-semibold cursor-pointer ${
                isActive
                  ? 'border-hl text-hl bg-hl/10 rounded-t-xl'
                  : 'border-transparent text-muted-foreground hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-hl' : 'text-muted-foreground'}`} />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: RAG DOCUMENTS (SUPER ADMIN MANAGEMENT) */}
      {activeTab === 'rag' && (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-bold text-foreground font-heading">{t('admin.tenant_detail.rag.title')}</h2>
              <p className="text-xs text-muted-foreground">
                {t('admin.tenant_detail.rag.desc')}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".pdf,.docx,.doc,.png,.jpg,.jpeg"
                className="hidden"
                onChange={(e) => handleAdminFileUpload(e.target.files)}
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                className="btn-primary !py-2 !px-4 !text-xs cursor-pointer"
              >
                {uploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />}
                <span>{uploading ? t('admin.tenant_detail.rag.btn_uploading') : t('admin.tenant_detail.rag.btn_add_doc')}</span>
              </button>
            </div>
          </div>

          <div className="bg-card border border-line rounded-2xl overflow-hidden shadow-xs">
            {documents.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground space-y-2">
                <BookOpen className="w-8 h-8 mx-auto text-muted-foreground" />
                <p>{t('admin.tenant_detail.rag.empty')}</p>
              </div>
            ) : (
              <div className="divide-y divide-line">
                {documents.map((doc) => (
                  <div key={doc.id} className="p-3.5 sm:p-4 flex flex-wrap items-center justify-between gap-3 hover:bg-slate-50/60 dark:hover:bg-raised/50 transition-colors">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-9 h-9 rounded-xl bg-hl/10 text-hl flex items-center justify-center font-bold text-xs shrink-0">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div className="min-w-0 cursor-pointer" onClick={() => handleViewDocument(doc)}>
                        <div className="flex items-center gap-2 flex-wrap">
                          <p className="text-xs font-bold text-foreground hover:text-hl transition-colors truncate">
                            {doc.file_name || doc.title}
                          </p>
                          {doc.source === 'company_knowledge' && (
                            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-hl/10 text-hl border border-hl/20">
                              Savoir-faire Client
                            </span>
                          )}
                          {doc.source === 'export_template' && (
                            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-corten/10 text-corten border border-corten/20">
                              Modèle Word
                            </span>
                          )}
                          {doc.source === 'tenant_documents' && (
                            <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-hl/10 text-hl border border-hl/20">
                              Document Admin
                            </span>
                          )}
                          {doc.category && doc.category !== 'document' && (
                            <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-sunken text-muted-foreground border border-line">
                              {doc.category}
                            </span>
                          )}
                        </div>
                        <p className="text-[10px] text-muted-foreground font-mono mt-0.5">
                          {doc.file_size ? `${formatBytes(doc.file_size)} • ` : ''}
                          {doc.created_at ? new Date(doc.created_at).toLocaleDateString('fr-FR') : 'Date inconnue'}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      {doc.status && doc.status.includes('OCR') ? (
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-hl/10 text-hl border border-hl/20 flex items-center gap-1.5 animate-pulse">
                          <Loader2 className="w-3 h-3 animate-spin text-hl" />
                          <span>{t('admin.tenant_detail.rag.status_ocr')}</span>
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-positive/10 text-positive border border-positive/25 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3 h-3 text-positive" />
                          <span>{t('admin.tenant_detail.rag.status_ready')}</span>
                        </span>
                      )}

                      {/* Visualiser / Preview Button */}
                      <button
                        onClick={() => handleViewDocument(doc)}
                        disabled={openingDocId === doc.id}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-hl hover:bg-hl/10 transition-colors cursor-pointer"
                        title="Visualiser le document"
                      >
                        {openingDocId === doc.id ? (
                          <Loader2 className="w-4 h-4 animate-spin text-hl" />
                        ) : (
                          <Eye className="w-4 h-4" />
                        )}
                      </button>

                      {/* Télécharger / Download Button */}
                      <button
                        onClick={() => handleDownloadDocument(doc)}
                        disabled={openingDocId === doc.id}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-positive hover:bg-positive/10 transition-colors cursor-pointer"
                        title="Télécharger le fichier original"
                      >
                        <Download className="w-4 h-4" />
                      </button>

                      {/* Supprimer Button */}
                      <button
                        onClick={() => handleDeleteDocument(doc.id, doc.file_path)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                        title={t('admin.tenant_detail.rag.btn_delete_doc_title')}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: PROMPT & CONTINUOUS LEARNING LOOP */}
      {activeTab === 'memory' && (
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <h2 className="text-sm font-bold text-foreground font-heading">{t('admin.tenant_detail.memory.title')}</h2>
            <p className="text-xs text-muted-foreground">
              {t('admin.tenant_detail.memory.desc')}
            </p>
          </div>

          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-3 shadow-xs">
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-slate-800 dark:text-zinc-200 flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-hl" />
                <span>{t('admin.tenant_detail.memory.label_learned_rules')}</span>
              </label>
              <p className="text-[11px] text-muted-foreground">
                {t('admin.tenant_detail.memory.desc_learned_rules')}
              </p>
            </div>

            <textarea
              rows={8}
              value={settings?.system_prompt_memory || ''}
              onChange={(e) => setSettings(prev => ({ ...prev, system_prompt_memory: e.target.value }))}
              placeholder={t('admin.tenant_detail.memory.placeholder_learned_rules')}
              className="w-full p-3.5 rounded-xl bg-sunken border border-line focus:border-hl text-slate-800 dark:text-zinc-200 text-xs font-mono focus:outline-none leading-relaxed"
            />
          </div>

          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-3 shadow-xs">
            <div className="space-y-1">
              <label className="block text-xs font-semibold text-slate-800 dark:text-zinc-200">{t('admin.tenant_detail.memory.label_system_prompt')}</label>
              <p className="text-[11px] text-muted-foreground">{t('admin.tenant_detail.memory.desc_system_prompt')}</p>
            </div>

            <textarea
              rows={3}
              value={settings?.custom_system_prompt || ''}
              onChange={(e) => setSettings(prev => ({ ...prev, custom_system_prompt: e.target.value }))}
              className="w-full p-3 rounded-xl bg-sunken border border-line focus:border-hl text-slate-800 dark:text-zinc-200 text-xs font-mono focus:outline-none leading-relaxed"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="btn-primary !py-2 !px-5 !text-xs cursor-pointer"
            >
              {saving ? t('admin.common.saving') : t('admin.tenant_detail.memory.btn_save')}
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: LLM ROUTING */}
      {activeTab === 'routing' && (
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <h2 className="text-sm font-bold text-foreground font-heading">{t('admin.tenant_detail.routing.title')}</h2>
            <p className="text-xs text-muted-foreground">
              {t('admin.tenant_detail.routing.desc')}
            </p>
            <p className="text-[11px] text-muted-foreground mt-1">
              {t('admin.tenant_detail.routing.also_on_main_tab')}{' '}
              <Link href="/admin?tab=routing" className="text-hl hover:underline">
                {t('admin.tenant_detail.routing.main_tab_link')}
              </Link>
            </p>
          </div>

          {/* Level 2: Per-Client Model Tier Selection */}
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-3.5 shadow-xs">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
              <div>
                <h3 className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
                  <Cpu className="w-4 h-4 text-hl" />
                  <span>{t('admin.common.ai_model_override_title')}</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('admin.tenant_detail.routing.desc2')}
                </p>
              </div>
              <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full border ${
                modelTier === 'inherit' 
                  ? 'bg-sunken text-muted-foreground border-line' 
                  : 'bg-hl/10 text-hl border-hl/20'
              }`}>
                {modelTier === 'inherit' ? t('admin.tenant_detail.routing.badge_inherited') : t('admin.tenant_detail.routing.badge_override')}
              </span>
            </div>

            <div className="space-y-2">
              <label htmlFor="tenant-model-tier-select" className="block text-xs font-semibold text-foreground">
                {t('admin.tenant_detail.routing.label_tier')}
              </label>
              <select
                id="tenant-model-tier-select"
                value={modelTier}
                onChange={(e) => setModelTier(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-xs text-foreground font-medium focus:outline-none cursor-pointer"
              >
                <option value="inherit">{t('admin.common.inherit_option')}</option>
                {LLM_MODEL_TIERS.map((tier) => (
                  <option key={tier.id} value={tier.id}>
                    {tier.display_label}
                  </option>
                ))}
              </select>

              <p className="text-[11px] text-muted-foreground">
                {t('admin.tenant_detail.routing.hint_inherit')}
              </p>
            </div>

            <div className="space-y-2 pt-2">
              <label htmlFor="tenant-fallback-tier-select" className="block text-xs font-semibold text-foreground">
                Modèle de repli pour ce client
              </label>
              <select
                id="tenant-fallback-tier-select"
                value={modelFallbackTier}
                onChange={(e) => setModelFallbackTier(e.target.value)}
                className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-xs text-foreground font-medium focus:outline-none cursor-pointer"
              >
                <option value="inherit">{t('admin.common.inherit_option')}</option>
                {LLM_MODEL_TIERS.map((tier) => (
                  <option key={tier.id} value={tier.id}>
                    {tier.display_label}
                  </option>
                ))}
              </select>

              <p className="text-[11px] text-muted-foreground">
                Modèle utilisé pour UN essai de secours si l'appel au modèle principal de ce client échoue, avant le moteur de gabarits. « Hérite » suit le réglage plateforme (lui-même automatique si rien n'y est configuré).
              </p>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="btn-primary !py-2 !px-5 !text-xs cursor-pointer"
            >
              {saving ? t('admin.common.saving') : t('admin.tenant_detail.routing.btn_save')}
            </button>
          </div>
        </form>
      )}

      {/* TAB 4: ECONOMIC RULES */}
      {activeTab === 'economic' && (
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <h2 className="text-sm font-bold text-foreground font-heading">{t('admin.tenant_detail.tab_economic')}</h2>
            <p className="text-xs text-muted-foreground">{t('admin.tenant_detail.economic.desc')}</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-2xl bg-card border border-line space-y-2 shadow-xs">
              <label className="block text-xs font-semibold text-foreground">{t('admin.tenant_detail.economic.label_inflation')}</label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  value={settings?.taux_inflation_pct || 3.5}
                  onChange={(e) => setSettings(prev => ({ ...prev, taux_inflation_pct: parseFloat(e.target.value) || 0 }))}
                  className="w-full pl-3 pr-8 py-2 rounded-xl bg-sunken border border-line text-foreground font-mono text-xs focus:border-hl focus:outline-none"
                />
                <Percent className="w-3.5 h-3.5 text-muted-foreground absolute right-3 top-2.5" />
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-card border border-line space-y-2 shadow-xs">
              <label className="block text-xs font-semibold text-foreground">{t('admin.tenant_detail.economic.label_margin')}</label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  value={settings?.marge_cible_pct || 12.0}
                  onChange={(e) => setSettings(prev => ({ ...prev, marge_cible_pct: parseFloat(e.target.value) || 0 }))}
                  className="w-full pl-3 pr-8 py-2 rounded-xl bg-sunken border border-line text-foreground font-mono text-xs focus:border-hl focus:outline-none"
                />
                <Percent className="w-3.5 h-3.5 text-muted-foreground absolute right-3 top-2.5" />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="btn-primary !py-2 !px-5 !text-xs cursor-pointer"
            >
              {saving ? t('admin.common.saving') : t('admin.tenant_detail.economic.btn_save')}
            </button>
          </div>
        </form>
      )}

      {/* TAB 5: COMPANY INFO */}
      {activeTab === 'info' && (
        <form onSubmit={handleSave} className="space-y-4">
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-4 shadow-xs">
            <h2 className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
              <Building2 className="w-4 h-4 text-hl" />
              <span>{t('admin.tenant_detail.info.title')}</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-semibold text-foreground mb-1">{t('admin.tenant_detail.info.label_name')}</label>
                <input
                  type="text"
                  required
                  value={tenant.name}
                  onChange={(e) => setTenant({ ...tenant, name: e.target.value })}
                  className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-foreground text-xs focus:outline-none font-medium"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1">{t('admin.super.modal.label_siret')}</label>
                <input
                  type="text"
                  value={tenant.siret || ''}
                  onChange={(e) => setTenant({ ...tenant, siret: e.target.value })}
                  placeholder={t('admin.tenant_detail.info.placeholder_siret')}
                  className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-foreground text-xs focus:outline-none font-mono"
                />
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1">{t('admin.tenant_detail.info.label_email')}</label>
                <input
                  type="email"
                  value={tenant.contact_email || ''}
                  onChange={(e) => setTenant({ ...tenant, contact_email: e.target.value })}
                  placeholder={t('admin.tenant_detail.info.placeholder_email')}
                  className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-foreground text-xs focus:outline-none font-medium"
                />
              </div>
            </div>
          </div>

          {/* BT02 (01/09) : jusqu'ici branding_config.primary_color etait deja lu par
              gantt_service.py / diagram_service.py mais AUCUN champ, ici ou ailleurs,
              ne permettait de le regler -- seule une ecriture DB directe le pouvait. Ce
              bloc est le premier point d'entree UI reel, avec le nouveau shape_style. */}
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-4 shadow-xs">
            <h2 className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
              <Palette className="w-4 h-4 text-hl" />
              <span>{t('admin.tenant_detail.branding.title')}</span>
            </h2>
            <p className="text-[11px] text-muted-foreground -mt-2">{t('admin.tenant_detail.branding.subtitle')}</p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-semibold text-foreground mb-1">{t('admin.tenant_detail.branding.label_color')}</label>
                <div className="flex items-center gap-2">
                  <input
                    type="color"
                    value={tenant.branding_config?.primary_color || '#1C6091'}
                    onChange={(e) => setTenant({ ...tenant, branding_config: { ...(tenant.branding_config || {}), primary_color: e.target.value } })}
                    className="w-10 h-9 rounded-lg border border-line bg-transparent cursor-pointer shrink-0"
                  />
                  <input
                    type="text"
                    value={tenant.branding_config?.primary_color || ''}
                    onChange={(e) => setTenant({ ...tenant, branding_config: { ...(tenant.branding_config || {}), primary_color: e.target.value } })}
                    placeholder="#1C6091"
                    className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-foreground text-xs focus:outline-none font-mono"
                  />
                </div>
                <p className="text-[10px] text-muted-foreground mt-1">{t('admin.tenant_detail.branding.hint_color')}</p>
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1">{t('admin.tenant_detail.branding.label_shape')}</label>
                <select
                  value={tenant.branding_config?.shape_style || 'arrondi'}
                  onChange={(e) => setTenant({ ...tenant, branding_config: { ...(tenant.branding_config || {}), shape_style: e.target.value } })}
                  className="w-full px-3 py-2 rounded-xl bg-sunken border border-line focus:border-hl text-foreground text-xs focus:outline-none font-medium"
                >
                  <option value="anguleux">{t('admin.tenant_detail.branding.shape_anguleux')}</option>
                  <option value="arrondi">{t('admin.tenant_detail.branding.shape_arrondi')}</option>
                  <option value="pilule">{t('admin.tenant_detail.branding.shape_pilule')}</option>
                </select>
                <p className="text-[10px] text-muted-foreground mt-1">{t('admin.tenant_detail.branding.hint_shape')}</p>
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="btn-primary !py-2 !px-5 !text-xs cursor-pointer"
            >
              {saving ? t('admin.common.saving') : t('admin.tenant_detail.info.btn_save')}
            </button>
          </div>
        </form>
      )}

      {/* MODAL DE PRÉVISUALISATION DU DOCUMENT */}
      {previewDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs animate-fade-in">
          <div className="bg-card border border-line rounded-2xl w-full max-w-4xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex items-center justify-between p-4 border-b border-line">
              <div className="flex items-center gap-2.5">
                <FileText className="w-5 h-5 text-hl" />
                <h3 className="text-sm font-bold text-foreground truncate max-w-md">
                  {previewDoc.title}
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <a
                  href={previewDoc.url}
                  download={previewDoc.title}
                  className="btn-secondary !py-1.5 !px-3 !text-xs flex items-center gap-1.5 cursor-pointer"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Télécharger</span>
                </a>
                <button
                  onClick={() => setPreviewDoc(null)}
                  className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised transition-colors cursor-pointer"
                  title="Fermer"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            <div className="flex-1 bg-slate-100 dark:bg-slate-950 p-2 overflow-hidden">
              <iframe
                src={previewDoc.url}
                className="w-full h-[70vh] rounded-xl border border-line"
                title={previewDoc.title}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
