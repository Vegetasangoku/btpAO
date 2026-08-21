'use client';

import React, { useState } from 'react';
import {
  UploadCloud,
  FileText,
  CheckCircle2,
  AlertCircle,
  Sparkles,
  Shield,
  Layers,
  Search,
} from 'lucide-react';
import { DCECriterion } from '@/lib/types';
import { api } from '@/lib/api';

interface DCEUploaderProps {
  projectId: string;
  criteria?: DCECriterion[];
  onCriteriaExtracted?: (criteria: DCECriterion[]) => void;
}

export function DCEUploader({ projectId, criteria = [], onCriteriaExtracted }: DCEUploaderProps) {
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [docType, setDocType] = useState('rc');
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files || files.length === 0) return;

    const file = files[0];
    setIsUploading(true);
    setUploadProgress(20);
    setStatusMessage('Téléchargement du fichier vers le bucket sécurisé S3...');

    try {
      setTimeout(() => setUploadProgress(50), 400);
      setTimeout(() => setStatusMessage('Analyse OCR & extraction du texte par Azure Document Intelligence...'), 800);
      setTimeout(() => setUploadProgress(80), 1200);
      setTimeout(() => setStatusMessage('Vectorisation des chunks sémantiques (pgvector) & Extraction des critères RC...'), 1600);

      const res = await api.uploadDCE(projectId, docType, file);
      setUploadProgress(100);
      setStatusMessage('Document analysé avec succès ! Grille de critères extraite.');

      // Refresh criteria
      const updatedCriteria = await api.getCriteria(projectId);
      if (onCriteriaExtracted) {
        onCriteriaExtracted(updatedCriteria);
      }
    } catch (err) {
      console.error('Upload failed', err);
      setStatusMessage('Erreur lors du traitement du document.');
    } finally {
      setTimeout(() => {
        setIsUploading(false);
        setUploadProgress(0);
      }, 3000);
    }
  };

  return (
    <div className="space-y-6">
      {/* Upload Box Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <UploadCloud className="w-5 h-5 text-sky-400" />
              Ingestion & Traitement des Pièces du DCE
            </h3>
            <p className="text-xs text-slate-400">
              Extraction automatique du texte, des tableaux et des critères de notation (RC, CCTP, CCAP).
            </p>
          </div>

          <div className="flex items-center gap-2">
            <label className="text-xs text-slate-400 font-medium">Type de pièce :</label>
            <select
              value={docType}
              onChange={(e) => setDocType(e.target.value)}
              className="bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-sky-500"
            >
              <option value="rc">RC (Règlement de Consultation)</option>
              <option value="cctp">CCTP (Cahier des Clauses Techniques)</option>
              <option value="ccap">CCAP (Clauses Administratives)</option>
              <option value="bpu">BPU / DPGF</option>
            </select>
          </div>
        </div>

        {/* Drag & Drop Zone */}
        <label className="border-2 border-dashed border-slate-700 hover:border-sky-500/60 rounded-xl p-8 flex flex-col items-center justify-center gap-3 cursor-pointer bg-slate-950/40 hover:bg-slate-950/70 transition-all group">
          <div className="w-12 h-12 rounded-2xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center group-hover:scale-110 transition-transform">
            <UploadCloud className="w-6 h-6 text-sky-400" />
          </div>
          <div className="text-center">
            <p className="text-xs font-bold text-slate-200">
              Glissez-déposez le fichier PDF ici ou <span className="text-sky-400 underline">parcourez vos fichiers</span>
            </p>
            <p className="text-[11px] text-slate-400 mt-1">
              Formats acceptés : PDF, DOCX (Taille max : 100 Mo) • Traitement OCR & pgvector
            </p>
          </div>
          <input
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileUpload}
            disabled={isUploading}
            className="hidden"
          />
        </label>

        {/* Upload Progress Bar */}
        {isUploading && (
          <div className="space-y-2 p-4 rounded-xl bg-slate-950/80 border border-sky-500/30">
            <div className="flex justify-between text-xs font-semibold">
              <span className="text-sky-300 flex items-center gap-2">
                <Sparkles className="w-3.5 h-3.5 text-sky-400 animate-spin" />
                {statusMessage}
              </span>
              <span className="text-slate-400">{uploadProgress}%</span>
            </div>
            <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
              <div
                className="bg-gradient-to-r from-sky-500 to-emerald-500 h-2 transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Extracted Criteria Table */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div>
            <h3 className="text-sm font-bold text-white flex items-center gap-2">
              <Layers className="w-5 h-5 text-emerald-400" />
              Grille de Pondération & Critères de Notation (Extrait RC)
            </h3>
            <p className="text-xs text-slate-400">
              Le moteur RAG s'assure que 100% de ces exigences sont couvertes et chiffrées dans chaque section rédigée.
            </p>
          </div>

          <span className="text-xs font-mono font-bold bg-emerald-500/10 text-emerald-300 border border-emerald-500/30 px-3 py-1 rounded-full">
            Valeur Technique : 60% • Prix : 40%
          </span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {criteria.map((c, idx) => (
            <div
              key={c.id || idx}
              className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-slate-700 transition-all flex flex-col justify-between space-y-3"
            >
              <div className="space-y-2">
                <div className="flex items-start justify-between gap-2">
                  <h4 className="text-xs font-bold text-slate-200">{c.criterion_title}</h4>
                  <span className="shrink-0 px-2 py-0.5 rounded bg-sky-500/20 text-sky-300 text-[11px] font-mono font-bold border border-sky-500/30">
                    {c.weight_percentage}%
                  </span>
                </div>
                <p className="text-[11px] text-slate-400 leading-relaxed">{c.description}</p>
              </div>

              <div className="space-y-1.5 pt-2 border-t border-slate-900">
                <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                  Preuves & Éléments attendus :
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {c.key_expectations.map((exp, eIdx) => (
                    <span
                      key={eIdx}
                      className="text-[10px] bg-slate-900 border border-slate-800 text-slate-300 px-2 py-0.5 rounded"
                    >
                      ✓ {exp}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
