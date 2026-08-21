'use client';

import React from 'react';
import Link from 'next/link';
import {
  Server,
  Activity,
  ArrowLeft,
  CheckCircle2,
  Database,
  Cpu,
  Layers,
  HardDrive,
} from 'lucide-react';

export default function AdminInfrastructurePage() {
  const buckets = [
    { name: 'dce-files', desc: 'Fichiers PDF des dossiers de consultation déposés par les conducteurs', size: '2.4 Go', count: 18, status: 'Actif' },
    { name: 'company-memories', desc: 'Bases documentaires entreprises : Qualibat, CVs, fiches grues et mémoires types', size: '1.1 Go', count: 42, status: 'Actif' },
    { name: 'generated-docs', desc: 'Mémoires techniques assemblés finaux en formats Word (.docx) et PDF', size: '850 Mo', count: 29, status: 'Actif' },
  ];

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
              Super Administration
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">
            Supervision Cluster OCR & Stockage
          </h1>
          <p className="text-xs text-slate-400">
            État des services de numérisation, connecteurs API IA et volumes des buckets Supabase Storage.
          </p>
        </div>

        <Link
          href="/admin"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tableau de bord</span>
        </Link>
      </div>

      {/* Services Status Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white">Moteur OCR & Extraction DCE</span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <p className="text-2xl font-black text-white font-mono">99.98 % Uptime</p>
          <p className="text-xs text-slate-400">Latence moyenne : <strong>2.4s / 100 pages</strong></p>
        </div>

        <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white">Passerelle Modèles IA</span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <p className="text-2xl font-black text-white font-mono">Opérationnel</p>
          <p className="text-xs text-slate-400">Claude 3.5, GPT-4o, Gemini 1.5, Mistral</p>
        </div>

        <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-white">Générateur Word & PDF</span>
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
          </div>
          <p className="text-2xl font-black text-white font-mono">0 Erreur</p>
          <p className="text-xs text-slate-400">Assemblage haute fidélité</p>
        </div>
      </div>

      {/* Buckets List */}
      <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <HardDrive className="w-4 h-4 text-rose-400" />
          <span>Buckets de Stockage Supabase Storage</span>
        </h2>

        <div className="divide-y divide-slate-800">
          {buckets.map((b) => (
            <div key={b.name} className="py-4 flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold font-mono text-white">{b.name}</span>
                  <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    {b.status}
                  </span>
                </div>
                <p className="text-xs text-slate-400">{b.desc}</p>
              </div>

              <div className="text-right">
                <p className="text-sm font-bold text-white font-mono">{b.size}</p>
                <p className="text-[10px] text-slate-500">{b.count} fichiers indexés</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
