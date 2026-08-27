'use client';

import React, { useEffect, useState } from 'react';
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
} from 'lucide-react';
import { api } from '@/lib/api';

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
    zone: string;
    source: string;
  }>;
  system: {
    cpu_percent: number;
    ram_used_pct: number;
    ram_available_mb: number;
  };
}

export default function AdminInfrastructurePage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastChecked, setLastChecked] = useState<string>('');

  async function checkHealth() {
    try {
      setRefreshing(true);
      const data = await api.getClusterHealth();
      setHealth(data as HealthData);
      setLastChecked(new Date().toLocaleTimeString('fr-FR'));
    } catch (err) {
      console.error('Erreur health check:', err);
      // If backend returns a non-200 JSON payload, try to extract it
      try {
        const rawApiUrl = (process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000').replace(/\/$/, '');
        const targetUrl = rawApiUrl.endsWith('/api') ? `${rawApiUrl}/health` : `${rawApiUrl}/api/health`;
        const res = await fetch(targetUrl);
        const data = await res.json();
        setHealth(data as HealthData);
      } catch {
        setHealth({
          status: 'unhealthy',
          timestamp: new Date().toISOString(),
          latency_ms: 0,
          database: { status: 'unhealthy', latency_ms: 0, error: 'Impossible de joindre le backend FastAPI (port 8000)' },
          redis_celery: { status: 'unhealthy', broker_url: 'N/A', error: 'Service injoignable' },
          llm_providers: {},
          system: { cpu_percent: 0, ram_used_pct: 0, ram_available_mb: 0 },
        });
      }
      setLastChecked(new Date().toLocaleTimeString('fr-FR'));
    } finally {
      setLoading(false);
      setRefreshing(false);
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
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
              Super Administration
            </span>
            {health && (
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded border flex items-center gap-1 ${
                isHealthy
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : isDegraded
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
              }`}>
                <span className={`w-1.5 h-1.5 rounded-full ${
                  isHealthy ? 'bg-emerald-400' : isDegraded ? 'bg-amber-400' : 'bg-rose-400'
                }`} />
                <span>Cluster {health.status.toUpperCase()}</span>
              </span>
            )}
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">
            Supervision Cluster OCR, Celery & IA
          </h1>
          <p className="text-xs text-slate-400">
            Métriques réelles de persistance, brokers asynchrones et passerelles LLM.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={checkHealth}
            disabled={refreshing}
            className="px-3.5 py-2 rounded-xl bg-slate-900 border border-slate-800 hover:bg-slate-800 text-xs font-bold text-slate-300 flex items-center gap-1.5 transition-all cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin text-sky-400' : ''}`} />
            <span>Actualiser {lastChecked ? `(${lastChecked})` : ''}</span>
          </button>

          <Link
            href="/admin"
            className="inline-flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
            <span>Tableau de bord</span>
          </Link>
        </div>
      </div>

      {loading && !health ? (
        <div className="p-12 rounded-3xl bg-slate-900/90 border border-slate-800 flex items-center justify-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
          <span className="text-xs font-bold text-slate-300">Interrogation des composants d'infrastructure...</span>
        </div>
      ) : (
        <>
          {/* Services Status Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Database Card */}
            <div className={`p-6 rounded-3xl bg-slate-900/90 border space-y-3 shadow-xl transition-all ${
              health?.database.status === 'healthy' ? 'border-emerald-500/30' : 'border-rose-500/50'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-2">
                  <Database className={`w-4 h-4 ${
                    health?.database.status === 'healthy' ? 'text-emerald-400' : 'text-rose-400'
                  }`} />
                  PostgreSQL Supabase (RLS)
                </span>
                <span className={`w-2.5 h-2.5 rounded-full ${
                  health?.database.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
                }`} />
              </div>
              <p className={`text-2xl font-black font-mono ${
                health?.database.status === 'healthy' ? 'text-emerald-400' : 'text-rose-400'
              }`}>
                {health?.database.status === 'healthy' ? 'Connecté' : 'Échec'}
              </p>
              <div className="text-[11px] text-slate-400 flex items-center justify-between">
                <span>Latence SELECT 1 :</span>
                <span className="font-mono text-white font-bold">{health?.database.latency_ms} ms</span>
              </div>
              {health?.database.error && (
                <p className="text-[10px] text-rose-400 bg-rose-500/10 p-2 rounded-xl border border-rose-500/20">
                  {health.database.error}
                </p>
              )}
            </div>

            {/* Redis & Celery Card */}
            <div className={`p-6 rounded-3xl bg-slate-900/90 border space-y-3 shadow-xl transition-all ${
              health?.redis_celery.status === 'healthy' ? 'border-sky-500/30' : 'border-amber-500/50'
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-2">
                  <Cpu className={`w-4 h-4 ${
                    health?.redis_celery.status === 'healthy' ? 'text-sky-400' : 'text-amber-400'
                  }`} />
                  Broker Celery & Redis
                </span>
                <span className={`w-2.5 h-2.5 rounded-full ${
                  health?.redis_celery.status === 'healthy' ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
                }`} />
              </div>
              <p className={`text-2xl font-black font-mono ${
                health?.redis_celery.status === 'healthy' ? 'text-sky-400' : 'text-amber-400'
              }`}>
                {health?.redis_celery.status === 'healthy' ? 'Opérationnel' : 'Dégradé'}
              </p>
              <div className="text-[11px] text-slate-400 flex items-center justify-between">
                <span>Broker :</span>
                <span className="font-mono text-white text-[10px]">{health?.redis_celery.broker_url}</span>
              </div>
              {health?.redis_celery.error && (
                <p className="text-[10px] text-amber-400 bg-amber-500/10 p-2 rounded-xl border border-amber-500/20">
                  {health.redis_celery.error}
                </p>
              )}
            </div>

            {/* System Resources Card */}
            <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-3 shadow-xl">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white flex items-center gap-2">
                  <HardDrive className="w-4 h-4 text-purple-400" />
                  Ressources Serveur
                </span>
                <span className="w-2.5 h-2.5 rounded-full bg-purple-400" />
              </div>
              <div className="grid grid-cols-2 gap-2 pt-1">
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-center">
                  <p className="text-[10px] text-slate-400 uppercase font-bold">CPU</p>
                  <p className="text-base font-black text-white font-mono">{health?.system.cpu_percent}%</p>
                </div>
                <div className="p-2.5 rounded-xl bg-slate-950 border border-slate-800 text-center">
                  <p className="text-[10px] text-slate-400 uppercase font-bold">RAM</p>
                  <p className="text-base font-black text-white font-mono">{health?.system.ram_used_pct}%</p>
                </div>
              </div>
              <p className="text-[10px] text-slate-400 text-right font-mono">
                {health?.system.ram_available_mb} Mo RAM disponible
              </p>
            </div>
          </div>

          {/* LLM Providers Status */}
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-white flex items-center gap-2">
                <Activity className="w-4 h-4 text-sky-400" />
                <span>Passerelle Modèles IA (LiteLLM) & Conformité RGPD</span>
              </h2>
              <span className="text-[10px] font-bold text-slate-400">
                Temps de réponse global : {health?.latency_ms} ms
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {health?.llm_providers && Object.entries(health.llm_providers).map(([key, prov]) => (
                <div key={key} className="p-4 rounded-2xl bg-slate-950/60 border border-slate-800/80 flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <p className="text-xs font-bold text-white uppercase">{key}</p>
                      <span className={`text-[9px] font-extrabold px-1.5 py-0.5 rounded border ${
                        prov.zone.includes('UE')
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                          : prov.zone.includes('US')
                          ? 'bg-sky-500/10 text-sky-400 border-sky-500/30'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/30'
                      }`}>
                        Zone {prov.zone}
                      </span>
                    </div>
                    <p className="text-[10px] text-slate-400">{prov.source}</p>
                  </div>

                  <div>
                    {prov.configured ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" />
                        <span>Prêt</span>
                      </span>
                    ) : prov.status === 'disabled_by_default' ? (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        Désactivé
                      </span>
                    ) : (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" />
                        <span>Non configuré</span>
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Security & RLS Guarantees */}
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-400" />
              <span>Garanties de Résilience et Sécurité</span>
            </h2>

            <div className="divide-y divide-slate-800 text-xs">
              <div className="py-3 flex items-center justify-between">
                <span className="text-slate-300 font-medium">Politique de RLS PostgreSQL</span>
                <span className="font-mono text-emerald-400 font-bold">100% des tables isolées par tenant_id</span>
              </div>
              <div className="py-3 flex items-center justify-between">
                <span className="text-slate-300 font-medium">Indexation Sémantique</span>
                <span className="font-mono text-sky-400 font-bold">pgvector 1536d + Cosine Distance</span>
              </div>
              <div className="py-3 flex items-center justify-between">
                <span className="text-slate-300 font-medium">Droit à l'effacement RGPD</span>
                <span className="font-mono text-purple-400 font-bold">Purge 90 jours (obsolètes) + Hard-Delete immédiat</span>
              </div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

