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
  LayoutDashboard,
} from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';

const PIPELINE_STEPS = [
  { key: 'dce',       label: 'Ingestion DCE',       icon: UploadCloud,     desc: 'OCR + extraction des critères RC automatique' },
  { key: 'decisions', label: 'Données Chantier',     icon: ClipboardList,   desc: 'Engins, délais, encadrement, RSE, PPSPS' },
  { key: 'editor',    label: 'Rédaction IA & Édition', icon: FileEdit,      desc: 'Génération RAG section par section + WYSIWYG Tiptap' },
  { key: 'visuals',   label: 'Gantt & Organigramme', icon: BarChart2,       desc: 'Visuels haute-résolution Python Matplotlib' },
  { key: 'export',    label: 'Export Word & PDF',    icon: Download,        desc: 'Compilation docxtpl + LibreOffice headless' },
];

export default function ProjectHubPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [project, setProject] = useState<Project | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getProject(projectId)
      .then(setProject)
      .catch(console.warn)
      .finally(() => setLoading(false));
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="w-8 h-8 animate-spin text-sky-400" />
      </div>
    );
  }

  if (!project) {
    return (
      <div className="text-center py-20 text-slate-500">
        <p>Projet introuvable.</p>
        <Link href="/projects" className="text-sky-400 hover:underline text-sm mt-2 inline-block">← Retour aux projets</Link>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-12">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-xs text-slate-500">
        <Link href="/projects" className="hover:text-slate-300 flex items-center gap-1">
          <ArrowLeft className="w-3.5 h-3.5" /> Projets
        </Link>
        <ChevronRight className="w-3 h-3" />
        <span className="text-slate-300 font-semibold truncate">{project.title}</span>
      </div>

      {/* Hero Card */}
      <div className="relative rounded-3xl p-7 overflow-hidden bg-gradient-to-br from-slate-900 via-slate-900 to-sky-950/30 border border-sky-500/20 shadow-2xl">
        <div className="absolute -right-10 -bottom-10 w-60 h-60 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="relative z-10 space-y-3">
          <span className="text-[11px] font-mono font-bold px-2 py-1 rounded-md bg-sky-500/10 border border-sky-500/20 text-sky-300">
            {project.reference_code}
          </span>
          <h1 className="text-2xl font-extrabold text-white tracking-tight">{project.title}</h1>

          <div className="flex flex-wrap gap-5 text-xs text-slate-400 pt-1">
            <div className="flex items-center gap-1.5">
              <Building2 className="w-3.5 h-3.5 text-slate-500" />
              <span>Maître d'Ouvrage : <strong className="text-slate-200">{project.client_name}</strong></span>
            </div>
            {project.budget_estimate && (
              <div className="flex items-center gap-1.5">
                <Banknote className="w-3.5 h-3.5 text-slate-500" />
                <span>Budget : <strong className="text-slate-200 font-mono">{project.budget_estimate.toLocaleString('fr-FR')} € HT</strong></span>
              </div>
            )}
            {project.submission_deadline && (
              <div className="flex items-center gap-1.5">
                <Calendar className="w-3.5 h-3.5 text-slate-500" />
                <span>Remise le : <strong className="text-slate-200">{new Date(project.submission_deadline).toLocaleDateString('fr-FR')}</strong></span>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Pipeline Steps */}
      <div>
        <h2 className="text-base font-bold text-white mb-4">Pipeline de Génération du Mémoire Technique</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          {PIPELINE_STEPS.map((step, index) => {
            const Icon = step.icon;
            const done = true; // In real app would be computed from project state
            return (
              <Link
                key={step.key}
                href={`/projects/${projectId}/${step.key}`}
                className="group relative p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-sky-500/50 hover:shadow-xl transition-all space-y-3 flex flex-col"
              >
                <div className="absolute top-4 right-4">
                  {done
                    ? <CheckCircle2 className="w-4 h-4 text-emerald-400 opacity-80" />
                    : <Circle className="w-4 h-4 text-slate-600" />
                  }
                </div>

                <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/20 flex items-center justify-center group-hover:scale-105 transition-transform">
                  <Icon className="w-5 h-5 text-sky-400" />
                </div>

                <div className="space-y-1 flex-1">
                  <div className="text-xs font-bold text-slate-200 group-hover:text-sky-300 transition-colors flex items-center gap-1">
                    <span className="text-[10px] font-mono text-slate-500">{String(index + 1).padStart(2, '0')}</span>
                    <span>{step.label}</span>
                  </div>
                  <p className="text-[11px] text-slate-500 leading-tight">{step.desc}</p>
                </div>

                <div className="flex items-center justify-end text-sky-400 opacity-0 group-hover:opacity-100 transition-opacity">
                  <ChevronRight className="w-3.5 h-3.5" />
                </div>
              </Link>
            );
          })}
        </div>
      </div>

      {/* Quick Links */}
      <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800 flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-400 font-semibold">Accès rapide :</span>
        {PIPELINE_STEPS.map((step) => (
          <Link
            key={step.key}
            href={`/projects/${projectId}/${step.key}`}
            className="px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-xs font-semibold text-slate-300 hover:text-sky-300 border border-slate-700 hover:border-sky-500/40 transition-all"
          >
            {step.label}
          </Link>
        ))}
      </div>
    </div>
  );
}
