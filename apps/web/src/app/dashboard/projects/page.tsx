'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  FileText,
  Plus,
  ArrowRight,
  HardHat,
  Calendar,
  Building,
  CheckCircle2,
  Clock,
  ChevronRight,
  Sliders,
  Edit3,
  Download,
} from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';

export default function DashboardProjectsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadProjects() {
      try {
        const data = await api.getProjects();
        setProjects(data);
      } catch (err) {
        console.warn('Erreur chargement projets:', err);
      } finally {
        setLoading(false);
      }
    }
    loadProjects();
  }, []);

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-xs font-bold px-2.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
              Espace Conducteur & Chiffrage
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">
            Dossiers d'Appels d'Offres
          </h1>
          <p className="text-xs text-slate-400">
            Retrouvez tous vos dossiers en cours, reprenez l'analyse du DCE ou téléchargez les mémoires techniques finalisés.
          </p>
        </div>

        <Link
          href="/dashboard"
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold shadow-glow transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Nouveau Mémoire Technique</span>
        </Link>
      </div>

      {/* Projects List */}
      <div className="space-y-4">
        {projects.map((project) => (
          <div
            key={project.id}
            className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 hover:border-slate-700 transition-all shadow-xl space-y-4"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="space-y-1">
                <span className="text-[10px] font-mono font-bold px-2.5 py-0.5 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20">
                  {project.reference_code}
                </span>
                <h3 className="text-base font-black text-white">{project.title}</h3>
                <p className="text-xs text-slate-400">
                  Maître d'Ouvrage : <strong>{project.client_name}</strong> • {project.location || 'Île-de-France'}
                </p>
              </div>

              <span className="text-xs font-bold px-3 py-1 rounded-full bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 flex items-center gap-1.5">
                <CheckCircle2 className="w-3.5 h-3.5" /> Mémoire Prêt (Score 96%)
              </span>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-2 border-t border-slate-800">
              <Link
                href="/dashboard"
                className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-sky-500 text-left transition-colors group"
              >
                <p className="text-[10px] text-slate-500">Étape 1</p>
                <p className="text-xs font-bold text-slate-200 group-hover:text-sky-400">Analyse DCE</p>
              </Link>

              <Link
                href="/dashboard"
                className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-sky-500 text-left transition-colors group"
              >
                <p className="text-[10px] text-slate-500">Étape 2</p>
                <p className="text-xs font-bold text-slate-200 group-hover:text-sky-400">Chiffrage & Planning</p>
              </Link>

              <Link
                href="/dashboard"
                className="p-3 rounded-xl bg-slate-950/60 border border-slate-800 hover:border-sky-500 text-left transition-colors group"
              >
                <p className="text-[10px] text-slate-500">Étape 3</p>
                <p className="text-xs font-bold text-slate-200 group-hover:text-sky-400">Rédaction & Tiptap</p>
              </Link>

              <Link
                href="/dashboard"
                className="p-3 rounded-xl bg-sky-600/10 border border-sky-500/30 text-left hover:bg-sky-600/20 transition-colors group"
              >
                <p className="text-[10px] text-sky-400">Étape 4</p>
                <p className="text-xs font-bold text-sky-300">Télécharger Word / PDF</p>
              </Link>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
