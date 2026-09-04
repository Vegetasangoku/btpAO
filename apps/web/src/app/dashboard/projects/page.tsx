'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  FolderKanban,
  Plus,
  ArrowRight,
  HardHat,
  Calendar,
  Building,
  CheckCircle2,
  Clock,
  ChevronRight,
  ShieldCheck,
  Edit3,
  Download,
  Sparkles,
  Search,
  Filter,
  Loader2,
  TrendingUp,
  BarChart2,
  X,
  RefreshCw,
  AlertTriangle,
  Check,
  XCircle,
  ExternalLink,
} from 'lucide-react';
import { Project, GoNoGoAnalysis } from '@/lib/types';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

export default function DashboardProjectsPage() {
  const { t } = useTranslation();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Go/No-Go Scores cache per project ID
  const [scoresMap, setScoresMap] = useState<Record<string, GoNoGoAnalysis | null>>({});
  const [selectedModalProject, setSelectedModalProject] = useState<Project | null>(null);
  const [modalAnalysis, setModalAnalysis] = useState<GoNoGoAnalysis | null>(null);
  const [loadingModalScore, setLoadingModalScore] = useState(false);
  const [recalculatingScore, setRecalculatingScore] = useState(false);
  const [confirmingIssue, setConfirmingIssue] = useState<string | null>(null);

  useEffect(() => {
    async function loadProjects() {
      try {
        const data = await api.getProjects();
        const loadedProjects = data || [];
        setProjects(loadedProjects);

        // Pre-populate scores directly from loaded project data
        const initialScores: Record<string, GoNoGoAnalysis | null> = {};
        for (const p of loadedProjects) {
          if (p.go_no_go) {
            initialScores[p.id] = p.go_no_go;
          }
        }
        setScoresMap(initialScores);

        // Also fetch/refresh Go/No-Go scores for visible projects in background if needed
        for (const p of loadedProjects) {
          if (!initialScores[p.id]) {
            api.getGoNoGo(p.id)
              .then((analysis) => {
                if (analysis) {
                  setScoresMap((prev) => ({ ...prev, [p.id]: analysis }));
                }
              })
              .catch(() => {});
          }
        }
      } catch (err) {
        console.warn('Erreur chargement projets:', err);
      } finally {
        setLoading(false);
      }
    }
    loadProjects();
  }, []);

  async function handleOpenScoreModal(project: Project) {
    setSelectedModalProject(project);
    const existing = scoresMap[project.id] || project.go_no_go;
    if (existing) {
      setModalAnalysis(existing);
    } else {
      setLoadingModalScore(true);
      try {
        const res = await api.getGoNoGo(project.id);
        setModalAnalysis(res);
        if (res) {
          setScoresMap((prev) => ({ ...prev, [project.id]: res }));
        }
      } catch {
        setModalAnalysis(null);
      } finally {
        setLoadingModalScore(false);
      }
    }
  }

  async function handleRecalculateModalScore() {
    if (!selectedModalProject) return;
    setRecalculatingScore(true);
    try {
      const res = await api.runGoNoGo(selectedModalProject.id);
      setModalAnalysis(res);
      setScoresMap((prev) => ({ ...prev, [selectedModalProject.id]: res }));
    } catch (err: any) {
      alert('Erreur calcul Go/No-Go : ' + (err?.message || err));
    } finally {
      setRecalculatingScore(false);
    }
  }

  async function handleConfirmCompliance(issue: string) {
    if (!selectedModalProject) return;
    setConfirmingIssue(issue);
    try {
      const label = issue.includes(':') ? issue.split(':').slice(1).join(':').trim() : issue;
      await api.addKnowledgeAsset({
        category: 'certificat_qualibat',
        title: label || issue,
        description: `Conformité confirmée manuellement par l'utilisateur depuis le module Go/No-Go, suite au point bloquant : "${issue}".`,
        tags: ['confirmation_manuelle', 'go_no_go'],
      });
      const refreshed = await api.runGoNoGo(selectedModalProject.id);
      setModalAnalysis(refreshed);
      setScoresMap((prev) => ({ ...prev, [selectedModalProject.id]: refreshed }));
    } catch (err: any) {
      alert("Erreur lors de la confirmation de conformité : " + (err?.message || err));
    } finally {
      setConfirmingIssue(null);
    }
  }

  const filteredProjects = projects.filter((p) => {
    const matchesSearch =
      (p.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.client_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (p.reference_code || '').toLowerCase().includes(searchQuery.toLowerCase());

    if (statusFilter === 'all') return matchesSearch;
    if (statusFilter === 'in_progress') return matchesSearch && (p.status === 'draft' || p.status === 'in_progress');
    if (statusFilter === 'completed')
      return matchesSearch && (p.status === 'completed' || p.outcome_status === 'submitted' || p.outcome_status === 'won');
    return matchesSearch;
  });

  return (
    <div className="page-container max-w-5xl mx-auto">
      {/* ─── Top Header ─── */}
      <div className="card-elevated p-6 sm:p-7 flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-2">
          <span className="badge-pill text-[10px]">{t('projects.badge')}</span>
          <h1 className="text-xl sm:text-2xl font-extrabold text-foreground font-heading tracking-tight">
            {t('projects.title')}
          </h1>
          <p className="section-desc">{t('projects.desc')}</p>
        </div>

        <Link href="/dashboard/wizard" className="btn-primary">
          <Sparkles className="w-4 h-4" />
          <span>{t('projects.btn_new')}</span>
        </Link>
      </div>

      {/* ─── Filter & Search Bar ─── */}
      <div className="card-modern p-3.5 flex flex-wrap items-center justify-between gap-3">
        <div className="relative flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-muted-foreground absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('projects.search_placeholder')}
            className="input-field-with-icon !py-2 !rounded-lg"
          />
        </div>

        <div className="tab-group">
          {[
            { id: 'all', label: t('projects.filter_all') },
            { id: 'in_progress', label: t('projects.filter_in_progress') },
            { id: 'completed', label: t('projects.filter_completed') },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={statusFilter === tab.id ? 'tab-item-active' : 'tab-item'}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* ─── Projects List ─── */}
      <div className="space-y-3">
        {loading ? (
          <div className="card-modern p-12 text-center text-[13px] text-muted-foreground flex items-center justify-center gap-2.5">
            <Loader2 className="w-4 h-4 animate-spin text-hl" />
            <span>{t('dash.loading')}</span>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="card-modern p-12 text-center space-y-3">
            <FolderKanban className="w-10 h-10 text-slate-300 dark:text-zinc-600 mx-auto" />
            <p className="text-[14px] font-semibold text-foreground font-heading">{t('projects.empty_title')}</p>
            <Link href="/dashboard/wizard" className="btn-primary">
              <Plus className="w-4 h-4" />
              <span>{t('projects.empty_btn')}</span>
            </Link>
          </div>
        ) : (
          filteredProjects.map((project) => {
            const projectScore = scoresMap[project.id];
            const hasScore = projectScore && typeof projectScore.score === 'number' && projectScore.has_sufficient_data !== false;

            return (
              <div
                key={project.id}
                className="card-modern-hover p-5 space-y-4 rounded-2xl"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1.5 min-w-0 flex-1">
                    <div className="flex items-center gap-2.5">
                      <span className="badge-pill-slate text-[10px]">
                        {project.reference_code || 'AO-EN-COURS'}
                      </span>
                      <span className="text-[11px] text-muted-foreground">{project.lot_number || 'Marché Public BTP'}</span>
                    </div>
                    <Link href={`/projects/${project.id}`} className="block group">
                      <h3 className="text-[15px] font-bold text-foreground group-hover:text-hl transition-colors truncate font-heading">
                        {project.title}
                      </h3>
                    </Link>
                    <p className="text-[12px] text-muted-foreground">
                      {t('projects.buyer')} : <strong className="text-foreground">{project.client_name}</strong> • {project.location || 'France'}
                    </p>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    {hasScore && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenScoreModal(project);
                        }}
                        className="font-mono text-[11px] font-bold px-2.5 py-1 rounded-lg card-inset hover:border-hl/30 transition-all flex items-center gap-1.5 cursor-pointer"
                        title="Voir la matrice de décision Go / No-Go"
                      >
                        <TrendingUp className="w-3.5 h-3.5 text-hl" />
                        <span className={
                          projectScore.recommendation === 'GO'
                            ? 'text-positive'
                            : projectScore.recommendation === 'RESERVES' || projectScore.recommendation === 'RÉSERVES'
                            ? 'text-hl'
                            : 'text-danger'
                        }>
                          {Math.round(projectScore.score)}%
                        </span>
                        <span className="text-muted-foreground">{projectScore.recommendation}</span>
                      </button>
                    )}
                    <span className="text-[11px] text-muted-foreground flex items-center gap-2 min-w-[70px]">
                      <span className={`w-2 h-2 rounded-full ${project.status === 'completed' || project.outcome_status === 'won' ? 'bg-positive' : 'bg-hl'}`}></span>
                      {project.status === 'completed' ? t('projects.status_ready') : t('projects.status_drafting')}
                    </span>
                  </div>
                </div>

                {/* Action Buttons */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-3.5 border-t border-line">
                  <button
                    type="button"
                    onClick={() => handleOpenScoreModal(project)}
                    className="card-inset p-3.5 text-left transition-all group cursor-pointer hover:border-hl/40"
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Décision</p>
                      {hasScore ? (
                        <span
                          className={`text-[10px] font-mono font-bold ${
                            projectScore.recommendation === 'GO'
                              ? 'text-positive'
                              : projectScore.recommendation === 'RESERVES' || projectScore.recommendation === 'RÉSERVES'
                              ? 'text-hl'
                              : 'text-danger'
                          }`}
                        >
                          {Math.round(projectScore.score)}%
                        </span>
                      ) : (
                        <span className="text-[10px] text-muted-foreground">Score...</span>
                      )}
                    </div>
                    <p className="text-[13px] font-semibold text-foreground group-hover:text-hl flex items-center gap-1.5 mt-1 font-heading">
                      <TrendingUp className="w-3.5 h-3.5 text-hl" />
                      <span>{t('projects.btn_gonogo')}</span>
                    </p>
                  </button>

                  <Link
                    href={`/projects/${project.id}/visuals`}
                    className="card-inset p-3.5 text-left transition-all group hover:border-hl/40"
                  >
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Chantier</p>
                    <p className="text-[13px] font-semibold text-foreground group-hover:text-hl flex items-center gap-1.5 mt-1 font-heading">
                      <BarChart2 className="w-3.5 h-3.5 text-hl" />
                      <span>{t('projects.btn_planning')}</span>
                    </p>
                  </Link>

                  <Link
                    href={`/projects/${project.id}/editor`}
                    className="card-inset p-3.5 text-left transition-all group hover:border-hl/40"
                  >
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Rédaction</p>
                    <p className="text-[13px] font-semibold text-foreground group-hover:text-hl flex items-center gap-1.5 mt-1 font-heading">
                      <Edit3 className="w-3.5 h-3.5 text-hl" />
                      <span>{t('projects.btn_wizard')}</span>
                    </p>
                  </Link>

                  <Link
                    href={`/projects/${project.id}/export`}
                    className="card-inset p-3.5 text-left transition-all group hover:border-hl/40"
                  >
                    <p className="text-[10px] text-muted-foreground uppercase tracking-wider">Livraison</p>
                    <p className="text-[13px] font-semibold text-foreground group-hover:text-hl flex items-center gap-1.5 mt-1 font-heading">
                      <Download className="w-3.5 h-3.5 text-hl" />
                      <span>{t('projects.btn_download')}</span>
                    </p>
                  </Link>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* ═══ MODAL: GO / NO-GO SCORE DETAILS ═══ */}
      {selectedModalProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/60 backdrop-blur-md animate-in fade-in">
          <div className="relative w-full max-w-xl bg-card border border-line rounded-2xl p-6 sm:p-7 shadow-floating space-y-5 animate-scale-in">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4 pb-4 border-b border-line">
              <div className="space-y-1">
                <div className="flex items-center gap-2.5">
                  <span className="badge-pill text-[9px]">
                    {selectedModalProject.reference_code || t('projects.gonogo_modal.ref_fallback')}
                  </span>
                  <span className="text-[11px] text-muted-foreground">{t('projects.gonogo_modal.eyebrow')}</span>
                </div>
                <h3 className="text-[15px] font-bold text-foreground truncate max-w-md font-heading">
                  {selectedModalProject.title}
                </h3>
              </div>

              <button
                type="button"
                onClick={() => setSelectedModalProject(null)}
                className="p-2 rounded-lg text-slate-400 hover:text-foreground hover:bg-slate-100 dark:hover:bg-raised transition-all cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Content */}
            {loadingModalScore ? (
              <div className="p-12 text-center space-y-2.5">
                <Loader2 className="w-6 h-6 text-hl animate-spin mx-auto" />
                <p className="text-[13px] text-muted-foreground">{t('projects.gonogo_modal.loading')}</p>
              </div>
            ) : modalAnalysis ? (
              <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-1">
                {/* Completion Rate */}
                <div className="card-inset p-4 space-y-2 rounded-xl">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{t('projects.gonogo_modal.completion_label')}</span>
                    <span className="text-[14px] font-extrabold text-foreground">
                      {Math.round(modalAnalysis.completion_rate ?? 0)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-200 dark:bg-raised overflow-hidden">
                    <div
                      className="h-full rounded-full bg-hl transition-all duration-500"
                      style={{ width: `${Math.min(100, Math.max(0, modalAnalysis.completion_rate ?? 0))}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-muted-foreground">{t('projects.gonogo_modal.completion_desc')}</p>
                </div>

                {/* Strategic Score */}
                {modalAnalysis.has_sufficient_data === false ? (
                  <div className="card-inset p-5 text-center space-y-1.5 border-dashed rounded-xl">
                    <p className="text-[14px] font-semibold text-foreground">{t('projects.gonogo_modal.score_unavailable_title')}</p>
                    <p className="text-[12px] text-muted-foreground max-w-sm mx-auto">{t('projects.gonogo_modal.score_unavailable_desc')}</p>
                  </div>
                ) : (
                <div className="card-inset p-5 flex items-center justify-between gap-4 rounded-xl">
                  <div className="space-y-2">
                    <span
                      className={`badge-pill text-[10px] ${
                        modalAnalysis.recommendation === 'GO'
                          ? 'bg-positive/10 text-positive border-positive/20'
                          : modalAnalysis.recommendation === 'RESERVES' || modalAnalysis.recommendation === 'RÉSERVES'
                          ? 'bg-hl/10 text-hl border-hl/20'
                          : 'bg-danger/10 text-danger border-danger/20'
                      }`}
                    >
                      {modalAnalysis.recommendation === 'GO'
                        ? t('projects.export.gonogo_go')
                        : modalAnalysis.recommendation === 'RESERVES' || modalAnalysis.recommendation === 'RÉSERVES'
                        ? t('projects.export.gonogo_reserves')
                        : t('projects.export.gonogo_nogo')}
                    </span>
                    <p className="text-[13px] text-foreground leading-relaxed">{modalAnalysis.summary}</p>
                  </div>

                  <div className="shrink-0 flex flex-col items-center justify-center p-4 rounded-xl bg-white dark:bg-raised border border-line text-center min-w-[85px] shadow-xs">
                    <span
                      className={`text-2xl font-extrabold font-heading ${
                        modalAnalysis.score >= 70
                          ? 'text-positive'
                          : modalAnalysis.score >= 50
                          ? 'text-hl'
                          : 'text-danger'
                      }`}
                    >
                      {Math.round(modalAnalysis.score)}%
                    </span>
                    <span className="text-[9px] text-muted-foreground uppercase font-bold tracking-wider mt-0.5">{t('projects.gonogo_modal.score_global')}</span>
                  </div>
                </div>
                )}

                {/* Criteria Checks */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="card-inset p-3.5 flex items-start gap-2.5 rounded-xl">
                    {modalAnalysis.mandatory_criteria_met ? (
                      <Check className="w-4 h-4 text-positive shrink-0 mt-0.5" />
                    ) : (
                      <XCircle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
                    )}
                    <div>
                      <p className="text-[13px] font-semibold text-foreground font-heading">{t('projects.export.mandatory_criteria')}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {modalAnalysis.mandatory_criteria_met
                          ? t('projects.export.mandatory_criteria_ok')
                          : t('projects.gonogo_modal.criteria_ko')}
                      </p>
                    </div>
                  </div>

                  <div className="card-inset p-3.5 flex items-start gap-2.5 rounded-xl">
                    <ShieldCheck className="w-4 h-4 text-hl shrink-0 mt-0.5" />
                    <div>
                      <p className="text-[13px] font-semibold text-foreground font-heading">{t('projects.export.compliance')}</p>
                      <p className="text-[11px] text-muted-foreground">
                        {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0
                          ? t('projects.gonogo_modal.compliance_issues', { count: String(modalAnalysis.blocking_issues.length) })
                          : t('projects.gonogo_modal.compliance_ok')}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Blocking Issues List */}
                {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0 && (
                  <div className="p-4 rounded-xl bg-danger/5 border border-danger/30 dark:border-danger/20 space-y-2.5">
                    <p className="text-[11px] font-bold text-danger uppercase tracking-wider">{t('projects.gonogo_modal.blocking_issues_title')}</p>
                    <ul className="space-y-2">
                      {modalAnalysis.blocking_issues.map((issue, idx) => (
                        <li key={idx} className="text-[12px] text-danger flex items-start justify-between gap-2">
                          <span className="flex items-start gap-2">
                            <span className="mt-0.5">•</span>
                            <span>{issue}</span>
                          </span>
                          <button
                            type="button"
                            onClick={() => handleConfirmCompliance(issue)}
                            disabled={confirmingIssue === issue}
                            className="shrink-0 flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-positive/8 hover:bg-positive/15 border border-positive/20 text-positive text-[10px] font-semibold disabled:opacity-50 transition-all cursor-pointer"
                          >
                            {confirmingIssue === issue ? (
                              <Loader2 className="w-3 4-3 animate-spin" />
                            ) : (
                              <Check className="w-3 h-3" />
                            )}
                            <span>{t('projects.gonogo_modal.confirm_compliance_btn')}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Factors Detail */}
                {modalAnalysis.factors && modalAnalysis.factors.length > 0 && (
                  <div className="space-y-2.5">
                    <p className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider">
                      {t('projects.gonogo_modal.factors_title', { count: String(modalAnalysis.factors.length) })}
                    </p>
                    {modalAnalysis.factors.map((factor, idx) => {
                      const statusStyles: Record<string, string> = {
                        ok: 'border-positive/60 dark:border-positive/20 bg-positive/5',
                        warning: 'border-hl/30 bg-hl/5',
                        blocking: 'border-danger/60 dark:border-danger/20 bg-danger/5',
                        missing_data: 'border-line bg-slate-50/50 dark:bg-raised',
                      };
                      return (
                        <div
                          key={idx}
                          className={`p-3.5 rounded-xl border space-y-1 ${statusStyles[factor.status] || statusStyles.missing_data}`}
                        >
                          <p className="text-[13px] font-semibold text-foreground font-heading">{factor.title}</p>
                          <p className="text-[12px] text-foreground/80 leading-relaxed">{factor.detail}</p>
                          {factor.recommendation && (
                            <p className="text-[11px] text-muted-foreground leading-relaxed">
                              <span className="font-semibold">{t('projects.gonogo_modal.recommendation_label')}</span>
                              {factor.recommendation}
                            </p>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 rounded-xl card-inset border-dashed text-center space-y-3">
                <Sparkles className="w-8 h-8 text-hl mx-auto" />
                <p className="text-[14px] font-semibold text-foreground font-heading">{t('projects.export.gonogo_empty_title')}</p>
                <p className="text-[12px] text-muted-foreground max-w-sm mx-auto">{t('projects.gonogo_modal.empty_desc')}</p>
                <button
                  type="button"
                  onClick={handleRecalculateModalScore}
                  disabled={recalculatingScore}
                  className="btn-primary cursor-pointer"
                >
                  {recalculatingScore ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  <span>{t('projects.gonogo_modal.calc_btn')}</span>
                </button>
              </div>
            )}

            {/* Modal Footer Actions */}
            <div className="flex items-center justify-between gap-3 pt-3.5 border-t border-line">
              {modalAnalysis ? (
                <button
                  type="button"
                  onClick={handleRecalculateModalScore}
                  disabled={recalculatingScore}
                  className="btn-secondary !py-2 cursor-pointer"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${recalculatingScore ? 'animate-spin text-hl' : ''}`} />
                  <span>{t('projects.gonogo_modal.recalc_btn')}</span>
                </button>
              ) : <div />}

              <Link
                href={`/projects/${selectedModalProject.id}/export`}
                className="btn-primary !py-2 cursor-pointer"
              >
                <span>{t('projects.gonogo_modal.open_export_btn')}</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
