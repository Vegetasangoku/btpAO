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
  FolderPlus,
  RefreshCw,
  XCircle,
  AlertCircle,
} from 'lucide-react';

import { TiptapEditor } from '@/components/editor/tiptap-editor';
import { GeneratedSection, Project, GoNoGoAnalysis, ProjectDecisionsForm, DCECriterion } from '@/lib/types';
import { api, fetchAuthenticatedBlobUrl } from '@/lib/api';
import { supabase } from '@/lib/supabase/client';
import { useTranslation } from '@/components/i18n-provider';

function WorkspaceContent() {
  const searchParams = useSearchParams();
  const queryProjectId = searchParams.get('projectId');
  const { t } = useTranslation();

  const [activeDeliverable, setActiveDeliverable] = useState<'gonogo' | 'planning' | 'editor' | 'download'>('gonogo');
  const [showNewAOWizard, setShowNewAOWizard] = useState(false);

  // New AO Form state
  const [aoTitle, setAoTitle] = useState('');
  const [aoClient, setAoClient] = useState('');
  const [aoUrl, setAoUrl] = useState('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [wizardError, setWizardError] = useState<string | null>(null);
  const [isSubmittingWizard, setIsSubmittingWizard] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Real Project & Deliverables State
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
        setWizardError(t('dashboard.workspace.session_expired'));
      } else {
        setWizardError(err?.message || t('dashboard.workspace.wizard_generic_error'));
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
      alert(t('dashboard.workspace.memory_save_error_prefix') + err.message);
    }
  }

  // --- RENDERING HELPERS FOR GO/NO-GO ---
  function getRecommendationBadge(recommendation: string) {
    const rec = (recommendation || '').toUpperCase();
    if (rec.includes('GO') && !rec.includes('NO')) {
      return {
        label: t('dashboard.workspace.badge_go'),
        color: 'text-positive',
        bg: 'bg-positive/10',
        border: 'border-positive/20',
        icon: CheckCircle2,
      };
    } else if (rec.includes('RESERVE') || rec.includes('RÉSERVE')) {
      return {
        label: t('dashboard.workspace.badge_reserves'),
        color: 'text-hl',
        bg: 'bg-hl/10',
        border: 'border-hl/20',
        icon: AlertTriangle,
      };
    } else {
      return {
        label: t('dashboard.workspace.badge_nogo'),
        color: 'text-danger',
        bg: 'bg-danger/10',
        border: 'border-danger/20',
        icon: XCircle,
      };
    }
  }

  // Loading Screen
  if (loadingProject) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-3 text-[13px] text-muted-foreground font-mono">
        <Loader2 className="w-8 h-8 animate-spin text-hl" />
        <p>{t('dashboard.workspace.loading')}</p>
      </div>
    );
  }

  // Empty State when no project exists in the workspace
  if (!project) {
    return (
      <div className="page-container max-w-4xl mx-auto py-12 space-y-6 font-sans">
        <div className="card-elevated p-8 sm:p-12 text-center space-y-6 rounded-2xl animate-fade-in-up">
          <div className="w-16 h-16 rounded-2xl bg-hl/10 border border-hl/20 flex items-center justify-center mx-auto text-hl shadow-xs">
            <FolderPlus className="w-8 h-8" />
          </div>
          <div className="space-y-2 max-w-md mx-auto">
            <h1 className="text-2xl font-extrabold text-foreground font-heading">{t('dashboard.workspace.empty_title')}</h1>
            <p className="text-[13px] text-muted-foreground leading-relaxed">
              {t('dashboard.workspace.empty_desc')}
            </p>
          </div>
          <div className="flex flex-wrap items-center justify-center gap-3 pt-2">
            <button
              onClick={() => setShowNewAOWizard(true)}
              className="btn-primary cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>{t('dashboard.workspace.empty_create_btn')}</span>
            </button>
            <Link
              href="/dashboard/projects"
              className="btn-secondary cursor-pointer"
            >
              <Building className="w-4 h-4 text-muted-foreground" />
              <span>{t('dashboard.workspace.empty_view_existing_btn')}</span>
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
    <div className="page-container max-w-5xl mx-auto font-sans space-y-5">
      {/* Fil d'Ariane / Breadcrumbs */}
      <nav className="flex items-center gap-2 text-[12px] text-muted-foreground">
        <Link
          href="/dashboard/projects"
          className="hover:text-hl transition-colors flex items-center gap-1.5 font-medium cursor-pointer"
        >
          <Building className="w-3.5 h-3.5" />
          <span>{t('dashboard.workspace.breadcrumb_my_tenders')}</span>
        </Link>
        <ChevronRight className="w-3.5 h-3.5 opacity-50 shrink-0" />
        <span className="text-foreground font-semibold truncate max-w-md">
          {project.title}
        </span>
      </nav>

      {/* Top Banner with Real Project Metadata */}
      <div className="card-elevated p-6 sm:p-7 space-y-5 rounded-2xl">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="space-y-1.5 min-w-0 flex-1">
            <div className="flex items-center gap-2.5">
              <span className="badge-pill text-[9px]">
                {project.reference_code || t('dashboard.workspace.ref_fallback')}
              </span>
              <span className="text-[11px] text-muted-foreground">{t('dashboard.workspace.public_market_badge')}</span>
            </div>
            <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight truncate">{project.title}</h1>
            <p className="text-[12px] text-muted-foreground">
              {t('dashboard.workspace.client_line_prefix')}<strong className="text-foreground">{project.client_name}</strong> • {project.location || t('dashboard.workspace.france_fallback')}
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => setShowNewAOWizard(true)}
              className="btn-primary cursor-pointer"
            >
              <Plus className="w-4 h-4" />
              <span>{t('dashboard.workspace.new_project_btn')}</span>
            </button>
          </div>
        </div>

        {/* Live Generation Progress Bar */}
        {isGenerating && (
          <div className="card-inset p-4 space-y-3 rounded-xl animate-fade-in-up">
            <div className="flex items-center justify-between text-[12px] font-semibold text-hl">
              <span className="flex items-center gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-hl" />
                {generationStep === 1 && t('dashboard.workspace.gen_step1')}
                {generationStep === 2 && t('dashboard.workspace.gen_step2')}
                {generationStep === 3 && t('dashboard.workspace.gen_step3')}
              </span>
              <span className="font-mono text-[11px] text-muted-foreground">{t('dashboard.workspace.gen_step_counter', { step: String(generationStep) })}</span>
            </div>
            <div className="w-full h-2 bg-slate-200 dark:bg-raised rounded-full overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-hl to-positive rounded-full transition-all duration-500"
                style={{ width: `${(generationStep / 3) * 100}%` }}
              />
            </div>
          </div>
        )}

        {/* 4 Deliverables Tabs Navigation */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-3 border-t border-line">
          {[
            { id: 'gonogo', title: t('dashboard.workspace.tab1_title'), desc: t('dashboard.workspace.tab1_desc'), icon: ShieldCheck },
            { id: 'planning', title: t('dashboard.workspace.tab2_title'), desc: t('dashboard.workspace.tab2_desc'), icon: Calendar },
            { id: 'editor', title: t('dashboard.workspace.tab3_title'), desc: t('dashboard.workspace.tab3_desc'), icon: FileText },
            { id: 'download', title: t('dashboard.workspace.tab4_title'), desc: t('dashboard.workspace.tab4_desc'), icon: Download },
          ].map((tab) => {
            const Icon = tab.icon;
            const isCurrent = activeDeliverable === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveDeliverable(tab.id as any)}
                className={`p-3 rounded-xl text-left border transition-all duration-200 flex items-start gap-2.5 cursor-pointer ${
                  isCurrent
                    ? 'bg-hl/10 border-hl text-foreground font-bold shadow-xs'
                    : 'card-inset text-muted-foreground hover:text-foreground hover:border-hl/40'
                }`}
              >
                <div
                  className={`w-6 h-6 rounded-lg flex items-center justify-center font-bold text-xs shrink-0 ${
                    isCurrent ? 'bg-hl text-hl-contrast shadow-xs' : 'bg-slate-200 dark:bg-raised text-muted-foreground'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                </div>
                <div className="min-w-0">
                  <p className="text-[12px] font-bold truncate font-heading">{tab.title}</p>
                  <p className="text-[10px] text-muted-foreground truncate">{tab.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* ═══ DELIVERABLE 1: GO/NO-GO DECISION MATRIX ═══ */}
      {activeDeliverable === 'gonogo' && (
        <div className="space-y-5 animate-fade-in-up">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="section-header">
              <h2 className="section-title text-[15px]">{t('dashboard.workspace.d1_title')}</h2>
              <p className="section-desc text-[12px]">
                {t('dashboard.workspace.d1_desc')}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => loadGoNoGoAnalysis(project.id, true)}
                disabled={loadingGoNoGo || isEvaluatingGoNoGo}
                className="btn-secondary !py-2 !text-[12px] cursor-pointer"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${isEvaluatingGoNoGo ? 'animate-spin text-hl' : ''}`} />
                <span>{t('dashboard.workspace.recalc_btn')}</span>
              </button>
              <button
                onClick={() => setActiveDeliverable('planning')}
                className="btn-primary !py-2 !text-[12px] cursor-pointer"
              >
                <span>{t('dashboard.workspace.view_planning_btn')}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {loadingGoNoGo ? (
            <div className="card-modern p-12 flex flex-col items-center justify-center space-y-3 text-[13px] text-muted-foreground rounded-2xl">
              <Loader2 className="w-8 h-8 animate-spin text-hl" />
              <p className="font-semibold">{t('dashboard.workspace.gonogo_evaluating')}</p>
            </div>
          ) : !goNoGo ? (
            <div className="card-modern p-8 text-center space-y-4 rounded-2xl">
              <AlertCircle className="w-8 h-8 text-hl mx-auto" />
              <div className="space-y-1">
                <p className="text-[14px] font-bold text-foreground font-heading">{t('dashboard.workspace.no_analysis_title')}</p>
                <p className="text-[12px] text-muted-foreground">{t('dashboard.workspace.no_analysis_desc')}</p>
              </div>
              <button
                onClick={() => loadGoNoGoAnalysis(project.id, true)}
                className="btn-primary cursor-pointer"
              >
                {t('dashboard.workspace.evaluate_btn')}
              </button>
            </div>
          ) : (
            <>
              {/* Top Decision Summary & Score Cards */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="card-modern p-6 space-y-4 md:col-span-2 rounded-2xl">
                  <div className="flex items-center justify-between">
                    <span className="text-[13px] font-bold text-foreground flex items-center gap-2 font-heading">
                      <FileText className="w-4 h-4 text-hl" />
                      {t('dashboard.workspace.synthesis_title')}
                    </span>
                    <span className="badge-pill-slate font-mono text-[10px]">
                      {t('dashboard.workspace.evaluated_on', { date: new Date(goNoGo.created_at).toLocaleDateString('fr-FR') })}
                    </span>
                  </div>

                  <p className="text-[13px] text-foreground/90 leading-relaxed card-inset p-4 rounded-xl">
                    {goNoGo.summary}
                  </p>

                  <div className="pt-3 border-t border-line flex items-center justify-between text-[12px]">
                    <span className="text-muted-foreground">{t('dashboard.workspace.mandatory_criteria_label')}</span>
                    <span className={`font-bold flex items-center gap-1.5 ${goNoGo.mandatory_criteria_met ? 'text-positive' : 'text-danger'}`}>
                      {goNoGo.mandatory_criteria_met ? (
                        <>
                          <CheckCircle2 className="w-4 h-4" />
                          <span>{t('dashboard.workspace.mandatory_met')}</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="w-4 h-4" />
                          <span>{t('dashboard.workspace.mandatory_not_met')}</span>
                        </>
                      )}
                    </span>
                  </div>
                </div>

                {/* Score and Recommendation Box */}
                {badge && (
                  <div className={`p-6 rounded-2xl card-inset ${badge.border} space-y-4`}>
                    <div className="flex items-center justify-between">
                      <span className="text-[12px] font-bold text-foreground font-heading">{t('dashboard.workspace.opportunity_score')}</span>
                      <span className={`text-3xl font-extrabold font-heading ${badge.color}`}>{Math.round(goNoGo.score)} / 100</span>
                    </div>

                    <div className={`p-4 rounded-xl bg-white dark:bg-raised border border-line shadow-xs`}>
                      <div className="flex items-center gap-2 mb-1">
                        <BadgeIcon className={`w-4 h-4 ${badge.color} shrink-0`} />
                        <p className={`text-[13px] font-bold font-heading ${badge.color}`}>{badge.label}</p>
                      </div>
                      <p className="text-[11px] text-muted-foreground leading-relaxed">
                        {goNoGo.score >= 70
                          ? t('dashboard.workspace.score_msg_high')
                          : goNoGo.score >= 45
                          ? t('dashboard.workspace.score_msg_mid')
                          : t('dashboard.workspace.score_msg_low')}
                      </p>
                    </div>

                    <div className="text-[10px] text-muted-foreground text-center font-mono">
                      {t('dashboard.workspace.factors_weighted', { count: String(goNoGo.factors?.length || 0) })}
                    </div>
                  </div>
                )}
              </div>

              {/* Blocking Issues Alert Box (if any) */}
              {goNoGo.blocking_issues && goNoGo.blocking_issues.length > 0 && (
                <div className="p-4 rounded-2xl bg-danger/8 border border-danger/20 space-y-2">
                  <div className="flex items-center gap-2 text-danger text-[12px] font-bold font-heading">
                    <AlertTriangle className="w-4 h-4" />
                    <span>{t('dashboard.workspace.blocking_title', { count: String(goNoGo.blocking_issues.length) })}</span>
                  </div>
                  <ul className="space-y-1 text-[12px] text-danger pl-6 list-disc">
                    {goNoGo.blocking_issues.map((issue, idx) => (
                      <li key={idx}>{issue}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Detailed Decision Factors Grid */}
              <div className="space-y-3">
                <h3 className="section-title text-[14px]">
                  <Sliders className="w-4 h-4 text-hl" />
                  <span>{t('dashboard.workspace.factors_detail_title')}</span>
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {goNoGo.factors?.map((factor, idx) => {
                    const isPassed = factor.status === 'passed';
                    const isWarning = factor.status === 'warning';
                    return (
                      <div
                        key={idx}
                        className={`p-4 rounded-xl border space-y-2 transition-all duration-200 ${
                          isPassed
                            ? 'card-modern hover:border-hl/40'
                            : isWarning
                            ? 'bg-hl/5 border-hl/20'
                            : 'bg-danger/5 border-danger/20'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="space-y-0.5 min-w-0">
                            <span className="text-[10px] font-mono text-muted-foreground uppercase">
                              {factor.category}
                            </span>
                            <h4 className="text-[13px] font-bold text-foreground truncate font-heading">{factor.title}</h4>
                          </div>
                          <span
                            className={`badge-pill text-[9px] font-mono uppercase ${
                              isPassed
                                ? 'bg-positive/10 text-positive border-positive/20'
                                : isWarning
                                ? 'bg-hl/10 text-hl border-hl/20'
                                : 'bg-danger/10 text-danger border-danger/20'
                            }`}
                          >
                            {factor.status}
                          </span>
                        </div>

                        <p className="text-[12px] text-muted-foreground leading-relaxed">{factor.detail}</p>

                        {factor.recommendation && (
                          <div className="pt-2 border-t border-line text-[11px] text-hl">
                            <strong>{t('dashboard.workspace.recommendation_prefix')}</strong> {factor.recommendation}
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

      {/* ═══ DELIVERABLE 2: PLANNING CHANTIER ═══ */}
      {activeDeliverable === 'planning' && (
        <div className="space-y-5 animate-fade-in-up">
          <div className="flex items-center justify-between">
            <div className="section-header">
              <h2 className="section-title text-[15px]">{t('dashboard.workspace.d2_title')}</h2>
              <p className="section-desc text-[12px]">
                {t('dashboard.workspace.d2_desc')}
              </p>
            </div>
            <button
              onClick={() => setActiveDeliverable('editor')}
              className="btn-primary !py-2 !text-[12px] cursor-pointer"
            >
              <span>{t('dashboard.workspace.review_memo_btn')}</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {decisions?.phasage_travaux && decisions.phasage_travaux.length > 0 ? (
              decisions.phasage_travaux.map((p: any, idx: number) => (
                <div key={idx} className="card-modern p-5 space-y-3 rounded-2xl">
                  <div className="flex items-center justify-between">
                    <h3 className="text-[14px] font-bold text-foreground font-heading">{p.phase || t('dashboard.workspace.phase_fallback', { n: String(idx + 1) })}</h3>
                    <span className="badge-pill text-[9px]">
                      {p.duree_semaines ? t('dashboard.workspace.duree_semaines', { n: String(p.duree_semaines) }) : t('dashboard.workspace.phase_label_short')}
                    </span>
                  </div>
                  <p className="text-[12px] text-muted-foreground">
                    <strong>{t('dashboard.workspace.jalon_prefix')}</strong> {p.jalon || t('dashboard.workspace.jalon_fallback')}
                  </p>
                </div>
              ))
            ) : (
              <div className="card-modern p-8 sm:col-span-2 text-center space-y-2.5 rounded-2xl">
                <Calendar className="w-8 h-8 text-slate-400 mx-auto" />
                <p className="text-[13px] font-bold text-foreground font-heading">{t('dashboard.workspace.no_phasage_title')}</p>
                <p className="text-[11px] text-muted-foreground">
                  {t('dashboard.workspace.no_phasage_desc', { months: String(decisions?.delai_mois || 6) })}
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ═══ DELIVERABLE 3: RICH TEXT EDITOR ═══ */}
      {activeDeliverable === 'editor' && (
        <div className="space-y-5 animate-fade-in-up">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="section-header">
              <h2 className="section-title text-[15px]">{t('dashboard.workspace.d3_title')}</h2>
              <p className="section-desc text-[12px]">
                {t('dashboard.workspace.d3_desc')}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setActiveDeliverable('download')}
                className="btn-primary !py-2 !text-[12px] cursor-pointer"
              >
                <span>{t('dashboard.workspace.finalize_btn')}</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>

          {/* Section Selector if multiple sections */}
          {sections.length > 1 && (
            <div className="tab-group !p-1.5 flex-wrap">
              {sections.map((sec, idx) => (
                <button
                  key={sec.id}
                  onClick={() => setCurrentSectionIndex(idx)}
                  className={currentSectionIndex === idx ? 'tab-item-active !bg-hl !text-hl-contrast' : 'tab-item'}
                >
                  {sec.title || t('dashboard.workspace.section_fallback', { n: String(idx + 1) })}
                </button>
              ))}
            </div>
          )}

          {/* Floating Learning Loop helper */}
          <div className="p-4 rounded-2xl card-inset border-hl/20 bg-hl/5 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <BrainCircuit className="w-5 h-5 text-hl shrink-0" />
              <div>
                <p className="text-[13px] font-bold text-foreground font-heading">{t('dashboard.workspace.learning_loop_title')}</p>
                <p className="text-[11px] text-muted-foreground">
                  {t('dashboard.workspace.learning_loop_desc')}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 w-full sm:w-auto">
              <input
                type="text"
                value={selectedTextRule}
                onChange={(e) => setSelectedTextRule(e.target.value)}
                placeholder={t('dashboard.workspace.rule_placeholder')}
                className="input-field !py-1.5 !text-[12px] w-full sm:w-80"
              />
              <button
                type="button"
                onClick={handleAddSelectedToMemory}
                className="btn-primary !py-1.5 !px-3 !text-[12px] shrink-0 cursor-pointer"
              >
                {t('dashboard.workspace.add_to_memory_btn')}
              </button>
            </div>
          </div>

          {memorySavedMsg && (
            <div className="p-3.5 rounded-xl bg-positive/8 border border-positive/20 text-positive text-[13px] font-semibold flex items-center gap-2 animate-fade-in-up">
              <CheckCircle2 className="w-4 h-4 text-positive shrink-0" />
              <span>{t('dashboard.workspace.memory_saved_msg')}</span>
            </div>
          )}

          {currentSection ? (
            <div className="card-modern overflow-hidden rounded-2xl">
              <TiptapEditor
                projectId={project.id}
                section={currentSection}
                onSave={(updated) => {
                  setSections(prev => prev.map(s => s.id === updated.id ? updated : s));
                }}
              />
            </div>
          ) : (
            <div className="card-modern p-12 text-center space-y-3 rounded-2xl">
              <FileText className="w-8 h-8 text-slate-400 mx-auto" />
              <p className="text-[13px] font-bold text-foreground font-heading">{t('dashboard.workspace.no_sections_title')}</p>
              <p className="text-[11px] text-muted-foreground">{t('dashboard.workspace.no_sections_desc')}</p>
            </div>
          )}
        </div>
      )}

      {/* ═══ DELIVERABLE 4: FINAL WORD & PDF DOWNLOADS ═══ */}
      {activeDeliverable === 'download' && (
        <div className="card-elevated p-8 space-y-7 text-center max-w-2xl mx-auto shadow-floating rounded-2xl animate-fade-in-up">
          <div className="space-y-2">
            <div className="w-16 h-16 rounded-2xl bg-positive/10 border border-positive/20 flex items-center justify-center mx-auto text-positive shadow-xs">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-xl font-extrabold text-foreground font-heading">{t('dashboard.workspace.d4_title')}</h2>
            <p className="text-[13px] text-muted-foreground">
              {t('dashboard.workspace.d4_desc_prefix')}<strong className="text-foreground">{project.title}</strong>{t('dashboard.workspace.d4_desc_suffix')}
            </p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <button
              onClick={async () => {
                try {
                  const { data: { session } } = await supabase.auth.getSession();
                  const token = session?.access_token;
                  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
                  const res = await fetch(
                    `${apiBase}/api/export/stream/${project.id}.docx`,
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
                  alert(t('dashboard.workspace.export_word_error_prefix') + err.message);
                }
              }}
              className="flex flex-col items-center justify-center p-6 rounded-2xl bg-hl hover:bg-hl-strong text-hl-contrast shadow-xs transition-all duration-200 group cursor-pointer"
            >
              <FileText className="w-8 h-8 mb-2 group-hover:scale-105 transition-transform" />
              <span className="text-[14px] font-extrabold font-heading">{t('dashboard.workspace.download_word_title')}</span>
              <span className="text-[11px] opacity-80 mt-0.5">{t('dashboard.workspace.download_word_desc')}</span>
            </button>

            <button
              onClick={async () => {
                try {
                  // Correctif (02/09, découvert en corrigeant la tâche #66) : res.pdf_url
                  // n'a jamais existé sur la vraie réponse backend, donc ce bouton
                  // redirigeait systématiquement vers la page d'export complète au lieu de
                  // jamais livrer de PDF directement. On interroge maintenant le job
                  // jusqu'à complétion et on télécharge via un blob authentifié.
                  const job = await api.exportProject(project.id, { format: 'pdf' });
                  let attempts = 0;
                  let finalJob = job;
                  while (finalJob.status !== 'completed' && finalJob.status !== 'failed' && attempts < 30) {
                    await new Promise((resolve) => setTimeout(resolve, 2000));
                    finalJob = await api.getExportJob(job.id);
                    attempts += 1;
                  }
                  if (finalJob.status === 'failed') {
                    throw new Error(finalJob.error_message || 'Échec de la génération du PDF.');
                  }
                  if (!finalJob.s3_docx_url) {
                    window.location.href = `/projects/${project.id}/export`;
                    return;
                  }
                  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
                  const blobUrl = await fetchAuthenticatedBlobUrl(`${apiBase}${finalJob.s3_docx_url}`);
                  const ext = finalJob.format === 'pdf' && finalJob.s3_pdf_url ? 'pdf' : 'docx';
                  const a = document.createElement('a');
                  a.href = blobUrl;
                  a.download = `Memoire_Technique_${project.title.replace(/[^a-zA-Z0-9]/g, '_')}.${ext}`;
                  document.body.appendChild(a);
                  a.click();
                  document.body.removeChild(a);
                  setTimeout(() => URL.revokeObjectURL(blobUrl), 60000);
                } catch (err: any) {
                  alert(t('dashboard.workspace.export_pdf_error_prefix') + (err.message || t('dashboard.workspace.unknown_error')));
                }
              }}
              className="flex flex-col items-center justify-center p-6 rounded-2xl card-inset hover:border-slate-300 dark:hover:border-line text-foreground transition-all duration-200 group cursor-pointer"
            >
              <Download className="w-8 h-8 mb-2 group-hover:scale-105 transition-transform text-danger" />
              <span className="text-[14px] font-extrabold font-heading">{t('dashboard.workspace.download_pdf_title')}</span>
              <span className="text-[11px] text-muted-foreground mt-0.5">{t('dashboard.workspace.download_pdf_desc')}</span>
            </button>
          </div>

          <div className="pt-4 border-t border-line flex items-center justify-center gap-2 text-[12px] text-muted-foreground">
            <ShieldCheck className="w-4 h-4 text-positive" />
            <span>{t('dashboard.workspace.built_with_disclaimer')}</span>
          </div>
        </div>
      )}

      {/* NEW AO WIZARD MODAL */}
      {showNewAOWizard && renderWizardModal()}

    </div>
  );

  function renderWizardModal() {
    return (
      <div className="fixed inset-0 bg-slate-950/60 backdrop-blur-md z-50 flex items-center justify-center p-4 animate-in fade-in">
        <div className="bg-card border border-line rounded-2xl p-6 sm:p-8 max-w-lg w-full shadow-floating space-y-6 animate-scale-in">
          <div className="flex items-center justify-between">
            <div className="space-y-0.5">
              <h3 className="text-lg font-bold text-foreground font-heading">{t('dashboard.workspace.wizard_title')}</h3>
              <p className="text-[12px] text-muted-foreground">
                {t('dashboard.workspace.wizard_subtitle')}
              </p>
            </div>
            <button
              onClick={() => setShowNewAOWizard(false)}
              className="p-2 rounded-lg text-slate-400 hover:text-foreground hover:bg-slate-100 dark:hover:bg-raised transition-colors cursor-pointer"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {wizardError && (
            <div className="p-3.5 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-0.5">
                <p className="font-bold">{t('dashboard.workspace.wizard_error_title')}</p>
                <p>{wizardError}</p>
              </div>
            </div>
          )}

          <form onSubmit={handleLaunchGeneration} className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-[12px] font-semibold uppercase tracking-wider text-muted-foreground">{t('dashboard.workspace.field_title_label')}</label>
              <input
                type="text"
                required
                disabled={isSubmittingWizard}
                value={aoTitle}
                onChange={(e) => setAoTitle(e.target.value)}
                placeholder={t('dashboard.workspace.field_title_placeholder')}
                className="input-field disabled:opacity-50"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-[12px] font-semibold uppercase tracking-wider text-muted-foreground">{t('dashboard.workspace.field_client_label')}</label>
              <input
                type="text"
                required
                disabled={isSubmittingWizard}
                value={aoClient}
                onChange={(e) => setAoClient(e.target.value)}
                placeholder={t('dashboard.workspace.field_client_placeholder')}
                className="input-field disabled:opacity-50"
              />
            </div>

            <div className="space-y-2">
              <label className="text-[12px] font-semibold uppercase tracking-wider text-muted-foreground">
                {t('dashboard.workspace.field_files_label')}
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
                className={`p-6 rounded-2xl border-2 border-dashed text-center cursor-pointer transition-all duration-200 ${
                  isDragging
                    ? 'border-hl bg-hl/10'
                    : 'card-inset border-slate-300 dark:border-line hover:border-hl/60'
                } ${isSubmittingWizard ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <FileUp className="w-8 h-8 text-hl mx-auto mb-2" />
                <p className="text-[13px] font-bold text-foreground font-heading">{t('dashboard.workspace.dropzone_text')}</p>
                <p className="text-[11px] text-muted-foreground mt-0.5">{t('dashboard.workspace.dropzone_subtext')}</p>
              </div>

              {selectedFiles.length > 0 && (
                <div className="space-y-1.5 max-h-32 overflow-y-auto">
                  {selectedFiles.map((file, idx) => (
                    <div key={idx} className="flex items-center justify-between p-2.5 rounded-lg card-inset text-[12px] text-foreground">
                      <span className="truncate">{file.name}</span>
                      <button
                        type="button"
                        disabled={isSubmittingWizard}
                        onClick={() => handleRemoveFile(idx)}
                        className="text-slate-400 hover:text-danger ml-2 disabled:opacity-40 cursor-pointer"
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
                className="btn-primary w-full !py-3 !text-[14px] cursor-pointer"
              >
                {isSubmittingWizard ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>{t('dashboard.workspace.wizard_submitting')}</span>
                  </>
                ) : (
                  <>
                    <Sparkles className="w-4 h-4" />
                    <span>{t('dashboard.workspace.wizard_submit_btn')}</span>
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
      <div className="flex items-center justify-center min-h-[50vh] text-[13px] text-muted-foreground font-mono">
        <Loader2 className="w-8 h-8 animate-spin text-hl" />
      </div>
    }>
      <WorkspaceContent />
    </Suspense>
  );
}
