'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import {
  ArrowLeft,
  UploadCloud,
  ClipboardList,
  FileEdit,
  BarChart2,
  Download,
  CheckCircle2,
  Circle,
  ChevronRight,
  Loader2,
  Building2,
  Calendar,
  Banknote,
  Sparkles,
} from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';

const PIPELINE_STEPS = [
  { key: 'dce', label: '1. Ingestion DCE', icon: UploadCloud, desc: 'Analyse & extraction des critères de sélection' },
  { key: 'decisions', label: '2. Données Chantier', icon: ClipboardList, desc: 'Engins, délais, encadrement, RSE & PPSPS' },
  { key: 'editor', label: '3. Rédaction IA', icon: FileEdit, desc: 'Génération sur-mesure des 5 chapitres réglementaires' },
  { key: 'visuals', label: '4. Gantt & Visuels', icon: BarChart2, desc: 'Planning prévisionnel & organigramme d’encadrement' },
  { key: 'export', label: '5. Export Word & PDF', icon: Download, desc: 'Génération souveraine du livrable officiel prêt à déposer' },
];

export default function ProjectHubPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api
      .getProject(projectId)
      .then(setProject)
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-amber-500" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-20 text-slate-500">
        <p>Projet introuvable.</p>
        <Link href="/projects" className="text-amber-500 hover:underline text-sm mt-2 inline-block">
          ← Retour aux projets
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16 max-w-6xl mx-auto">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-slate-500 dark:text-slate-400">
        <Link href="/projects" className="hover:text-amber-600 dark:hover:text-amber-400 transition-colors flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Projets
        </Link>
        <ChevronRight className="w-3 h-3 text-slate-400 dark:text-slate-600" />
        <span className="text-amber-600 dark:text-amber-400 font-semibold truncate">{project.title}</span>
      </div>

      {/* Hero Card */}
      <div className="relative rounded-3xl p-7 overflow-hidden bg-white dark:bg-gradient-to-br dark:from-[#0F1422] dark:via-[#131B2E] dark:to-amber-950/30 border border-slate-200 dark:border-amber-500/20 shadow-sm dark:shadow-2xl transition-colors">
        <div className="absolute -right-10 -bottom-10 w-60 h-60 bg-amber-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-700 dark:text-amber-300">
              {project.reference_code || 'REF-AO'}
            </span>
            {project.go_no_go && project.go_no_go.has_sufficient_data !== false && (
              <span
                className={`text-[11px] font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                  project.go_no_go.recommendation === 'GO'
                    ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-700 dark:text-emerald-300'
                    : project.go_no_go.recommendation === 'RESERVES' || project.go_no_go.recommendation === 'RÉSERVES'
                    ? 'bg-amber-500/15 border-amber-500/30 text-amber-700 dark:text-amber-300'
                    : 'bg-rose-500/15 border-rose-500/30 text-rose-700 dark:text-rose-300'
                }`}
              >
                Score Go/No-Go : {Math.round(project.go_no_go.score)}% ({project.go_no_go.recommendation})
              </span>
            )}
            <span className="text-[11px] px-2.5 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
              Dossier Actif
            </span>
          </div>

          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 dark:text-white tracking-tight">{project.title}</h1>

          <div className="flex flex-wrap gap-5 text-xs text-slate-600 dark:text-slate-400 pt-1">
            <div className="flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-amber-500" />
              <span>Maître d'Ouvrage : <strong className="text-slate-900 dark:text-slate-200">{project.client_name}</strong></span>
            </div>
            {project.budget_estimate && (
              <div className="flex items-center gap-1.5">
                <Banknote className="w-3.5 h-3.5 text-emerald-500" />
                <span>Budget : <strong className="text-slate-900 dark:text-slate-200 font-mono">{project.budget_estimate.toLocaleString('fr-FR')} € HT</strong></span>
              </div>
            )}
            {project.submission_deadline && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-sky-500" />
                <span>Remise le : <strong className="text-slate-900 dark:text-slate-200">{new Date(project.submission_deadline).toLocaleDateString('fr-FR')}</strong></span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Pipeline Steps Cards */}
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-bold text-slate-900 dark:text-white">Workflow de Génération du Mémoire</h2>
          <span className="text-xs text-slate-500 dark:text-slate-400">5 Étapes de Réponse</span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {PIPELINE_STEPS.map((step, index) => {
            const Icon = step.icon;
            return (
              <Link
                key={step.key}
                href={`/projects/${projectId}/${step.key}`}
                className="group relative p-5 rounded-2xl bg-white dark:bg-[#0F1422] border border-slate-200 dark:border-[#1E293F] hover:border-amber-500/50 hover:shadow-lg dark:hover:shadow-amber-500/5 transition-all space-y-3 flex flex-col justify-between cursor-pointer"
              >
                <div className="space-y-3">
                  <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                    <Icon className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                  </div>

                  <div className="space-y-1">
                    <div className="text-xs font-bold text-slate-900 dark:text-slate-200 group-hover:text-amber-600 dark:group-hover:text-amber-400 transition-colors">
                      {step.label}
                    </div>
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-tight">{step.desc}</p>
                  </div>
                </div>

                <div className="flex items-center justify-end text-amber-600 dark:text-amber-400 text-xs font-bold pt-2 opacity-80 group-hover:opacity-100 group-hover:translate-x-1 transition-all">
                  <span>Accéder</span>
                  <ChevronRight className="w-4 h-4" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>
    </div>
  );
}
