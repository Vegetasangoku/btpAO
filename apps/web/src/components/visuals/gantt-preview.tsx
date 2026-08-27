'use client';

import React, { useEffect, useRef, useState } from 'react';
import { BarChart3, RefreshCw, Calendar, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api, fetchAuthenticatedBlobUrl } from '@/lib/api';

interface GanttPreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function GanttPreview({ projectId, projectTitle = 'Projet BTP', initialImageUrl }: GanttPreviewProps) {
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  const [rawPath, setRawPath] = useState<string>(
    initialImageUrl || `${apiBase}/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/gantt_planning.png`
  );
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading');
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  async function loadImage(path: string) {
    setLoadState('loading');
    try {
      const url = await fetchAuthenticatedBlobUrl(path);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = url;
      setBlobUrl(url);
      setLoadState('ready');
    } catch (err: any) {
      if (String(err?.message || '').includes('404')) {
        setLoadState('missing');
      } else {
        console.error('Failed to load gantt image', err);
        setLoadState('error');
      }
    }
  }

  useEffect(() => {
    loadImage(rawPath);
    return () => {
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rawPath]);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateGantt(projectId, projectTitle, []);
      setLastGenerated(`${res.total_weeks} semaines (Livraison le ${res.completion_date})`);
      // Cache-bust via un nouveau chemin s3_key + timestamp, puis recharge en tant qu'image
      // authentifiée (plus jamais un <img src> direct vers une route protégée).
      setRawPath(`${apiBase}/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
    } catch (err) {
      console.error('Failed to generate gantt', err);
      setLoadState('error');
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
        {loadState === 'ready' && blobUrl ? (
          <img
            src={blobUrl}
            alt="Planning Gantt BTP"
            className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          />
        ) : loadState === 'loading' || isGenerating ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs">
            <RefreshCw className="w-6 h-6 animate-spin" />
            Chargement du planning...
          </div>
        ) : loadState === 'missing' ? (
          <div className="flex flex-col items-center gap-2 text-slate-500 text-xs text-center px-6">
            <Calendar className="w-8 h-8 text-slate-600" />
            Aucun planning généré pour ce projet pour l'instant.
            <span>Cliquez sur « Régénérer Gantt HD » pour le créer à partir des données du chantier.</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-rose-400 text-xs text-center px-6">
            <AlertTriangle className="w-8 h-8" />
            Impossible de charger le planning (session expirée ou service indisponible).
            <span>Réessayez « Régénérer Gantt HD », ou reconnectez-vous si le problème persiste.</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Format : PNG Haute Définition (300 DPI) • Intégration directe dans le document Word .docx</span>
        <span className="text-sky-400 font-medium">Inclus dans la section 3 (Méthodologie & Phasage)</span>
      </div>
    </div>
  );
}
