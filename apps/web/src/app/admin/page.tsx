'use client';

import React, { useState, useEffect, useMemo } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
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
  RefreshCw,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { WebSearchKeysCard } from '@/components/admin/web-search-keys-card';
import { LLM_MODEL_TIERS } from '@/lib/types';
import type { LlmCatalogResponse } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';
import { DismissibleNotice } from '@/components/ui/dismissible-notice';


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


function SuperAdminPageContent() {
  const { t } = useTranslation();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<'tenants' | 'master_keys' | 'routing' | 'rag_supervision' | 'prompts' | 'revenue'>('master_keys');
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);

  // Permet à d'autres pages (ex: /admin/tenants) de lier directement vers le
  // formulaire de création plutôt que de simplement renvoyer sur /admin.
  useEffect(() => {
    if (searchParams?.get('create') === '1') {
      setShowCreateModal(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // 01/09 : permet à la page de détail tenant de lier directement vers un onglet
  // précis (ex: /admin?tab=routing depuis le renvoi ajouté sur l'onglet de routage
  // dupliqué de /admin/tenants/[id]) plutôt que de toujours retomber sur master_keys.
  useEffect(() => {
    const tabParam = searchParams?.get('tab');
    const validTabs = ['tenants', 'master_keys', 'routing', 'rag_supervision', 'prompts', 'revenue'];
    if (tabParam && validTabs.includes(tabParam)) {
      setActiveTab(tabParam as typeof activeTab);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  const [isCreating, setIsCreating] = useState(false);
  const [notice, setNotice] = useState<{ message: string; detail?: string; variant?: 'error' | 'success' } | null>(null);
  const [llmCatalog, setLlmCatalog] = useState<LlmCatalogResponse | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogSyncing, setCatalogSyncing] = useState(false);
  // Par défaut, ne montrer que les modèles dont le tarif est vérifié (socle de référence).
  const [catalogVerifiedOnly, setCatalogVerifiedOnly] = useState(true);

  // Master LLM Keys & Platform Default Model State
  const [platformDefaultTier, setPlatformDefaultTier] = useState('equilibre');
  // Modele de repli plateforme (03/09) -- chaine vide = mode automatique (premier
  // fournisseur actif dote d'une cle, voir model_routing_service.get_fallback_candidate()).
  const [platformFallbackTier, setPlatformFallbackTier] = useState('');
  // Sélection en attente du sélecteur "appliquer aux 3 tâches" du routage par tâche,
  // par tenant -- state local, rien n'est envoyé tant que l'admin ne clique pas sur
  // le bouton d'application (30/08, réponse à "je dois me faire chier trois fois ?").
  const [bulkRoutingSelection, setBulkRoutingSelection] = useState<Record<string, string>>({});
  const [customProviders, setCustomProviders] = useState<any[]>([
    { id: 'anthropic', name: 'Anthropic Claude — rédaction des mémoires techniques', litellm_id: 'anthropic/claude-sonnet-5', api_key: '', api_base: '', zone: 'US', enabled: true },
    { id: 'openai', name: 'OpenAI — lecture des plans et raisonnement sur la DPGF', litellm_id: 'openai/gpt-5.6-terra', api_key: '', api_base: '', zone: 'US', enabled: true },
    { id: 'mistral', name: 'Mistral AI — hébergement européen, marchés publics', litellm_id: 'mistral/mistral-large-3-25-12', api_key: '', api_base: '', zone: 'UE', enabled: true },
    { id: 'gemini', name: 'Google Gemini — palier gratuit pour les essais', litellm_id: 'gemini/gemini-3.8-flash', api_key: '', api_base: '', zone: 'US', enabled: true },
    { id: 'deepseek', name: 'DeepSeek — coût plancher, hors UE', litellm_id: 'deepseek/deepseek-v4-flash', api_key: '', api_base: 'https://api.deepseek.com/v1', zone: 'Chine', enabled: true },
  ]);
  // 30/08 : surcharge de modele par palier (model_tier_overrides) -- le backend supportait deja
  // ce champ (voir admin.py::update_llm_keys) mais aucune UI ne l'exposait encore. availableTiers
  // vient de GET /admin/llm-keys::available_tiers (tiers avec surcharge deja appliquee, pour
  // afficher le modele reellement actif par palier, pas seulement le defaut code en dur).
  const [tierOverrides, setTierOverrides] = useState<Record<string, string>>({});
  const [availableTiers, setAvailableTiers] = useState<Record<string, any>>({});
  const [keyStatus, setKeyStatus] = useState<any>(null);
  // 30/08 : suivi de consommation LLM (tokens + cout estime par fournisseur, ce mois-ci) --
  // reponse a une demande explicite utilisateur, voir GET /admin/llm-usage-summary.
  const [usageSummary, setUsageSummary] = useState<any>(null);
  const [usageLoading, setUsageLoading] = useState(false);
  // 30/08 : remplace le calcul frontend MRR/ARR (grille de prix codee en dur et fausse,
  // multipliee par TOUS les tenants y compris demo/essai) par le vrai calcul serveur --
  // voir GET /admin/revenue-summary.
  const [revenueSummary, setRevenueSummary] = useState<any>(null);
  const [revenueLoading, setRevenueLoading] = useState(false);
  const [isSavingKeys, setIsSavingKeys] = useState(false);
  /* Empreinte de la configuration telle qu'elle est en base, prise à chaque
     chargement et à chaque enregistrement. Elle sert à savoir s'il reste des
     modifications non enregistrées : sans ce repère, on pouvait quitter l'écran
     en croyant avoir tout validé — c'est exactement ce qui faisait perdre une
     clé d'API saisie puis seulement testée. */
  const [savedFingerprint, setSavedFingerprint] = useState<string>('');
  const [testingProviderId, setTestingProviderId] = useState<string | null>(null);
  const [highlightedProviderId, setHighlightedProviderId] = useState<string | null>(null);

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

  // Tab 2 search filter state
  const [routingSearch, setRoutingSearch] = useState<string>('');

  // New tenant form state
  const [newTenantName, setNewTenantName] = useState('');
  const [newTenantSiret, setNewTenantSiret] = useState('');
  const [newTenantEmail, setNewTenantEmail] = useState('');
  const [newTenantPlan, setNewTenantPlan] = useState('pro');
  const [newTenantModelTier, setNewTenantModelTier] = useState('inherit');
  const [newTenantModel, setNewTenantModel] = useState('anthropic/claude-sonnet-5');


  // Repli hors ligne : ce que l'écran affiche tant que le catalogue synchronisé n'a pas
  // répondu. Miroir du socle serveur app/services/llm_reference_catalog.py, relevé le
  // 2026-09-02 sur les pages tarifaires officielles. Tarifs en dollars par million de
  // tokens (entrée / sortie).
  const BUILTIN_MODEL_CHOICES: Record<string, Array<{ id: string; label: string; cost: string }>> = {
    anthropic: [
      { id: 'anthropic/claude-sonnet-5', label: 'Claude Sonnet 5 (rédaction du mémoire technique)', cost: '2.00 $ / 10.00 $ par M tokens' },
      { id: 'anthropic/claude-haiku-4-5-20251001', label: 'Claude Haiku 4.5 (extraction rapide du DCE)', cost: '1.00 $ / 5.00 $ par M tokens' },
      { id: 'anthropic/claude-opus-5', label: 'Claude Opus 5 (analyse juridique)', cost: '5.00 $ / 25.00 $ par M tokens' },
      { id: 'anthropic/claude-fable-5-1', label: 'Claude Fable 5.1 (dossiers à fort enjeu)', cost: '10.00 $ / 50.00 $ par M tokens' },
    ],
    openai: [
      { id: 'openai/gpt-5.6-terra', label: 'GPT-5.6 Terra (usage courant)', cost: '1.00 $ / 6.00 $ par M tokens' },
      { id: 'openai/gpt-5.6-sol', label: 'GPT-5.6 Sol (raisonnement approfondi)', cost: '2.00 $ / 10.00 $ par M tokens' },
      { id: 'openai/gpt-5.6-luna', label: 'GPT-5.6 Luna (traitement de masse)', cost: '0.10 $ / 0.60 $ par M tokens' },
      { id: 'openai/gpt-5.3-codex', label: 'GPT-5.3 Codex (structuration de données)', cost: '1.75 $ / 14.00 $ par M tokens' },
    ],
    mistral: [
      { id: 'mistral/mistral-large-3-25-12', label: 'Mistral Large 3 (souveraineté UE, marchés publics)', cost: '0.50 $ / 1.50 $ par M tokens' },
      { id: 'mistral/mistral-medium-3.5-26.04', label: 'Mistral Medium 3.5', cost: '1.50 $ / 7.50 $ par M tokens' },
      { id: 'mistral/mistral-small-4-0-26-03', label: 'Mistral Small 4 (économique, UE)', cost: '0.15 $ / 0.60 $ par M tokens' },
      { id: 'mistral/leanstral-1.5', label: 'Leanstral 1.5 — gratuit (Labs, UE)', cost: 'gratuit dans les quotas Mistral Labs' },
    ],
    gemini: [
      { id: 'gemini/gemini-3.8-flash', label: 'Gemini 3.8 Flash — palier gratuit (recette)', cost: 'gratuit dans les quotas Google AI Studio, puis 0.75 $ / 3.75 $' },
      { id: 'gemini/gemini-3.5-flash-lite', label: 'Gemini 3.5 Flash-Lite', cost: 'gratuit dans les quotas, puis 0.30 $ / 2.50 $' },
      { id: 'gemini/gemini-2.5-pro', label: 'Gemini 2.5 Pro', cost: 'gratuit dans les quotas, puis 1.25 $ / 10.00 $' },
    ],
    deepseek: [
      { id: 'deepseek/deepseek-v4-flash', label: 'DeepSeek V4 Flash (coût plancher, hors UE)', cost: '0.44 $ / 1.32 $ par M tokens (heures pleines)' },
      { id: 'deepseek/deepseek-v4-pro', label: 'DeepSeek V4 Pro (hors UE)', cost: '1.32 $ / 3.96 $ par M tokens (heures pleines)' },
    ],
  };

  // Modèles par fournisseur dynamiquement synchronisés depuis le catalogue en base (mis à jour chaque nuit ou à la demande)
  const providerModelChoices = useMemo(() => {
    const choices: Record<string, Array<{ id: string; label: string; cost: string; isActive?: boolean }>> = {
      anthropic: [],
      openai: [],
      mistral: [],
      gemini: [],
      deepseek: [],
    };

    // 1. Ingestion des modèles issus du catalogue synchronisé (socle de référence daté,
    //    base LiteLLM embarquée, puis OpenRouter si le réseau répond)
    if (llmCatalog?.models && llmCatalog.models.length > 0) {
      for (const m of llmCatalog.models) {
        const pSlug = (m.provider_slug || '').toLowerCase();
        let targetKey: string | null = null;
        if (pSlug.includes('anthropic')) targetKey = 'anthropic';
        else if (pSlug.includes('openai')) targetKey = 'openai';
        else if (pSlug.includes('mistral')) targetKey = 'mistral';
        else if (pSlug.includes('gemini') || pSlug.includes('google')) targetKey = 'gemini';
        else if (pSlug.includes('deepseek')) targetKey = 'deepseek';

        if (targetKey) {
          const costStr = (m.pricing_prompt_per_million != null && m.pricing_completion_per_million != null)
            ? `${m.pricing_prompt_per_million.toFixed(2)} $ / ${m.pricing_completion_per_million.toFixed(2)} $ par M tokens`
            : 'Tarif officiel fournisseur';

          choices[targetKey].push({
            id: m.external_id,
            label: `${m.display_name || m.external_id}${!m.is_active ? ' [Déprécié]' : ''}`,
            cost: costStr,
            isActive: m.is_active,
          });
        }
      }
    }

    // 2. Fusion avec les modèles phares prédéfinis pour garantir la présence au sommet des meilleurs modèles BTP
    for (const [provId, presets] of Object.entries(BUILTIN_MODEL_CHOICES)) {
      if (choices[provId].length === 0) {
        choices[provId] = presets.map((p) => ({ ...p, isActive: true }));
      } else {
        const existingIds = new Set(choices[provId].map((c) => c.id));
        for (const preset of presets) {
          if (!existingIds.has(preset.id)) {
            choices[provId].unshift({ ...preset, isActive: true });
          }
        }
      }
    }

    return choices;
  }, [llmCatalog]);

  // Rendu unifié de tous les modèles sélectionnables (intégrés + synchronisés du catalogue + personnalisés)
  function renderSelectableModelOptions() {
    const customList = customProviders.filter(
      (p) => !['anthropic', 'openai', 'mistral', 'deepseek'].includes(p.id) && (p.litellm_id || p.name)
    );

    return (
      <>
        <optgroup label="Anthropic Claude (Rédaction Mémoires Techniques & Analyse CCTP)">
          {(providerModelChoices.anthropic || []).map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} ({m.cost})
            </option>
          ))}
        </optgroup>
        <optgroup label="OpenAI — lecture des plans et raisonnement sur la DPGF">
          {(providerModelChoices.openai || []).map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} ({m.cost})
            </option>
          ))}
        </optgroup>
        <optgroup label="Mistral AI (Souveraineté Européenne 🇪🇺 & Marchés Publics)">
          {(providerModelChoices.mistral || []).map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} ({m.cost})
            </option>
          ))}
        </optgroup>
        <optgroup label="DeepSeek (Raisonnement Mathématique & Coût Plancher)">
          {(providerModelChoices.deepseek || []).map((m) => (
            <option key={m.id} value={m.id}>
              {m.label} ({m.cost})
            </option>
          ))}
        </optgroup>
        {customList.length > 0 && (
          <optgroup label="Modèles Personnalisés & Serveurs Privés">
            {customList.map((p) => (
              <option key={p.id} value={p.litellm_id || p.id}>
                {p.name || p.id} ({p.litellm_id || 'custom'}) {p.zone ? `[Zone ${p.zone}]` : ''}
              </option>
            ))}
          </optgroup>
        )}
      </>
    );
  }

  // Calcul en direct des détails du Modèle Master sélectionné pour feedback immédiat
  const activeMasterDetails = useMemo(() => {
    // 1. Profil / Tier prédéfini
    const tierMatch = LLM_MODEL_TIERS.find((t) => t.id === platformDefaultTier);
    if (tierMatch) {
      const rawModel = availableTiers[platformDefaultTier]?.model_string || tierOverrides[platformDefaultTier] || (
        platformDefaultTier === 'equilibre' ? 'anthropic/claude-sonnet-5' :
        platformDefaultTier === 'economique' ? 'anthropic/claude-haiku-4-5-20251001' :
        platformDefaultTier === 'avance' ? 'anthropic/claude-opus-5' :
        platformDefaultTier === 'souverain' ? 'mistral/mistral-large-3-25-12' :
        platformDefaultTier === 'gratuit' ? 'gemini/gemini-3.8-flash' :
        'anthropic/claude-fable-5-1'
      );
      const providerId = rawModel.split('/')[0];
      const provObj = customProviders.find((p) => p.id === providerId || (providerId === 'openai' && p.id === 'openai'));
      const hasKey = !!(
        (provObj?.api_key && provObj.api_key.trim() !== '') ||
        keyStatus?.custom_providers?.find((p: any) => p.id === providerId)?.api_key ||
        (providerId === 'anthropic' && keyStatus?.anthropic_api_key_configured) ||
        (providerId === 'openai' && keyStatus?.openai_api_key_configured) ||
        (providerId === 'mistral' && keyStatus?.mistral_api_key_configured)
      );
      return {
        isTier: true,
        tierName: tierMatch.name,
        modelString: rawModel,
        providerName: provObj?.name || providerId,
        providerId,
        zone: provObj?.zone || (providerId === 'mistral' ? 'UE' : 'US'),
        hasKey,
        pricing: tierMatch.pricing,
      };
    }

    // 2. Modèle direct sélectionné parmi les fournisseurs ou le catalogue
    const provObj = customProviders.find(
      (p) => p.litellm_id === platformDefaultTier || p.id === platformDefaultTier || (providerModelChoices[p.id]?.some((m) => m.id === platformDefaultTier))
    );
    const providerId = provObj?.id || platformDefaultTier.split('/')[0];
    const hasKey = !!(
      (provObj?.api_key && provObj.api_key.trim() !== '') ||
      keyStatus?.custom_providers?.find((p: any) => p.id === providerId)?.api_key ||
      (providerId === 'anthropic' && keyStatus?.anthropic_api_key_configured) ||
      (providerId === 'openai' && keyStatus?.openai_api_key_configured) ||
      (providerId === 'mistral' && keyStatus?.mistral_api_key_configured)
    );

    let cost = null;
    let label = platformDefaultTier;
    if (providerModelChoices[providerId]) {
      const mMatch = providerModelChoices[providerId].find((m) => m.id === platformDefaultTier);
      if (mMatch) {
        cost = mMatch.cost;
        label = mMatch.label;
      }
    }

    return {
      isTier: false,
      tierName: null,
      modelString: platformDefaultTier,
      label,
      providerName: provObj?.name || providerId,
      providerId,
      zone: provObj?.zone || (providerId === 'mistral' ? 'UE' : 'US'),
      hasKey,
      pricing: cost,
    };
  }, [platformDefaultTier, customProviders, keyStatus, availableTiers, tierOverrides]);


  useEffect(() => {
    fetchTenants();
    fetchMasterKeys();
    fetchRagStats();
    fetchLlmCatalog();
    fetchUsageSummary();
    fetchRevenueSummary();
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
    } catch (err: any) {
      console.error('Erreur chargement tenants:', err);
      setNotice({ message: t('admin.super.err_load_tenants'), detail: err?.message || String(err), variant: 'error' });
    } finally {
      setLoading(false);
    }
  }


  async function fetchMasterKeys() {
    try {
      const data = await api.getPlatformLLMKeys();
      if (data) {
        setKeyStatus(data);
        setTierOverrides(data.model_tier_overrides || {});
        setAvailableTiers(data.available_tiers || {});
        if (data.default_llm_tier) {
          setPlatformDefaultTier(data.default_llm_tier);
        }
        setPlatformFallbackTier(data.default_fallback_tier || '');
        if (data.custom_providers && data.custom_providers.length > 0) {
          const standardNames: Record<string, string> = {
            anthropic: 'Anthropic Claude — rédaction des mémoires techniques',
            openai: 'OpenAI — lecture des plans et raisonnement sur la DPGF',
            mistral: 'Mistral AI — hébergement européen, marchés publics',
            gemini: 'Google Gemini — palier gratuit pour les essais',
            deepseek: 'DeepSeek — coût plancher, hors UE',
          };

          // Normalize legacy IDs to standard built-in IDs if present
          const normalized = data.custom_providers.map((p: any) => {
            let pid = p.id;
            if (pid === 'anthropic-claude' || pid === 'anthropic_claude') pid = 'anthropic';
            else if (pid === 'openai-custom' || pid === 'openai_custom') pid = 'openai';
            else if (pid === 'mistral-eu' || pid === 'mistral_eu') pid = 'mistral';
            else if (pid === 'google' || pid === 'google-gemini' || pid === 'google_gemini') pid = 'gemini';
            else if (pid === 'deepseek-custom' || pid === 'deepseek_custom') pid = 'deepseek';

            const name = standardNames[pid] || p.name;
            return { ...p, id: pid, name };
          });

          // Guarantee all 4 primary built-ins (anthropic, openai, mistral, deepseek) are present
          const existingIds = new Set(normalized.map((p: any) => p.id));
          const baseDefaults = [
            { id: 'anthropic', name: standardNames.anthropic, litellm_id: 'anthropic/claude-sonnet-5', api_key: '', api_base: '', zone: 'US', enabled: true },
            { id: 'openai', name: standardNames.openai, litellm_id: 'openai/gpt-5.6-terra', api_key: '', api_base: '', zone: 'US', enabled: true },
            { id: 'mistral', name: standardNames.mistral, litellm_id: 'mistral/mistral-large-3-25-12', api_key: '', api_base: '', zone: 'UE', enabled: true },
            { id: 'gemini', name: standardNames.gemini, litellm_id: 'gemini/gemini-3.8-flash', api_key: '', api_base: '', zone: 'US', enabled: true },
            { id: 'deepseek', name: standardNames.deepseek, litellm_id: 'deepseek/deepseek-v4-flash', api_key: '', api_base: 'https://api.deepseek.com/v1', zone: 'Chine', enabled: true },
          ];

          const merged = [...normalized];
          for (const base of baseDefaults) {
            if (!existingIds.has(base.id)) {
              merged.push(base);
            }
          }
          setCustomProviders(merged);
          setSavedFingerprint(
            fingerprintConfig(
              data.default_llm_tier || 'equilibre',
              data.model_tier_overrides || {},
              merged,
              data.default_fallback_tier || '',
            ),
          );
        }
      }
    } catch (e) {
      console.warn('[Admin] Fetch master keys notice:', e);
    }
  }

  // Catalogue de modèles en lecture seule. Source de vérité : le socle daté du serveur
  // (app/services/llm_reference_catalog.py), complété par LiteLLM et OpenRouter.
  async function fetchLlmCatalog() {
    setCatalogLoading(true);
    try {
      const data = await api.getLlmCatalog();
      setLlmCatalog(data);
    } catch (e) {
      console.warn('[Admin] Fetch LLM catalog notice:', e);
    } finally {
      setCatalogLoading(false);
    }
  }

  async function handleSyncLlmCatalog() {
    setCatalogSyncing(true);
    try {
      const result = await api.syncLlmCatalog();
      setNotice({
        message: t('admin.super.keys.catalog_sync_success', {
          created: String(result.created),
          updated: String(result.updated),
          deactivated: String(result.deactivated),
        }),
        variant: 'success',
      });
      await fetchLlmCatalog();
    } catch (e: any) {
      setNotice({ message: t('admin.super.keys.catalog_sync_error'), detail: e?.message || String(e), variant: 'error' });
    } finally {
      setCatalogSyncing(false);
    }
  }

  async function fetchUsageSummary() {
    setUsageLoading(true);
    try {
      const data = await api.getLlmUsageSummary();
      setUsageSummary(data);
    } catch (e) {
      console.warn('[Admin] Fetch usage summary notice:', e);
    } finally {
      setUsageLoading(false);
    }
  }

  async function fetchRevenueSummary() {
    setRevenueLoading(true);
    try {
      const data = await api.getRevenueSummary();
      setRevenueSummary(data);
    } catch (e) {
      console.warn('[Admin] Fetch revenue summary notice:', e);
    } finally {
      setRevenueLoading(false);
    }
  }

  async function fetchRagStats() {
    try {
      const data = await api.getRagSupervision();
      setRagStats(data);
    } catch (e) {
      console.warn('[Admin] Fetch RAG stats notice:', e);
    }
  }

  async function fetchTenantPrompt(tenantId: string) {
    try {
      const data = await api.getTenantSystemPrompt(tenantId);
      setCurrentPrompt(data.system_prompt || '');
    } catch (e) {
      console.warn('[Admin] Fetch system prompt notice:', e);
    }
  }

  /* Amène à la carte d'un fournisseur et place le curseur dans son champ de clé.
     Sans cela, l'avertissement « clé manquante » demandait de trouver soi-même la
     bonne carte dans une liste de cinq — le clic évident n'existait pas. */
  function focusProviderCard(providerId: string) {
    const card = document.getElementById(`provider-card-${providerId}`);
    if (!card) return;
    card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    setHighlightedProviderId(providerId);
    window.setTimeout(() => setHighlightedProviderId(null), 2200);
    const input = card.querySelector<HTMLInputElement>('input[data-api-key-input="true"]');
    window.setTimeout(() => input?.focus(), 420);
  }

  function handleAddProvider() {
    const newId = `custom-provider-${Date.now()}`;
    setCustomProviders([
      ...customProviders,
      {
        id: newId,
        name: 'Nouveau Fournisseur',
        litellm_id: 'openai/custom-model',
        api_key: '',
        api_base: '',
        zone: 'autre',
        enabled: true,
      }
    ]);
  }

  function handleUpdateProvider(index: number, field: string, value: any) {
    const updated = [...customProviders];
    updated[index] = { ...updated[index], [field]: value };
    setCustomProviders(updated);
  }

  function handleDeleteProvider(index: number) {
    if (customProviders.length <= 1) {
      setNotice({ message: t('admin.super.err_min_provider'), variant: 'error' });
      return;
    }
    const updated = customProviders.filter((_, i) => i !== index);
    setCustomProviders(updated);
  }

  const currentFingerprint = useMemo(
    () => fingerprintConfig(platformDefaultTier, tierOverrides, customProviders, platformFallbackTier),
    [platformDefaultTier, tierOverrides, customProviders, platformFallbackTier],
  );

  const hasUnsavedChanges = savedFingerprint !== '' && currentFingerprint !== savedFingerprint;

  async function handleTestProvider(index: number) {
    const prov = customProviders[index];
    if (!prov) return;
    setTestingProviderId(prov.id);
    try {
      const res = await api.testLLMProvider({
        provider_id: prov.id,
        name: prov.name,
        litellm_id: prov.litellm_id,
        api_key: prov.api_key || undefined,
        api_base: prov.api_base || undefined,
      });
      const updated = [...customProviders];
      updated[index] = {
        ...updated[index],
        test_status: res.status,
        last_tested_at: res.tested_at,
        last_latency_ms: res.latency_ms,
        confirmed_model: (res as any).confirmed_model || prov.litellm_id,
        last_error_message: res.error_message || null,
        // Le serveur conserve désormais une clé qui vient de répondre : on vide
        // le champ local pour que l'écran affiche « clé enregistrée » et non une
        // saisie en attente.
        api_key: (res as any).key_persisted ? '' : updated[index].api_key,
      };
      setCustomProviders(updated);
      if ((res as any).key_persisted) {
        fetchMasterKeys();
      }
    } catch (err: any) {
      const updated = [...customProviders];
      updated[index] = {
        ...updated[index],
        test_status: 'error',
        last_tested_at: new Date().toISOString(),
        last_error_message: err.message,
      };
      setCustomProviders(updated);
    } finally {
      setTestingProviderId(null);
    }
  }


  async function handleSaveMasterKeys(e: React.FormEvent) {
    e.preventDefault();
    setIsSavingKeys(true);
    try {
      await api.updatePlatformLLMKeys({
        default_llm_tier: platformDefaultTier,
        default_fallback_tier: platformFallbackTier,
        // 03/09 : ce bouton ne gere plus les cles -- seul "Tester et enregistrer
        // la cle" sur chaque fournisseur peut en ecrire une (voir admin.py). On ne
        // renvoie meme plus le champ api_key ici, pour que ce soit vrai aussi cote
        // ecran : ce formulaire ne peut plus, par construction, ecraser une cle.
        custom_providers: customProviders.map(({ api_key, ...rest }) => rest),
        model_tier_overrides: tierOverrides,
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
      setSavedFingerprint(currentFingerprint);
      fetchMasterKeys();
    } catch (err: any) {
      setNotice({ message: t('admin.super.err_save_keys'), detail: err.message, variant: 'error' });
    } finally {
      setIsSavingKeys(false);
    }
  }



  async function handleSaveSystemPrompt() {
    if (!selectedTenantForPrompt) return;
    setIsSavingPrompt(true);
    try {
      await api.updateTenantSystemPrompt(selectedTenantForPrompt, currentPrompt);
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err: any) {
      setNotice({ message: t('admin.super.err_save_prompt'), detail: err.message, variant: 'error' });
    } finally {
      setIsSavingPrompt(false);
    }
  }

  const isDuplicateName = !!newTenantName.trim() && tenants.some(
    (t) => t.name.trim().toLowerCase() === newTenantName.trim().toLowerCase()
  );
  const isDuplicateSiret = !!newTenantSiret.trim() && tenants.some(
    (t) => t.siret && t.siret.trim() === newTenantSiret.trim()
  );

  async function handleCreateTenant(e: React.FormEvent) {
    e.preventDefault();
    if (!newTenantName.trim()) return;

    if (isDuplicateName) {
      setNotice({ message: t('admin.super.err_duplicate_name'), variant: 'error' });
      return;
    }

    if (isDuplicateSiret) {
      setNotice({ message: t('admin.super.err_duplicate_siret'), variant: 'error' });
      return;
    }

    setIsCreating(true);

    try {
      const slug = newTenantName.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Math.floor(Math.random() * 1000);
      const created = await api.createTenant({
        name: newTenantName.trim(),
        slug,
        siret: newTenantSiret.trim() || undefined,
        contact_email: newTenantEmail.trim() || undefined,
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
        setNotice({ message: "Entreprise cliente créée avec succès.", variant: 'success' });
        setTimeout(() => setNotice(null), 3000);
      }
    } catch (err: any) {
      setNotice({ message: err.message || t('admin.super.err_create_tenant'), variant: 'error' });
    } finally {
      setIsCreating(false);
    }
  }


  async function handleUpdateModelRouting(tenantId: string, task: 'extraction_gonogo' | 'redaction_memoire' | 'analyse_prix', modelId: string) {
    const tenant = tenants.find(t => t.id === tenantId);
    if (!tenant) return;

    const provider = customProviders.find((p) => p.litellm_id === modelId)?.name
      || (modelId.includes('claude') ? 'Anthropic' : modelId.includes('gpt') ? 'OpenAI' : modelId.includes('mistral') ? 'Mistral AI' : 'Fournisseur');
    const updatedRouting = {
      ...(tenant.model_routing_config || {}),
      [task]: { provider, model: modelId },
    };

    setTenants(prev => prev.map(t => t.id === tenantId ? { ...t, model_routing_config: updatedRouting } : t));

    try {
      await api.updateTenantModelRouting({
        tenant_id: tenantId,
        [task]: { provider, model: modelId },
      });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      console.error('Erreur mise à jour routage:', err);
    }
  }

  // Applique le même modèle aux 3 tâches en un seul appel réseau (30/08, réponse directe à
  // "pourquoi je peux pas mettre un LLM pour les trois... je dois me faire chier trois
  // fois ?"). Réutilise le même endpoint POST /admin/model-routing que les 3 sélecteurs
  // individuels -- juste les 3 clés envoyées d'un coup au lieu d'un appel par tâche.
  async function handleBulkApplyModelRouting(tenantId: string, modelId: string) {
    const tenant = tenants.find(t => t.id === tenantId);
    if (!tenant || !modelId) return;

    const provider = customProviders.find((p) => p.litellm_id === modelId)?.name || 'Fournisseur';
    const entry = { provider, model: modelId };
    const updatedRouting = { extraction_gonogo: entry, redaction_memoire: entry, analyse_prix: entry };

    setTenants(prev => prev.map(t => t.id === tenantId ? { ...t, model_routing_config: updatedRouting } : t));

    try {
      await api.updateTenantModelRouting({ tenant_id: tenantId, ...updatedRouting });
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 2500);
    } catch (err) {
      console.error('Erreur mise à jour routage (application groupée):', err);
    }
  }

  async function handleDeleteTenant(tenantId: string) {
    if (!confirm(t('admin.super.confirm_delete_tenant'))) return;
    const { error } = await supabase.from('tenants').delete().eq('id', tenantId);
    if (error) {
      setNotice({ message: t('admin.super.err_delete_tenant'), detail: error.message, variant: 'error' });
    } else {
      setTenants(prev => prev.filter(t => t.id !== tenantId));
    }
  }

  const filteredRoutingTenants = tenants.filter((tenant) => {
    if (!routingSearch.trim()) return true;
    const q = routingSearch.toLowerCase();
    return (
      tenant.name.toLowerCase().includes(q) ||
      (tenant.id && tenant.id.toLowerCase().includes(q)) ||
      (tenant.siret && tenant.siret.toLowerCase().includes(q)) ||
      (tenant.contact_email && tenant.contact_email.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6 pb-16">
      {/* ─── En-tête ────────────────────────────────────────────────────────
          Le titre passe avant les chiffres : on sait d'abord où l'on est, ensuite
          où l'on en est. L'ordre inverse obligeait à lire quatre nombres hors
          contexte avant de trouver le nom de l'écran. */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow-mono">{t('admin.super.badge')}</p>
          <h1 className="mt-2 text-[22px] sm:text-[26px] font-bold text-foreground font-heading tracking-tight leading-tight">
            {t('admin.super.heading')}
          </h1>
          <p className="mt-1 text-[12.5px] text-[hsl(var(--muted-foreground))] max-w-2xl leading-relaxed">
            {t('admin.super.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          {saveSuccess && (
            <span className="badge-pill-emerald">
              <CheckCircle2 className="w-3 h-3" strokeWidth={1.5} />
              <span>{t('admin.super.save_success')}</span>
            </span>
          )}
          <button onClick={() => setShowCreateModal(true)} className="btn-primary">
            <Plus className="w-3.5 h-3.5" strokeWidth={1.5} />
            <span>{t('admin.super.btn_create_tenant')}</span>
          </button>
        </div>
      </div>

      {/* ─── Chiffres de tête ───────────────────────────────────────────────
          Une ligne de valeurs séparées par des filets, sans barres de progression :
          les anciennes étaient décoratives (35 % en dur, dénominateur arbitraire de
          20 clients) et faisaient passer une invention pour une mesure. */}
      <div className="grid grid-cols-2 lg:grid-cols-4 border-y border-[hsl(var(--border))]">
        {[
          {
            label: t('admin.super.kpi_providers'),
            value: `${customProviders.filter((p) => p.enabled).length}`,
            unit: `/ ${customProviders.length}`,
            hint: t('admin.super.kpi_providers_hint'),
          },
          {
            label: t('admin.super.kpi_tenants'),
            value: `${tenants.length}`,
            unit: '',
            hint: t('admin.super.kpi_tenants_hint'),
          },
          {
            label: t('admin.super.kpi_spend'),
            // `total_estimated_cost_usd` est le champ réellement renvoyé par
            // GET /admin/llm-usage-summary ; le repli somme le détail par fournisseur.
            value: (() => {
              const rows: any[] = Array.isArray(usageSummary?.by_provider) ? usageSummary.by_provider : [];
              const total =
                usageSummary?.total_estimated_cost_usd ??
                (rows.length ? rows.reduce((acc, r) => acc + (r.estimated_cost_usd || 0), 0) : null);
              return total != null ? `${Number(total).toFixed(2)} $` : '—';
            })(),
            unit: '',
            hint: t('admin.super.kpi_spend_hint'),
          },
          {
            label: t('admin.super.kpi_index'),
            value: new Intl.NumberFormat('fr-FR').format(
              (ragStats.total_knowledge_chunks || 0) + (ragStats.total_dce_chunks || 0),
            ),
            unit: '',
            hint: t('admin.super.kpi_index_hint'),
          },
        ].map((stat, i) => (
          <div
            key={stat.label}
            className={`py-4 px-4 ${i > 0 ? 'lg:border-s border-[hsl(var(--border))]' : ''} ${i === 0 ? 'lg:ps-0' : ''} ${i % 2 === 1 ? 'border-s border-[hsl(var(--border))] lg:border-s' : ''}`}
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
              {stat.label}
            </p>
            <p className="mt-1.5 font-mono text-[24px] leading-none tabular-nums text-foreground">
              {stat.value}
              {stat.unit && (
                <span className="ms-1.5 text-[13px] text-[hsl(var(--muted-foreground))]">{stat.unit}</span>
              )}
            </p>
            <p className="mt-1.5 text-[11.5px] text-[hsl(var(--muted-foreground))]">{stat.hint}</p>
          </div>
        ))}
      </div>

      {notice && (
        <DismissibleNotice
          message={notice.message}
          detail={notice.detail}
          variant={notice.variant}
          onDismiss={() => setNotice(null)}
        />
      )}

      {/* ─── Onglets ────────────────────────────────────────────────────────
          Soulignés plutôt qu'en pastilles : moins de bruit, et la position active
          se lit sans dépendre d'un aplat de couleur. */}
      <div className="border-b border-[hsl(var(--border))] overflow-x-auto">
        <div className="flex items-end gap-6 min-w-max" role="tablist">
          {[
            { id: 'master_keys', label: t('admin.super.tab1') },
            { id: 'routing', label: t('admin.super.tab2') },
            { id: 'rag_supervision', label: t('admin.super.tab3') },
            { id: 'prompts', label: t('admin.super.tab4') },
            { id: 'tenants', label: t('admin.super.tab5') },
            { id: 'revenue', label: t('admin.super.tab6') },
          ].map((tab) => {
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => setActiveTab(tab.id as any)}
                className={`relative pb-2.5 text-[13px] whitespace-nowrap transition-colors duration-150 cursor-pointer ${
                  isActive
                    ? 'text-foreground font-semibold'
                    : 'text-[hsl(var(--muted-foreground))] hover:text-foreground font-medium'
                }`}
              >
                {tab.label}
                {isActive && (
                  <span className="absolute inset-x-0 -bottom-px h-[2px] bg-hl" />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* TAB 1: MASTER LLM KEYS & CUSTOM PROVIDERS */}
      {activeTab === 'master_keys' && (
        <div className="space-y-6">
          {/* Repères : à quoi sert chaque famille de modèle, sans jargon d'implémentation.
              Les noms de modèles viennent du socle de référence daté côté serveur
              (llm_reference_catalog.py) — plus de génération périmée codée en dur ici. */}
          <div className="card-drafted p-5 space-y-4">
            <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-[hsl(var(--border))] pb-3">
              <h3 className="section-title">{t('admin.super.roles.title')}</h3>
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
                {t('admin.super.roles.as_of')}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-4">
              {[
                { k: 'drafting', models: 'Claude Sonnet 5 · Mistral Large 3' },
                { k: 'plans', models: 'GPT-5.6 Terra · Claude Sonnet 5' },
                { k: 'pricing', models: 'GPT-5.6 Sol · Claude Opus 5' },
                { k: 'retrieval', models: 'text-embedding-3-small' },
              ].map((role, i) => (
                <div
                  key={role.k}
                  className={`px-4 py-3 ${i > 0 ? 'md:border-s border-[hsl(var(--border))]' : ''} ${i === 0 ? 'md:ps-0' : ''}`}
                >
                  <h4 className="text-[13px] font-semibold text-foreground">{t(`admin.super.roles.${role.k}_title`)}</h4>
                  <p className="mt-1.5 font-mono text-[10.5px] text-hl">{role.models}</p>
                  <p className="mt-1.5 text-[11.5px] leading-relaxed text-[hsl(var(--muted-foreground))]">
                    {t(`admin.super.roles.${role.k}_body`)}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-6">
            <div className="flex flex-wrap items-center justify-between border-b border-line pb-4 gap-3">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                  <Key className="w-4 h-4 text-hl" />
                  <span>{t('admin.super.keys.section_title')}</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('admin.super.keys.section_desc')}
                </p>
              </div>
              <div className="flex items-center gap-2">
                <span className="badge-pill-emerald">
                  <ShieldAlert className="w-3.5 h-3.5" />
                  <span>{t('admin.super.keys.encryption_badge')}</span>
                </span>
              </div>
            </div>

            <form onSubmit={handleSaveMasterKeys} className="space-y-6">
              {/* Platform Default LLM Model Tier Selection */}
              <div className="p-5 rounded-2xl bg-card border border-line shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <label htmlFor="platform-default-tier-select" className="text-xs font-bold text-foreground flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-hl" />
                    <span>Modèle par défaut de la plateforme</span>
                  </label>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-hl/10 text-hl">
                    Tous les clients
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Modèle d'IA utilisé pour toute la plateforme (génération du mémoire technique, analyse CCTP et extraction DCE) lorsqu'aucun modèle spécifique n'est assigné à un client ou à une tâche.
                </p>

                {/* Dropdown containing both intelligent BTP tiers AND all direct provider models */}
                <select
                  id="platform-default-tier-select"
                  value={platformDefaultTier}
                  onChange={(e) => setPlatformDefaultTier(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-sunken border border-line text-xs text-foreground font-semibold focus:outline-none focus:ring-1 focus:ring-hl cursor-pointer"
                >
                  <optgroup label="Profils & Niveaux Intelligents Recommandés BTP">
                    {LLM_MODEL_TIERS.map((tier) => (
                      <option key={tier.id} value={tier.id}>
                        {tier.display_label}
                      </option>
                    ))}
                  </optgroup>
                  {renderSelectableModelOptions()}
                </select>

                {/* Live Feedback Card */}
                <div className="p-3.5 rounded-xl bg-sunken border border-line flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-3">
                    <div className="w-8 h-8 rounded-lg bg-hl/10 text-hl flex items-center justify-center font-bold shrink-0">
                      <Sparkles className="w-4 h-4" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-foreground">
                          Modèle utilisé : <span className="font-mono text-hl">{activeMasterDetails.modelString}</span>
                        </span>
                        <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                          activeMasterDetails.zone === 'UE'
                            ? 'bg-positive/10 text-positive border border-positive/20'
                            : 'bg-slate-200/70 dark:bg-line text-muted-foreground'
                        }`}>
                          {activeMasterDetails.zone === 'UE' ? '🇪🇺 Souveraineté UE' : `Zone ${activeMasterDetails.zone}`}
                        </span>
                      </div>
                      <p className="text-[10px] text-muted-foreground mt-0.5">
                        Fournisseur : <strong>{activeMasterDetails.providerName}</strong>
                        {activeMasterDetails.pricing && ` • Coût : ${activeMasterDetails.pricing}`}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {activeMasterDetails.hasKey ? (
                      <span className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-positive/10 text-positive border border-positive/25 flex items-center gap-1.5">
                        <CheckCircle2 className="w-3.5 h-3.5 text-positive" />
                        <span>Clé API configurée</span>
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-corten/10 text-corten border border-corten/25 flex items-center gap-1.5">
                        <AlertTriangle className="w-3.5 h-3.5 text-corten" />
                        <span>Clé API requise pour {activeMasterDetails.providerName}</span>
                      </span>
                    )}
                  </div>
                </div>

                {!activeMasterDetails.hasKey && (
                  <div className="p-3.5 rounded-[5px] border border-corten/45 bg-corten/10 text-[13px] flex items-start gap-2.5">
                    <AlertTriangle className="w-4 h-4 text-corten shrink-0 mt-0.5" strokeWidth={1.5} />
                    <div className="min-w-0 space-y-2">
                      <p className="font-semibold text-foreground">
                        Aucune clé pour {activeMasterDetails.providerName}
                      </p>
                      <p className="text-[12.5px] leading-relaxed text-[hsl(var(--muted-foreground))]">
                        Ce modèle ne répondra pas tant que la clé n’est pas saisie.
                        {PROVIDER_KEY_CONSOLES[activeMasterDetails.providerId] && (
                          <>
                            {' '}Créez-la sur{' '}
                            <a
                              href={PROVIDER_KEY_CONSOLES[activeMasterDetails.providerId].url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-mono text-hl underline underline-offset-2"
                            >
                              {PROVIDER_KEY_CONSOLES[activeMasterDetails.providerId].label}
                            </a>
                            , puis collez-la ici.
                          </>
                        )}
                      </p>
                      {/* Emmener directement à la bonne carte plutôt que de demander de
                          la chercher dans la liste : c'est la seule action utile ici. */}
                      <button
                        type="button"
                        onClick={() => focusProviderCard(activeMasterDetails.providerId)}
                        className="btn-primary !py-1.5 !px-3 !text-[12.5px]"
                      >
                        Saisir la clé maintenant
                      </button>
                    </div>
                  </div>
                )}
              </div>

              {/* Fallback / repli plateforme -- modele de secours si le principal echoue (03/09) */}
              <div className="p-5 rounded-2xl bg-card border border-line shadow-xs space-y-4">
                <div className="flex items-center justify-between">
                  <label htmlFor="platform-fallback-tier-select" className="text-xs font-bold text-foreground flex items-center gap-2">
                    <Cpu className="w-4 h-4 text-hl" />
                    <span>Modèle de repli de la plateforme</span>
                  </label>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-hl/10 text-hl">
                    Tous les clients
                  </span>
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Modèle utilisé pour UN essai de secours quand l'appel au modèle principal échoue (clé invalide, modèle indisponible, quota fournisseur dépassé...), avant de retomber sur le moteur de gabarits. En mode automatique, le premier autre fournisseur activé et doté d'une clé réelle est utilisé sans réglage explicite.
                </p>
                <select
                  id="platform-fallback-tier-select"
                  value={platformFallbackTier}
                  onChange={(e) => setPlatformFallbackTier(e.target.value)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-sunken border border-line text-xs text-foreground font-semibold focus:outline-none focus:ring-1 focus:ring-hl cursor-pointer"
                >
                  <option value="">Automatique (recommandé) — premier fournisseur disponible</option>
                  <optgroup label="Profils & Niveaux Intelligents Recommandés BTP">
                    {LLM_MODEL_TIERS.map((tier) => (
                      <option key={tier.id} value={tier.id}>
                        {tier.display_label}
                      </option>
                    ))}
                  </optgroup>
                </select>
              </div>

              {/* Fournisseurs d'IA Principaux */}
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-bold text-foreground">
                      Fournisseurs et clés d’API
                    </h4>
                    <p className="text-[11px] text-muted-foreground">
                      Configurez vos clés API pour alimenter les moteurs d'extraction, de rédaction et de chiffrage.
                    </p>
                  </div>

                  <button
                    type="button"
                    onClick={handleAddProvider}
                    className="btn-secondary !py-1.5 !px-3 !text-xs cursor-pointer"
                  >
                    <Plus className="w-3.5 h-3.5 text-hl" />
                    <span>{t('admin.super.keys.btn_add_provider')}</span>
                  </button>
                </div>

                {/* Live Catalog Auto-Sync Status Card */}
                <div className="p-4 rounded-xl bg-sunken border border-line flex flex-wrap items-center justify-between gap-3 text-xs">
                  <div className="flex items-center gap-2.5">
                    <div className="w-7 h-7 rounded-lg bg-hl/10 text-hl flex items-center justify-center shrink-0">
                      <RefreshCw className={`w-3.5 h-3.5 text-hl ${catalogSyncing ? 'animate-spin' : ''}`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-foreground">
                          Catalogue mis à jour chaque nuit à 4 h
                        </span>
                        <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-positive/10 text-positive border border-positive/20">
                          {llmCatalog?.models ? `${llmCatalog.models.filter(m => m.is_active).length} modèles actifs répertoriés` : 'Synchro active'}
                        </span>
                      </div>
                      <p className="text-[11px] text-muted-foreground mt-0.5">
                        {llmCatalog?.last_synced_at
                          ? `Dernière mise à jour automatique : ${new Date(llmCatalog.last_synced_at).toLocaleString()} • Tout nouveau modèle de fournisseur est automatiquement disponible avec ses tarifs exacts.`
                          : "Synchronisation automatique active chaque nuit. Les nouveaux modèles d'Anthropic, OpenAI, Mistral et DeepSeek sont automatiquement intégrés avec leurs tarifs officiels."}
                      </p>
                    </div>
                  </div>

                  <button
                    type="button"
                    onClick={handleSyncLlmCatalog}
                    disabled={catalogSyncing}
                    className="btn-secondary !py-1.5 !px-3 !text-xs shrink-0 flex items-center gap-1.5 cursor-pointer"
                  >
                    <RefreshCw className={`w-3 h-3 text-hl ${catalogSyncing ? 'animate-spin' : ''}`} />
                    <span>{catalogSyncing ? 'Mise à jour…' : 'Mettre à jour maintenant'}</span>
                  </button>
                </div>

                {/* Dit une fois, clairement : le pays d'hébergement n'est pas un réglage.
                    L'écran affichait auparavant un sélecteur de pays sur chaque
                    fournisseur, ce qui laissait croire qu'on pouvait choisir où le
                    traitement a lieu. C'est le fournisseur qui le décide. */}
                <p className="text-[12.5px] leading-relaxed text-[hsl(var(--muted-foreground))] border-s-2 border-[hsl(var(--border))] ps-3">
                  Le pays d’hébergement dépend du fournisseur, pas d’un réglage : aucune option de
                  cet écran ne déplace un traitement d’un pays à l’autre. Pour qu’un dossier reste
                  dans l’Union européenne, choisissez un fournisseur qui y héberge — Mistral&nbsp;AI
                  aujourd’hui. La zone affichée sert à décider si l’avertissement RGPD apparaît.
                </p>

                <p className="text-[12.5px] leading-relaxed text-[hsl(var(--muted-foreground))] border-s-2 border-corten/50 ps-3">
                  <strong className="text-foreground">Deux boutons, deux rôles distincts.</strong> « Tester et
                  enregistrer la clé » sur chaque fournisseur ci-dessous teste ET sauvegarde cette clé
                  immédiatement, indépendamment du reste — c’est le seul endroit qui écrit une clé.
                  Le bouton « Enregistrer » en bas de page ne concerne que le modèle par défaut, le
                  modèle de repli et les réglages des fournisseurs (nom, zone, activation) : il ne touche plus
                  jamais aux clés, même si vous le cliquez juste après un test.
                </p>

                <div className="grid grid-cols-1 gap-4">
                  {customProviders.map((prov, index) => {
                    const isBuiltin = BUILTIN_PROVIDER_IDS.includes(prov.id);
                    const keyConsole = PROVIDER_KEY_CONSOLES[prov.id];
                    const currentMaskedKey = keyStatus?.custom_providers?.find((p: any) => p.id === prov.id)?.api_key;
                    const modelsForThis = providerModelChoices[prov.id];

                    return (
                      <div
                        key={prov.id || index}
                        id={`provider-card-${prov.id}`}
                        className={`p-5 rounded-[6px] bg-card border space-y-4 transition-colors duration-150 ${
                          highlightedProviderId === prov.id
                            ? 'border-corten'
                            : 'border-[hsl(var(--border))]'
                        }`}
                      >
                        {/* Header Row */}
                        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line">
                          <div className="flex items-center gap-3">
                            <div className="w-9 h-9 rounded-xl bg-hl text-hl-contrast flex items-center justify-center font-bold shadow-xs">
                              <Cpu className="w-4 h-4" />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-foreground">{prov.name}</span>
                                <span className={`text-[9px] font-bold px-2 py-0.5 rounded-full ${
                                  prov.zone === 'UE' ? 'bg-positive/10 text-positive border border-positive/20' : 'bg-sunken text-muted-foreground'
                                }`}>
                                  {prov.zone === 'UE' ? '🇪🇺 Souveraineté UE' : `Zone ${prov.zone}`}
                                </span>
                              </div>
                              <p className="text-[10px] text-muted-foreground font-mono mt-0.5">{prov.litellm_id || 'custom'}</p>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            {/* Live Test Status Badge with confirmed model */}
                            {prov.test_status === 'success' && (
                              <span className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-positive/10 text-positive border border-positive/25 flex items-center gap-1.5" title={`Modèle confirmé par l'API : ${prov.confirmed_model || prov.litellm_id}`}>
                                <CheckCircle2 className="w-3.5 h-3.5 text-positive" />
                                <span>Connecté ({prov.last_latency_ms} ms) • {prov.confirmed_model ? prov.confirmed_model.split('/').pop() : prov.litellm_id}</span>
                              </span>
                            )}
                            {prov.test_status === 'error' && (
                              <span className="text-[10px] font-bold px-2.5 py-1 rounded-lg bg-danger/10 text-danger border border-danger/25 flex items-center gap-1.5">
                                <AlertTriangle className="w-3.5 h-3.5 text-danger" />
                                <span>Erreur de connexion</span>
                              </span>
                            )}
                            {(!prov.test_status || prov.test_status === 'untested') && (
                              <span className="text-[10px] text-muted-foreground px-2 py-1 rounded-lg bg-sunken border border-line">
                                Non testé
                              </span>
                            )}

                            {/* Test Button */}
                            <button
                              type="button"
                              onClick={() => handleTestProvider(index)}
                              disabled={testingProviderId === prov.id}
                              className="btn-secondary !py-1.5 !px-3 !text-xs flex items-center gap-1.5 cursor-pointer"
                            >
                              {testingProviderId === prov.id ? (
                                <>
                                  <Loader2 className="w-3.5 h-3.5 animate-spin text-hl" />
                                  <span>Test en cours…</span>
                                </>
                              ) : (
                                <>
                                  <Zap className="w-3.5 h-3.5 text-hl" />
                                  <span>Tester et enregistrer la clé</span>
                                </>
                              )}
                            </button>

                            {!isBuiltin && (
                              <button
                                type="button"
                                onClick={() => handleDeleteProvider(index)}
                                className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                                title="Supprimer ce fournisseur"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        </div>

                        {/* Custom Provider Meta Inputs if not builtin */}
                        {!isBuiltin && (
                          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs pb-1">
                            <div>
                              <label className="block text-[11px] font-semibold text-foreground mb-1">
                                Nom affiché
                              </label>
                              <input
                                type="text"
                                value={prov.name || ''}
                                onChange={(e) => handleUpdateProvider(index, 'name', e.target.value)}
                                placeholder="ex: Serveur Local vLLM"
                                className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-medium focus:outline-none focus:ring-1 focus:ring-hl"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-foreground mb-1">
                                Adresse du service (facultatif)
                              </label>
                              <input
                                type="text"
                                value={prov.api_base || ''}
                                onChange={(e) => handleUpdateProvider(index, 'api_base', e.target.value)}
                                placeholder="ex: http://localhost:11434/v1"
                                className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-hl"
                              />
                            </div>
                            <div>
                              <label className="block text-[11px] font-semibold text-foreground mb-1">
                                Zone déclarée de votre service
                              </label>
                              <select
                                value={prov.zone || 'US'}
                                onChange={(e) => handleUpdateProvider(index, 'zone', e.target.value)}
                                className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-medium focus:outline-none focus:ring-1 focus:ring-hl cursor-pointer"
                              >
                                <option value="UE">Union européenne</option>
                                <option value="US">États-Unis</option>
                                <option value="Chine">Chine</option>
                                <option value="autre">Autre / non vérifiée</option>
                              </select>
                              {/* Déclaratif, et l'écran doit le dire : ce champ ne choisit
                                  aucun serveur, il sert uniquement à décider si
                                  l'avertissement RGPD s'affiche pour ce point d'accès. */}
                              <p className="mt-1.5 text-[11px] leading-relaxed text-[hsl(var(--muted-foreground))]">
                                Où tourne réellement le service que vous avez renseigné. Ce champ ne
                                déplace aucun traitement : il détermine seulement l’avertissement RGPD.
                              </p>
                            </div>
                          </div>
                        )}

                        {isBuiltin && (
                          <p className="text-[11.5px] text-[hsl(var(--muted-foreground))]">
                            Hébergement&nbsp;:{' '}
                            <strong className="text-foreground">{BUILTIN_PROVIDER_ZONES[prov.id] || prov.zone || '—'}</strong>
                            {' '}— imposé par le fournisseur.
                          </p>
                        )}

                        {/* Configuration Grid */}
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                          <div>
                            <label className="block text-[11px] font-semibold text-foreground mb-1">
                              Modèle utilisé par défaut
                            </label>
                            {modelsForThis ? (
                              <div className="space-y-1.5">
                                <select
                                  value={modelsForThis.some(m => m.id === prov.litellm_id) ? prov.litellm_id : '__manual__'}
                                  onChange={(e) => {
                                    if (e.target.value === '__manual__') {
                                      handleUpdateProvider(index, 'litellm_id', '');
                                    } else {
                                      handleUpdateProvider(index, 'litellm_id', e.target.value);
                                    }
                                  }}
                                  className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-medium focus:outline-none focus:ring-1 focus:ring-hl cursor-pointer"
                                >
                                  {modelsForThis.map(m => (
                                    <option key={m.id} value={m.id}>
                                      {m.label} ({m.cost})
                                    </option>
                                  ))}
                                  <option value="__manual__">
                                    ✏️ Saisir un autre identifiant LiteLLM sur-mesure...
                                  </option>
                                </select>
                                {(!modelsForThis.some(m => m.id === prov.litellm_id)) && (
                                  <input
                                    type="text"
                                    value={prov.litellm_id || ''}
                                    onChange={(e) => handleUpdateProvider(index, 'litellm_id', e.target.value)}
                                    placeholder={`ex: ${prov.id}/votre-modele-specifique`}
                                    className="w-full px-3 py-1.5 rounded-lg bg-sunken border border-line text-xs text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-hl"
                                  />
                                )}
                              </div>
                            ) : (
                              <input
                                type="text"
                                value={prov.litellm_id || ''}
                                onChange={(e) => handleUpdateProvider(index, 'litellm_id', e.target.value)}
                                placeholder="ex: ollama/mistral ou openai/custom-model"
                                className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-hl"
                              />
                            )}
                          </div>

                          <div>
                            <div className="flex items-center justify-between mb-1">
                              <label className="text-[11px] font-semibold text-foreground">
                                Clé d’API
                              </label>
                              {currentMaskedKey && (
                                <span className="text-[10px] font-mono text-positive">
                                  ✓ Clé enregistrée ({currentMaskedKey})
                                </span>
                              )}
                            </div>
                            <input
                              type="password"
                              data-api-key-input="true"
                              value={prov.api_key || ''}
                              onChange={(e) => handleUpdateProvider(index, 'api_key', e.target.value)}
                              placeholder={currentMaskedKey ? "•••••••••••••••• (laissez vide pour conserver la clé actuelle)" : "Collez la clé du fournisseur"}
                              className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-hl"
                            />
                            {/* La clé se crée chez le fournisseur, pas ailleurs : LiteLLM est la
                                bibliothèque que le serveur utilise pour les appeler tous et
                                n'a pas de clé ; OpenRouter n'est lu que pour le catalogue. */}
                            {keyConsole && !currentMaskedKey && (
                              <p className="mt-1.5 text-[11px] text-[hsl(var(--muted-foreground))]">
                                À créer sur{' '}
                                <a
                                  href={keyConsole.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-mono text-hl underline underline-offset-2"
                                >
                                  {keyConsole.label}
                                </a>
                              </p>
                            )}
                          </div>

                          {/* 02/09 : monthly_budget_usd existe et est reellement applique cote
                              backend (bascule automatique de secours si le budget du mois est
                              atteint, voir model_routing_service.py) depuis le debut, mais
                              n'avait AUCUN champ ici pour le renseigner -- le seul lien reel
                              entre "palier", "clé" et "budget" etait invisible. Ajoute ici,
                              a cote de la clé, plutot que sur un autre onglet. */}
                          <div>
                            <label className="block text-[11px] font-semibold text-foreground mb-1">
                              Plafond mensuel en dollars (facultatif)
                            </label>
                            <input
                              type="number"
                              min="0"
                              step="1"
                              value={prov.monthly_budget_usd ?? ''}
                              onChange={(e) => handleUpdateProvider(index, 'monthly_budget_usd', e.target.value === '' ? null : Number(e.target.value))}
                              placeholder="ex: 200 (bascule automatique si dépassé)"
                              className="w-full px-3 py-2 rounded-lg bg-sunken border border-line text-xs text-foreground font-mono focus:outline-none focus:ring-1 focus:ring-hl"
                            />
                          </div>
                        </div>

                        {/* Error message callout if test failed */}
                        {prov.test_status === 'error' && prov.last_error_message && (
                          <div className="p-3 rounded-xl bg-danger/10 border border-danger/25 text-danger text-xs flex items-start gap-2">
                            <AlertTriangle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
                            <div className="min-w-0">
                              <p className="font-bold">Échec du test de clé</p>
                              <p className="font-mono text-[11px] mt-0.5 break-all">{prov.last_error_message}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* Barre d'enregistrement flottante ──────────────────────────
                  Le bouton se trouvait auparavant tout en bas d'un formulaire de
                  plusieurs écrans de haut : on saisissait une clé, on la testait,
                  on lisait « Connecté », et on quittait la page sans jamais
                  l'atteindre — c'est ainsi qu'une clé pouvait être perdue.
                  Une barre `sticky` ne suffisait pas : posée dans le formulaire,
                  elle disparaissait dès qu'on remontait dans la liste. Celle-ci
                  est ancrée à la fenêtre et n'apparaît que s'il reste quelque
                  chose à enregistrer. */}
              {hasUnsavedChanges && (
                <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-40 max-w-[calc(100vw-3rem)]">
                  <div className="flex items-center gap-5 rounded-[6px] border border-corten/60 bg-card ps-4 pe-3 py-2.5 shadow-elevated whitespace-nowrap">
                    <p className="text-[12.5px] text-foreground truncate">
                      <span className="font-medium">Modifications non enregistrées.</span>
                    </p>
                    <div className="flex items-center gap-2 shrink-0">
                      <button type="button" onClick={() => fetchMasterKeys()} className="btn-ghost !text-[12.5px]">
                        Annuler
                      </button>
                      <button type="submit" disabled={isSavingKeys} className="btn-primary disabled:opacity-50">
                        <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
                        <span>{isSavingKeys ? 'Enregistrement…' : 'Enregistrer'}</span>
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {/* Repère de fin de formulaire, toujours présent : la barre
                  flottante ne s'affiche que lorsqu'il y a quelque chose à faire. */}
              <div className="flex items-center justify-between gap-3 pt-2 border-t border-line">
                <p className="text-[12.5px] text-muted-foreground pt-3">
                  {hasUnsavedChanges ? 'Modifications en attente d’enregistrement.' : 'Tout est enregistré.'}
                </p>
                <button
                  type="submit"
                  disabled={isSavingKeys || !hasUnsavedChanges}
                  className="btn-primary mt-3 disabled:opacity-45 disabled:cursor-not-allowed"
                >
                  <Save className="w-3.5 h-3.5" strokeWidth={1.5} />
                  <span>{isSavingKeys ? 'Enregistrement…' : 'Enregistrer'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Clés de recherche web (04/09) : sert la veille et la génération sur les
              sites officiels déclarés par pays. */}
          <WebSearchKeysCard />

          {/* Suivi de la consommation LLM (Tokens & Coûts ce mois-ci) */}
          <div id="llm-consumption" className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 dark:border-zinc-800/80 pb-4">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                  <Activity className="w-4 h-4 text-zinc-400" />
                  <span>{t('admin.super.keys.usage_title')}</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('admin.super.keys.usage_desc')}
                </p>
              </div>
              <button
                type="button"
                onClick={fetchUsageSummary}
                disabled={usageLoading}
                className="btn-secondary py-1.5 px-3 text-xs shrink-0"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-zinc-400 ${usageLoading ? 'animate-spin' : ''}`} />
                <span>{usageLoading ? t('admin.super.keys.catalog_btn_syncing') : t('admin.super.keys.usage_btn_refresh')}</span>
              </button>
            </div>

            {/* CORRECTIF (03/09) : cet écran lisait des champs que le backend n'a jamais
                renvoyés — `total_tokens`, `total_cost_usd`, `total_requests`, et un
                `by_provider` traité comme un objet. GET /admin/llm-usage-summary renvoie
                en réalité `total_estimated_cost_usd` et un TABLEAU `by_provider` avec
                `provider_name`, `call_count`, `prompt_tokens`, `completion_tokens`,
                `estimated_cost_usd`. Conséquence : le panneau affichait des zéros en
                permanence, y compris quand la consommation était réelle. Les totaux sont
                désormais dérivés du tableau, seule source disponible. */}
            {(() => {
              const rows: any[] = Array.isArray(usageSummary?.by_provider) ? usageSummary.by_provider : [];
              const totalTokens = rows.reduce(
                (acc, r) => acc + (r.prompt_tokens || 0) + (r.completion_tokens || 0),
                0,
              );
              const totalCalls = rows.reduce((acc, r) => acc + (r.call_count || 0), 0);
              const totalCost =
                usageSummary?.total_estimated_cost_usd ??
                rows.reduce((acc, r) => acc + (r.estimated_cost_usd || 0), 0);
              const nf = new Intl.NumberFormat('fr-FR');

              if (usageLoading && !usageSummary) {
                return (
                  <div className="p-8 flex items-center justify-center">
                    <Loader2 className="w-4 h-4 animate-spin text-[hsl(var(--muted-foreground))]" />
                  </div>
                );
              }
              if (rows.length === 0) {
                return (
                  <div className="p-8 text-center text-[12.5px] text-[hsl(var(--muted-foreground))]">
                    {t('admin.super.keys.usage_empty')}
                  </div>
                );
              }

              return (
                <div className="space-y-5">
                  <div className="grid grid-cols-1 sm:grid-cols-3 border-y border-[hsl(var(--border))]">
                    {[
                      { label: t('admin.super.keys.usage_total_tokens'), value: nf.format(totalTokens) },
                      { label: t('admin.super.keys.usage_estimated_cost'), value: `${totalCost.toFixed(2)} $` },
                      { label: t('admin.super.keys.usage_total_requests'), value: nf.format(totalCalls) },
                    ].map((stat, i) => (
                      <div
                        key={stat.label}
                        className={`py-3.5 px-4 ${i > 0 ? 'sm:border-s border-[hsl(var(--border))]' : ''} ${i === 0 ? 'sm:ps-0' : ''}`}
                      >
                        <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
                          {stat.label}
                        </p>
                        <p className="mt-1 font-mono text-[20px] leading-none tabular-nums text-foreground">
                          {stat.value}
                        </p>
                      </div>
                    ))}
                  </div>

                  <div className="overflow-x-auto">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>{t('admin.super.keys.usage_col_provider')}</th>
                          <th className="!text-end">{t('admin.super.keys.usage_col_requests')}</th>
                          <th className="!text-end">{t('admin.super.keys.usage_col_tokens')}</th>
                          <th className="!text-end">{t('admin.super.keys.usage_col_cost')}</th>
                          <th className="!text-end">{t('admin.super.keys.usage_col_budget')}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((r) => {
                          const tokens = (r.prompt_tokens || 0) + (r.completion_tokens || 0);
                          const cap = r.monthly_budget_usd;
                          const over = cap != null && cap > 0 && (r.estimated_cost_usd || 0) >= cap;
                          return (
                            <tr key={r.provider_id || r.provider_name}>
                              <td className="text-foreground">{r.provider_name || r.provider_id}</td>
                              <td className="text-end font-mono tabular-nums text-[hsl(var(--muted-foreground))]">
                                {nf.format(r.call_count || 0)}
                              </td>
                              <td className="text-end font-mono tabular-nums text-[hsl(var(--muted-foreground))]">
                                {nf.format(tokens)}
                              </td>
                              <td className="text-end font-mono tabular-nums text-foreground">
                                {(r.estimated_cost_usd || 0).toFixed(2)} $
                              </td>
                              <td
                                className="text-end font-mono tabular-nums"
                                style={{ color: over ? 'var(--cost-friction)' : undefined }}
                              >
                                {cap != null ? `${Number(cap).toFixed(0)} $` : '—'}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })()}
          </div>

          {/* Catalogue de modèles en lecture seule */}
          <div className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                  <Layers className="w-4 h-4 text-hl" />
                  <span>{t('admin.super.keys.catalog_title')}</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5 max-w-xl">
                  {t('admin.super.keys.catalog_desc')}
                </p>
                <p className="text-[10px] text-muted-foreground mt-1">
                  {llmCatalog?.last_synced_at
                    ? t('admin.super.keys.catalog_last_synced', { date: new Date(llmCatalog.last_synced_at).toLocaleString() })
                    : t('admin.super.keys.catalog_never_synced')}
                </p>
              </div>
              <button
                type="button"
                onClick={handleSyncLlmCatalog}
                disabled={catalogSyncing}
                className="btn-secondary !py-1.5 !px-3 !text-xs shrink-0 cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 text-hl ${catalogSyncing ? 'animate-spin' : ''}`} />
                <span>{catalogSyncing ? t('admin.super.keys.catalog_btn_syncing') : t('admin.super.keys.catalog_btn_sync')}</span>
              </button>
            </div>

            {/* Le catalogue brut agrège trois sources et contient encore des générations
                retirées par leurs fournisseurs (la base LiteLLM embarquée les liste tant
                que le paquet n'est pas mis à jour). Par défaut on n'affiche donc que les
                modèles du socle de référence, relevé à la main sur les pages tarifaires
                officielles — ceux dont on peut garantir le prix. */}
            <label className="flex items-center gap-2 text-[12px] text-[hsl(var(--muted-foreground))] cursor-pointer select-none">
              <input
                type="checkbox"
                checked={catalogVerifiedOnly}
                onChange={(e) => setCatalogVerifiedOnly(e.target.checked)}
                className="accent-hl cursor-pointer"
              />
              <span>{t('admin.super.keys.catalog_verified_only')}</span>
            </label>

            {catalogLoading ? (
              <div className="p-8 text-center text-xs text-muted-foreground flex items-center justify-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-hl" />
              </div>
            ) : !llmCatalog || llmCatalog.models.length === 0 ? (
              <div className="p-8 text-center text-xs text-muted-foreground">{t('admin.super.keys.catalog_empty')}</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-left text-[10px] font-mono font-bold uppercase tracking-wider text-muted-foreground border-b border-line">
                      <th className="px-3 py-2">{t('admin.super.keys.catalog_col_model')}</th>
                      <th className="px-3 py-2">{t('admin.super.keys.catalog_col_provider')}</th>
                      <th className="px-3 py-2 text-right">{t('admin.super.keys.catalog_col_pricing')}</th>
                      <th className="px-3 py-2 text-right">{t('admin.super.keys.catalog_col_context')}</th>
                      <th className="px-3 py-2">{t('admin.super.keys.catalog_col_status')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line">
                    {llmCatalog.models
                      .filter((m) => (catalogVerifiedOnly ? m.source === 'reference_catalog' : true))
                      .map((m) => (
                      <tr key={m.id} className={m.is_active ? '' : 'opacity-50'}>
                        <td className="px-3 py-2.5 font-mono text-[11px] text-foreground">{m.display_name || m.external_id}</td>
                        <td className="px-3 py-2.5 text-muted-foreground">{m.provider_slug || '—'}</td>
                        <td className="px-3 py-2.5 text-right font-mono tabular-nums text-foreground">
                          {m.pricing_prompt_per_million != null && m.pricing_completion_per_million != null
                            ? `$${m.pricing_prompt_per_million.toFixed(2)} / $${m.pricing_completion_per_million.toFixed(2)}`
                            : '—'}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono tabular-nums text-muted-foreground">
                          {m.context_length ? m.context_length.toLocaleString() : '—'}
                        </td>
                        <td className="px-3 py-2.5">
                          <span className={`text-[9px] font-mono font-bold px-2 py-0.5 rounded-full ${m.is_active ? 'bg-positive/10 text-positive border border-positive/25' : 'bg-sunken text-muted-foreground border border-line'}`}>
                            {m.is_active ? t('admin.super.keys.catalog_status_active') : t('admin.super.keys.catalog_status_inactive')}
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 2: TASK-BASED LLM ROUTING PER REAL TENANT */}
      {activeTab === 'routing' && (
        <div className="space-y-6">
          {/* Guide d'affectation des modèles par tâche */}
          <div className="p-5 rounded-2xl bg-card border border-line shadow-xs space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line pb-3">
              <h3 className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
                <Cpu className="w-4 h-4 text-hl" />
                <span>Routage Intelligent des Modèles par Entreprise Cliente</span>
              </h3>
              <span className="badge-pill font-medium">
                Personnalisation Multi-Tâches
              </span>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
              <div className="p-3.5 rounded-xl bg-sunken border border-line space-y-1">
                <p className="font-bold text-foreground flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-hl"></span>
                  1. Extraction & Synthèse RC
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Extraction des exigences du dossier de consultation et décision go/no-go. Modèles rapides conseillés : Claude Haiku 4.5, GPT-5.6 Luna, Mistral Small 4.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-sunken border border-line space-y-1">
                <p className="font-bold text-foreground flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-hl"></span>
                  2. Rédaction Long-Form
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Rédaction des chapitres du mémoire technique. Modèles conseillés : Claude Sonnet 5, GPT-5.6 Terra, Mistral Large 3.
                </p>
              </div>
              <div className="p-3.5 rounded-xl bg-sunken border border-line space-y-1">
                <p className="font-bold text-foreground flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-positive"></span>
                  3. Chiffrage & Prix (DPGF)
                </p>
                <p className="text-[11px] text-muted-foreground">
                  Analyse des déboursés et formules d'indexation BT01. Modèles de raisonnement recommandés (GPT-5.6 Sol, Claude Opus 5, Mistral Large 3).
                </p>
              </div>
            </div>
          </div>

          {/* Search bar for clients */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4 p-4 rounded-2xl bg-card border border-line shadow-xs">
            <div className="relative flex-1 group">
              <Search className="w-4 h-4 text-slate-400 group-focus-within:text-hl absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors" />
              <input
                type="text"
                value={routingSearch}
                onChange={(e) => setRoutingSearch(e.target.value)}
                placeholder="Rechercher une entreprise cliente (nom, SIRET, ID)..."
                className="w-full pl-9 pr-4 py-2 rounded-xl bg-sunken border border-line text-xs text-foreground placeholder:text-slate-400 dark:placeholder:text-zinc-500 focus:outline-none focus:border-hl transition-all font-medium"
              />
            </div>
            <span className="text-xs text-muted-foreground font-mono self-center shrink-0">
              {filteredRoutingTenants.length} / {tenants.length} client(s)
            </span>
          </div>

          {filteredRoutingTenants.length === 0 ? (
            <div className="p-12 text-center text-xs text-muted-foreground rounded-2xl bg-card border border-dashed border-line">
              {tenants.length === 0 ? t('admin.super.routing.empty') : 'Aucune entreprise trouvée pour cette recherche.'}
            </div>
          ) : (
            filteredRoutingTenants.map((tenant) => {
              const routing = tenant.model_routing_config || {};
              const currentGoNoGo = routing.extraction_gonogo?.model || 'anthropic/claude-sonnet-5';
              const currentRedaction = routing.redaction_memoire?.model || tenant.llm_model || 'anthropic/claude-sonnet-5';
              const currentPricing = routing.analyse_prix?.model || 'mistral/mistral-large-3-25-12';

              return (
                <div key={tenant.id} className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-5">
                  <div className="flex items-center justify-between border-b border-line pb-3">
                    <div>
                      <h3 className="text-sm font-bold text-foreground font-heading">{tenant.name}</h3>
                      <p className="text-[11px] text-muted-foreground font-mono">{t('admin.tenant_detail.id_label', { id: tenant.id })}</p>
                    </div>
                    <span className="badge-pill-emerald">
                      {t('admin.super.routing.active_badge')}
                    </span>
                  </div>

                  {/* Bulk Apply Model to All Tasks */}
                  <div className="flex flex-wrap items-center gap-3 p-3.5 rounded-xl bg-sunken border border-line">
                    <span className="text-[11px] font-semibold text-foreground">{t('admin.super.routing.bulk_label')}</span>
                    <select
                      value={bulkRoutingSelection[tenant.id] ?? currentRedaction}
                      onChange={(e) => setBulkRoutingSelection(prev => ({ ...prev, [tenant.id]: e.target.value }))}
                      className="px-3 py-2 rounded-lg bg-card border border-line text-xs text-foreground focus:outline-none focus:border-hl cursor-pointer font-medium"
                    >
                      {renderSelectableModelOptions()}
                    </select>
                    <button
                      type="button"
                      onClick={() => handleBulkApplyModelRouting(tenant.id, bulkRoutingSelection[tenant.id] ?? currentRedaction)}
                      className="btn-primary !py-1.5 !px-3 !text-xs cursor-pointer"
                    >
                      {t('admin.super.routing.bulk_btn')}
                    </button>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
                    {/* Task 1: Go/No-Go */}
                    <div className="p-4 rounded-xl bg-sunken border border-line space-y-2">
                      <label className="block text-xs font-semibold text-slate-800 dark:text-zinc-200">{t('admin.super.routing.task1_label')}</label>
                      <select
                        value={currentGoNoGo}
                        onChange={(e) => handleUpdateModelRouting(tenant.id, 'extraction_gonogo', e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-card border border-line focus:border-hl text-xs text-foreground focus:outline-none font-medium cursor-pointer"
                      >
                        {renderSelectableModelOptions()}
                      </select>
                      <p className="text-[10px] text-muted-foreground">{t('admin.super.routing.task1_desc')}</p>
                    </div>

                    {/* Task 2: Redaction */}
                    <div className="p-4 rounded-xl bg-sunken border border-line space-y-2">
                      <label className="block text-xs font-semibold text-slate-800 dark:text-zinc-200">{t('admin.super.routing.task2_label')}</label>
                      <select
                        value={currentRedaction}
                        onChange={(e) => handleUpdateModelRouting(tenant.id, 'redaction_memoire', e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-card border border-line focus:border-hl text-xs text-foreground focus:outline-none font-medium cursor-pointer"
                      >
                        {renderSelectableModelOptions()}
                      </select>
                      <p className="text-[10px] text-muted-foreground">{t('admin.super.routing.task2_desc')}</p>
                    </div>

                    {/* Task 3: Pricing */}
                    <div className="p-4 rounded-xl bg-sunken border border-line space-y-2">
                      <label className="block text-xs font-semibold text-slate-800 dark:text-zinc-200">{t('admin.super.routing.task3_label')}</label>
                      <select
                        value={currentPricing}
                        onChange={(e) => handleUpdateModelRouting(tenant.id, 'analyse_prix', e.target.value)}
                        className="w-full px-3 py-2 rounded-lg bg-card border border-line focus:border-hl text-xs text-foreground focus:outline-none font-medium cursor-pointer"
                      >
                        {renderSelectableModelOptions()}
                      </select>
                      <p className="text-[10px] text-muted-foreground">{t('admin.super.routing.task3_desc')}</p>
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
            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs">
              <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase">{t('admin.super.rag.status_label')}</span>
              {ragStats.embedding_mode === 'real' ? (
                <p className="text-lg font-bold text-positive flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-positive animate-pulse" />
                  {t('admin.super.rag.status_online')}
                </p>
              ) : (
                <p className="text-lg font-bold text-hl flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-hl animate-pulse" />
                  {t('admin.super.rag.status_degraded')}
                </p>
              )}
              <p className="text-[11px] text-muted-foreground font-mono">{ragStats.index_type}</p>
            </div>

            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs">
              <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase">{t('admin.super.rag.embedding_model_label')}</span>
              <p className={`text-sm font-bold font-mono ${ragStats.embedding_mode === 'real' ? 'text-foreground' : 'text-hl'}`}>
                {ragStats.embedding_mode === 'real' ? ragStats.embedding_model : t('admin.super.rag.embedding_model_fallback')}
              </p>
              {ragStats.embedding_mode === 'real' ? (
                <p className="text-[11px] text-muted-foreground font-mono">{t('admin.super.rag.dimensions_suffix', { count: ragStats.dimensions })}</p>
              ) : (
                <p className="text-[11px] text-hl leading-tight">{t('admin.super.rag.embedding_key_missing')}</p>
              )}
            </div>

            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs">
              <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase">{t('admin.super.rag.dce_chunks_label')}</span>
              <p className="text-xl font-bold text-foreground font-mono">{ragStats.total_dce_chunks}</p>
              <p className="text-[11px] text-muted-foreground">{t('admin.super.rag.dce_chunks_note')}</p>
            </div>

            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs">
              <span className="text-[10px] font-mono font-bold text-muted-foreground uppercase">{t('admin.super.rag.knowledge_chunks_label')}</span>
              <p className="text-xl font-bold text-foreground font-mono">{ragStats.total_knowledge_chunks}</p>
              <p className="text-[11px] text-muted-foreground">{t('admin.super.rag.knowledge_chunks_note')}</p>
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-4">
            <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
              <Database className="w-4 h-4 text-hl" />
              <span>{t('admin.super.rag.section_title')}</span>
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs text-foreground">
              <div className="p-4 rounded-xl bg-sunken border border-line space-y-1.5">
                <p className="font-bold text-foreground">{t('admin.super.rag.hnsw_title')}</p>
                <p className="text-muted-foreground leading-relaxed text-[11px]">
                  {t('admin.super.rag.hnsw_desc')}
                </p>
              </div>
              <div className="p-4 rounded-xl bg-sunken border border-line space-y-1.5">
                <p className="font-bold text-foreground">{t('admin.super.rag.rerank_title')}</p>
                <p className="text-muted-foreground leading-relaxed text-[11px]">
                  {t('admin.super.rag.rerank_desc')}
                </p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* TAB 4: ADVANCED SYSTEM PROMPT EDITOR */}
      {activeTab === 'prompts' && (
        <div className="space-y-6">
          <div className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line pb-4">
              <div>
                <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                  <FileCode className="w-4 h-4 text-hl" />
                  <span>{t('admin.super.prompt.editor_title')}</span>
                </h3>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t('admin.super.prompt.editor_desc')}
                </p>
              </div>

              <div className="flex items-center gap-2.5">
                <select
                  value={selectedTenantForPrompt}
                  onChange={(e) => setSelectedTenantForPrompt(e.target.value)}
                  className="px-3 py-2 rounded-xl bg-sunken border border-line text-xs text-foreground focus:outline-none cursor-pointer font-medium"
                >
                  {tenants.map((tenant) => (
                    <option key={tenant.id} value={tenant.id}>{tenant.name}</option>
                  ))}
                </select>

                <button
                  onClick={handleSaveSystemPrompt}
                  disabled={isSavingPrompt}
                  className="btn-primary !py-2 !px-4 !text-xs cursor-pointer shadow-xs disabled:opacity-50"
                >
                  <Save className="w-3.5 h-3.5" />
                  <span>{isSavingPrompt ? t('admin.super.prompt.btn_saving') : t('admin.super.prompt.btn_save')}</span>
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-semibold text-foreground">
                {t('admin.super.prompt.directives_label')}
              </label>
              <textarea
                rows={12}
                value={currentPrompt}
                onChange={(e) => setCurrentPrompt(e.target.value)}
                placeholder={t('admin.super.prompt.placeholder_prompt')}
                className="w-full p-4 rounded-xl bg-sunken border border-line focus:border-hl text-xs text-slate-800 dark:text-zinc-200 font-mono leading-relaxed focus:outline-none"
              />
              <p className="text-[11px] text-muted-foreground">
                {t('admin.super.prompt.footer_note')}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* TAB 5: REAL TENANTS LIST */}
      {activeTab === 'tenants' && (
        <div className="space-y-4">
          {tenants.length === 0 ? (
            <div className="p-12 rounded-2xl bg-card border border-dashed border-line text-center space-y-4">
              <Building2 className="w-10 h-10 text-muted-foreground mx-auto" />
              <div className="space-y-1">
                <h3 className="text-sm font-bold text-foreground font-heading">{t('admin.super.tenants_tab.empty_title')}</h3>
                <p className="text-xs text-slate-500">{t('admin.super.tenants_tab.empty_desc')}</p>
              </div>
              <button
                onClick={() => setShowCreateModal(true)}
                className="btn-primary !py-2 !px-4 !text-xs cursor-pointer shadow-xs mx-auto"
              >
                <Plus className="w-4 h-4" />
                <span>{t('admin.super.btn_create_tenant')}</span>
              </button>
            </div>
          ) : (
            <div className="bg-card border border-line rounded-2xl overflow-hidden shadow-xs">
              <div className="divide-y divide-line">
                {tenants.map((tenant) => (
                  <div key={tenant.id} className="p-4 sm:p-5 flex flex-wrap items-center justify-between gap-4 hover:bg-slate-50/60 dark:hover:bg-raised/50 transition-colors">
                    <Link href={`/admin/tenants/${tenant.id}`} className="flex items-center gap-3 group">
                      <div className="w-9 h-9 rounded-xl bg-hl/10 text-hl font-bold text-xs flex items-center justify-center border border-hl/20">
                        {tenant.name.substring(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <h3 className="text-xs font-bold text-foreground group-hover:text-hl transition-colors flex items-center gap-1.5 font-heading">
                          <span>{tenant.name}</span>
                          <ChevronRight className="w-3.5 h-3.5 opacity-0 group-hover:opacity-100 transition-opacity text-hl" />
                        </h3>
                        <p className="text-[11px] text-muted-foreground font-mono">
                          {t('admin.tenants_list.siret_line', { siret: tenant.siret || t('admin.tenants_list.no_siret'), email: tenant.contact_email || t('admin.tenants_list.no_email') })}
                        </p>
                      </div>
                    </Link>

                    <div className="flex items-center gap-3">
                      <Link
                        href={`/admin/tenants/${tenant.id}`}
                        className="btn-secondary !py-1 !px-2.5 !text-[11px]"
                      >
                        {t('admin.super.tenants_tab.btn_manage')}
                      </Link>
                      <span className="text-[9px] font-mono font-bold px-2 py-0.5 rounded bg-hl/10 text-hl border border-hl/20 uppercase">
                        {t('admin.tenants_list.plan_badge', { plan: tenant.plan })}
                      </span>
                      <span className="text-xs text-muted-foreground font-mono hidden sm:inline">
                        {t('admin.super.tenants_tab.files_count', { used: tenant.used_this_month || 0, limit: tenant.monthly_limit || 15 })}
                      </span>
                      <button
                        onClick={() => handleDeleteTenant(tenant.id)}
                        className="p-1.5 rounded-lg text-slate-400 hover:text-danger hover:bg-danger/10 transition-colors cursor-pointer"
                        title={t('admin.tenant_detail.delete_title')}
                      >
                        <Trash2 className="w-3.5 h-3.5" />
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
        <div className="space-y-4">
          {!revenueSummary?.any_payment_processor_verified && (
            <div className="p-4 rounded-2xl bg-card border border-line flex items-start gap-2.5 shadow-xs">
              <AlertTriangle className="w-4 h-4 text-hl shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground leading-relaxed">{t('admin.super.revenue.disclaimer')}</p>
            </div>
          )}

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-6 rounded-2xl bg-card border border-line space-y-1.5 shadow-xs">
              <p className="text-xs font-mono font-bold text-muted-foreground uppercase">{t('admin.super.revenue.mrr_label')}</p>
              <p className="text-2xl font-bold text-foreground font-mono">
                {revenueLoading && !revenueSummary ? '…' : (revenueSummary?.mrr_estimated_eur ?? 0).toLocaleString('fr-FR')} €
              </p>
              <p className="text-xs text-positive font-semibold flex items-center gap-1">
                <TrendingUp className="w-3.5 h-3.5" />
                {t('admin.super.revenue.mrr_note', { count: revenueSummary?.billed_active_count ?? 0 })}
              </p>
            </div>

            <div className="p-6 rounded-2xl bg-card border border-line space-y-1.5 shadow-xs">
              <p className="text-xs font-mono font-bold text-muted-foreground uppercase">{t('admin.super.revenue.arr_label')}</p>
              <p className="text-2xl font-bold text-foreground font-mono">
                {revenueLoading && !revenueSummary ? '…' : (revenueSummary?.arr_estimated_eur ?? 0).toLocaleString('fr-FR')} €
              </p>
              <p className="text-xs text-muted-foreground">{t('admin.super.revenue.arr_note')}</p>
            </div>

            <div className="p-6 rounded-2xl bg-card border border-line space-y-1.5 shadow-xs">
              <p className="text-xs font-mono font-bold text-muted-foreground uppercase">{t('admin.super.revenue.storage_label')}</p>
              <p className="text-2xl font-bold text-positive font-mono">{t('admin.super.revenue.storage_value')}</p>
              <p className="text-xs text-muted-foreground">{t('admin.super.revenue.storage_note')}</p>
            </div>
          </div>

          {revenueSummary && (
            <div className="p-5 rounded-2xl bg-card border border-line shadow-xs">
              <p className="text-xs font-bold text-foreground mb-3 font-heading">{t('admin.super.revenue.breakdown_title')}</p>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
                <div>
                  <p className="text-muted-foreground">{t('admin.super.revenue.breakdown_billed')}</p>
                  <p className="font-mono font-bold text-foreground">{revenueSummary.billed_active_count}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{t('admin.super.revenue.breakdown_trial')}</p>
                  <p className="font-mono font-bold text-foreground">{revenueSummary.free_trial_count}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{t('admin.super.revenue.breakdown_custom')}</p>
                  <p className="font-mono font-bold text-foreground">{revenueSummary.custom_pricing_count}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">{t('admin.super.revenue.breakdown_none')}</p>
                  <p className="font-mono font-bold text-foreground">{revenueSummary.tenants_without_subscription_record}</p>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* CREATE TENANT MODAL */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-card border border-line rounded-2xl p-6 max-w-md w-full shadow-elevated space-y-6 animate-in fade-in zoom-in-95">
            <div>
              <h3 className="text-sm font-bold text-foreground font-heading">{t('admin.super.modal.title')}</h3>
              <p className="text-xs text-muted-foreground mt-1">
                {t('admin.super.modal.desc')}
              </p>
            </div>

            <form onSubmit={handleCreateTenant} className="space-y-4">
              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">{t('admin.super.modal.label_name')}</label>
                <input
                  type="text"
                  required
                  value={newTenantName}
                  onChange={(e) => setNewTenantName(e.target.value)}
                  placeholder={t('admin.super.modal.placeholder_name')}
                  className={`w-full px-3.5 py-2.5 rounded-xl bg-sunken border text-foreground text-xs focus:outline-none transition-colors ${
                    isDuplicateName 
                      ? 'border-danger focus:border-danger' 
                      : 'border-line focus:border-hl'
                  }`}
                />
                {isDuplicateName && (
                  <p className="text-[11px] text-danger font-semibold mt-1 flex items-center gap-1">
                    <span>⚠️</span> {t('admin.super.err_duplicate_name')}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">{t('admin.super.modal.label_siret')}</label>
                <input
                  type="text"
                  value={newTenantSiret}
                  onChange={(e) => setNewTenantSiret(e.target.value)}
                  placeholder={t('admin.super.modal.placeholder_siret')}
                  className={`w-full px-3.5 py-2.5 rounded-xl bg-sunken border text-foreground text-xs focus:outline-none transition-colors ${
                    isDuplicateSiret 
                      ? 'border-danger focus:border-danger' 
                      : 'border-line focus:border-hl'
                  }`}
                />
                {isDuplicateSiret && (
                  <p className="text-[11px] text-danger font-semibold mt-1 flex items-center gap-1">
                    <span>⚠️</span> {t('admin.super.err_duplicate_siret')}
                  </p>
                )}
              </div>

              <div>
                <label className="block text-xs font-semibold text-foreground mb-1.5">{t('admin.super.modal.label_email')}</label>
                <input
                  type="email"
                  value={newTenantEmail}
                  onChange={(e) => setNewTenantEmail(e.target.value)}
                  placeholder={t('admin.super.modal.placeholder_email')}
                  className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 focus:border-zinc-500 text-foreground text-xs focus:outline-none"
                />
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-xs font-semibold text-foreground mb-1.5">{t('admin.super.modal.label_plan')}</label>
                  <select
                    value={newTenantPlan}
                    onChange={(e) => setNewTenantPlan(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-xs text-foreground focus:outline-none cursor-pointer font-medium"
                  >
                    <option value="starter">{t('admin.super.modal.plan_starter')}</option>
                    <option value="pro">{t('admin.super.modal.plan_pro')}</option>
                    <option value="enterprise">{t('admin.super.modal.plan_enterprise')}</option>
                  </select>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-foreground mb-1.5">{t('admin.common.ai_model_override_title')}</label>
                  <select
                    id="new-tenant-tier-select"
                    value={newTenantModelTier}
                    onChange={(e) => setNewTenantModelTier(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-slate-50 dark:bg-zinc-950 border border-slate-200 dark:border-zinc-800 text-xs text-foreground focus:outline-none cursor-pointer font-medium"
                  >
                    <option value="inherit">{t('admin.common.inherit_option')}</option>
                    {LLM_MODEL_TIERS.map((tier) => (
                      <option key={tier.id} value={tier.id}>
                        {tier.display_label}
                      </option>
                    ))}
                  </select>
                  <p className="text-[10px] text-muted-foreground mt-1">
                    {t('admin.super.modal.hint_inherit')}
                  </p>
                </div>
              </div>

              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn-secondary flex-1 py-2 text-xs"
                >
                  {t('admin.common.btn_cancel')}
                </button>
                <button
                  type="submit"
                  disabled={isCreating || isDuplicateName || isDuplicateSiret || !newTenantName.trim()}
                  className="btn-primary flex-1 py-2 text-xs disabled:opacity-50"
                >
                  {isCreating ? t('admin.super.modal.btn_creating') : t('admin.super.modal.btn_create_submit')}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* Fournisseurs livrés d'origine : leur zone d'hébergement est imposée par le
   fournisseur lui-même et n'est donc pas modifiable ici. */
const BUILTIN_PROVIDER_IDS = ['anthropic', 'openai', 'mistral', 'gemini', 'deepseek'];

/* Où créer la clé : la console du fournisseur, et nulle part ailleurs.
   LiteLLM est la bibliothèque que le serveur utilise pour parler à tous ces
   fournisseurs — ce n'est pas un service et il n'y a pas de clé LiteLLM.
   OpenRouter n'est lu que comme source du catalogue de modèles ; aucun appel de
   génération n'y transite. */
const PROVIDER_KEY_CONSOLES: Record<string, { url: string; label: string }> = {
  anthropic: { url: 'https://console.anthropic.com/settings/keys', label: 'console.anthropic.com' },
  openai: { url: 'https://platform.openai.com/api-keys', label: 'platform.openai.com' },
  mistral: { url: 'https://console.mistral.ai/api-keys', label: 'console.mistral.ai' },
  gemini: { url: 'https://aistudio.google.com/apikey', label: 'aistudio.google.com' },
  deepseek: { url: 'https://platform.deepseek.com/api_keys', label: 'platform.deepseek.com' },
};

/* Zone réellement déclarée par chaque fournisseur intégré. Miroir de
   PROVIDER_ZONES côté serveur (app/services/llm_reference_catalog.py), qui écrase
   de toute façon toute valeur envoyée depuis cet écran pour ces fournisseurs. */
const BUILTIN_PROVIDER_ZONES: Record<string, string> = {
  anthropic: 'US',
  openai: 'US',
  mistral: 'UE',
  gemini: 'US',
  deepseek: 'Chine',
};

/* Empreinte de la configuration des modèles. Sert uniquement à comparer l'état
   affiché à l'état enregistré, pour savoir s'il reste des modifications en
   attente. La clé y figure en clair : elle ne quitte pas la mémoire du
   navigateur, où elle se trouve déjà, et c'est la seule façon de détecter une
   clé fraîchement saisie par-dessus une clé existante. */
function fingerprintConfig(tier: string, overrides: Record<string, string>, providers: any[], fallbackTier: string = '') {
  return JSON.stringify({
    tier,
    fallbackTier,
    overrides,
    providers: providers.map((p) => ({
      id: p.id,
      name: p.name,
      litellm_id: p.litellm_id,
      api_base: p.api_base || '',
      zone: p.zone,
      enabled: p.enabled !== false,
      budget: p.monthly_budget_usd ?? null,
      key: p.api_key || '',
    })),
  });
}

export default function SuperAdminPage() {
  return (
    <React.Suspense
      fallback={
        <div className="p-20 text-center space-y-3">
          <Loader2 className="w-8 h-8 text-hl animate-spin mx-auto" />
          <p className="text-xs text-slate-600 dark:text-slate-400">Chargement de l'administration...</p>
        </div>
      }
    >
      <SuperAdminPageContent />
    </React.Suspense>
  );
}
