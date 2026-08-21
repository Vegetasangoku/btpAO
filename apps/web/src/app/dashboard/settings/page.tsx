'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Building2,
  Users,
  CreditCard,
  BookOpen,
  FileText,
  Palette,
  Upload,
  Plus,
  Mail,
  CheckCircle2,
  Trash2,
  ShieldCheck,
  Award,
  ChevronRight,
  Download,
  Clock,
  Sparkles,
  TrendingUp,
  Percent,
  SlidersHorizontal,
  Loader2,
  FileUp,
  BrainCircuit,
  HardHat,
  FileCheck,
  Key,
  AlertTriangle,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';


interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: 'conducteur' | 'chiffreur' | 'admin_local';
  activeProjects: number;
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

export default function EnterpriseAdminSettingsPage() {
  const [activeTab, setActiveTab] = useState<'knowledge' | 'memory' | 'economic' | 'team' | 'branding' | 'billing'>('knowledge');
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [savedSuccess, setSavedSuccess] = useState(false);
  const [currentTenantId, setCurrentTenantId] = useState<string | null>(null);

  // Word template state
  const [wordTemplateFile, setWordTemplateFile] = useState<File | null>(null);
  const [wordTemplateInfo, setWordTemplateInfo] = useState<{ has_template: boolean; filename: string | null; updated_at: string | null }>({ has_template: false, filename: null, updated_at: null });
  const [uploadingTemplate, setUploadingTemplate] = useState(false);
  const [templateUploadSuccess, setTemplateUploadSuccess] = useState(false);
  const wordTemplateInputRef = useRef<HTMLInputElement>(null);

  // Documents state (RAG)
  const [documents, setDocuments] = useState<TenantDocument[]>([]);
  const [uploading, setUploading] = useState(false);

  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Team state
  const [team, setTeam] = useState<TeamMember[]>([
    { id: '1', name: 'Jean-Marc Alibert', email: 'j.alibert@eiffabtp.fr', role: 'conducteur', activeProjects: 3 },
    { id: '2', name: 'Sébastien Vasseur', email: 's.vasseur@eiffabtp.fr', role: 'conducteur', activeProjects: 2 },
    { id: '3', name: 'Chloé Fontaine', email: 'c.fontaine@eiffabtp.fr', role: 'chiffreur', activeProjects: 4 },
  ]);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteRole, setInviteRole] = useState<'conducteur' | 'chiffreur'>('conducteur');

  // RGPD Account deletion state
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeletingAccount, setIsDeletingAccount] = useState(false);
  const [deletionStatus, setDeletionStatus] = useState<{
    pending: boolean;
    scheduled_purge_at?: string;
    message?: string;
    legal_notice?: string;
  }>({ pending: false });

  // Company info state
  const [company, setCompany] = useState({
    name: 'EiffaBTP Construction SAS',
    siret: '452 871 609 00041',
    qualibat: '2152 — Béton Armé et Travaux Complexes',
    primaryColor: '#0284c7',
    address: '12 Allée des Bâtisseurs, 93200 Saint-Denis',
  });


  // Economic & Prompt settings state
  const [economicSettings, setEconomicSettings] = useState({
    inflationRate: 3.5,
    targetMargin: 12.0,
    hourlyRateWorker: 38.0,
    hourlyRateManager: 65.0,
    customApiKey: '',
    systemPrompt: `Vous êtes l'ingénieur d'études BTP principal de notre entreprise. Vous rédigez des mémoires techniques hautement percutants pour les marchés publics, en valorisant nos certifications Qualibat, notre flotte de matériel propre, nos engagements RSE bas-carbone et notre encadrement de chantier dédié.`,
    systemPromptMemory: `- Toujours mettre en avant notre certification Qualibat 2152 et notre flotte de matériel propre.
- Appliquer systématiquement une majoration de 5% sur les déboursés de transport et logistique pour les chantiers situés en Île-de-France.
- Utiliser un béton bas-carbone (CEM III/A) avec justification environnementale conforme aux fiches FDES pour tout le gros œuvre.
- Pour les terrassements, privilégier le recyclage in situ avec concassage mobile pour viser un taux de valorisation matière supérieur à 85%.`,
  });

  useEffect(() => {
    async function loadTenantData() {
      setLoading(true);
      try {
        const tenant = await api.getTenant().catch(() => null);
        let tenantId = tenant?.id;

        if (tenant) {
          setCompany(prev => ({
            ...prev,
            name: tenant.name || prev.name,
            siret: tenant.siret || prev.siret,
          }));
        }

        if (!tenantId) {
          const { data: { user } } = await supabase.auth.getUser();
          tenantId = user?.app_metadata?.tenant_id || user?.user_metadata?.tenant_id;
        }

        if (tenantId) {
          setCurrentTenantId(tenantId);

          const timeoutPromise = <T,>(p: PromiseLike<T>, ms = 1200): Promise<T | null> =>
            Promise.race([Promise.resolve(p), new Promise<null>((resolve) => setTimeout(() => resolve(null), ms))]);


          // 1. Load Settings & Memory
          try {
            const settingsData = await timeoutPromise(
              supabase.from('tenants_settings').select('*').eq('tenant_id', tenantId).single().then(r => r.data)
            );
            if (settingsData) {
              setEconomicSettings(prev => ({
                ...prev,
                inflationRate: Number(settingsData.taux_inflation_pct) || prev.inflationRate,
                targetMargin: Number(settingsData.marge_cible_pct) || prev.targetMargin,
                systemPrompt: settingsData.custom_system_prompt || prev.systemPrompt,
                systemPromptMemory: settingsData.system_prompt_memory || prev.systemPromptMemory,
                hourlyRateWorker: settingsData.taux_horaires?.ouvrier || prev.hourlyRateWorker,
                hourlyRateManager: settingsData.taux_horaires?.conducteur || prev.hourlyRateManager,
              }));
            }
          } catch {}

          // 2. Load Documents from tenant_documents
          try {
            const docsData = await timeoutPromise(
              supabase.from('tenant_documents').select('*').eq('tenant_id', tenantId).order('created_at', { ascending: false }).then(r => r.data)
            );
            if (docsData) {
              setDocuments(docsData);
            }
          } catch {}
        }
      } catch (err) {
        console.error('Erreur chargement réglages tenant:', err);
      } finally {
        setLoading(false);
      }

    }
    loadTenantData();
  }, []);

  // Handle Drag & Drop / File Upload to Supabase Storage
  async function handleFileUpload(files: FileList | null) {
    if (!files || files.length === 0 || !currentTenantId) return;
    setUploading(true);
    setUploadError(null);

    try {
      for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const cleanName = file.name.replace(/[^a-zA-Z0-9._-]/g, '_');
        const storagePath = `${currentTenantId}/${Date.now()}_${cleanName}`;

        // 1. Upload to Supabase Storage (bucket company-memories)
        const { error: uploadErr } = await supabase.storage
          .from('company-memories')
          .upload(storagePath, file, { upsert: true });

        if (uploadErr) throw uploadErr;

        // 2. Insert into tenant_documents table with initial OCR status
        const fileType = file.name.endsWith('.docx') ? 'memoire_word' : file.name.endsWith('.pdf') ? 'memoire_pdf' : 'certification';
        const { data: newDoc, error: dbErr } = await supabase
          .from('tenant_documents')
          .insert({
            tenant_id: currentTenantId,
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

          // 3. Trigger backend OCR & vectorization pipeline
          fetch('/api/process-document', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              documentId: newDoc.id,
              filePath: storagePath,
              tenantId: currentTenantId,
              fileName: file.name,
            }),
          }).then(res => res.json()).then(json => {
            if (json.success) {
              setDocuments(prev => prev.map(d => d.id === newDoc.id ? { ...d, status: 'Prêt - Indexé' } : d));
            }
          }).catch(err => console.error('Erreur process-document:', err));
        }
      }
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      console.error('Erreur upload:', err);
      setUploadError(err.message || 'Erreur lors du téléversement du fichier.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function handleDeleteDocument(docId: string, filePath: string) {
    if (!confirm('Supprimer ce document de votre base de connaissances ?')) return;

    try {
      await supabase.storage.from('company-memories').remove([filePath]);
      await supabase.from('tenant_documents').delete().eq('id', docId);
      setDocuments(prev => prev.filter(d => d.id !== docId));
    } catch (err: any) {
      alert('Erreur suppression : ' + err.message);
    }
  }

  async function handleSaveSettings(e: React.FormEvent) {
    e.preventDefault();
    if (!currentTenantId) return;
    setIsSaving(true);

    try {
      const { error } = await supabase
        .from('tenants_settings')
        .upsert({
          tenant_id: currentTenantId,
          custom_system_prompt: economicSettings.systemPrompt,
          system_prompt_memory: economicSettings.systemPromptMemory,
          taux_inflation_pct: economicSettings.inflationRate,
          marge_cible_pct: economicSettings.targetMargin,
          taux_horaires: {
            ouvrier: economicSettings.hourlyRateWorker,
            conducteur: economicSettings.hourlyRateManager,
          },
          mis_a_jour_le: new Date().toISOString(),
        }, { onConflict: 'tenant_id' });

      if (error) throw error;
      setSavedSuccess(true);
      setTimeout(() => setSavedSuccess(false), 3000);
    } catch (err: any) {
      alert('Erreur lors de l\'enregistrement : ' + err.message);
    } finally {
      setIsSaving(false);
    }
  }

  function handleInvite(e: React.FormEvent) {
    e.preventDefault();
    if (!inviteEmail) return;
    setTeam(prev => [
      ...prev,
      {
        id: String(Date.now()),
        name: inviteEmail.split('@')[0].replace('.', ' '),
        email: inviteEmail,
        role: inviteRole,
        activeProjects: 0,
      },
    ]);
    setInviteEmail('');
    setShowInviteModal(false);
  }

  function formatBytes(bytes: number) {
    if (bytes === 0) return '0 Ko';
    const k = 1024;
    const sizes = ['Octets', 'Ko', 'Mo', 'Go'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Espace Entreprise
            </span>
            <span className="text-xs text-slate-500">SIRET : {company.siret}</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">{company.name}</h1>
          <p className="text-xs text-slate-400">
            Gestion de vos documents de référence, mémoire de l'entreprise et règles de chiffrage.
          </p>
        </div>

        {savedSuccess && (
          <div className="px-4 py-2 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-1.5 animate-in fade-in">
            <CheckCircle2 className="w-4 h-4" />
            <span>Enregistré dans la base de données !</span>
          </div>
        )}
      </div>

      {/* Tabs Bar */}
      <div className="flex flex-wrap border-b border-slate-800 gap-2">
        {[
          { id: 'knowledge', label: 'Base de Connaissances (Documents)', icon: BookOpen },
          { id: 'memory', label: 'Comportement de l\'IA & Mémoire', icon: BrainCircuit },
          { id: 'economic', label: 'Règles Économiques & Inflation', icon: SlidersHorizontal },
          { id: 'team', label: 'Équipe & Conducteurs', icon: Users },
          { id: 'branding', label: 'Charte du Mémoire & Logo', icon: Palette },
          { id: 'billing', label: 'Forfait & Quota DCE', icon: CreditCard },
        ].map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`flex items-center gap-2 px-4 py-3 border-b-2 text-xs font-bold transition-all ${
                isActive
                  ? 'border-sky-500 text-sky-400 bg-sky-500/5'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              <Icon className="w-4 h-4" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </div>

      {loading ? (
        <div className="p-12 text-center space-y-2">
          <Loader2 className="w-6 h-6 text-sky-400 animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Chargement des paramètres entreprise...</p>
        </div>
      ) : (
        <>
          {/* TAB 1: KNOWLEDGE BASE (DRAG & DROP RAG UPLOAD) */}
          {activeTab === 'knowledge' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-base font-bold text-white">Base de Connaissances & Documents de Référence</h2>
                <p className="text-xs text-slate-400">
                  Déposez vos anciens mémoires techniques, attestations Qualibat, CVs des équipes et fiches matériels. Ils seront automatiquement indexés pour enrichir les futures réponses.
                </p>
              </div>

              {uploadError && (
                <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs">
                  {uploadError}
                </div>
              )}

              {/* Drag & Drop Upload Zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); }}
                onDrop={(e) => {
                  e.preventDefault();
                  handleFileUpload(e.dataTransfer.files);
                }}
                onClick={() => fileInputRef.current?.click()}
                className="border-2 border-dashed border-slate-700 hover:border-sky-500 rounded-3xl p-8 text-center cursor-pointer transition-all bg-slate-900/40 hover:bg-slate-900/70 group space-y-3"
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.doc,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={(e) => handleFileUpload(e.target.files)}
                />
                <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center mx-auto group-hover:scale-110 transition-transform">
                  {uploading ? <Loader2 className="w-6 h-6 animate-spin" /> : <FileUp className="w-6 h-6" />}
                </div>
                <div>
                  <p className="text-sm font-bold text-white">
                    {uploading ? 'Téléversement et indexation en cours...' : 'Glissez-déposez vos documents ici, ou cliquez pour parcourir'}
                  </p>
                  <p className="text-xs text-slate-400 mt-1">
                    Formats acceptés : PDF, Word (.docx), Images (PNG/JPG) jusqu'à 50 Mo par fichier.
                  </p>
                </div>
              </div>

              {/* Documents List */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider">
                  Documents Indexés ({documents.length})
                </h3>

                {documents.length === 0 ? (
                  <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800 text-center text-xs text-slate-500">
                    Aucun document téléversé pour le moment.
                  </div>
                ) : (
                  <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl divide-y divide-slate-800">
                    {documents.map((doc) => (
                      <div key={doc.id} className="p-4 flex flex-wrap items-center justify-between gap-3 hover:bg-slate-800/40 transition-colors">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-xl bg-sky-500/10 border border-sky-500/20 text-sky-400 flex items-center justify-center font-bold text-xs">
                            <FileText className="w-4 h-4" />
                          </div>
                          <div>
                            <p className="text-xs font-bold text-white">{doc.file_name}</p>
                            <p className="text-[10px] text-slate-400 font-mono">
                              {formatBytes(doc.file_size)} • Ajouté le {new Date(doc.created_at).toLocaleDateString('fr-FR')}
                            </p>
                          </div>
                        </div>

                        <div className="flex items-center gap-3">
                          {doc.status.includes('OCR') ? (
                            <span className="text-[10px] font-semibold px-2.5 py-1 rounded bg-amber-500/10 text-amber-300 border border-amber-500/30 flex items-center gap-1.5 animate-pulse">
                              <Loader2 className="w-3 h-3 animate-spin text-amber-400" />
                              <span>En cours de traitement OCR...</span>
                            </span>
                          ) : (
                            <span className="text-[10px] font-semibold px-2.5 py-1 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1.5">
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

          {/* TAB 2: AI BEHAVIOR & LEARNING LOOP MEMORY */}
          {activeTab === 'memory' && (
            <form onSubmit={handleSaveSettings} className="space-y-6">
              <div>
                <h2 className="text-base font-bold text-white">Comportement de l'IA & Mémoire Continue de l'Entreprise</h2>
                <p className="text-xs text-slate-400">
                  Définissez et ajustez les règles métier apprises qui guident la rédaction automatique pour votre entreprise.
                </p>
              </div>

              <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
                <div className="flex items-center justify-between">
                  <div className="space-y-0.5">
                    <label className="block text-xs font-bold text-white flex items-center gap-2">
                      <BrainCircuit className="w-4 h-4 text-sky-400" />
                      <span>Règles Apprises & Instructions Permanentes (Mémoire Active)</span>
                    </label>
                    <p className="text-[11px] text-slate-400">
                      Ces règles sont prioritaires et injectées dans chaque génération de chapitre de mémoire technique.
                    </p>
                  </div>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-300 border border-emerald-500/30">
                    Synchronisé en base
                  </span>
                </div>

                <textarea
                  rows={8}
                  value={economicSettings.systemPromptMemory}
                  onChange={(e) => setEconomicSettings({ ...economicSettings, systemPromptMemory: e.target.value })}
                  placeholder="- Toujours mentionner nos fiches FDES pour les bétons bas-carbone..."
                  className="w-full p-4 rounded-2xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-slate-200 text-xs focus:outline-none leading-relaxed font-mono"
                />

                <p className="text-[10px] text-slate-500">
                  Astuce : Vous pouvez ajouter une règle par ligne commençant par un tiret (-).
                </p>
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all disabled:opacity-50"
                >
                  {isSaving ? 'Enregistrement...' : 'Enregistrer les règles apprises'}
                </button>
              </div>
            </form>
          )}

          {/* TAB 3: ECONOMIC RULES & INFLATION */}
          {activeTab === 'economic' && (
            <form onSubmit={handleSaveSettings} className="space-y-6">
              <div>
                <h2 className="text-base font-bold text-white">Règles Économiques de Chiffrage</h2>
                <p className="text-xs text-slate-400">
                  Ces paramètres sont enregistrés en base Supabase et appliqués automatiquement au chiffrage des mémoires.
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
                  <label className="block text-xs font-bold text-slate-300">
                    Taux d'Ajustement Inflation (%)
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      step="0.1"
                      value={economicSettings.inflationRate}
                      onChange={(e) => setEconomicSettings({ ...economicSettings, inflationRate: parseFloat(e.target.value) || 0 })}
                      className="w-full pl-3 pr-8 py-2 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white font-mono text-sm focus:outline-none"
                    />
                    <Percent className="w-4 h-4 text-slate-500 absolute right-3 top-2.5" />
                  </div>
                  <p className="text-[10px] text-slate-500">Majoration appliquée aux bordereaux de prix pluriannuels.</p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
                  <label className="block text-xs font-bold text-slate-300">
                    Marge Cible Entreprise (%)
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      step="0.1"
                      value={economicSettings.targetMargin}
                      onChange={(e) => setEconomicSettings({ ...economicSettings, targetMargin: parseFloat(e.target.value) || 0 })}
                      className="w-full pl-3 pr-8 py-2 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white font-mono text-sm focus:outline-none"
                    />
                    <Percent className="w-4 h-4 text-slate-500 absolute right-3 top-2.5" />
                  </div>
                  <p className="text-[10px] text-slate-500">Objectif de rentabilité nette sur le chantier.</p>
                </div>

                <div className="p-4 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-2">
                  <label className="block text-xs font-bold text-slate-300">
                    Taux Horaire Ouvrier (€ HT / h)
                  </label>
                  <div className="relative">
                    <input
                      type="number"
                      step="0.5"
                      value={economicSettings.hourlyRateWorker}
                      onChange={(e) => setEconomicSettings({ ...economicSettings, hourlyRateWorker: parseFloat(e.target.value) || 0 })}
                      className="w-full pl-3 pr-8 py-2 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white font-mono text-sm focus:outline-none"
                    />
                    <span className="text-xs text-slate-500 absolute right-3 top-2.5 font-bold">€</span>
                  </div>
                  <p className="text-[10px] text-slate-500">Base horaire ouvrier chargée pour le déboursé sec.</p>
                </div>
              </div>

              {/* BYOK Option */}
              <div className="p-5 rounded-2xl bg-slate-950/60 border border-slate-800 space-y-2">
                <label className="block text-xs font-bold text-white flex items-center gap-2">
                  <Key className="w-3.5 h-3.5 text-amber-400" />
                  Votre Clé API IA Personnalisée (Optionnel — BYOK)
                </label>
                <input
                  type="password"
                  value={economicSettings.customApiKey}
                  onChange={(e) => setEconomicSettings({ ...economicSettings, customApiKey: e.target.value })}
                  placeholder="sk-ant-... ou sk-... (Laissez vide pour utiliser l'infrastructure btpAO incluse)"
                  className="w-full px-4 py-2.5 rounded-xl bg-slate-900 border border-slate-800 focus:border-sky-500 text-xs text-white font-mono focus:outline-none"
                />
                <p className="text-[10px] text-slate-500">
                  Si renseignée, vos générations de mémoires utiliseront directement votre quota personnel Anthropic ou OpenAI.
                </p>
              </div>

              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={isSaving}
                  className="px-6 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all disabled:opacity-50"
                >
                  {isSaving ? 'Enregistrement...' : 'Enregistrer les règles économiques'}
                </button>
              </div>
            </form>
          )}

          {/* TAB 4: TEAM */}
          {activeTab === 'team' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-base font-bold text-white">Conducteurs de travaux & Chiffreurs</h2>
                  <p className="text-xs text-slate-400">
                    Invitez vos collaborateurs pour leur permettre de rédiger les mémoires techniques.
                  </p>
                </div>
                <button
                  onClick={() => setShowInviteModal(true)}
                  className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all"
                >
                  <Plus className="w-3.5 h-3.5" />
                  <span>Inviter un collaborateur</span>
                </button>
              </div>

              <div className="bg-slate-900/80 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
                <div className="divide-y divide-slate-800">
                  {team.map((member) => (
                    <div key={member.id} className="p-4 flex items-center justify-between hover:bg-slate-800/40 transition-colors">
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-xl bg-sky-500/20 text-sky-300 font-bold text-xs flex items-center justify-center border border-sky-500/30">
                          {member.name.split(' ').map(n => n[0]).join('')}
                        </div>
                        <div>
                          <p className="text-xs font-bold text-white">{member.name}</p>
                          <p className="text-[11px] text-slate-400">{member.email}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-4">
                        <span className="text-[10px] font-semibold px-2.5 py-1 rounded bg-slate-800 text-slate-300 border border-slate-700 capitalize">
                          {member.role === 'conducteur' ? 'Conducteur de Travaux' : member.role === 'chiffreur' ? 'Ingénieur Études & Prix' : 'Admin Entreprise'}
                        </span>
                        <button
                          onClick={() => setTeam(prev => prev.filter(m => m.id !== member.id))}
                          className="p-1.5 rounded-lg text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* TAB 5: BRANDING */}
          {activeTab === 'branding' && (
            <div className="space-y-6">
              <div>
                <h2 className="text-base font-bold text-white">Charte Graphique du Mémoire Technique</h2>
                <p className="text-xs text-slate-400">
                  Uploadez votre template Word avec votre en-tête, logo et pied de page. Il sera utilisé comme base pour tous les exports de mémoires.
                </p>
              </div>

              {/* Word Template Upload */}
              <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
                <div className="flex items-center gap-2">
                  <FileCheck className="w-5 h-5 text-sky-400" />
                  <span className="text-xs font-bold text-white">Template Word de l'Entreprise (.docx)</span>
                </div>
                <p className="text-xs text-slate-400">
                  Le fichier .docx doit contenir votre en-tête personnalisé (logo + raison sociale), votre pied de page (SIRET, adresse) et vos styles de police. L'IA injectera le contenu généré directement dans ce template.
                </p>

                {wordTemplateInfo.has_template && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs">
                    <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span className="text-emerald-300 font-bold">Template actif :</span>
                    <span className="text-emerald-200">{wordTemplateInfo.filename}</span>
                  </div>
                )}

                <input
                  ref={wordTemplateInputRef}
                  type="file"
                  accept=".docx"
                  className="hidden"
                  onChange={(e) => setWordTemplateFile(e.target.files?.[0] || null)}
                />

                <div
                  onClick={() => wordTemplateInputRef.current?.click()}
                  className="border-2 border-dashed border-slate-700 hover:border-sky-500 rounded-2xl p-6 text-center cursor-pointer transition-colors bg-slate-950/40 group"
                >
                  <Upload className="w-8 h-8 text-sky-400 mx-auto mb-2 group-hover:scale-110 transition-transform" />
                  <p className="text-xs font-bold text-slate-200">
                    {wordTemplateFile ? wordTemplateFile.name : 'Cliquez pour sélectionner votre template Word'}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-1">
                    Format .docx uniquement — template avec en-tête, logo et pied de page
                  </p>
                </div>

                {wordTemplateFile && (
                  <button
                    type="button"
                    disabled={uploadingTemplate}
                    onClick={async () => {
                      if (!wordTemplateFile) return;
                      setUploadingTemplate(true);
                      setTemplateUploadSuccess(false);
                      try {
                        const { data: { session } } = await supabase.auth.getSession();
                        const token = session?.access_token;
                        const formData = new FormData();
                        formData.append('file', wordTemplateFile);
                        const res = await fetch('http://localhost:8000/api/knowledge/template/word', {
                          method: 'POST',
                          headers: { Authorization: `Bearer ${token}` },
                          body: formData,
                        });
                        if (!res.ok) throw new Error(await res.text());
                        const json = await res.json();
                        setWordTemplateInfo({ has_template: true, filename: json.filename, updated_at: new Date().toISOString() });
                        setWordTemplateFile(null);
                        setTemplateUploadSuccess(true);
                        setTimeout(() => setTemplateUploadSuccess(false), 4000);
                      } catch (err: any) {
                        alert('Erreur upload template : ' + err.message);
                      } finally {
                        setUploadingTemplate(false);
                      }
                    }}
                    className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold transition-all"
                  >
                    {uploadingTemplate ? (
                      <><Loader2 className="w-4 h-4 animate-spin" /> Envoi en cours...</>
                    ) : (
                      <><FileUp className="w-4 h-4" /> Enregistrer ce template Word</>
                    )}
                  </button>
                )}

                {templateUploadSuccess && (
                  <div className="flex items-center gap-2 p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-300 animate-in fade-in">
                    <CheckCircle2 className="w-4 h-4" />
                    Template enregistré ! Il sera utilisé pour le prochain export de mémoire.
                  </div>
                )}
              </div>

              {/* Color picker */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-4">
                  <label className="block text-xs font-bold text-white">Couleur Principale du Dossier</label>
                  <div className="flex items-center gap-3">
                    <input
                      type="color"
                      value={company.primaryColor}
                      onChange={(e) => setCompany({ ...company, primaryColor: e.target.value })}
                      className="w-12 h-12 rounded-xl bg-transparent border-0 cursor-pointer"
                    />
                    <div>
                      <p className="text-xs font-mono font-bold text-white">{company.primaryColor}</p>
                      <p className="text-[10px] text-slate-400">Utilisée pour les titres et tableaux du dossier.</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 6: BILLING */}
          {activeTab === 'billing' && (
            <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-6">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div>
                  <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    Abonnement Actif
                  </span>
                  <h2 className="text-xl font-bold text-white mt-1">Forfait Pro BTP (15 Dossiers / mois)</h2>
                  <p className="text-xs text-slate-400">Renouvellement automatique le 1er du mois prochain.</p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-black text-white">490 € <span className="text-xs text-slate-400 font-normal">HT / mois</span></p>
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex justify-between text-xs font-bold">
                  <span className="text-slate-300">Consommation du mois en cours</span>
                  <span className="text-sky-400">7 / 15 Dossiers utilisés</span>
                </div>
                <div className="w-full h-3 bg-slate-950 rounded-full overflow-hidden border border-slate-800">
                  <div className="h-full bg-gradient-to-r from-sky-500 to-emerald-500 rounded-full" style={{ width: '46%' }} />
                </div>
              </div>
            </div>
          )}

          {/* RGPD / Right to Erasure Section */}
          <div className="mt-12 p-6 rounded-2xl bg-rose-950/20 border border-rose-900/30 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-400" />
                <h3 className="text-sm font-bold text-rose-200">Droit à l'effacement & Suppression du compte (RGPD)</h3>
              </div>
              <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-rose-500/10 text-rose-400 border border-rose-500/20 font-bold">
                RGPD Art. 17
              </span>
            </div>
            
            <p className="text-xs text-rose-300/80 leading-relaxed">
              Vous pouvez à tout moment demander la suppression de votre compte. Conformément à notre politique de confidentialité, votre compte sera désactivé pendant <strong>30 jours</strong> (période de rétractation), après quoi l'ensemble de vos données personnelles sera définitivement effacé et les journaux d'audit anonymisés.
            </p>

            {deletionStatus.pending ? (
              <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/30 text-amber-200 space-y-2 text-xs">
                <div className="flex items-center justify-between">
                  <span className="font-bold flex items-center gap-1.5">
                    <Clock className="w-4 h-4 text-amber-400" />
                    Suppression programmée le {new Date(deletionStatus.scheduled_purge_at || '').toLocaleDateString('fr-FR')}
                  </span>
                  <button
                    onClick={async () => {
                      setIsDeletingAccount(true);
                      try {
                        await api.cancelAccountDeletion();
                        setDeletionStatus({ pending: false });
                      } catch (err: any) {
                        alert(err.message);
                      } finally {
                        setIsDeletingAccount(false);
                      }
                    }}
                    disabled={isDeletingAccount}
                    className="px-3 py-1.5 rounded-lg bg-amber-500 hover:bg-amber-400 text-slate-950 font-bold text-xs transition-colors"
                  >
                    {isDeletingAccount ? 'Annulation...' : 'Annuler la demande de suppression'}
                  </button>
                </div>
                <p className="text-[11px] text-amber-300/80">{deletionStatus.legal_notice}</p>
              </div>
            ) : (
              <div className="pt-2">
                <button
                  type="button"
                  onClick={() => setShowDeleteModal(true)}
                  className="px-4 py-2.5 rounded-xl bg-rose-600/20 hover:bg-rose-600/30 text-rose-300 hover:text-rose-200 border border-rose-500/30 text-xs font-bold transition-colors flex items-center gap-2"
                >
                  <Trash2 className="w-4 h-4 text-rose-400" />
                  <span>Demander la suppression de mon compte</span>
                </button>
              </div>
            )}
          </div>
        </>
      )}

      {/* RGPD Account Deletion Modal */}
      {showDeleteModal && (
        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-rose-900/50 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <div className="flex items-center gap-2 text-rose-400">
              <AlertTriangle className="w-6 h-6 shrink-0" />
              <h3 className="text-base font-bold text-white">Confirmer la demande de suppression</h3>
            </div>
            
            <div className="space-y-2 text-xs text-slate-300 leading-relaxed">
              <p>
                Votre compte entrera en état de <strong>désactivation temporaire pendant 30 jours</strong>. Durant ce délai, vous pourrez annuler la demande à tout moment depuis cet écran.
              </p>
              <p className="text-[11px] text-slate-400">
                Passé ce délai de 30 jours, la suppression de vos données personnelles est <strong>irréversible</strong>. Les pièces de marchés publics et journaux d'audit anonymisés sont conservés conformément aux délais légaux applicables (garantie décennale, recours contentieux).
              </p>
            </div>

            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={() => setShowDeleteModal(false)}
                disabled={isDeletingAccount}
                className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-colors"
              >
                Annuler
              </button>
              <button
                type="button"
                disabled={isDeletingAccount}
                onClick={async () => {
                  setIsDeletingAccount(true);
                  try {
                    const res = await api.requestAccountDeletion();
                    setDeletionStatus({
                      pending: true,
                      scheduled_purge_at: res.scheduled_purge_at,
                      message: res.message,
                      legal_notice: res.legal_notice,
                    });
                    setShowDeleteModal(false);
                  } catch (err: any) {
                    alert('Erreur : ' + (err.message || 'Erreur inconnue'));
                  } finally {
                    setIsDeletingAccount(false);
                  }
                }}
                className="flex-1 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg transition-all flex items-center justify-center gap-1.5"
              >
                {isDeletingAccount ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Traitement...</>
                ) : (
                  'Confirmer la suppression'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invite Modal */}
      {showInviteModal && (

        <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 max-w-md w-full shadow-2xl space-y-4">
            <h3 className="text-base font-bold text-white">Inviter un nouveau collaborateur</h3>
            <p className="text-xs text-slate-400">
              Un e-mail sera envoyé pour lui permettre d'accéder aux dossiers de l'entreprise.
            </p>

            <form onSubmit={handleInvite} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Adresse e-mail</label>
                <input
                  type="email"
                  required
                  value={inviteEmail}
                  onChange={(e) => setInviteEmail(e.target.value)}
                  placeholder="conducteur@eiffabtp.fr"
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white text-xs focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1">Rôle</label>
                <select
                  value={inviteRole}
                  onChange={(e) => setInviteRole(e.target.value as any)}
                  className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white text-xs focus:outline-none"
                >
                  <option value="conducteur">Conducteur de Travaux</option>
                  <option value="chiffreur">Ingénieur Études & Chiffrage</option>
                </select>
              </div>

              <div className="flex gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowInviteModal(false)}
                  className="flex-1 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold transition-colors"
                >
                  Annuler
                </button>
                <button
                  type="submit"
                  className="flex-1 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all"
                >
                  Envoyer l'invitation
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
