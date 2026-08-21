'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  CreditCard,
  DollarSign,
  TrendingUp,
  ArrowLeft,
  CheckCircle2,
  Calendar,
  Building2,
  ShieldAlert,
  Loader2,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Tenant } from '@/lib/types';

const PLAN_PRICES: Record<string, number> = {
  starter: 190,
  pro: 490,
  enterprise: 1490,
};

export default function AdminBillingPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const data = await api.getTenants();
        setTenants(data);
      } catch (err) {
        console.error('Erreur chargement abonnements:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  const totalMRR = tenants.reduce((acc, t) => acc + (PLAN_PRICES[t.plan?.toLowerCase() || 'pro'] || 490), 0);
  const totalDossiersQuota = tenants.reduce((acc, t) => acc + (t.monthly_limit || (t.plan === 'enterprise' ? 50 : 15)), 0);

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
              Super Administration
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white">
            Facturation & Abonnements Clients
          </h1>
          <p className="text-xs text-slate-400">
            Suivi en temps réel des abonnements des entreprises BTP, des quotas mensuels et des revenus récurrents.
          </p>
        </div>

        <Link
          href="/admin"
          className="inline-flex items-center gap-2 text-xs font-bold text-slate-400 hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Tableau de bord</span>
        </Link>
      </div>

      {loading ? (
        <div className="p-12 rounded-3xl bg-slate-900/90 border border-slate-800 flex items-center justify-center gap-3">
          <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
          <span className="text-xs font-bold text-slate-300">Chargement des abonnements...</span>
        </div>
      ) : (
        <>
          {/* Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <p className="text-xs font-bold text-slate-400">Revenu Mensuel Récurrent (MRR Calculé)</p>
              <p className="text-3xl font-black text-white font-mono">{totalMRR.toLocaleString('fr-FR')} €</p>
              <p className="text-xs text-emerald-400 font-bold flex items-center gap-1">
                <CheckCircle2 className="w-3.5 h-3.5" /> {tenants.length} Entreprises Actives
              </p>
            </div>

            <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <p className="text-xs font-bold text-slate-400">Capacité Quotas Dossiers</p>
              <p className="text-3xl font-black text-sky-400 font-mono">{totalDossiersQuota} DCE / mois</p>
              <p className="text-xs text-slate-400 font-medium">Capacité totale souscrite</p>
            </div>

            <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
              <p className="text-xs font-bold text-slate-400">Passerelle Bancaire</p>
              <p className="text-xl font-bold text-white flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-indigo-400" /> Stripe Connect B2B
              </p>
              <p className="text-xs text-emerald-400 font-semibold">Prélèvements SEPA & CB actifs</p>
            </div>
          </div>

          {/* Tenants Subscription Table */}
          <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4 shadow-xl">
            <h2 className="text-sm font-bold text-white flex items-center gap-2">
              <Building2 className="w-4 h-4 text-sky-400" />
              <span>Abonnements par Entreprise ({tenants.length})</span>
            </h2>

            {tenants.length === 0 ? (
              <p className="text-xs text-slate-400 text-center py-6">Aucun tenant enregistré pour le moment.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] text-slate-500 uppercase tracking-wider border-b border-slate-800">
                    <tr>
                      <th className="pb-3">Entreprise</th>
                      <th className="pb-3">Formule / Plan</th>
                      <th className="pb-3">Montant Mensuel</th>
                      <th className="pb-3">Quota Dossiers</th>
                      <th className="pb-3">Date d'inscription</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800/60 font-mono">
                    {tenants.map((t) => {
                      const planKey = (t.plan || 'pro').toLowerCase();
                      const price = PLAN_PRICES[planKey] || 490;
                      return (
                        <tr key={t.id} className="hover:bg-slate-800/30 transition-colors">
                          <td className="py-3 font-sans font-bold text-white flex items-center gap-2">
                            <Building2 className="w-3.5 h-3.5 text-slate-500" />
                            {t.name}
                          </td>
                          <td className="py-3 font-sans">
                            <span className="px-2 py-0.5 rounded-md bg-sky-500/10 text-sky-300 border border-sky-500/20 font-bold uppercase text-[10px]">
                              {t.plan || 'Pro'}
                            </span>
                          </td>
                          <td className="py-3 text-slate-200 font-bold">{price} € HT / mois</td>
                          <td className="py-3 text-slate-300">{t.monthly_limit || (t.plan === 'enterprise' ? 50 : 15)} dossiers</td>
                          <td className="py-3 text-slate-400 text-[11px]">
                            {t.created_at ? new Date(t.created_at).toLocaleDateString('fr-FR') : '—'}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
