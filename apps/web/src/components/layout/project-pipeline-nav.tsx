'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname, useParams } from 'next/navigation';
import {
  UploadCloud,
  ClipboardList,
  FileEdit,
  BarChart2,
  Download,
  CheckCircle2,
  ChevronRight,
  Sparkles,
} from 'lucide-react';
import { useTranslation } from '@/components/i18n-provider';

const PIPELINE_STEP_KEYS = [
  { key: 'dce', labelKey: 'projects.hub.step1_label', icon: UploadCloud },
  { key: 'decisions', labelKey: 'projects.hub.step2_label', icon: ClipboardList },
  { key: 'editor', labelKey: 'projects.hub.step3_label', icon: FileEdit },
  { key: 'visuals', labelKey: 'projects.hub.step4_label', icon: BarChart2 },
  { key: 'export', labelKey: 'projects.hub.step5_label', icon: Download },
];

export function ProjectPipelineNav() {
  const pathname = usePathname();
  const params = useParams();
  const projectId = params?.id as string;
  const { t } = useTranslation();

  if (!projectId) return null;

  return (
    <nav className="mb-5 p-1.5 rounded-2xl bg-white/90 dark:bg-card/90 backdrop-blur-md border border-line shadow-xs flex items-center gap-1 overflow-x-auto select-none">
      {PIPELINE_STEP_KEYS.map((step, idx) => {
        const href = `/projects/${projectId}/${step.key}`;
        const isActive = pathname.endsWith(`/${step.key}`);
        const Icon = step.icon;

        return (
          <Link
            key={step.key}
            href={href}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs whitespace-nowrap transition-all ${
              isActive
                ? 'bg-hl text-hl-contrast font-bold shadow-xs'
                : 'text-muted-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-raised font-medium'
            }`}
          >
            <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[9px] font-mono font-bold ${
              isActive ? 'bg-white text-hl' : 'bg-slate-200/70 dark:bg-raised text-muted-foreground'
            }`}>
              {idx + 1}
            </span>
            <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-white' : 'text-muted-foreground'}`} />
            <span>{t(step.labelKey)}</span>
          </Link>
        );
      })}
    </nav>
  );
}
