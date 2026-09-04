'use client';

import React, { useEffect, useRef, useState } from 'react';
import { BarChart3, RefreshCw, Calendar, CheckCircle2, AlertTriangle } from 'lucide-react';
import { api, fetchAuthenticatedBlobUrl } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

interface GanttPreviewProps {
  projectId: string;
  projectTitle?: string;
  initialImageUrl?: string;
}

export function GanttPreview({ projectId, projectTitle = 'Projet BTP', initialImageUrl }: GanttPreviewProps) {
  const { t } = useTranslation();
  const apiBase = (process.env.NEXT_PUBLIC_API_URL || '').replace(/\/$/, '');
  const [rawPath, setRawPath] = useState<string>(
    // Même correctif que organigramme-preview.tsx : "self/" est résolu côté backend
    // depuis le tenant authentifié réel, plus de tenant de démo hardcodé ici.
    initialImageUrl || `${apiBase}/api/visuals/file/self/visuals/${projectId}/gantt_planning.png`
  );
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading');
  const [authExpired, setAuthExpired] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [lastGenerated, setLastGenerated] = useState<string | null>(null);
  const objectUrlRef = useRef<string | null>(null);

  async function loadImage(path: string) {
    setLoadState('loading');
    setAuthExpired(false);
    try {
      const url = await fetchAuthenticatedBlobUrl(path);
      if (objectUrlRef.current) URL.revokeObjectURL(objectUrlRef.current);
      objectUrlRef.current = url;
      setBlobUrl(url);
      setLoadState('ready');
    } catch (err: any) {
      if (err?.status === 404 || String(err?.message || '').includes('404')) {
        setLoadState('missing');
      } else {
        console.error('Failed to load gantt image', err);
        setAuthExpired(err?.status === 401);
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
      setLastGenerated(t('visuals.gantt_static.completion_summary', { weeks: res.total_weeks, date: res.completion_date }));
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
    <div className="bg-card border border-line rounded-2xl p-6 shadow-xs space-y-4 font-sans">
      <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-line">
        <div>
          <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
            <BarChart3 className="w-5 h-5 text-hl" />
            {t('visuals.gantt_static.title')}
          </h3>
          <p className="text-xs text-muted-foreground">
            {t('visuals.gantt_static.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleRegenerate}
            disabled={isGenerating}
            className="btn-primary !py-1.5 !px-3 !text-xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isGenerating ? 'animate-spin' : ''}`} />
            <span>{isGenerating ? t('visuals.gantt_static.generating') : t('visuals.gantt_static.regenerate_btn')}</span>
          </button>
        </div>
      </div>

      {lastGenerated && (
        <div className="p-2.5 rounded-xl bg-positive/10 border border-positive/20 text-positive text-xs flex items-center gap-2">
          <CheckCircle2 className="w-3.5 h-3.5 text-positive" />
          {t('visuals.gantt_static.sync_prefix')} {lastGenerated}
        </div>
      )}

      {/* Image Preview Container */}
      <div className="relative rounded-xl border border-line overflow-hidden bg-sunken flex items-center justify-center p-2 min-h-[340px]">
        {loadState === 'ready' && blobUrl ? (
          <img
            src={blobUrl}
            alt={t('visuals.gantt_static.alt_text')}
            className="w-full h-auto rounded-lg shadow-sm object-contain max-h-[500px]"
          />
        ) : loadState === 'loading' || isGenerating ? (
          <div className="flex flex-col items-center gap-2 text-muted-foreground text-xs">
            <RefreshCw className="w-6 h-6 animate-spin text-hl" />
            {t('visuals.gantt_static.loading')}
          </div>
        ) : loadState === 'missing' ? (
          <div className="flex flex-col items-center gap-2 text-muted-foreground text-xs text-center px-6">
            <Calendar className="w-8 h-8 opacity-40" />
            {t('visuals.gantt_static.empty_title')}
            <span>{t('visuals.gantt_static.empty_hint')}</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-danger text-xs text-center px-6">
            <AlertTriangle className="w-8 h-8" />
            {t(authExpired ? 'visuals.gantt_static.error_title_auth' : 'visuals.gantt_static.error_title')}
            <span>{t('visuals.gantt_static.error_hint')}</span>
          </div>
        )}
      </div>

      <div className="flex items-center justify-between text-xs text-muted-foreground pt-2 border-t border-line">
        <span>{t('visuals.gantt_static.footer_format')}</span>
        <span className="text-hl font-medium">{t('visuals.section3_badge')}</span>
      </div>
    </div>
  );
}
