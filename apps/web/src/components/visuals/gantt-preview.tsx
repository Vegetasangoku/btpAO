'use client';

import React, { useState } from 'react';
import { BarChart3, RefreshCw, Download, Calendar, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';

interface GanttPreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function GanttPreview({ projectId, projectTitle = 'Projet BTP', initialImageUrl }: GanttPreviewProps) {
  const [imageUrl, setImageUrl] = useState<string>(
    initialImageUrl || `http://localhost:8000/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/gantt_planning.png`
  );
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateGantt(projectId, projectTitle, []);
      // Add timestamp to bypass browser cache
      setImageUrl(`http://localhost:8000/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
      setLastGenerated(`${res.total_weeks} semaines (Livraison le ${res.completion_date})`);
    } catch (err) {
      console.error('Failed to generate gantt', err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-sky-400" />
            Planning Prévisionnel de Phasage (Gantt BTP)
          </h3>
          <p className="text-xs text-slate-400">
            Généré automatiquement par Python Matplotlib avec chemin critique, jalons et marge intempéries.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRegenerate}
            disabled={isGenerating}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? 'Calcul du Gantt...' : 'Régénérer Gantt HD'}</span>
          </button>
        </div>
      </div>

      {lastGenerated && (
        <div className="p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
          Planning synchronisé : {lastGenerated}
        </div>
      )}

      {/* Image Preview Container */}
      <div className="relative rounded-xl border border-slate-800 overflow-hidden bg-slate-950 flex items-center justify-center p-2 min-h-[340px]">
        <img
          src={imageUrl}
          alt="Planning Gantt BTP"
          className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          onError={(e) => {
            // Trigger generation if not present
            handleRegenerate();
          }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Format : PNG Haute Définition (300 DPI) • Intégration directe dans le document Word .docx</span>
        <span className="text-sky-400 font-medium">Inclus dans la section 3 (Méthodologie & Phasage)</span>
      </div>
    </div>
  );
}
