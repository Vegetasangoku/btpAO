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

  // "Je confirme être conforme" — ajoute le critère manquant au corpus entreprise (via l'endpoint
  // existant /knowledge/assets) puis relance un vrai recalcul Go/No-Go (pas de score simulé
  // côté client) pour refléter instantanément l'information nouvellement disponible.
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
    <div className="space-y-6 pb-20 max-w-5xl mx-auto">
      {/* Top Header */}
      <div className="p-6 sm:p-8 rounded-2xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-sm flex flex-wrap items-center justify-between gap-4">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-400 border border-amber-500/20">
              {t('projects.badge')}
            </span>
          </div>
          <h1 className="text-xl sm:text-2xl font-black text-slate-900 dark:text-white tracking-tight">
            {t('projects.title')}
          </h1>
          <p className="text-xs text-slate-600 dark:text-slate-400">
            {t('projects.desc')}
          </p>
        </div>

        <Link
          href="/dashboard/wizard"
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black shadow-sm shadow-amber-500/20 transition-all cursor-pointer"
        >
          <Sparkles className="w-4 h-4" />
          <span>{t('projects.btn_new')}</span>
        </Link>
      </div>

      {/* Filter & Search Bar */}
      <div className="p-4 rounded-2xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] shadow-sm flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 bg-slate-50 dark:bg-[#0C0F17] px-3.5 py-2 rounded-xl border border-slate-200 dark:border-[#1E2638] flex-1 min-w-[240px]">
          <Search className="w-4 h-4 text-slate-400 shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder={t('projects.search_placeholder')}
            className="w-full bg-transparent text-xs text-slate-900 dark:text-white placeholder:text-slate-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          {[
            { id: 'all', label: t('projects.filter_all') },
            { id: 'in_progress', label: t('projects.filter_in_progress') },
            { id: 'completed', label: t('projects.filter_completed') },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setStatusFilter(tab.id)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold border transition-all cursor-pointer ${
                statusFilter === tab.id
                  ? 'bg-amber-500 text-slate-950 border-amber-500 shadow-sm'
                  : 'bg-slate-50 dark:bg-[#0C0F17] text-slate-600 dark:text-slate-400 border-slate-200 dark:border-[#1E2638] hover:text-slate-900 dark:hover:text-white'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        {loading ? (
          <div className="p-12 rounded-2xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] text-center text-xs text-slate-500 flex items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-amber-500" />
            <span>{t('dash.loading')}</span>
          </div>
        ) : filteredProjects.length === 0 ? (
          <div className="p-12 rounded-2xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] text-center space-y-3 shadow-sm">
            <FolderKanban className="w-8 h-8 text-slate-400 mx-auto" />
            <p className="text-xs font-bold text-slate-700 dark:text-slate-300">{t('projects.empty_title')}</p>
            <Link
              href="/dashboard/wizard"
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold transition-colors"
            >
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
                className="p-6 rounded-2xl bg-white dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] space-y-4 shadow-sm hover:border-amber-500/40 transition-colors"
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="space-y-1 min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-800 text-amber-700 dark:text-amber-400 border border-slate-200 dark:border-slate-700">
                        {project.reference_code || 'AO-EN-COURS'}
                      </span>
                      <span className="text-xs text-slate-500 font-semibold">{project.lot_number || 'Marché Public BTP'}</span>
                    </div>
                    <Link href={`/projects/${project.id}`} className="block group">
                      <h3 className="text-base font-bold text-slate-900 dark:text-white group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors truncate">
                        {project.title}
                      </h3>
                    </Link>
                    <p className="text-xs text-slate-600 dark:text-slate-400">
                      {t('projects.buyer')} : <strong className="text-slate-800 dark:text-slate-200">{project.client_name}</strong> • {project.location || 'France'}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 shrink-0">
                    {hasScore && (
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleOpenScoreModal(project);
                        }}
                        className={`text-[11px] font-mono font-black px-2.5 py-1 rounded-full border flex items-center gap-1.5 cursor-pointer shadow-xs hover:scale-105 transition-all ${
                          projectScore.recommendation === 'GO'
                            ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/25'
                            : projectScore.recommendation === 'RESERVES' || projectScore.recommendation === 'RÉSERVES'
                            ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/30 hover:bg-amber-500/25'
                            : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/30 hover:bg-rose-500/25'
                        }`}
                        title="Voir la matrice de décision Go / No-Go"
                      >
                        <TrendingUp className="w-3 h-3" />
                        <span>{Math.round(projectScore.score)}% {projectScore.recommendation}</span>
                      </button>
                    )}
                    <span
                      className={`text-[11px] font-mono font-bold px-3 py-1 rounded-full border ${
                        project.status === 'completed' || project.outcome_status === 'won'
                          ? 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20'
                          : 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20'
                      }`}
                    >
                      {project.status === 'completed' ? t('projects.status_ready') : t('projects.status_drafting')}
                    </span>
                  </div>
                </div>

                {/* Action Buttons to Dossier Tools */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 pt-3 border-t border-slate-200 dark:border-[#1E2638]">
                  {/* 1. Go / No-Go Button with Direct Score Preview */}
                  <button
                    type="button"
                    onClick={() => handleOpenScoreModal(project)}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] hover:border-amber-500/50 hover:bg-amber-500/5 text-left transition-all group cursor-pointer"
                  >
                    <div className="flex items-center justify-between">
                      <p className="text-[10px] text-slate-500 font-mono">Décision</p>
                      {hasScore ? (
                        <span
                          className={`text-[10px] font-mono font-black px-1.5 py-0.5 rounded ${
                            projectScore.recommendation === 'GO'
                              ? 'bg-emerald-500/20 text-emerald-600 dark:text-emerald-400'
                              : projectScore.recommendation === 'RESERVES' || projectScore.recommendation === 'RÉSERVES'
                              ? 'bg-amber-500/20 text-amber-700 dark:text-amber-400'
                              : 'bg-rose-500/20 text-rose-600 dark:text-rose-400'
                          }`}
                        >
                          {Math.round(projectScore.score)}% {projectScore.recommendation}
                        </span>
                      ) : (
                        <span className="text-[10px] font-mono text-slate-400">Score...</span>
                      )}
                    </div>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-200 group-hover:text-amber-600 dark:group-hover:text-amber-400 flex items-center gap-1 mt-0.5">
                      <TrendingUp className="w-3.5 h-3.5 text-amber-500" />
                      <span>{t('projects.btn_gonogo')}</span>
                    </p>
                  </button>

                  {/* 2. Planning & Gantt Button */}
                  <Link
                    href={`/projects/${project.id}/visuals`}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] hover:border-amber-500/50 hover:bg-amber-500/5 text-left transition-all group"
                  >
                    <p className="text-[10px] text-slate-500 font-mono">Chantier</p>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-200 group-hover:text-amber-600 dark:group-hover:text-amber-400 flex items-center gap-1 mt-0.5">
                      <BarChart2 className="w-3.5 h-3.5 text-amber-500" />
                      <span>{t('projects.btn_planning')}</span>
                    </p>
                  </Link>

                  {/* 3. AI Editor Button */}
                  <Link
                    href={`/projects/${project.id}/editor`}
                    className="p-3 rounded-xl bg-slate-50 dark:bg-[#0C0F17] border border-slate-200 dark:border-[#1E2638] hover:border-amber-500/50 hover:bg-amber-500/5 text-left transition-all group"
                  >
                    <p className="text-[10px] text-slate-500 font-mono">Rédaction</p>
                    <p className="text-xs font-bold text-slate-800 dark:text-slate-200 group-hover:text-amber-600 dark:group-hover:text-amber-400 flex items-center gap-1 mt-0.5">
                      <Edit3 className="w-3.5 h-3.5 text-amber-500" />
                      <span>{t('projects.btn_wizard')}</span>
                    </p>
                  </Link>

                  {/* 4. Export & Download Button */}
                  <Link
                    href={`/projects/${project.id}/export`}
                    className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/30 hover:bg-amber-500/20 text-left transition-all group"
                  >
                    <p className="text-[10px] text-amber-700 dark:text-amber-400 font-mono">Livraison</p>
                    <p className="text-xs font-bold text-amber-700 dark:text-amber-300 flex items-center gap-1 mt-0.5">
                      <Download className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
                      <span>{t('projects.btn_download')}</span>
                    </p>
                  </Link>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* MODAL: GO / NO-GO SCORE DETAILS POPUP */}
      {selectedModalProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-md animate-in fade-in">
          <div className="relative w-full max-w-xl rounded-3xl bg-white dark:bg-[#0F1422] border border-slate-200 dark:border-[#1E293F] p-6 sm:p-7 shadow-2xl space-y-5">
            {/* Modal Header */}
            <div className="flex items-start justify-between gap-4 border-b border-slate-100 dark:border-slate-800 pb-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-amber-500/15 text-amber-700 dark:text-amber-400 border border-amber-500/30">
                    {selectedModalProject.reference_code || 'AO-REF'}
                  </span>
                  <span className="text-xs text-slate-500">Évaluation Stratégique IA</span>
                </div>
                <h3 className="text-base font-bold text-slate-900 dark:text-white truncate max-w-md">
                  {selectedModalProject.title}
                </h3>
              </div>

              <button
                type="button"
                onClick={() => setSelectedModalProject(null)}
                className="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            {loadingModalScore ? (
              <div className="p-12 text-center space-y-3">
                <Loader2 className="w-8 h-8 text-amber-500 animate-spin mx-auto" />
                <p className="text-xs text-slate-500">Chargement de la matrice Go/No-Go...</p>
              </div>
            ) : modalAnalysis ? (
              <div className="space-y-4">
                {/* Taux de Complétion — avancement factuel du remplissage du dossier, toujours affiché */}
                <div className="p-4 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-slate-600 dark:text-slate-400 uppercase tracking-wide">Taux de Complétion du Dossier</span>
                    <span className="text-sm font-black font-mono text-slate-900 dark:text-white">
                      {Math.round(modalAnalysis.completion_rate ?? 0)}%
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-slate-200 dark:bg-slate-800 overflow-hidden">
                    <div
                      className="h-full rounded-full bg-amber-500 transition-all"
                      style={{ width: `${Math.min(100, Math.max(0, modalAnalysis.completion_rate ?? 0))}%` }}
                    />
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-slate-500">
                    Données trouvées vs. requises pour ce dossier (sections du mémoire technique générées).
                  </p>
                </div>

                {/* Score Stratégique — masqué si aucune donnée réelle ne permet de le justifier (jamais de score arbitraire) */}
                {modalAnalysis.has_sufficient_data === false ? (
                  <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-dashed border-slate-300 dark:border-slate-700 text-center space-y-1.5">
                    <p className="text-xs font-bold text-slate-600 dark:text-slate-400">Score Stratégique non disponible</p>
                    <p className="text-[11px] text-slate-500 dark:text-slate-500 max-w-sm mx-auto">
                      Données insuffisantes (DCE, qualifications, délais, historique) pour évaluer la pertinence stratégique de cet AO. Complétez le profil entreprise ou le DCE pour débloquer ce score.
                    </p>
                  </div>
                ) : (
                <div className="p-5 rounded-2xl bg-slate-50 dark:bg-slate-950/80 border border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4">
                  <div className="space-y-1.5">
                    <span
                      className={`text-xs font-black uppercase tracking-wider px-3 py-1 rounded-full border inline-block ${
                        modalAnalysis.recommendation === 'GO'
                          ? 'bg-emerald-500/15 text-emerald-700 dark:text-emerald-300 border-emerald-500/40'
                          : modalAnalysis.recommendation === 'RESERVES' || modalAnalysis.recommendation === 'RÉSERVES'
                          ? 'bg-amber-500/15 text-amber-700 dark:text-amber-300 border-amber-500/40'
                          : 'bg-rose-500/15 text-rose-700 dark:text-rose-300 border-rose-500/40'
                      }`}
                    >
                      {modalAnalysis.recommendation === 'GO'
                        ? '✅ DÉCISION : GO CONFIRMÉ'
                        : modalAnalysis.recommendation === 'RESERVES' || modalAnalysis.recommendation === 'RÉSERVES'
                        ? '⚠️ DÉCISION : GO SOUS RÉSERVES'
                        : '🛑 DÉCISION : NO-GO RECOMMANDÉ'}
                    </span>
                    <p className="text-xs text-slate-700 dark:text-slate-300 leading-relaxed pt-1">
                      {modalAnalysis.summary}
                    </p>
                  </div>

                  <div className="shrink-0 flex flex-col items-center justify-center p-4 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 text-center min-w-[100px] shadow-sm">
                    <span
                      className={`text-3xl font-black font-mono ${
                        modalAnalysis.score >= 70
                          ? 'text-emerald-500'
                          : modalAnalysis.score >= 50
                          ? 'text-amber-500'
                          : 'text-rose-500'
                      }`}
                    >
                      {Math.round(modalAnalysis.score)}%
                    </span>
                    <span className="text-[10px] text-slate-400 uppercase font-bold tracking-wider">Score Global</span>
                  </div>
                </div>
                )}

                {/* Criteria Checks */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
                    {modalAnalysis.mandatory_criteria_met ? (
                      <Check className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" />
                    ) : (
                      <XCircle className="w-4 h-4 text-rose-500 shrink-0 mt-0.5" />
                    )}
                    <div>
                      <p className="font-bold text-slate-900 dark:text-white">Critères éliminatoires</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {modalAnalysis.mandatory_criteria_met
                          ? '100% des critères minimaux DCE validés'
                          : 'Critères obligatoires non satisfaits'}
                      </p>
                    </div>
                  </div>

                  <div className="p-3.5 rounded-xl bg-slate-50 dark:bg-slate-950/60 border border-slate-200 dark:border-slate-800 flex items-start gap-2.5">
                    <ShieldCheck className="w-4 h-4 text-sky-500 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-bold text-slate-900 dark:text-white">Conformité Entreprise</p>
                      <p className="text-[11px] text-slate-500 dark:text-slate-400">
                        {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0
                          ? `${modalAnalysis.blocking_issues.length} points de vigilance`
                          : 'Aucun blocage réglementaire'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Blocking Issues List (texte réel, pas juste un compteur) */}
                {modalAnalysis.blocking_issues && modalAnalysis.blocking_issues.length > 0 && (
                  <div className="p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-500/30 space-y-1.5">
                    <p className="text-[11px] font-bold text-rose-700 dark:text-rose-300 uppercase tracking-wide">Points bloquants identifiés</p>
                    <ul className="space-y-2">
                      {modalAnalysis.blocking_issues.map((issue, idx) => (
                        <li key={idx} className="text-[11px] text-rose-700 dark:text-rose-300 flex items-start justify-between gap-2">
                          <span className="flex items-start gap-1.5">
                            <span className="mt-0.5">•</span>
                            <span>{issue}</span>
                          </span>
                          <button
                            type="button"
                            onClick={() => handleConfirmCompliance(issue)}
                            disabled={confirmingIssue === issue}
                            className="shrink-0 flex items-center gap-1 px-2 py-1 rounded-lg bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 text-[10px] font-semibold disabled:opacity-50 transition-colors cursor-pointer"
                          >
                            {confirmingIssue === issue ? (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            ) : (
                              <Check className="w-3 h-3" />
                            )}
                            <span>Je confirme être conforme</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Detail facteur par facteur — donnees reelles calculees par go_no_go_service.py */}
                {modalAnalysis.factors && modalAnalysis.factors.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-[11px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wide px-0.5">
                      Détail de l'analyse ({modalAnalysis.factors.length} critères évalués)
                    </p>
                    {modalAnalysis.factors.map((factor, idx) => {
                      const statusStyles: Record<string, string> = {
                        ok: 'border-emerald-200 dark:border-emerald-500/30 bg-emerald-50 dark:bg-emerald-950/20',
                        warning: 'border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-950/20',
                        blocking: 'border-rose-200 dark:border-rose-500/30 bg-rose-50 dark:bg-rose-950/20',
                        missing_data: 'border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/40',
                      };
                      const statusIcon: Record<string, string> = {
                        ok: '✅',
                        warning: '⚠️',
                        blocking: '🛑',
                        missing_data: 'ℹ️',
                      };
                      return (
                        <div
                          key={idx}
                          className={`p-3 rounded-xl border text-xs space-y-1 ${statusStyles[factor.status] || statusStyles.missing_data}`}
                        >
                          <p className="font-bold text-slate-900 dark:text-white flex items-center gap-1.5">
                            <span>{statusIcon[factor.status] || 'ℹ️'}</span>
                            <span>{factor.title}</span>
                          </p>
                          <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">{factor.detail}</p>
                          {factor.recommendation && (
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                              <span className="font-semibold">Recommandation : </span>
                              {factor.recommendation}
                            </p>
                          )}
                        </div>
                      );
                    })}
                    <p className="text-[10px] text-slate-400 dark:text-slate-500 italic px-0.5 pt-1">
                      Analyse calculée à partir de données réelles de votre dossier (DCE, profil entreprise, délais, historique) — aucune donnée n'est inventée.
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="p-8 rounded-2xl bg-slate-50 dark:bg-slate-950/50 border border-dashed border-slate-200 dark:border-slate-800 text-center space-y-3">
                <Sparkles className="w-8 h-8 text-amber-500 mx-auto animate-pulse" />
                <p className="text-xs font-bold text-slate-900 dark:text-white">Analyse Go/No-Go non encore calculée</p>
                <p className="text-[11px] text-slate-500 max-w-sm mx-auto">
                  L'IA croise les critères extraits du DCE avec vos moyens disponibles pour calculer votre chance de remporter l'appel d'offres.
                </p>
                <button
                  type="button"
                  onClick={handleRecalculateModalScore}
                  disabled={recalculatingScore}
                  className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-extrabold shadow-md shadow-amber-500/20 transition-all cursor-pointer"
                >
                  {recalculatingScore ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                  <span>Calculer le score Go / No-Go</span>
                </button>
              </div>
            )}

            {/* Modal Actions Footer */}
            <div className="flex items-center justify-between gap-3 pt-3 border-t border-slate-100 dark:border-slate-800">
              {modalAnalysis ? (
                <button
                  type="button"
                  onClick={handleRecalculateModalScore}
                  disabled={recalculatingScore}
                  className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-300 text-xs font-bold border border-slate-200 dark:border-slate-700 transition-colors cursor-pointer disabled:opacity-50"
                >
                  <RefreshCw className={`w-3.5 h-3.5 ${recalculatingScore ? 'animate-spin text-amber-500' : ''}`} />
                  <span>Recalculer l'analyse</span>
                </button>
              ) : <div />}

              <Link
                href={`/projects/${selectedModalProject.id}/export`}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black shadow-sm transition-all"
              >
                <span>Ouvrir l'Espace Export & Livrables</span>
                <ChevronRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
