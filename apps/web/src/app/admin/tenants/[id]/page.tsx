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
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { LLM_MODEL_TIERS } from '@/lib/types';

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
  file_path: string;
  file_type: string;
  file_size: number;
  status: string;
  created_at: string;
}

export default function TenantDetailPage() {
  const params = useParams();
  const rawId = params?.id;
  const tenantId = Array.isArray(rawId) ? rawId[0] : (rawId as string);

  const [activeTab, setActiveTab] = useState<'info' | 'routing' | 'rag' | 'memory' | 'economic'>('routing');
  const [tenant, setTenant] = useState<TenantDetail | null>(null);
  const [settings, setSettings] = useState<TenantSettings | null>(null);
  const [modelTier, setModelTier] = useState<string>('inherit');
  const [documents, setDocuments] = useState<TenantDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const AVAILABLE_MODELS = [
    { id: 'claude-3-5-sonnet-20241022', provider: 'Anthropic', name: 'Claude 3.5 Sonnet (Rédaction Haute Qualité)' },
    { id: 'gpt-4o', provider: 'OpenAI', name: 'GPT-4o (Synthèse Rapide & Go/No-Go)' },
    { id: 'gemini-1.5-pro', provider: 'Google', name: 'Gemini 1.5 Pro (Grand Contexte DCE)' },
    { id: 'mistral-large-2407', provider: 'Mistral AI', name: 'Mistral Large 2 (Souveraineté RGPD)' },
  ];

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

        // 3. Documents RAG (resilient fallback)
        try {
          const { data: docsData } = await supabase
            .from('tenant_documents')
            .select('*')
            .eq('tenant_id', tenantId)
            .order('created_at', { ascending: false });

          setDocuments(docsData || []);
        } catch {}
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
      alert('Erreur upload : ' + err.message);
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleDeleteDocument(docId: string, filePath: string) {
    if (!confirm('Supprimer ce document RAG du client ?')) return;
    try {
      await supabase.storage.from('company-memories').remove([filePath]);
      await supabase.from('tenant_documents').delete().eq('id', docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err: any) {
      alert('Erreur suppression : ' + err.message);
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
          branding_config: {
            ...(tenant.branding_config || {}),
            llm_model_tier: modelTier,
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
      alert('Erreur enregistrement : ' + err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!confirm('Supprimer définitivement cette entreprise cliente et tous ses accès ?')) return;
    const { error } = await supabase.from('tenants').delete().eq('id', tenantId);
    if (error) {
      alert('Erreur suppression : ' + error.message);
    } else {
      router.push('/admin/tenants');
    }
  }

  function formatBytes(bytes: number) {
    if (bytes === 0) return '0 Ko';
    const k = 1024;
    const sizes = ['Octets', 'Ko', 'Mo', 'Go'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  if (loading) {
    return (
      <div className="p-16 text-center space-y-3">
        <Loader2 className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
        <p className="text-xs text-slate-400">Chargement de la fiche client...</p>
      </div>
    );
  }

  if (!tenant) {
    return (
      <div className="p-12 text-center space-y-4">
        <h2 className="text-base font-bold text-white">Entreprise cliente introuvable</h2>
        <Link href="/admin/tenants" className="text-xs text-rose-400 hover:underline">
          ← Retour à la liste des entreprises
        </Link>
      </div>
    );
  }

  const routing = tenant.model_routing_config || {};
  const currentGoNoGo = routing.extraction_gonogo?.model || 'gpt-4o';
  const currentRedaction = routing.redaction_memoire?.model || tenant.llm_model || 'claude-3-5-sonnet-20241022';
  const currentPricing = routing.analyse_prix?.model || 'gemini-1.5-pro';

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      {/* Back link & Actions */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <Link
          href="/admin/tenants"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Retour aux entreprises clientes</span>
        </Link>

        <div className="flex items-center gap-3">
          {saveSuccess && (
            <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-1.5 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4" />
              <span>Modifications enregistrées !</span>
            </div>
          )}

          <button
            onClick={handleDelete}
            className="p-2 rounded-xl text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
            title="Supprimer le tenant"
          >
            <Trash2 className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Main Info Card */}
      <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-slate-800 text-rose-400 font-black text-sm flex items-center justify-center border border-slate-700">
              {tenant.name.substring(0, 2).toUpperCase()}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 uppercase">
                  Plan {tenant.plan}
                </span>
                <span className="text-xs text-slate-500 font-mono">ID : {tenant.id}</span>
              </div>
              <h1 className="text-xl sm:text-2xl font-black text-white">{tenant.name}</h1>
            </div>
          </div>

          <div className="text-right">
            <p className="text-xs text-slate-400 font-mono">Quota mensuel</p>
            <p className="text-lg font-black text-white">
              {tenant.used_this_month || 0} <span className="text-xs text-slate-400 font-normal">/ {tenant.monthly_limit || 15} DCE</span>
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap border-b border-slate-800 gap-2">
        {[
          { id: 'rag', label: 'Documents RAG (Base de Connaissance)', icon: BookOpen },
          { id: 'memory', label: 'Prompt & Mémoire Continue', icon: BrainCircuit },
          { id: 'routing', label: 'Moteurs IA Assignés', icon: Cpu },
          { id: 'economic', label: 'Règles Économiques & Inflation', icon: Sliders },
          { id: 'info', label: 'Informations Entreprise', icon: Building2 },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-3 border-b-2 text-xs font-bold transition-all ${
                isActive
                  ? 'border-rose-500 text-rose-400 bg-rose-500/5'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {/* TAB 1: RAG DOCUMENTS (SUPER ADMIN MANAGEMENT) */}
      {activeTab === 'rag' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-white">Documents RAG du Client (Bucket company-memories)</h2>
              <p className="text-xs text-slate-400">
                Vous pouvez ajouter des documents de référence (anciens mémoires, certificats) pour enrichir la mémoire de ce client.
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
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
              >
                {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
                <span>{uploading ? 'Téléversement...' : 'Ajouter un document RAG'}</span>
              </button>
            </div>
          </div>

          <div className="bg-slate-900/90 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
            {documents.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500 space-y-2">
                <BookOpen className="w-8 h-8 mx-auto text-slate-600" />
                <p>Aucun document RAG téléversé pour ce client.</p>
              </div>
            ) : (
              <div className="divide-y divide-slate-800">
                {documents.map((doc) => (
                  <div key={doc.id} className="p-4 flex items-center justify-between hover:bg-slate-800/40 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-xl bg-rose-500/10 text-rose-400 border border-rose-500/20 flex items-center justify-center font-bold text-xs">
                        <FileText className="w-4 h-4" />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-white">{doc.file_name}</p>
                        <p className="text-[10px] text-slate-400 font-mono">
                          {formatBytes(doc.file_size)} • Indexé le {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3">
                      {doc.status.includes('OCR') ? (
                        <span className="text-[10px] font-bold px-2.5 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 animate-pulse">
                          <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                          <span>En cours de traitement OCR...</span>
                        </span>
                      ) : (
                        <span className="text-[10px] font-bold px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
                          <CheckCircle2 className="w-3 h-3 text-emerald-400" />
                          <span>Prêt - Indexé</span>
                        </span>
                      )}
                      <button
                        onClick={() => handleDeleteDocument(doc.id, doc.file_path)}
                        className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        title="Supprimer le document"
                      >
                        <Trash2 className="w-4 h-4" />
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
        <form onSubmit={handleSave} className="space-y-6">
          <div>
            <h2 className="text-base font-bold text-white">Cerveau Client & Boucle d'Apprentissage (Prompt Memory)</h2>
            <p className="text-xs text-slate-400">
              Ajustez les consignes permanentes et les règles apprises injectées dans le moteur de rédaction de cette entreprise.
            </p>
          </div>

          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-white flex items-center gap-2">
                <BrainCircuit className="w-4 h-4 text-rose-400" />
                <span>Règles Métier Apprises & Mémoire Continue (`system_prompt_memory`)</span>
              </label>
              <p className="text-[11px] text-slate-400">
                Ces consignes sont prioritaires et automatiquement injectées lors de chaque génération de mémoire technique pour ce client.
              </p>
            </div>

            <textarea
              rows={8}
              value={settings?.system_prompt_memory || ''}
              onChange={(e) => setSettings(prev => ({ ...prev, system_prompt_memory: e.target.value }))}
              placeholder="- Toujours valoriser notre flotte de grues en propriété propre..."
              className="w-full p-4 rounded-2xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-slate-200 text-xs font-mono focus:outline-none leading-relaxed"
            />
          </div>

          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
            <div className="space-y-1">
              <label className="block text-xs font-bold text-white">Prompt Système Global (`custom_system_prompt`)</label>
              <p className="text-[11px] text-slate-400">Rôle de base attribué au modèle IA lors de la rédaction.</p>
            </div>

            <textarea
              rows={3}
              value={settings?.custom_system_prompt || ''}
              onChange={(e) => setSettings(prev => ({ ...prev, custom_system_prompt: e.target.value }))}
              className="w-full p-3 rounded-2xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-slate-200 text-xs font-mono focus:outline-none leading-relaxed"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
            >
              {saving ? 'Enregistrement...' : 'Enregistrer le cerveau client'}
            </button>
          </div>
        </form>
      )}

      {/* TAB 3: LLM ROUTING */}
      {activeTab === 'routing' && (
        <form onSubmit={handleSave} className="space-y-6">
          <div>
            <h2 className="text-base font-bold text-white">Moteurs d'Intelligence Artificielle & Modèle Assigné</h2>
            <p className="text-xs text-slate-400">
              Définissez le niveau d'intelligence artificielle alloué à cette entreprise cliente (override spécifique ou héritage).
            </p>
          </div>

          {/* Level 2: Per-Client Model Tier Selection */}
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-bold text-white flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-sky-400" />
                  <span>Modèle IA Assigné (Override Client)</span>
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Choisissez le palier de performance et de coût pour les générations de cette entreprise.
                </p>
              </div>
              <span className={`text-[10px] font-bold px-2.5 py-1 rounded border ${
                modelTier === 'inherit' 
                  ? 'bg-slate-800 text-slate-300 border-slate-700' 
                  : 'bg-rose-500/10 text-rose-300 border-rose-500/30'
              }`}>
                {modelTier === 'inherit' ? 'Mode Hérité (Plateforme)' : 'Override Spécifique'}
              </span>
            </div>

            <div className="space-y-2">
              <label htmlFor="tenant-model-tier-select" className="block text-xs font-bold text-slate-200">
                Palier de Modèle IA
              </label>
              <select
                id="tenant-model-tier-select"
                value={modelTier}
                onChange={(e) => setModelTier(e.target.value)}
                className="w-full px-4 py-3 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-xs text-white font-medium focus:outline-none cursor-pointer"
              >
                <option value="inherit">Hériter du réglage général (par défaut)</option>
                {LLM_MODEL_TIERS.map((tier) => (
                  <option key={tier.id} value={tier.id}>
                    {tier.display_label}
                  </option>
                ))}
              </select>
              <p className="text-[11px] text-slate-500">
                Si "Hériter du réglage général" est sélectionné, le client utilise instantanément le modèle global défini par le super-admin.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
              <label className="block text-xs font-bold text-slate-200">1. Synthèse DCE & Go/No-Go</label>

              <select
                value={currentGoNoGo}
                onChange={(e) => {
                  const model = e.target.value;
                  const provider = model.includes('claude') ? 'anthropic' : model.includes('gpt') ? 'openai' : 'google';
                  setTenant({
                    ...tenant,
                    model_routing_config: {
                      ...(tenant.model_routing_config || {}),
                      extraction_gonogo: { provider, model },
                    },
                  });
                }}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 focus:border-rose-500 text-xs text-white focus:outline-none"
              >
                {AVAILABLE_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/80 border border-rose-950/60 space-y-2">
              <label className="block text-xs font-bold text-rose-300">2. Rédaction Mémoire (30+ pages)</label>
              <select
                value={currentRedaction}
                onChange={(e) => {
                  const model = e.target.value;
                  const provider = model.includes('claude') ? 'anthropic' : model.includes('gpt') ? 'openai' : 'google';
                  setTenant({
                    ...tenant,
                    model_routing_config: {
                      ...(tenant.model_routing_config || {}),
                      redaction_memoire: { provider, model },
                    },
                  });
                }}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-rose-900/60 focus:border-rose-500 text-xs text-white focus:outline-none"
              >
                {AVAILABLE_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
              <label className="block text-xs font-bold text-slate-200">3. Chiffrage & Inflation</label>
              <select
                value={currentPricing}
                onChange={(e) => {
                  const model = e.target.value;
                  const provider = model.includes('claude') ? 'anthropic' : model.includes('gpt') ? 'openai' : 'google';
                  setTenant({
                    ...tenant,
                    model_routing_config: {
                      ...(tenant.model_routing_config || {}),
                      analyse_prix: { provider, model },
                    },
                  });
                }}
                className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 focus:border-rose-500 text-xs text-white focus:outline-none"
              >
                {AVAILABLE_MODELS.map((m) => (
                  <option key={m.id} value={m.id}>{m.name}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
            >
              {saving ? 'Enregistrement...' : 'Enregistrer le routage IA'}
            </button>
          </div>
        </form>
      )}

      {/* TAB 4: ECONOMIC RULES */}
      {activeTab === 'economic' && (
        <form onSubmit={handleSave} className="space-y-6">
          <div>
            <h2 className="text-base font-bold text-white">Règles Économiques & Inflation</h2>
            <p className="text-xs text-slate-400">Paramètres financiers appliqués au calcul des bordereaux de prix.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
              <label className="block text-xs font-bold text-slate-300">Taux d'Ajustement Inflation (%)</label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  value={settings?.taux_inflation_pct || 3.5}
                  onChange={(e) => setSettings(prev => ({ ...prev, taux_inflation_pct: parseFloat(e.target.value) || 0 }))}
                  className="w-full pl-3 pr-8 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-xs focus:outline-none"
                />
                <Percent className="w-4 h-4 text-slate-500 absolute right-3 top-2" />
              </div>
            </div>

            <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
              <label className="block text-xs font-bold text-slate-300">Marge Cible (%)</label>
              <div className="relative">
                <input
                  type="number"
                  step="0.1"
                  value={settings?.marge_cible_pct || 12.0}
                  onChange={(e) => setSettings(prev => ({ ...prev, marge_cible_pct: parseFloat(e.target.value) || 0 }))}
                  className="w-full pl-3 pr-8 py-2 rounded-xl bg-slate-900 border border-slate-800 text-white font-mono text-xs focus:outline-none"
                />
                <Percent className="w-4 h-4 text-slate-500 absolute right-3 top-2" />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
            >
              {saving ? 'Enregistrement...' : 'Enregistrer les règles économiques'}
            </button>
          </div>
        </form>
      )}

      {/* TAB 5: COMPANY INFO */}
      {activeTab === 'info' && (
        <form onSubmit={handleSave} className="space-y-6">
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Building2 className="w-4 h-4 text-rose-400" />
              <span>Informations de l'Entreprise</span>
            </h2>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Raison Sociale</label>
                <input
                  type="text"
                  required
                  value={tenant.name}
                  onChange={(e) => setTenant({ ...tenant, name: e.target.value })}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-white text-xs focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Numéro SIRET</label>
                <input
                  type="text"
                  value={tenant.siret || ''}
                  onChange={(e) => setTenant({ ...tenant, siret: e.target.value })}
                  placeholder="452 871 609 00041"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-white text-xs focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Email Contact</label>
                <input
                  type="email"
                  value={tenant.contact_email || ''}
                  onChange={(e) => setTenant({ ...tenant, contact_email: e.target.value })}
                  placeholder="direction@entreprise.fr"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-white text-xs focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={saving}
              className="px-6 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
            >
              {saving ? 'Enregistrement...' : 'Enregistrer les informations'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
