'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { InteractiveGanttChart } from '@/components/visuals/interactive-gantt-chart';
import { OrganigrammePreview } from '@/components/visuals/organigramme-preview';

export default function VisualsPage() {
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-white">Studio Visuels — Gantt & Organigramme</h1>
        <p className="text-sm text-slate-400 mt-1">
          Générez et personnalisez vos visuels haute-résolution (300 DPI) à injecter automatiquement
          dans le Word exporté. Chaque visuel est stocké dans votre espace tenant isolé.
        </p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <InteractiveGanttChart projectId={projectId} />
        <OrganigrammePreview projectId={projectId} />
      </div>
    </div>
  );
}
