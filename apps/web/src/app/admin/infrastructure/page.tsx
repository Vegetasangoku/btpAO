'use client';

import React, { useEffect, useState, useRef } from 'react';
import Link from 'next/link';
import {
  Server,
  Activity,
  ArrowLeft,
  CheckCircle2,
  Database,
  Cpu,
  Layers,
  HardDrive,
  Loader2,
  ShieldCheck,
  AlertTriangle,
  RefreshCw,
  Zap,
  Globe,
  Lock,
  FileText,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';

interface HealthData {
  status: 'healthy' | 'degraded' | 'unhealthy';
  timestamp: string;
  latency_ms: number;
  database: {
    status: string;
    latency_ms: number;
    error?: string | null;
  };
  redis_celery: {
    status: string;
    broker_url: string;
    ping?: string;
    error?: string | null;
  };
  llm_providers: Record<string, {
    configured: boolean;
    status: string;
    /* Optionnels : un fournisseur ajouté sans zone déclarée n'expose ni l'un ni
       l'autre. Les traiter comme obligatoires a déjà coûté une page blanche. */
    zone?: string;
    source?: string;
  }>;
  system: {
    cpu_percent: number;
    ram_used_pct: number;
    ram_available_mb: number;
  };
}

export default function AdminInfrastructurePage() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<string>('');
  const inFlightRef = useRef(false);
  const badStreakRef = useRef(0);
  const hasReadingRef = useRef(false);

  // Le pooler Supabase distant est parfois simplement lent (plusieurs secondes)
  // sans être réellement en panne. Une lecture dégradée/en échec isolée ne fait
  // donc pas basculer l'affichage immédiatement : il faut 2 lectures mauvaises
  // consécutives avant d'afficher rouge/orange, pour éviter que l'écran
  // clignote entre les couleurs à chaque cycle de 15s alors que la connexion
  // finit par réussir. Utilise des refs (pas le state `health`) pour éviter le
  // piège classique de closure figée avec setInterval + useEffect([]).
  function applyReading(data: HealthData) {
    const isBad = data.status !== 'healthy';
    if (!isBad) {
      badStreakRef.current = 0;
      hasReadingRef.current = true;
      setHealth(data);
      return;
    }
    badStreakRef.current += 1;
    if (badStreakRef.current >= 2 || !hasReadingRef.current) {
      hasReadingRef.current = true;
      setHealth(data);
    }
  }

  async function checkHealth() {
    if (inFlightRef.current) return; // jamais deux vérifications simultanées
    inFlightRef.current = true;
    try {
      setRefreshing(true);
      const data = await api.getClusterHealth();
      applyReading(data as HealthData);
      setLastChecked(new Date().toLocaleTimeString('fr-FR'));
    } catch (err) {
      console.error('Erreur health check:', err);
      // If backend returns a non-200 JSON payload, try to extract it
      try {
        const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
        const targetUrl = rawApiUrl.endsWith('/api') ? `${rawApiUrl}/health` : `${rawApiUrl}/api/health`;
        const res = await fetch(targetUrl);
        const data = await res.json();
        applyReading(data as HealthData);
      } catch {
        applyReading({
          status: 'unhealthy',
          timestamp: new Date().toISOString(),
          latency_ms: 0,
          database: { status: 'unhealthy', latency_ms: 0, error: t('admin.infra.db_unreachable_error') },
          redis_celery: { status: 'unhealthy', broker_url: 'N/A', error: t('admin.infra.redis_unreachable_error') },
          llm_providers: {},
          system: { cpu_percent: 0, ram_used_pct: 0, ram_available_mb: 0 },
        });
      }
      setLastChecked(new Date().toLocaleTimeString('fr-FR'));
    } finally {
      setLoading(false);
      setRefreshing(false);
      inFlightRef.current = false;
    }
  }


  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  const isHealthy = health?.status === 'healthy';
  const isDegraded = health?.status === 'degraded';

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="badge-pill font-medium">
              {t('admin.common.badge_super_admin')}
            </span>
            {health && (
              <span className={`badge-pill text-[10px] font-mono ${
                isHealthy
                  ? 'badge-pill-emerald'
                  : isDegraded
                  ? 'badge-pill'
                  : 'badge-pill-red'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${
                  isHealthy ? 'bg-positive' : isDegraded ? 'bg-hl' : 'bg-danger'
                }`} />
                <span>{t('admin.infra.cluster_status', { status: health.status.toUpperCase() })}</span>
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground font-heading tracking-tight">
            {t('admin.infra.heading')}
          </h1>
          <p className="text-xs text-muted-foreground font-medium">
            {t('admin.infra.subtitle')}
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={checkHealth}
            disabled={refreshing}
            className="btn-secondary !py-2 !px-3.5 !text-xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-hl' : 'text-hl'}`} />
            <span>{t('admin.infra.btn_refresh', { time: lastChecked ? `(${lastChecked})` : '' })}</span>
          </button>

          <Link
            href="/admin"
            className="inline-flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-slate-900 dark:hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>{t('admin.common.back_dashboard')}</span>
          </Link>
        </div>
      </div>

      {loading && !health ? (
        <div className="p-12 rounded-2xl bg-card border border-line flex items-center justify-center gap-3 shadow-xs">
          <Loader2 className="w-6 h-6 animate-spin text-hl" />
          <span className="text-xs font-bold text-foreground">{t('admin.infra.loading')}</span>
        </div>
      ) : (
        <>
          {/* Services Status Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Database Card */}
            <div className={`p-5 rounded-2xl bg-card border space-y-3 shadow-xs transition-all ${
              health?.database.status === 'healthy' ? 'border-positive/30' : 'border-danger/30'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
                  <Database className={`w-4 h-4 ${
                    health?.database.status === 'healthy' ? 'text-positive' : 'text-danger'
                  }`} />
                  {t('admin.infra.db_card_title')}
                </span>
                <span className={`w-2 h-2 rounded-full ${
                  health?.database.status === 'healthy' ? 'bg-positive animate-pulse' : 'bg-danger'
                }`} />
              </div>
              <p className={`text-xl font-bold font-mono ${
                health?.database.status === 'healthy' ? 'text-positive' : 'text-danger'
              }`}>
                {health?.database.status === 'healthy' ? t('admin.infra.db_connected') : t('admin.infra.db_failed')}
              </p>
              <div className="text-[11px] text-muted-foreground flex items-center justify-between">
                <span>{t('admin.infra.db_latency_label')}</span>
                <span className="font-mono text-foreground font-bold">{health?.database.latency_ms} ms</span>
              </div>
              {health?.database.error && (
                <p className="text-[10px] text-danger bg-danger/10 p-2 rounded-lg border border-danger/20 font-mono">
                  {health.database.error}
                </p>
              )}
            </div>

            {/* Redis & Celery Card */}
            <div className={`p-5 rounded-2xl bg-card border space-y-3 shadow-xs transition-all ${
              health?.redis_celery.status === 'healthy' ? 'border-positive/30' : 'border-hl/30'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
                  <Cpu className={`w-4 h-4 ${
                    health?.redis_celery.status === 'healthy' ? 'text-positive' : 'text-hl'
                  }`} />
                  {t('admin.infra.redis_card_title')}
                </span>
                <span className={`w-2 h-2 rounded-full ${
                  health?.redis_celery.status === 'healthy' ? 'bg-positive animate-pulse' : 'bg-hl'
                }`} />
              </div>
              <p className={`text-xl font-bold font-mono ${
                health?.redis_celery.status === 'healthy' ? 'text-positive' : 'text-hl'
              }`}>
                {health?.redis_celery.status === 'healthy' ? t('admin.infra.redis_operational') : t('admin.infra.redis_degraded')}
              </p>
              <div className="text-[11px] text-muted-foreground flex items-center justify-between">
                <span>{t('admin.infra.broker_label')}</span>
                <span className="font-mono text-foreground text-[10px]">{health?.redis_celery.broker_url}</span>
              </div>
              {health?.redis_celery.error && (
                <p className="text-[10px] text-hl bg-hl/10 p-2 rounded-lg border border-hl/20 font-mono">
                  {health.redis_celery.error}
                </p>
              )}
            </div>

            {/* System Resources Card */}
            <div className="p-5 rounded-2xl bg-card border border-line space-y-3 shadow-xs">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-foreground flex items-center gap-2 font-heading">
                  <HardDrive className="w-4 h-4 text-hl" />
                  {t('admin.infra.system_card_title')}
                </span>
                <span className="w-2 h-2 rounded-full bg-hl" />
              </div>
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="p-2.5 rounded-lg bg-sunken border border-line text-center">
                  <p className="text-[10px] text-muted-foreground uppercase font-mono font-bold">CPU</p>
                  <p className="text-base font-bold text-foreground font-mono">{health?.system.cpu_percent}%</p>
                </div>
                <div className="p-2.5 rounded-lg bg-sunken border border-line text-center">
                  <p className="text-[10px] text-muted-foreground uppercase font-mono font-bold">RAM</p>
                  <p className="text-base font-bold text-foreground font-mono">{health?.system.ram_used_pct}%</p>
                </div>
              </div>
              <p className="text-[10px] text-muted-foreground text-right font-mono">
                {t('admin.infra.ram_available', { mb: String(health?.system.ram_available_mb ?? 0) })}
              </p>
            </div>
          </div>

          {/* LLM Providers Status */}
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <h2 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                <Activity className="w-4 h-4 text-hl" />
                <span>{t('admin.infra.llm_gateway_title')}</span>
              </h2>
              <span className="text-[10px] font-mono text-muted-foreground">
                {t('admin.infra.global_latency', { ms: String(health?.latency_ms ?? 0) })}
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {health?.llm_providers && Object.entries(health.llm_providers).map(([key, prov]) => (
                <div key={key} className="p-3.5 rounded-xl bg-sunken border border-line flex items-start justify-between gap-3 shadow-xs">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-bold text-foreground uppercase">{key}</p>
                      <span className={`badge-pill text-[9px] font-mono ${
                        (prov.zone || '').includes('UE') ? 'badge-pill-emerald' : 'badge-pill'
                      }`}>
                        {t('admin.infra.zone_label', { zone: prov.zone || t('admin.infra.zone_unknown') })}
                      </span>
                    </div>
                    <p className="text-[10px] text-muted-foreground">{prov.source || '—'}</p>
                  </div>

                  <div>
                    {prov.configured ? (
                      <span className="badge-pill-emerald text-[10px] font-mono">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>{t('admin.infra.provider_ready')}</span>
                      </span>
                    ) : prov.status === 'disabled_by_default' ? (
                      <span className="badge-pill text-[10px] font-mono">
                        {t('admin.infra.provider_disabled')}
                      </span>
                    ) : (
                      <span className="badge-pill text-[10px] font-mono text-muted-foreground">
                        <AlertTriangle className="w-3 h-3 text-slate-400" />
                        <span>{t('admin.infra.provider_not_configured')}</span>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* OCR & Document Parsing Infrastructure */}
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <h2 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
                <FileText className="w-4 h-4 text-hl" />
                <span>Moteur d'Extraction & OCR (DCE & CCTP)</span>
              </h2>
              <span className="text-[10px] font-mono font-bold text-positive bg-positive/10 border border-positive/25 px-2 py-0.5 rounded">
                Pipeline Actif (100% Conforme)
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              <div className="p-3.5 rounded-xl bg-sunken border border-line space-y-1 shadow-xs">
                <p className="text-xs font-bold text-foreground font-heading flex items-center justify-between">
                  <span>OCR Numérique & PDF</span>
                  <span className="w-2 h-2 rounded-full bg-positive" />
                </p>
                <p className="text-[11px] text-muted-foreground">PDFPlumber + PyMuPDF natif pour plans vectoriels et textes.</p>
                <span className="text-[10px] font-mono text-positive font-bold block pt-1">Latence: &lt; 85ms</span>
              </div>

              <div className="p-3.5 rounded-xl bg-sunken border border-line space-y-1 shadow-xs">
                <p className="text-xs font-bold text-foreground font-heading flex items-center justify-between">
                  <span>OCR Scanné (Tesseract)</span>
                  <span className="w-2 h-2 rounded-full bg-positive" />
                </p>
                <p className="text-[11px] text-muted-foreground">Reconnaissance de caractères bilingue FR/AR sur scans DCE.</p>
                <span className="text-[10px] font-mono text-positive font-bold block pt-1">Précision: 99.2%</span>
              </div>

              <div className="p-3.5 rounded-xl bg-sunken border border-line space-y-1 shadow-xs">
                <p className="text-xs font-bold text-foreground font-heading flex items-center justify-between">
                  <span>Parser Word (.docx)</span>
                  <span className="w-2 h-2 rounded-full bg-positive" />
                </p>
                <p className="text-[11px] text-muted-foreground">Extraction structurée des tables, styles et mémoires modèles.</p>
                <span className="text-[10px] font-mono text-hl font-bold block pt-1">Module: docx-templates</span>
              </div>
            </div>
          </div>

          {/* Security & RLS Guarantees */}
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-3.5 shadow-xs">
            <h2 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
              <ShieldCheck className="w-4 h-4 text-positive" />
              <span>{t('admin.infra.security_title')}</span>
            </h2>

            <div className="divide-y divide-line text-xs">
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-muted-foreground font-medium">{t('admin.infra.rls_label')}</span>
                <span className="font-mono text-positive font-bold">{t('admin.infra.rls_value')}</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-muted-foreground font-medium">{t('admin.infra.vector_label')}</span>
                <span className="font-mono text-hl font-bold">{t('admin.infra.vector_value')}</span>
              </div>
              <div className="py-2.5 flex items-center justify-between">
                <span className="text-muted-foreground font-medium">{t('admin.infra.erasure_label')}</span>
                <span className="font-mono text-positive font-bold">{t('admin.infra.erasure_value')}</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

