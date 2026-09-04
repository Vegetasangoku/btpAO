'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { DecisionForm } from '@/components/decisions/decision-form';
import { useTranslation } from '@/components/i18n-provider';

export default function DecisionsPage() {
  const { t } = useTranslation();
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-foreground">{t('projects.decisions.heading')}</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
          {t('projects.decisions.subtitle')}
        </p>
      </div>
      <DecisionForm projectId={projectId} />
    </div>
  );
}
