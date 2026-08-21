'use client';

import React, { useState } from 'react';
import { Users, RefreshCw, CheckCircle2 } from 'lucide-react';
import { api } from '@/lib/api';

interface OrganigrammePreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function OrganigrammePreview({ projectId, projectTitle = 'Projet BTP', initialImageUrl }: OrganigrammePreviewProps) {
  const [imageUrl, setImageUrl] = useState<string>(
    initialImageUrl || `http://localhost:8000/api/visuals/file/tenants/11111111-1111-1111-1111-111111111111/visuals/${projectId}/organigramme_chantier.png`
  );
  const [isGenerating, setIsGenerating] = useState(false);

  const handleRegenerate = async () => {
    setIsGenerating(true);
    try {
      const res = await api.generateOrganigramme(projectId, projectTitle, []);
      setImageUrl(`http://localhost:8000/api/visuals/file/${res.s3_key}?t=${Date.now()}`);
    } catch (err) {
      console.error('Failed to generate organigramme', err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6 shadow-2xl space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <h3 className="text-sm font-bold text-white flex items-center gap-2">
            <Users className="w-5 h-5 text-emerald-400" />
            Organigramme d'Encadrement Chantier (BTP)
          </h3>
          <p className="text-xs text-slate-400">
            Hiérarchie opérationnelle, temps de présence effectif et qualifications des cadres (MOA, Conducteur, QSE).
          </p>
        </div>

        <button
          onClick={handleRegenerate}
          disabled={isGenerating}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-glow disabled:opacity-50 transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
          <span>{isGenerating ? 'Mise à jour...' : 'Régénérer Organigramme'}</span>
        </button>
      </div>

      {/* Image Preview */}
      <div className="relative rounded-xl border border-slate-800 overflow-hidden bg-slate-950 flex items-center justify-center p-2 min-h-[320px]">
        <img
          src={imageUrl}
          alt="Organigramme BTP"
          className="w-full h-auto rounded-lg shadow-md object-contain max-h-[500px]"
          onError={() => {
            handleRegenerate();
          }}
        />
      </div>

      <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-900">
        <span>Généré depuis les données du formulaire conducteur de travaux</span>
        <span className="text-emerald-400 font-medium">Inclus dans la section 1 (Moyens Humains)</span>
      </div>
    </div>
  );
}
