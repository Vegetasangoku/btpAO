'use client';

import React from 'react';
import { useParams } from 'next/navigation';
import { DCEUploader } from '@/components/dce/dce-uploader';
import { useTranslation } from '@/components/i18n-provider';

export default function DCEPage() {
  const { t } = useTranslation();
  const params = useParams();
  const projectId = params.id as string;

  return (
    <div className="space-y-6 pb-12">
      <div>
        <h1 className="text-2xl font-extrabold text-foreground">{t('projects.dce.heading')}</h1>
        <p className="text-sm text-slate-600 dark:text-slate-400 mt-1">
          {t('projects.dce.subtitle')}
        </p>
      </div>
      <DCEUploader projectId={projectId} />
    </div>
  );
}
