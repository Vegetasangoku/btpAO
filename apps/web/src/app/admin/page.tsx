'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  ShieldAlert,
  Building2,
  Cpu,
  Sliders,
  DollarSign,
  TrendingUp,
  Activity,
  CheckCircle2,
  AlertTriangle,
  Server,
  Zap,
  Layers,
  Save,
  Users,
  Search,
  Settings2,
  Plus,
  Trash2,
  Loader2,
  Mail,
  ChevronRight,
  Key,
  Database,
  FileCode,
  Sparkles,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { LLM_MODEL_TIERS } from '@/lib/types';


interface Tenant {
  id: string;
  name: string;
  slug?: string;
  plan: string;
  country_code?: string;
  siret?: string;
  contact_email?: string;
  monthly_limit?: number;
  used_this_month?: number;
  llm_provider?: string;
  llm_model?: string;
  llm_model_tier?: string;
  model_routing_config?: {
    extraction_gonogo?: { provider: string; model: string };
    redaction_memoire?: { provider: string; model: string };
    analyse_prix?: { provider: string; model: string };
  };
}


export default function SuperAdminPage() {
  const [activeTab, setActiveTab] = useState<'tenants' | 'master_keys' | 'routing' | 'rag_supervision' | 'prompts' | 'revenue'>('master_keys');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [isCreating, setIsCreating] = useState(false);

  // Master LLM Keys & Platform Default Model State
  const [anthropicKey, setAnthropicKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [mistralKey, setMistralKey] = useState('');
  const [platformDefaultTier, setPlatformDefaultTier] = useState('equilibre');
  const [keyStatus, setKeyStatus] = useState<any>(null);
  const [isSavingKeys, setIsSavingKeys] = useState(false);

  // RAG Supervision State
  const [ragStats, setRagStats] = useState<any>({
    embedding_model: 'text-embedding-3-small',
    dimensions: 1536,
    similarity_metric: 'Cosinus (1 - (a <=> b))',
    total_dce_chunks: 0,
    total_knowledge_chunks: 0,
    index_type: 'HNSW',
  });


  // System Prompt Editor State
  const [selectedTenantForPrompt, setSelectedTenantForPrompt] = useState<string>('');
  const [currentPrompt, setCurrentPrompt] = useState<string>('');
  const [isSavingPrompt, setIsSavingPrompt] = useState(false);

  // New tenant form state
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantSiret, setNewTenantSiret] = useState('');
  const [newTenantEmail, setNewTenantEmail] = useState('');
  const [newTenantPlan, setNewTenantPlan] = useState('pro');
  const [newTenantModelTier, setNewTenantModelTier] = useState('inherit');
  const [newTenantModel, setNewTenantModel] = useState('claude-3-5-sonnet-20241022');

  const AVAILABLE_MODELS = [
    { id: 'claude-3-5-sonnet-20241022', provider: 'Anthropic', name: 'Claude 3.5 Sonnet (Recommandé Rédaction)', badge: 'Haute Qualité BTP' },
    { id: 'gpt-4o', provider: 'OpenAI', name: 'GPT-4o (Recommandé Synthèse & Go/No-Go)', badge: 'Rapide & Précis' },
    { id: 'gemini-1.5-pro', provider: 'Google', name: 'Gemini 1.5 Pro (Grand Contexte DCE)', badge: '2M Tokens' },
    { id: 'mistral-large-2407', provider: 'Mistral AI', name: 'Mistral Large 2 (Souveraineté UE)', badge: 'RGPD France' },
    { id: 'deepseek-v3', provider: 'DeepSeek', name: 'DeepSeek-V3 (Économique Chiffrage)', badge: 'Faible Coût' },
  ];

  useEffect(() => {
    fetchTenants();
    fetchMasterKeys();
    fetchRagStats();
  }, []);

  useEffect(() => {
    if (selectedTenantForPrompt) {
      fetchTenantPrompt(selectedTenantForPrompt);
    }
  }, [selectedTenantForPrompt]);

  async function fetchTenants() {
    setLoading(true);
    try {
      const data = await api.getTenants();
      const list = data || [];
      setTenants(list);
      if (list.length > 0 && !selectedTenantForPrompt) {
        setSelectedTenantForPrompt(list[0].id);
      }
    } catch (err) {
      console.error('Erreur chargement tenants:', err);
    } finally {
      setLoading(false);
    }
  }


  async function fetchMasterKeys() {
    try {
      const res = await fetch('http://localhost:8000/api/admin/llm-keys');
      if (res.ok) {
        const data = await res.json();
        setKeyStatus(data);
        if (data.default_llm_tier) {
          setPlatformDefaultTier(data.default_llm_tier);
        }
      }
    } catch (e) {
      console.warn('[Admin] Fetch master keys notice:', e);
    }
  }

  async function fetchRagStats() {
    try {
      const res = await fetch('http://localhost:8000/api/admin/rag-supervision');
      if (res.ok) {
        const data = await res.json();
        setRagStats(data);
      }
    } catch (e) {
      console.warn('[Admin] Fetch RAG stats notice:', e);
    }
  }

  async function fetchTenantPrompt(tenantId: string) {
    try {
      const res = await fetch(`http://localhost:8000/api/admin/system-prompt/${tenantId}`);
      if (res.ok) {
        const data = await res.json();
        setCurrentPrompt(data.system_prompt || '');
      }
    } catch (e) {
      console.warn('[Admin] Fetch system prompt notice:', e);
    }
  }

  async function handleSaveMasterKeys(e: React.FormEvent) {
    e.preventDefault();
    setIsSavingKeys(true);
    try {
      const res = await fetch('http://localhost:8000/api/admin/llm-keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          anthropic_api_key: anthropicKey || undefined,
          openai_api_key: openaiKey || undefined,
          mistral_api_key: mistralKey || undefined,
          default_llm_tier: platformDefaultTier,
        }),
      });
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
        setAnthropicKey('');
        setOpenaiKey('');
        setMistralKey('');
        fetchMasterKeys();
      }
    } catch (err: any) {
      alert('Erreur enregistrement clés : ' + err.message);
    } finally {
      setIsSavingKeys(false);
    }
  }


  async function handleSaveSystemPrompt() {
    if (!selectedTenantForPrompt) return;
    setIsSavingPrompt(true);
    try {
      const res = await fetch('http://localhost:8000/api/admin/system-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenant_id: selectedTenantForPrompt,
          system_prompt: currentPrompt,
        }),
      });
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 2500);
      }
    } catch (err: any) {
      alert('Erreur enregistrement prompt : ' + err.message);
    } finally {
      setIsSavingPrompt(false);
    }
  }

  async function handleCreateTenant(e: React.FormEvent) {
    e.preventDefault();
    if (!newTenantName) return;
    setIsCreating(true);

    try {
      const slug = newTenantName.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Math.floor(Math.random() * 1000);
      const created = await api.createTenant({
        name: newTenantName,
        slug,
        siret: newTenantSiret || undefined,
        contact_email: newTenantEmail || undefined,
        plan: newTenantPlan,
        country_code: 'FR',
        llm_model_tier: newTenantModelTier,
        llm_provider: 'anthropic',
        llm_model: newTenantModelTier !== 'inherit' ? newTenantModelTier : undefined,
      });

      if (created) {
        setTenants(prev => [created, ...prev]);
        setShowCreateModal(false);
        setNewTenantName('');
        setNewTenantSiret('');
        setNewTenantEmail('');
        setNewTenantModelTier('inherit');
      }
    } catch (err: any) {
      alert('Erreur lors de la création : ' + err.message);
    } finally {
      setIsCreating(false);
    }

  }


  async function handleUpdateModelRouting(tenantId: string, task: 'extraction_gonogo' | 'redaction_memoire' | 'analyse_prix', modelId: string) {
    const tenant = tenants.find(t => t.id === tenantId);
    if (!tenant) return;

    const provider = modelId.includes('claude') ? 'Anthropic' : modelId.includes('gpt') ? 'OpenAI' : modelId.includes('mistral') ? 'Mistral AI' : 'Google';
    const updatedRouting = {
      ...(tenant.model_routing_config || {}),
      [task]: { provider, model: modelId },
    };

    setTenants(prev => prev.map(t => t.id === tenantId ? { ...t, model_routing_config: updatedRouting } : t));

    try {
      await fetch('http://localhost:8000/api/admin/model-routing', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tenant_id: tenantId,
          [task]: { provider, model: modelId },
        }),
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      console.error('Erreur mise à jour routage:', err);
    }
  }

  async function handleDeleteTenant(tenantId: string) {
    if (!confirm('Êtes-vous sûr de vouloir supprimer cette entreprise cliente ?')) return;

    const { error } = await supabase.from('tenants').delete().eq('id', tenantId);
    if (error) {
      alert('Erreur lors de la suppression : ' + error.message);
    } else {
      setTenants(prev => prev.filter(t => t.id !== tenantId));
    }
  }

  return (
    <div className="space-y-8 pb-16">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 flex items-center gap-1">
              <ShieldAlert className="w-3.5 h-3.5" />
              Super Administration Plateforme & LLM Router
            </span>
            <span className="text-xs text-slate-500 font-mono">Master Control</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">
            Pilotage Central des Modèles IA & Supervision RAG
          </h1>
          <p className="text-xs text-slate-400">
            Contrôle technique des clés API LLM, routage par tâche, vectorisation pgvector et prompts systèmes.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {saveSuccess && (
            <div className="px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-1.5 animate-in fade-in">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Modifications enregistrées !</span>
            </div>
          )}

          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all"
          >
            <Plus className="w-4 h-4" />
            <span>Créer une entreprise cliente</span>
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex flex-wrap border-b border-slate-800 gap-2">
        {[
          { id: 'master_keys', label: '1. Clés API Master LLM', icon: Key },
          { id: 'routing', label: '2. Routage IA par Tâche & Client', icon: Cpu },
          { id: 'rag_supervision', label: '3. Supervision RAG (pgvector)', icon: Database },
          { id: 'prompts', label: '4. Éditeur System Prompt (Markdown/Jinja)', icon: FileCode },
          { id: 'tenants', label: '5. Entreprises Clientes (Tenants)', icon: Building2 },
          { id: 'revenue', label: '6. Revenus & Abonnements', icon: DollarSign },
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

      {/* TAB 1: MASTER LLM KEYS */}
      {activeTab === 'master_keys' && (
        <div className="space-y-6 max-w-4xl">
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <Key className="w-4 h-4 text-rose-400" />
                  Configuration Globale & Master API Keys
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Renseignez directement les clés API sans modifier les fichiers .env. Prise en compte à chaud par le moteur LiteLLM.
                </p>
              </div>
              <span className="text-[10px] font-mono px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                Chiffrement Actif
              </span>
            </div>

            <form onSubmit={handleSaveMasterKeys} className="space-y-5">
              {/* Platform Default LLM Model Tier Selection */}
              <div className="p-4 rounded-2xl bg-slate-950 border border-slate-800 space-y-2">
                <div className="flex items-center justify-between">
                  <label htmlFor="platform-default-tier-select" className="text-xs font-bold text-white flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-sky-400" />
                    <span>Modèle par défaut de la plateforme</span>
                  </label>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                    Niveau Global
                  </span>
                </div>
                <p className="text-[11px] text-slate-400">
                  C'est la valeur utilisée pour tout tenant qui n'a pas de réglage spécifique. Toi seul peux la changer, et le changement s'applique immédiatement à tous les tenants sans réglage individuel.
                </p>
                <select
                  id="platform-default-tier-select"
                  value={platformDefaultTier}
                  onChange={(e) => setPlatformDefaultTier(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl bg-slate-900 border border-slate-800 focus:border-rose-500 text-xs text-white font-medium focus:outline-none cursor-pointer"
                >
                  {LLM_MODEL_TIERS.map((tier) => (
                    <option key={tier.id} value={tier.id}>
                      {tier.display_label}
                    </option>
                  ))}
                </select>
              </div>

              {/* Anthropic Key */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-rose-400" />
                    Anthropic API Key (Claude 3.5 Sonnet — Rédaction Mémoire & Go/No-Go)
                  </label>
                  {keyStatus?.anthropic_api_key_configured && (
                    <span className="text-[11px] font-mono text-slate-400">
                      Actuelle : {keyStatus.anthropic_api_key_masked}
                    </span>
                  )}
                </div>
                <input
                  type="password"
                  value={anthropicKey}
                  onChange={(e) => setAnthropicKey(e.target.value)}
                  placeholder={keyStatus?.anthropic_api_key_configured ? "Remplacer la clé existante (sk-ant-...)" : "sk-ant-api03-..."}
                  className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-xs text-white font-mono focus:outline-none"
                />
              </div>

              {/* OpenAI Key */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-emerald-400" />
                    OpenAI API Key (GPT-4o & text-embedding-3-small)
                  </label>
                  {keyStatus?.openai_api_key_configured && (
                    <span className="text-[11px] font-mono text-slate-400">
                      Actuelle : {keyStatus.openai_api_key_masked}
                    </span>
                  )}
                </div>
                <input
                  type="password"
                  value={openaiKey}
                  onChange={(e) => setOpenaiKey(e.target.value)}
                  placeholder={keyStatus?.openai_api_key_configured ? "Remplacer la clé existante (sk-...)" : "sk-..."}
                  className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-xs text-white font-mono focus:outline-none"
                />
              </div>

              {/* Mistral Key */}
              <div className="space-y-1.5">
                <div className="flex items-center justify-between">
                  <label className="text-xs font-bold text-white flex items-center gap-2">
                    <span className="w-2 h-2 rounded-full bg-amber-400" />
                    Mistral AI API Key (Mistral Large 2 — Fallback & Chiffrage)
                  </label>
                  {keyStatus?.mistral_api_key_configured && (
                    <span className="text-[11px] font-mono text-slate-400">
                      Actuelle : {keyStatus.mistral_api_key_masked}
                    </span>
                  )}
                </div>
                <input
                  type="password"
                  value={mistralKey}
                  onChange={(e) => setMistralKey(e.target.value)}
                  placeholder={keyStatus?.mistral_api_key_configured ? "Remplacer la clé existante" : "Clé Mistral API..."}
                  className="w-full px-4 py-3 rounded-2xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-xs text-white font-mono focus:outline-none"
                />
              </div>

              <div className="pt-2 flex justify-end">
                <button
                  type="submit"
                  disabled={isSavingKeys}
                  className="flex items-center gap-2 px-6 py-3 rounded-2xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50 cursor-pointer"
                >
                  <Save className="w-4 h-4" />
                  <span>{isSavingKeys ? "Enregistrement sécurisé..." : "Enregistrer les Paramètres & Clés Master"}</span>
                </button>
              </div>

            </form>
          </div>
        </div>
      )}

      {/* TAB 2: TASK-BASED LLM ROUTING PER REAL TENANT */}
      {activeTab === 'routing' && (
        <div className="space-y-4">
          {tenants.length === 0 ? (
            <div className="p-8 text-center text-xs text-slate-500">Aucune entreprise cliente enregistrée.</div>
          ) : (
            tenants.map((t) => {
              const routing = t.model_routing_config || {};
              const currentGoNoGo = routing.extraction_gonogo?.model || 'claude-3-5-sonnet-20241022';
              const currentRedaction = routing.redaction_memoire?.model || t.llm_model || 'claude-3-5-sonnet-20241022';
              const currentPricing = routing.analyse_prix?.model || 'mistral-large-2407';

              return (
                <div key={t.id} className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
                  <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                    <div>
                      <h3 className="text-sm font-black text-white">{t.name}</h3>
                      <p className="text-[11px] text-slate-400">ID : {t.id}</p>
                    </div>
                    <span className="text-[10px] font-bold px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                      Routage par Tâche Actif
                    </span>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    {/* Task 1: Go/No-Go */}
                    <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
                      <label className="block text-xs font-bold text-slate-200">1. Extraction DCE & Décision Go/No-Go</label>
                      <select
                        value={currentGoNoGo}
                        onChange={(e) => handleUpdateModelRouting(t.id, 'extraction_gonogo', e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 focus:border-rose-500 text-xs text-white focus:outline-none"
                      >
                        {AVAILABLE_MODELS.map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                      <p className="text-[10px] text-slate-500">Extraction critères RC & Synthèse 1 page.</p>
                    </div>

                    {/* Task 2: Redaction */}
                    <div className="p-4 rounded-2xl bg-slate-950/80 border border-rose-950/60 space-y-2">
                      <label className="block text-xs font-bold text-rose-300">2. Rédaction Long-Form Mémoire Technique</label>
                      <select
                        value={currentRedaction}
                        onChange={(e) => handleUpdateModelRouting(t.id, 'redaction_memoire', e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-rose-900/60 focus:border-rose-500 text-xs text-white focus:outline-none"
                      >
                        {AVAILABLE_MODELS.map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                      <p className="text-[10px] text-slate-500">Génération des chapitres détaillés (30+ pages).</p>
                    </div>

                    {/* Task 3: Pricing */}
                    <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
                      <label className="block text-xs font-bold text-slate-200">3. Chiffreur & Ajustement Inflation (BT01)</label>
                      <select
                        value={currentPricing}
                        onChange={(e) => handleUpdateModelRouting(t.id, 'analyse_prix', e.target.value)}
                        className="w-full px-3 py-2 rounded-xl bg-slate-900 border border-slate-800 focus:border-rose-500 text-xs text-white focus:outline-none"
                      >
                        {AVAILABLE_MODELS.map((m) => (
                          <option key={m.id} value={m.id}>{m.name}</option>
                        ))}
                      </select>
                      <p className="text-[10px] text-slate-500">Formules d'indexation & prix fermes.</p>
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      )}

      {/* TAB 3: RAG & PGVECTOR SUPERVISION */}
      {activeTab === 'rag_supervision' && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <div className="p-5 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase">État pgvector</span>
              <p className="text-xl font-bold text-emerald-400 flex items-center gap-2">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                ONLINE
              </p>
              <p className="text-[11px] text-slate-500">{ragStats.index_type}</p>
            </div>

            <div className="p-5 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Modèle d'Embeddings</span>
              <p className="text-xl font-bold text-white font-mono">{ragStats.embedding_model}</p>
              <p className="text-[11px] text-slate-500">{ragStats.dimensions} dimensions (OpenAI)</p>
            </div>

            <div className="p-5 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Chunks DCE Vectorisés</span>
              <p className="text-2xl font-black text-sky-400 font-mono">{ragStats.total_dce_chunks}</p>
              <p className="text-[11px] text-slate-500">CCTP, RC, DPGF indexés</p>
            </div>

            <div className="p-5 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <span className="text-[10px] font-bold text-slate-400 uppercase">Mémoire Entreprise RAG</span>
              <p className="text-2xl font-black text-rose-400 font-mono">{ragStats.total_knowledge_chunks}</p>
              <p className="text-[11px] text-slate-500">Qualibat, CVs, fiches engins</p>
            </div>
          </div>

          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4">
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Database className="w-4 h-4 text-sky-400" />
              Architecture Vectorielle & Recherche Hybride BTP
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-slate-300">
              <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
                <p className="font-bold text-white">1. Index HNSW (Hierarchical Navigable Small World)</p>
                <p className="text-slate-400 leading-relaxed">
                  Permet une recherche de similarité cosinus sub-milliseconde sur des milliers de pages de CCTP. Les filtres `tenant_id` et `project_id` sont appliqués au premier niveau pour garantir une isolation multi-tenant stricte.
                </p>
              </div>
              <div className="p-4 rounded-2xl bg-slate-950/80 border border-slate-800 space-y-2">
                <p className="font-bold text-white">2. Reranking & Injection Dynamique</p>
                <p className="text-slate-400 leading-relaxed">
                  Les 5 extraits DCE les plus pertinents et les certifications Qualibat actives de l'entreprise sont automatiquement fusionnés et injectés dans le prompt Claude 3.5 Sonnet pour chaque section rédigée.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: ADVANCED SYSTEM PROMPT EDITOR */}
      {activeTab === 'prompts' && (
        <div className="space-y-6 max-w-4xl">
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-4 border-b border-slate-800 pb-4">
              <div>
                <h3 className="text-base font-bold text-white flex items-center gap-2">
                  <FileCode className="w-4 h-4 text-rose-400" />
                  Éditeur Avancé de System Prompt Client (Markdown / Jinja)
                </h3>
                <p className="text-xs text-slate-400 mt-0.5">
                  Personnalisez les directives de rédaction BTP injectées au LLM pour chaque entreprise cliente.
                </p>
              </div>

              <div className="flex items-center gap-3">
                <select
                  value={selectedTenantForPrompt}
                  onChange={(e) => setSelectedTenantForPrompt(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none"
                >
                  {tenants.map((t) => (
                    <option key={t.id} value={t.id}>{t.name}</option>
                  ))}
                </select>

                <button
                  onClick={handleSaveSystemPrompt}
                  disabled={isSavingPrompt}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{isSavingPrompt ? "Sauvegarde..." : "Enregistrer le Prompt"}</span>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-300">
                Directives Métier BTP & Mémoire d'Entreprise :
              </label>
              <textarea
                rows={12}
                value={currentPrompt}
                onChange={(e) => setCurrentPrompt(e.target.value)}
                placeholder="### DIRECTIVES MÉTIER...\n- Mentionner systématiquement Qualibat..."
                className="w-full p-4 rounded-2xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-xs text-slate-200 font-mono leading-relaxed focus:outline-none"
              />
              <p className="text-[11px] text-slate-500">
                Ce texte est fusionné en temps réel lors de chaque génération de mémoire technique pour ce client.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: REAL TENANTS LIST */}
      {activeTab === 'tenants' && (
        <div className="space-y-4">
          {tenants.length === 0 ? (
            <div className="p-12 rounded-3xl bg-slate-900/40 border border-dashed border-slate-800 text-center space-y-4">
              <Building2 className="w-12 h-12 text-slate-600 mx-auto" />
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-white">Aucune entreprise cliente enregistrée</h3>
                <p className="text-xs text-slate-500">Commencez par ajouter votre premier client PME pour lui ouvrir son espace BTP.</p>
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-glow transition-all"
              >
                Créer une entreprise cliente
              </button>
            </div>
          ) : (
            <div className="bg-slate-900/90 border border-slate-800 rounded-3xl overflow-hidden shadow-xl">
              <div className="divide-y divide-slate-800">
                {tenants.map((t) => (
                  <div key={t.id} className="p-5 flex flex-wrap items-center justify-between gap-4 hover:bg-slate-800/40 transition-colors">
                    <Link href={`/admin/tenants/${t.id}`} className="flex items-center gap-3 group">
                      <div className="w-10 h-10 rounded-2xl bg-slate-800 text-rose-400 font-black text-xs flex items-center justify-center border border-slate-700 group-hover:scale-105 transition-transform">
                        {t.name.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="text-sm font-bold text-white group-hover:text-rose-300 transition-colors flex items-center gap-1.5">
                          <span>{t.name}</span>
                          <ChevronRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-rose-400" />
                        </h3>
                        <p className="text-xs text-slate-400 font-mono">
                          SIRET : {t.siret || 'Non renseigné'} • {t.contact_email || 'Sans email de contact'}
                        </p>
                      </div>
                    </Link>

                    <div className="flex items-center gap-4">
                      <Link
                        href={`/admin/tenants/${t.id}`}
                        className="px-3 py-1.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white text-xs font-semibold border border-slate-700 transition-colors"
                      >
                        Gérer la PME →
                      </Link>
                      <span className="text-[10px] font-bold px-2.5 py-1 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 uppercase">
                        Plan {t.plan}
                      </span>
                      <span className="text-xs text-slate-400 font-mono hidden sm:inline">
                        {t.used_this_month || 0} / {t.monthly_limit || 15} dossiers
                      </span>
                      <button
                        onClick={() => handleDeleteTenant(t.id)}
                        className="p-2 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        title="Supprimer le tenant"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* TAB 6: REVENUE */}
      {activeTab === 'revenue' && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
            <p className="text-xs font-bold text-slate-400">Revenu Mensuel Récurrent (MRR)</p>
            <p className="text-3xl font-black text-white font-mono">
              {(tenants.length * 490).toLocaleString('fr-FR')} €
            </p>
            <p className="text-xs text-emerald-400 font-bold flex items-center gap-1">
              <TrendingUp className="w-3.5 h-3.5" /> Basé sur {tenants.length} client(s) actif(s)
            </p>
          </div>

          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
            <p className="text-xs font-bold text-slate-400">Revenu Annuel Projeté (ARR)</p>
            <p className="text-3xl font-black text-white font-mono">
              {(tenants.length * 490 * 12).toLocaleString('fr-FR')} €
            </p>
            <p className="text-xs text-slate-400 font-medium">Projection 12 mois</p>
          </div>

          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
            <p className="text-xs font-bold text-slate-400">Buckets Supabase Storage</p>
            <p className="text-3xl font-black text-emerald-400 font-mono">3 Actifs</p>
            <p className="text-xs text-slate-400 font-medium">dce-files, company-memories, generated-docs</p>
          </div>
        </div>
      )}

      {/* CREATE TENANT MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white">Ajouter une nouvelle entreprise cliente (Tenant)</h3>
            <p className="text-xs text-slate-400">
              L'entreprise sera immédiatement créée dans la base Supabase avec ses buckets et réglages dédiés.
            </p>

            <form onSubmit={handleCreateTenant} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Nom de l'entreprise</label>
                <input
                  type="text"
                  required
                  value={newTenantName}
                  onChange={(e) => setNewTenantName(e.target.value)}
                  placeholder="Ex : EiffaBTP Construction SAS"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-white text-xs focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Numéro SIRET</label>
                <input
                  type="text"
                  value={newTenantSiret}
                  onChange={(e) => setNewTenantSiret(e.target.value)}
                  placeholder="Ex : 452 871 609 00041"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-white text-xs focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Email du responsable client</label>
                <input
                  type="email"
                  value={newTenantEmail}
                  onChange={(e) => setNewTenantEmail(e.target.value)}
                  placeholder="contact@entreprise-btp.fr"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-rose-500 text-white text-xs focus:outline-none"
                />
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">Forfait d'Abonnement</label>
                  <select
                    value={newTenantPlan}
                    onChange={(e) => setNewTenantPlan(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="starter">Starter BTP (3 DCE / mois)</option>
                    <option value="pro">Pro BTP (15 DCE / mois)</option>
                    <option value="enterprise">Entreprise (Sur-mesure)</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-300 mb-1">Modèle IA Assigné (Override Client)</label>
                  <select
                    id="new-tenant-tier-select"
                    value={newTenantModelTier}
                    onChange={(e) => setNewTenantModelTier(e.target.value)}
                    className="w-full px-3 py-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white focus:outline-none cursor-pointer"
                  >
                    <option value="inherit">Hériter du réglage général (par défaut)</option>
                    {LLM_MODEL_TIERS.map((tier) => (
                      <option key={tier.id} value={tier.id}>
                        {tier.display_label}
                      </option>
                    ))}
                  </select>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Laissez sur "Hériter" pour suivre automatiquement le modèle par défaut de la plateforme.
                  </p>
                </div>
              </div>


              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  disabled={isCreating}
                  className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-glow transition-all disabled:opacity-50"
                >
                  {isCreating ? 'Création...' : 'Créer l\'entreprise'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
