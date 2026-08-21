'use client';

import React, { useState } from 'react';
import { useParams } from 'next/navigation';
import {
  FileText,
  FileDown,
  Download,
  Loader2,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Package,
  Clock,
} from 'lucide-react';
import { api } from '@/lib/api';

interface ExportResult {
  docx_url?: string;
  pdf_url?: string;
  filename?: string;
  file_size_kb?: number;
  sections_count?: number;
}

export default function ExportPage() {
  const params = useParams();
  const projectId = params.id as string;
  const [exporting, setExporting] = useState<'docx' | 'pdf' | null>(null);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [includeVisuals, setIncludeVisuals] = useState(true);
  const [selectedTemplate, setSelectedTemplate] = useState('standard_btp');

  async function handleExport(format: 'docx' | 'pdf') {
    setExporting(format);
    setError(null);
    setResult(null);
    try {
      const data = await api.exportProject(projectId, { format, include_visuals: includeVisuals, template: selectedTemplate });
      setResult(data);
    } catch (err: any) {
      setError(err?.message || "Erreur lors de l'export. Vérifiez que toutes les sections ont été générées.");
    } finally {
      setExporting(null);
    }
  }

  return (
    <div className="space-y-8 pb-12 max-w-3xl">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-extrabold text-white">Centre d'Export — Word & PDF</h1>
        <p className="text-sm text-slate-400 mt-1">
          Compilez toutes les sections validées dans la charte de votre entreprise.
          Le moteur <strong className="text-slate-300">docxtpl</strong> injecte Gantt, Organigramme et toutes les données métier.
          LibreOffice génère ensuite le PDF fidèle au pixel.
        </p>
      </div>

      {/* Options Card */}
      <div className="p-6 rounded-2xl bg-slate-900/80 border border-slate-800 space-y-5">
        <h2 className="text-sm font-bold text-white">Paramètres d'Export</h2>

        {/* Template Selection */}
        <div>
          <label className="block text-xs font-semibold text-slate-300 mb-2">Modèle de document (charte Word)</label>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {[
              { id: 'standard_btp', label: 'Standard BTP', desc: 'Charte professionnelle gros œuvre' },
              { id: 'hqe_certified', label: 'HQE / Certifié', desc: 'Labels QE & Bâtiment Durable' },
              { id: 'compact_summary', label: 'Résumé Compact', desc: 'Version synthétique 20 pages max' },
            ].map((t) => (
              <button
                key={t.id}
                onClick={() => setSelectedTemplate(t.id)}
                className={`p-3 rounded-xl text-left border transition-all ${
                  selectedTemplate === t.id
                    ? 'border-sky-500 bg-sky-500/10 text-sky-300'
                    : 'border-slate-700 bg-slate-800/40 text-slate-400 hover:border-slate-600 hover:text-slate-200'
                }`}
              >
                <p className="text-xs font-bold">{t.label}</p>
                <p className="text-[10px] mt-0.5 opacity-70">{t.desc}</p>
              </button>
            ))}
          </div>
        </div>

        {/* Include Visuals Toggle */}
        <div className="flex items-center justify-between p-4 rounded-xl bg-slate-800/40 border border-slate-700">
          <div>
            <p className="text-xs font-semibold text-slate-200">Inclure les visuels Gantt & Organigramme</p>
            <p className="text-[11px] text-slate-400 mt-0.5">Injection automatique des PNGs 300 DPI dans le document Word</p>
          </div>
          <button
            onClick={() => setIncludeVisuals(!includeVisuals)}
            className={`w-11 h-6 rounded-full relative transition-colors ${includeVisuals ? 'bg-sky-600' : 'bg-slate-600'}`}
          >
            <span className={`absolute top-1 w-4 h-4 rounded-full bg-white shadow transition-transform ${includeVisuals ? 'translate-x-6' : 'translate-x-1'}`} />
          </button>
        </div>

        {/* Export Buttons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
          {/* Word Export */}
          <button
            onClick={() => handleExport('docx')}
            disabled={!!exporting}
            className="group relative overflow-hidden flex flex-col items-center gap-3 p-6 rounded-2xl bg-gradient-to-br from-sky-900/60 to-sky-900/20 border border-sky-500/30 hover:border-sky-500/60 hover:from-sky-900/80 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <div className="w-14 h-14 rounded-2xl bg-sky-500/20 border border-sky-500/30 flex items-center justify-center group-hover:scale-105 transition-transform">
              {exporting === 'docx'
                ? <Loader2 className="w-7 h-7 text-sky-400 animate-spin" />
                : <FileText className="w-7 h-7 text-sky-400" />
              }
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-white">Export Word (.docx)</p>
              <p className="text-xs text-slate-400 mt-0.5">Charte modifiable — Injection docxtpl</p>
            </div>
            {exporting === 'docx' && (
              <p className="text-xs text-sky-400 flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> Compilation en cours (≈5-15 sec)…
              </p>
            )}
          </button>

          {/* PDF Export */}
          <button
            onClick={() => handleExport('pdf')}
            disabled={!!exporting}
            className="group relative overflow-hidden flex flex-col items-center gap-3 p-6 rounded-2xl bg-gradient-to-br from-rose-900/40 to-rose-900/10 border border-rose-500/30 hover:border-rose-500/60 hover:from-rose-900/60 transition-all disabled:opacity-60 disabled:cursor-not-allowed"
          >
            <div className="w-14 h-14 rounded-2xl bg-rose-500/20 border border-rose-500/30 flex items-center justify-center group-hover:scale-105 transition-transform">
              {exporting === 'pdf'
                ? <Loader2 className="w-7 h-7 text-rose-400 animate-spin" />
                : <FileDown className="w-7 h-7 text-rose-400" />
              }
            </div>
            <div className="text-center">
              <p className="text-sm font-bold text-white">Export PDF</p>
              <p className="text-xs text-slate-400 mt-0.5">Rendu LibreOffice headless — Pixel perfect</p>
            </div>
            {exporting === 'pdf' && (
              <p className="text-xs text-rose-400 flex items-center gap-1.5">
                <Clock className="w-3 h-3" /> Conversion LibreOffice (≈20-30 sec)…
              </p>
            )}
          </button>
        </div>
      </div>

      {/* Error Banner */}
      {error && (
        <div className="flex items-start gap-3 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-sm">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
          <p>{error}</p>
        </div>
      )}

      {/* Success Result */}
      {result && (
        <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 space-y-4">
          <div className="flex items-center gap-2 text-emerald-300">
            <CheckCircle2 className="w-5 h-5" />
            <p className="text-sm font-bold">Document généré avec succès !</p>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
            {result.filename && (
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-700">
                <p className="text-slate-400">Fichier</p>
                <p className="text-slate-200 font-semibold mt-0.5 truncate">{result.filename}</p>
              </div>
            )}
            {result.file_size_kb && (
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-700">
                <p className="text-slate-400">Taille</p>
                <p className="text-slate-200 font-semibold font-mono mt-0.5">{result.file_size_kb} Ko</p>
              </div>
            )}
            {result.sections_count && (
              <div className="p-3 rounded-xl bg-slate-900/60 border border-slate-700">
                <p className="text-slate-400">Sections compilées</p>
                <p className="text-slate-200 font-semibold font-mono mt-0.5">{result.sections_count}</p>
              </div>
            )}
          </div>

          <div className="flex gap-3">
            {result.docx_url && (
              <a
                href={result.docx_url}
                download
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold transition-all"
              >
                <Download className="w-4 h-4" />
                Télécharger le Word
              </a>
            )}
            {result.pdf_url && (
              <a
                href={result.pdf_url}
                download
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all"
              >
                <Download className="w-4 h-4" />
                Télécharger le PDF
              </a>
            )}
          </div>
        </div>
      )}

      {/* Info Footer */}
      <div className="p-4 rounded-2xl bg-slate-900/40 border border-slate-800 text-xs text-slate-500 flex items-start gap-2">
        <Sparkles className="w-4 h-4 shrink-0 text-sky-500 mt-0.5" />
        <p>
          <strong className="text-slate-400">Technologie :</strong> Le moteur d'export utilise <em>docxtpl</em> (Jinja2 + python-docx) 
          pour injecter toutes les sections validées dans la charte Word de votre organisation,
          puis LibreOffice 7.x en mode headless pour la conversion PDF pixel-perfect. 
          Tous les fichiers sont stockés dans votre espace tenant isolé (MinIO S3).
        </p>
      </div>
    </div>
  );
}
