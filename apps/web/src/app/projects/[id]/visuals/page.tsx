'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { InteractiveGanttChart } from '@/components/visuals/interactive-gantt-chart';
import { OrganigrammePreview } from '@/components/visuals/organigramme-preview';
import { useTranslation } from '@/components/i18n-provider';

export default function VisualsPage() {
  const { t } = useTranslation();
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-8 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-foreground">{t('projects.visuals.heading')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          {t('projects.visuals.subtitle')}
        </p>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
        <InteractiveGanttChart projectId={projectId} />
        <OrganigrammePreview projectId={projectId} />
      </div>
    </div>
  );
}
