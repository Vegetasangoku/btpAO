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

const PIPELINE_STEPS = [
  { key: 'dce', label: '1. Ingestion DCE', icon: UploadCloud },
  { key: 'decisions', label: '2. Données Chantier', icon: ClipboardList },
  { key: 'editor', label: '3. Rédaction IA', icon: FileEdit },
  { key: 'visuals', label: '4. Gantt & Visuels', icon: BarChart2 },
  { key: 'export', label: '5. Export Word & PDF', icon: Download },
];

export function ProjectPipelineNav() {
  const pathname = usePathname();
  const params = useParams();
  const projectId = params?.id as string;

  if (!projectId) return null;

  return (
    <nav className="mb-6 p-1.5 rounded-2xl bg-white dark:bg-[#121622] border border-slate-200 dark:border-[#1E2638] shadow-sm flex items-center gap-1 overflow-x-auto">
      {PIPELINE_STEPS.map((step) => {
        const href = `/projects/${projectId}/${step.key}`;
        const isActive = pathname.endsWith(`/${step.key}`);
        const Icon = step.icon;

        return (
          <Link
            key={step.key}
            href={href}
            className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all ${
              isActive
                ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20 ring-1 ring-amber-400'
                : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#1A2030]'
            }`}
          >
            <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-slate-950' : 'text-slate-400 dark:text-slate-500'}`} />
            <span>{step.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
