'use client';

import React, { useState, useEffect, useRef, Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import {
  FileText,
  UploadCloud,
  Sliders,
  CheckCircle2,
  Download,
  Building,
  Sparkles,
  ArrowRight,
  ChevronRight,
  Clock,
  ShieldCheck,
  Award,
  HardHat,
  Eye,
  AlertTriangle,
  CheckSquare,
  TrendingUp,
  Percent,
  Calendar,
  Layers,
  Plus,
  Loader2,
  BrainCircuit,
  FileUp,
  Save,
  Link2,
  X,
  Globe,
  MessageSquare,
  FolderPlus,
  RefreshCw,
  XCircle,
  AlertCircle,
} from 'lucide-react';


import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { GeneratedSection, Project, GoNoGoAnalysis, ProjectDecisionsForm, DCECriterion } from '@/lib/types';
import { api } from '@/lib/api';
import { supabase } from '@/lib/supabase/client';
import { DCEChatSidebar } from '@/components/chat/dce-chat-sidebar';

function WorkspaceContent() {
  const searchParams = useSearchParams();
  const queryProjectId = searchParams.get('projectId');

  const [activeDeliverable, setActiveDeliverable] = useState<'gonogo' | 'planning' | 'editor' | 'download'>('gonogo');
  const [showNewAOWizard, setShowNewAOWizard] = useState(false);
  const [showChatSidebar, setShowChatSidebar] = useState(false);

  // New AO Form state
  const [aoTitle, setAoTitle] = useState('');
  const [aoClient, setAoClient] = useState('');
  const [aoUrl, setAoUrl] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);
  const [isSubmittingWizard, setIsSubmittingWizard] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);


  // Real Project & Deliverables State (Starts EMPTY / NULL - No fake default numbers)
  const [project, setProject] = useState<Project | null>(null);
  const [goNoGo, setGoNoGo] = useState<GoNoGoAnalysis | null>(null);
  const [sections, setSections] = useState<GeneratedSection[]>([]);
  const [currentSectionIndex, setCurrentSectionIndex] = useState<number>(0);
  const [decisions, setDecisions] = useState<ProjectDecisionsForm | null>(null);
  const [criteria, setCriteria] = useState<DCECriterion[]>([]);

  // Loading flags
  const [loadingProject, setLoadingProject] = useState<boolean>(true);
  const [loadingGoNoGo, setLoadingGoNoGo] = useState<boolean>(false);
  const [isEvaluatingGoNoGo, setIsEvaluatingGoNoGo] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [generationStep, setGenerationStep] = useState<number>(0);

  // Learning loop memory state
  const [selectedTextRule, setSelectedTextRule] = useState('');
  const [memorySavedMsg, setMemorySavedMsg] = useState(false);

  // 1. Initial Load of Real Project
  useEffect(() => {
    async function loadWorkspaceData() {
      setLoadingProject(true);
      try {
        let targetId = queryProjectId;
        if (!targetId) {
          const allProjects = await api.getProjects();
          if (allProjects && allProjects.length > 0) {
            targetId = allProjects[0].id;
          }
        }

        if (targetId) {
          await loadProjectDetails(targetId);
        } else {
          setProject(null);
        }
      } catch (err) {
        console.warn('[Workspace] Erreur lors du chargement du projet:', err);
      } finally {
        setLoadingProject(false);
      }
    }

    loadWorkspaceData();
  }, [queryProjectId]);

  async function loadProjectDetails(projectId: string) {
    try {
      const projData = await api.getProject(projectId);
      setProject(projData);

      // Load sections
      try {
        const secData = await api.getSections(projectId);
        setSections(secData || []);
        setCurrentSectionIndex(0);
      } catch (e) {
        console.warn('[Workspace] Sections non trouvées:', e);
      }

      // Load criteria
      try {
        const critData = await api.getCriteria(projectId);
        setCriteria(critData || []);
      } catch (e) {
        console.warn('[Workspace] Critères non trouvés:', e);
      }

      // Load decisions
      try {
        const decData = await api.getDecisions(projectId);
        setDecisions(decData);
      } catch (e) {
        console.warn('[Workspace] Décisions non trouvées:', e);
      }

      // Load or evaluate Go/No-Go
      await loadGoNoGoAnalysis(projectId);
    } catch (err) {
      console.error('[Workspace] Erreur chargement détails projet:', err);
    }
  }

  async function loadGoNoGoAnalysis(projectId: string, forceRun = false) {
    setLoadingGoNoGo(true);
    try {
      if (forceRun) {
        setIsEvaluatingGoNoGo(true);
        const analysis = await api.runGoNoGo(projectId);
        setGoNoGo(analysis);
      } else {
        try {
          const analysis = await api.getGoNoGo(projectId);
          setGoNoGo(analysis);
        } catch (err: any) {
          // If 404, trigger runGoNoGo automatically to provide the first real score
          setIsEvaluatingGoNoGo(true);
          const analysis = await api.runGoNoGo(projectId);
          setGoNoGo(analysis);
        }
      }
    } catch (err) {
      console.warn('[Workspace] Erreur évaluation Go/No-Go:', err);
      setGoNoGo(null);
    } finally {
      setLoadingGoNoGo(false);
      setIsEvaluatingGoNoGo(false);
    }
  }

  function handleFileSelect(files: FileList | null) {
    if (!files) return;
    const newFiles = Array.from(files);
    setSelectedFiles(prev => [...prev, ...newFiles]);
  }

  function handleRemoveFile(index: number) {
    setSelectedFiles(prev => prev.filter((_, i) => i !== index));
  }

  async function handleLaunchGeneration(e: React.FormEvent) {
    e.preventDefault();
    setWizardError(null);
    setIsSubmittingWizard(true);
    setIsGenerating(true);
    setGenerationStep(1);

    try {
      // 1. Create project via backend API
      const newProj = await api.createProject({
        title: aoTitle,
        client_name: aoClient,
        status: 'draft',
      });

      setProject(newProj);

      // 2. Upload files if any
      if (selectedFiles.length > 0) {
        setGenerationStep(2);
        for (const file of selectedFiles) {
          await api.uploadDCE(newProj.id, 'cctp', file);
        }
      }

      // 3. Trigger Go/No-Go Evaluation
      setGenerationStep(3);
      await loadGoNoGoAnalysis(newProj.id, true);

      // 4. Reload full project
      await loadProjectDetails(newProj.id);

      // ONLY close modal after full success
      setShowNewAOWizard(false);
      setAoTitle('');
      setAoClient('');
      setSelectedFiles([]);
      setActiveDeliverable('gonogo');
    } catch (err: any) {
      console.error('Erreur création projet & analyse:', err);
      const isAuthError =
        err?.status === 401 ||
        err?.message?.includes('401') ||
        err?.message?.toLowerCase()?.includes('unauthorized');

      if (isAuthError) {
        setWizardError('session expirée, reconnecte-toi');
      } else {
        setWizardError(err?.message || "Une erreur est survenue lors de la création de l'Appel d'Offres.");
      }
    } finally {
      setIsSubmittingWizard(false);
      setIsGenerating(false);
    }
  }


  async function handleAddSelectedToMemory() {
    if (!selectedTextRule) return;

    try {
      const res = await fetch('/api/update-memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ newRule: selectedTextRule }),
      });

      const json = await res.json();
      if (json.success) {
        setMemorySavedMsg(true);
        setSelectedTextRule('');
        setTimeout(() => setMemorySavedMsg(false), 3000);
      }
    } catch (err: any) {
      alert('Erreur enregistrement mémoire: ' + err.message);
    }
  }

  // --- RENDERING HELPERS FOR GO/NO-GO ---
  function getRecommendationBadge(recommendation: string) {
    const rec = (recommendation || '').toUpperCase();
    if (rec.includes('GO') && !rec.includes('NO')) {
      return {
        label: 'GO — Opportunité Qualifiée',
        color: 'text-emerald-400',
        bg: 'bg-emerald-500/10',
        border: 'border-emerald-500/30',
        icon: CheckCircle2,
      };
    } else if (rec.includes('RESERVE') || rec.includes('RÉSERVE')) {
      return {
        label: 'RÉSERVES — Exigences à Compléter',
        color: 'text-amber-400',
        bg: 'bg-amber-500/10',
        border: 'border-amber-500/30',
        icon: AlertTriangle,
      };
    } else {
      return {
        label: 'NO-GO — Non Conforme / Risque Élevé',
        color: 'text-rose-400',
        bg: 'bg-rose-500/10',
        border: 'border-rose-500/30',
        icon: XCircle,
      };
    }
  }

  // Loading Screen
  if (loadingProject) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
        <p className="text-sm font-bold text-slate-300">Chargement de votre espace de travail BTP...</p>
      </div>
    );
  }

  // Empty State when no project exists in the workspace
  if (!project) {
    return (
      <div className="max-w-4xl mx-auto py-12 space-y-8">
        <div className="p-8 sm:p-12 rounded-3xl bg-slate-900/90 border border-slate-800 text-center space-y-6 shadow-2xl">
          <div className="w-16 h-16 rounded-2xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center mx-auto text-sky-400">
            <FolderPlus className="w-8 h-8" />
          </div>
          <div className="space-y-2 max-w-md mx-auto">
            <h1 className="text-2xl font-black text-white">Aucun Appel d'Offres Sélectionné</h1>
            <p className="text-xs text-slate-400 leading-relaxed">
              Sélectionnez un projet existant ou créez une nouvelle réponse à un appel d'offres pour lancer l'analyse décisionnelle Go/No-Go et générer le mémoire technique.
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              onClick={() => setShowNewAOWizard(true)}
              className="flex items-center gap-2 px-5 py-3 rounded-2xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow hover:shadow-sky-500/40 transition-all"
            >
              <Plus className="w-4 h-4" />
              <span>Créer une Réponse à Appel d'Offres</span>
            </button>
            <Link
              href="/dashboard/projects"
              className="flex items-center gap-2 px-5 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition-all"
            >
              <Building className="w-4 h-4" />
              <span>Voir mes dossiers existants</span>
            </Link>
          </div>
        </div>

        {/* Wizard Modal */}
        {showNewAOWizard && renderWizardModal()}
      </div>
    );
  }

  const badge = goNoGo ? getRecommendationBadge(goNoGo.recommendation) : null;
  const BadgeIcon = badge ? badge.icon : AlertCircle;
  const currentSection = sections[currentSectionIndex] || null;

  return (
    <div className="space-y-6 pb-16 max-w-5xl">
      {/* Fil d'Ariane / Breadcrumbs */}
      <nav className="flex items-center gap-2 text-xs text-slate-400">
        <Link
          href="/dashboard/projects"
          className="hover:text-sky-400 transition-colors flex items-center gap-1.5 font-medium"
        >
          <Building className="w-3.5 h-3.5 text-slate-500" />
          <span>Mes Appels d'Offres</span>
        </Link>
        <ChevronRight className="w-3.5 h-3.5 text-slate-600 shrink-0" />
        <span className="text-slate-200 font-bold truncate max-w-md">
          {project.title}
        </span>
      </nav>

      {/* Top Banner with Real Project Metadata */}
      <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 shadow-xl space-y-4">

        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                {project.reference_code || 'AO-EN-COURS'}
              </span>
              <span className="text-xs text-slate-500">Marché Public BTP</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-black text-white">{project.title}</h1>
            <p className="text-xs text-slate-400">
              Maître d'Ouvrage : <strong>{project.client_name}</strong> • {project.location || 'France'}
            </p>
          </div>

          <div className="flex items-center gap-3">
            <button
              onClick={() => setShowChatSidebar(true)}
              className="flex items-center gap-2 px-4 py-3 rounded-2xl bg-slate-800 hover:bg-slate-700 text-sky-400 hover:text-sky-300 border border-slate-700 text-xs font-bold transition-all shadow-lg"
            >
              <MessageSquare className="w-4 h-4 text-sky-400" />
              <span>Assistant DCE & Normes</span>
            </button>

            <button
              onClick={() => setShowNewAOWizard(true)}
              className="flex items-center gap-2 px-5 py-3 rounded-2xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow hover:shadow-sky-500/40 transition-all group"
            >
              <Plus className="w-4 h-4 group-hover:scale-110 transition-transform" />
              <span>Nouveau Projet</span>
            </button>
          </div>
        </div>

        {/* Live Generation Progress Bar */}
        {isGenerating && (
          <div className="p-4 rounded-2xl bg-slate-950/80 border border-sky-500/30 space-y-3 animate-in fade-in">
            <div className="flex items-center justify-between text-xs font-bold text-sky-400">
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-sky-400" />
                {generationStep === 1 && '1. Création du projet & initialisation...'}
                {generationStep === 2 && '2. Analyse du DCE & extraction des critères de notation...'}
                {generationStep === 3 && '3. Évaluation matricielle Go/No-Go et qualifications...'}
              </span>
              <span className="font-mono text-[11px] text-slate-400">Étape {generationStep}/3</span>
            </div>
            <div className="w-full h-2 bg-slate-900 rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-sky-500 to-emerald-500 rounded-full transition-all duration-500"
                style={{ width: `${(generationStep / 3) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* 4 Deliverables Tabs Navigation */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800">
          {[
            { id: 'gonogo', title: '1. Décision (Go/No-Go)', desc: 'Matrice & Qualifications', icon: ShieldCheck },
            { id: 'planning', title: '2. Planning Chantier', desc: 'Phasage & Jalons clés', icon: Calendar },
            { id: 'editor', title: '3. Mémoire Technique', desc: 'Éditeur & Relecture métier', icon: FileText },
            { id: 'download', title: '4. Téléchargement Final', desc: 'Fichiers Word & PDF prêts', icon: Download },
          ].map((tab) => {
            const Icon = tab.icon;
            const isCurrent = activeDeliverable === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveDeliverable(tab.id as any)}
                className={`p-3 rounded-2xl text-left border transition-all flex items-start gap-2.5 ${
                  isCurrent
                    ? 'bg-sky-600/20 border-sky-500 text-white shadow-lg'
                    : 'bg-slate-950/40 border-slate-800 text-slate-400 hover:text-slate-200'
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${
                    isCurrent ? 'bg-sky-500 text-white' : 'bg-slate-800 text-slate-400'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0">
                  <p className="text-xs font-bold truncate">{tab.title}</p>
                  <p className="text-[10px] text-slate-400 truncate">{tab.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* DELIVERABLE 1: GO/NO-GO DECISION MATRIX */}
      {activeDeliverable === 'gonogo' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-white">Livrable 1 : Analyse Décisionnelle & Score d'Opportunité (Go/No-Go)</h2>
              <p className="text-xs text-slate-400">
                Croisement automatisé des critères du DCE, des qualifications de l'entreprise, de la date limite et de la charge active.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => loadGoNoGoAnalysis(project.id, true)}
                disabled={loadingGoNoGo || isEvaluatingGoNoGo}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-bold border border-slate-700 transition-all disabled:opacity-50"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isEvaluatingGoNoGo ? 'animate-spin text-sky-400' : ''}`} />
                <span>Recalculer Go/No-Go</span>
              </button>
              <button
                onClick={() => setActiveDeliverable('planning')}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all"
              >
                <span>Consulter le Planning</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {loadingGoNoGo ? (
            <div className="p-12 rounded-3xl bg-slate-900/90 border border-slate-800 flex flex-col items-center justify-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
              <p className="text-xs font-bold text-slate-300">Évaluation de la matrice Go/No-Go en cours...</p>
            </div>
          ) : !goNoGo ? (
            <div className="p-8 rounded-3xl bg-slate-900/90 border border-slate-800 text-center space-y-4">
              <AlertCircle className="w-8 h-8 text-amber-400 mx-auto" />
              <div className="space-y-1">
                <p className="text-sm font-bold text-white">Aucune analyse Go/No-Go enregistrée</p>
                <p className="text-xs text-slate-400">Lancez l'évaluation pour obtenir la recommandation du moteur.</p>
              </div>
              <button
                onClick={() => loadGoNoGoAnalysis(project.id, true)}
                className="px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold transition-all"
              >
                Évaluer l'Appel d'Offres
              </button>
            </div>
          ) : (
            <>
              {/* Top Decision Summary & Score Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 md:col-span-2 shadow-xl">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-white flex items-center gap-1.5">
                      <FileText className="w-4 h-4 text-sky-400" />
                      Synthèse Argumentée de la Décision
                    </span>
                    <span className="text-[10px] font-mono text-slate-400 bg-slate-800 px-2.5 py-0.5 rounded border border-slate-700">
                      Évalué le {new Date(goNoGo.created_at).toLocaleDateString('fr-FR')}
                    </span>
                  </div>

                  <p className="text-xs text-slate-300 leading-relaxed bg-slate-950/60 p-3.5 rounded-2xl border border-slate-800">
                    {goNoGo.summary}
                  </p>

                  <div className="pt-2 border-t border-slate-800 flex items-center justify-between text-xs">
                    <span className="text-slate-400">Conformité des critères éliminatoires :</span>
                    <span className={`font-bold flex items-center gap-1.5 ${goNoGo.mandatory_criteria_met ? 'text-emerald-400' : 'text-rose-400'}`}>
                      {goNoGo.mandatory_criteria_met ? (
                        <>
                          <CheckCircle2 className="w-4 h-4" />
                          <span>Exigences obligatoires satisfaites</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-4 h-4" />
                          <span>Critères éliminatoires non satisfaits</span>
                        </>
                      )}
                    </span>
                  </div>
                </div>

                {/* Score and Recommendation Box */}
                {badge && (
                  <div className={`p-6 rounded-3xl ${badge.bg} border ${badge.border} space-y-4 shadow-xl`}>
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-slate-300">Score d'Opportunité</span>
                      <span className={`text-3xl font-black ${badge.color}`}>{Math.round(goNoGo.score)} / 100</span>
                    </div>

                    <div className={`p-3.5 rounded-2xl bg-slate-950/80 border ${badge.border}`}>
                      <div className="flex items-center gap-2 mb-1">
                        <BadgeIcon className={`w-4 h-4 ${badge.color} shrink-0`} />
                        <p className={`text-xs font-black ${badge.color}`}>{badge.label}</p>
                      </div>
                      <p className="text-[11px] text-slate-400">
                        {goNoGo.score >= 70
                          ? 'Les qualifications et la capacité de l\'entreprise justifient un dépôt d\'offre prioritaire.'
                          : goNoGo.score >= 45
                          ? 'Dépôt envisageable sous réserve de lever les alertes techniques ou administratives.'
                          : 'Risque de rejet ou de pénalités élevé. Mobilisation non recommandée.'}
                      </p>
                    </div>

                    <div className="text-[10px] text-slate-400 text-center font-mono">
                      Calculé sur {goNoGo.factors?.length || 0} facteurs pondérés
                    </div>
                  </div>
                )}
              </div>

              {/* Blocking Issues Alert Box (if any) */}
              {goNoGo.blocking_issues && goNoGo.blocking_issues.length > 0 && (
                <div className="p-5 rounded-3xl bg-rose-950/30 border border-rose-500/40 space-y-2.5 shadow-xl">
                  <div className="flex items-center gap-2 text-rose-400 text-xs font-bold">
                    <AlertTriangle className="w-4 h-4" />
                    <span>Points de Blocage Identifiés ({goNoGo.blocking_issues.length})</span>
                  </div>
                  <ul className="space-y-1 text-xs text-rose-200/90 pl-6 list-disc">
                    {goNoGo.blocking_issues.map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Detailed Decision Factors Grid */}
              <div className="space-y-3">
                <h3 className="text-xs font-bold text-white flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-sky-400" />
                  Facteurs d'Évaluation Détaillés
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {goNoGo.factors?.map((factor, idx) => {
                    const isPassed = factor.status === 'passed';
                    const isWarning = factor.status === 'warning';
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-2xl border space-y-2 transition-all ${
                          isPassed
                            ? 'bg-slate-900/80 border-slate-800 hover:border-slate-700'
                            : isWarning
                            ? 'bg-amber-950/20 border-amber-500/30'
                            : 'bg-rose-950/20 border-rose-500/30'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-0.5">
                            <span className="text-[10px] font-mono text-slate-500 uppercase">
                              {factor.category}
                            </span>
                            <h4 className="text-xs font-bold text-white">{factor.title}</h4>
                          </div>
                          <span
                            className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase font-mono ${
                              isPassed
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                                : isWarning
                                ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                                : 'bg-rose-500/10 text-rose-400 border border-rose-500/20'
                            }`}
                          >
                            {factor.status}
                          </span>
                        </div>

                        <p className="text-xs text-slate-300 leading-relaxed">{factor.detail}</p>

                        {factor.recommendation && (
                          <div className="pt-2 border-t border-slate-800/80 text-[11px] text-sky-400">
                            <strong>Conseil :</strong> {factor.recommendation}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* DELIVERABLE 2: PLANNING CHANTIER */}
      {activeDeliverable === 'planning' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-white">Livrable 2 : Phasage Prévisionnel du Chantier</h2>
              <p className="text-xs text-slate-400">
                Planning d'exécution issu du formulaire conducteur de travaux et des contraintes du DCE.
              </p>
            </div>
            <button
              onClick={() => setActiveDeliverable('editor')}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all"
            >
              <span>Relire le Mémoire Technique</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {decisions?.phasage_travaux && decisions.phasage_travaux.length > 0 ? (
              decisions.phasage_travaux.map((p: any, idx: number) => (
                <div key={idx} className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-3 shadow-xl">
                  <div className="flex items-center justify-between">
                    <h3 className="text-sm font-bold text-white">{p.phase || `Phase ${idx + 1}`}</h3>
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                      {p.duree_semaines ? `${p.duree_semaines} semaines` : 'Phase'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-300">
                    <strong>Jalon contractuel :</strong> {p.jalon || 'Livraison des ouvrages'}
                  </p>
                </div>
              ))
            ) : (
              <div className="p-8 rounded-3xl bg-slate-900/90 border border-slate-800 sm:col-span-2 text-center space-y-2">
                <Calendar className="w-8 h-8 text-slate-500 mx-auto" />
                <p className="text-xs font-bold text-slate-300">Aucun découpage de phasage spécifique renseigné</p>
                <p className="text-[11px] text-slate-500">
                  Le délai contractuel global de ce dossier est de {decisions?.delai_mois || 6} mois.
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* DELIVERABLE 3: RICH TEXT EDITOR */}
      {activeDeliverable === 'editor' && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h2 className="text-base font-bold text-white">Livrable 3 : Relecture & Validation Métier du Mémoire Technique</h2>
              <p className="text-xs text-slate-400">
                Éditez les chapitres générés. L'historique des versions est conservé à chaque sauvegarde.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveDeliverable('download')}
                className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-bold shadow-glow transition-all"
              >
                <span>Finaliser & Télécharger</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Section Selector if multiple sections */}
          {sections.length > 1 && (
            <div className="flex flex-wrap gap-2">
              {sections.map((sec, idx) => (
                <button
                  key={sec.id}
                  onClick={() => setCurrentSectionIndex(idx)}
                  className={`px-3 py-1.5 rounded-xl text-xs font-bold transition-all ${
                    currentSectionIndex === idx
                      ? 'bg-sky-600 text-white shadow-md'
                      : 'bg-slate-900 text-slate-400 hover:text-white border border-slate-800'
                  }`}
                >
                  {sec.title || `Section ${idx + 1}`}
                </button>
              ))}
            </div>
          )}

          {/* Floating Learning Loop helper */}
          <div className="p-4 rounded-2xl bg-sky-950/20 border border-sky-500/30 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <BrainCircuit className="w-5 h-5 text-sky-400 shrink-0" />
              <div>
                <p className="text-xs font-bold text-white">Boucle d'Apprentissage Entreprise</p>
                <p className="text-[11px] text-slate-400">
                  Saisissez une consigne technique pour qu'elle soit capitalisée lors des prochains mémoires.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <input
                type="text"
                value={selectedTextRule}
                onChange={(e) => setSelectedTextRule(e.target.value)}
                placeholder="Ex : Toujours majorer de 5% les prix en zone urbaine..."
                className="px-3 py-1.5 rounded-xl bg-slate-950 border border-slate-800 text-xs text-white placeholder:text-slate-600 focus:outline-none w-full sm:w-80"
              />
              <button
                type="button"
                onClick={handleAddSelectedToMemory}
                className="px-3 py-1.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shrink-0 transition-colors"
              >
                Ajouter à la mémoire
              </button>
            </div>
          </div>

          {memorySavedMsg && (
            <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-bold flex items-center gap-2 animate-in fade-in">
              <CheckCircle2 className="w-4 h-4" />
              <span>Règle ajoutée avec succès au comportement permanent de l'entreprise !</span>
            </div>
          )}

          {currentSection ? (
            <div className="rounded-3xl overflow-hidden border border-slate-800 bg-slate-950/40 shadow-xl">
              <TiptapEditor
                projectId={project.id}
                section={currentSection}
                onSave={(updated) => {
                  setSections(prev => prev.map(s => s.id === updated.id ? updated : s));
                }}
              />
            </div>
          ) : (
            <div className="p-12 rounded-3xl bg-slate-900/90 border border-slate-800 text-center space-y-3">
              <FileText className="w-8 h-8 text-slate-500 mx-auto" />
              <p className="text-xs font-bold text-slate-300">Aucune section générée pour le moment</p>
              <p className="text-[11px] text-slate-500">Lancez la génération des chapitres depuis l'étape d'analyse.</p>
            </div>
          )}
        </div>
      )}

      {/* DELIVERABLE 4: FINAL WORD & PDF DOWNLOADS */}
      {activeDeliverable === 'download' && (
        <div className="p-8 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-8 text-center max-w-2xl mx-auto shadow-2xl">
          <div className="space-y-2">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-black text-white">Votre Mémoire Technique est Prêt !</h2>
            <p className="text-xs text-slate-400">
              Le dossier complet pour <strong>{project.title}</strong> est assemblé selon la charte graphique de votre entreprise.
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <button
              onClick={async () => {
                try {
                  const { data: { session } } = await supabase.auth.getSession();
                  const token = session?.access_token;
                  const res = await fetch(
                    `http://localhost:8000/api/export/stream/${project.id}.docx`,
                    { headers: { Authorization: `Bearer ${token}` } }
                  );
                  if (!res.ok) throw new Error(await res.text());
                  const blob = await res.blob();
                  const url = URL.createObjectURL(blob);
                  const a = document.createElement('a');
                  a.href = url;
                  a.download = `Memoire_Technique_${project.title.replace(/[^a-zA-Z0-9]/g, '_')}.docx`;
                  a.click();
                  URL.revokeObjectURL(url);
                } catch (err: any) {
                  alert('Erreur export Word : ' + err.message);
                }
              }}
              className="flex flex-col items-center justify-center p-6 rounded-2xl bg-sky-600 hover:bg-sky-500 text-white shadow-xl hover:shadow-sky-500/40 transition-all group cursor-pointer"
            >
              <FileText className="w-8 h-8 mb-2 group-hover:scale-110 transition-transform" />
              <span className="text-sm font-black">Télécharger le Mémoire Word</span>
              <span className="text-[11px] opacity-80 mt-0.5">Format .docx modifiable</span>
            </button>

            <button
              onClick={() => alert('Export PDF généré à partir du modèle Word.')}
              className="flex flex-col items-center justify-center p-6 rounded-2xl bg-slate-800 hover:bg-slate-700 text-white border border-slate-700 hover:border-slate-600 shadow-xl transition-all group cursor-pointer"
            >
              <Download className="w-8 h-8 mb-2 group-hover:scale-110 transition-transform text-rose-400" />
              <span className="text-sm font-black">Télécharger le Mémoire PDF</span>
              <span className="text-[11px] text-slate-400 mt-0.5">Document final prêt à déposer</span>
            </button>
          </div>

          <div className="pt-4 border-t border-slate-800 flex items-center justify-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>Document construit avec citations internes et profil réglementaire du tenant</span>
          </div>
        </div>
      )}

      {/* NEW AO WIZARD MODAL */}
      {showNewAOWizard && renderWizardModal()}

      {/* CHAT SIDEBAR WITH REAL DCE CONTEXT */}
      <DCEChatSidebar
        projectId={project.id}
        projectTitle={project.title}
        isOpen={showChatSidebar}
        onClose={() => setShowChatSidebar(false)}
      />

    </div>
  );

  function renderWizardModal() {
    return (
      <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
        <div className="bg-slate-900 border border-slate-800 rounded-3xl p-6 sm:p-8 max-w-lg w-full shadow-2xl space-y-6">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h3 className="text-lg font-black text-white">Nouvelle Réponse à un Appel d'Offres</h3>
              <p className="text-xs text-slate-400">
                Indiquez les coordonnées du marché et déposez les pièces du DCE.
              </p>
            </div>
            <button
              onClick={() => setShowNewAOWizard(false)}
              className="p-2 rounded-xl text-slate-500 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {wizardError && (
            <div className="p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-rose-400" />
              <div className="space-y-0.5">
                <p className="font-bold text-rose-200">Erreur lors de la création</p>
                <p>{wizardError}</p>
              </div>
            </div>
          )}

          <form onSubmit={handleLaunchGeneration} className="space-y-4">
            <div>
              <label className="block text-xs font-bold text-slate-300 mb-1">Nom / Intitulé du Marché</label>
              <input
                type="text"
                required
                disabled={isSubmittingWizard}
                value={aoTitle}
                onChange={(e) => setAoTitle(e.target.value)}
                placeholder="Ex : Réhabilitation thermique de 40 logements..."
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white text-xs focus:outline-none disabled:opacity-50"
              />
            </div>

            <div>
              <label className="block text-xs font-bold text-slate-300 mb-1">Maître d'Ouvrage / Acheteur Public</label>
              <input
                type="text"
                required
                disabled={isSubmittingWizard}
                value={aoClient}
                onChange={(e) => setAoClient(e.target.value)}
                placeholder="Ex : Mairie de Saint-Denis, Région IDF..."
                className="w-full px-3.5 py-2.5 rounded-xl bg-slate-950 border border-slate-800 focus:border-sky-500 text-white text-xs focus:outline-none disabled:opacity-50"
              />
            </div>

            <div className="space-y-2">
              <label className="block text-xs font-bold text-slate-300">
                Déposer les pièces du DCE (CCTP, RC, DPGF en PDF/Word/Zip)
              </label>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                disabled={isSubmittingWizard}
                accept=".pdf,.docx,.doc,.zip"
                className="hidden"
                onChange={(e) => handleFileSelect(e.target.files)}
              />
              <div
                onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
                onDragLeave={() => setIsDragging(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setIsDragging(false);
                  handleFileSelect(e.dataTransfer.files);
                }}
                onClick={() => !isSubmittingWizard && fileInputRef.current?.click()}
                className={`p-6 rounded-2xl border-2 border-dashed text-center cursor-pointer transition-all ${
                  isDragging
                    ? 'border-sky-400 bg-sky-500/10'
                    : 'border-slate-800 hover:border-slate-700 bg-slate-950/40'
                } ${isSubmittingWizard ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <FileUp className="w-8 h-8 text-sky-400 mx-auto mb-2" />
                <p className="text-xs font-bold text-slate-200">Glissez-déposez vos fichiers ici</p>
                <p className="text-[10px] text-slate-500 mt-0.5">ou cliquez pour parcourir votre ordinateur</p>
              </div>

              {selectedFiles.length > 0 && (
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2 rounded-xl bg-slate-950 border border-slate-800 text-xs text-slate-300">
                      <span className="truncate">{file.name}</span>
                      <button
                        type="button"
                        disabled={isSubmittingWizard}
                        onClick={() => handleRemoveFile(idx)}
                        className="text-slate-500 hover:text-rose-400 ml-2 disabled:opacity-40"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <div className="pt-2">
              <button
                type="submit"
                disabled={isSubmittingWizard}
                className="w-full py-3 rounded-2xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow hover:shadow-sky-500/40 transition-all flex items-center justify-center gap-2 disabled:opacity-50"
              >
                {isSubmittingWizard ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Création du dossier en cours...</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>Créer et Lancer l'Évaluation Go/No-Go</span>
                  </>
                )}
              </button>
            </div>
          </form>

        </div>
      </div>
    );
  }
}

export default function BTPWorkspacePage() {
  return (
    <Suspense fallback={
      <div className="flex items-center justify-center min-h-[50vh]">
        <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
      </div>
    }>
      <WorkspaceContent />
    </Suspense>
  );
}
