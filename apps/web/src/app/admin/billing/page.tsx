'use client';

import React from 'react';
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
} from 'lucide-react';

export default function AdminBillingPage() {
  const transactions = [
    { id: 'tx-1', client: 'EiffaBTP Construction SAS', amount: 490, date: '19/08/2026', status: 'Payé', invoice: 'FAC-2026-0819' },
    { id: 'tx-2', client: 'Bouygues Travaux Publics IDF', amount: 1490, date: '15/08/2026', status: 'Payé', invoice: 'FAC-2026-0815' },
    { id: 'tx-3', client: 'Vinci Construction & Ouvrages', amount: 1490, date: '01/08/2026', status: 'Payé', invoice: 'FAC-2026-0801' },
    { id: 'tx-4', client: 'Colas Route & Génie Civil', amount: 490, date: '01/08/2026', status: 'Payé', invoice: 'FAC-2026-0802' },
  ];

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
            Facturation & Flux Financiers Stripe
          </h1>
          <p className="text-xs text-slate-400">
            Suivi des abonnements clients, des encaissements mensuels et du volume de DCE souscrits.
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

      {/* Metrics Row */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
          <p className="text-xs font-bold text-slate-400">Revenu Mensuel Récurrent (MRR)</p>
          <p className="text-3xl font-black text-white font-mono">14 250 €</p>
          <p className="text-xs text-emerald-400 font-bold flex items-center gap-1">
            <TrendingUp className="w-3.5 h-3.5" /> +18.4% ce mois
          </p>
        </div>

        <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
          <p className="text-xs font-bold text-slate-400">Revenu Annuel Projeté (ARR)</p>
          <p className="text-3xl font-black text-white font-mono">171 000 €</p>
          <p className="text-xs text-slate-400 font-medium">18 PME BTP abonnées</p>
        </div>

        <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-2">
          <p className="text-xs font-bold text-slate-400">Panier Moyen Client</p>
          <p className="text-3xl font-black text-emerald-400 font-mono">791 €</p>
          <p className="text-xs text-slate-400 font-medium">Par entreprise / mois</p>
        </div>
      </div>

      {/* Transactions Table */}
      <div className="p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-4">
        <h2 className="text-sm font-bold text-white flex items-center gap-2">
          <CreditCard className="w-4 h-4 text-rose-400" />
          <span>Dernières Transactions Stripe Encaissées</span>
        </h2>

        <div className="divide-y divide-slate-800">
          {transactions.map((tx) => (
            <div key={tx.id} className="py-3.5 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-9 h-9 rounded-xl bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center justify-center font-bold text-xs">
                  ✓
                </div>
                <div>
                  <p className="text-xs font-bold text-white">{tx.client}</p>
                  <p className="text-[10px] text-slate-400 font-mono">{tx.invoice} • {tx.date}</p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <span className="text-sm font-black text-white font-mono">
                  {tx.amount.toLocaleString('fr-FR')} € HT
                </span>
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                  {tx.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
