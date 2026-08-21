'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Building2,
  Plus,
  ArrowRight,
  ShieldAlert,
  Loader2,
  Trash2,
  ChevronRight,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Tenant } from '@/lib/types';

export default function AdminTenantsListPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadTenants() {
      setLoading(true);
      try {
        const data = await api.getTenants();
        setTenants(data || []);
      } catch (err) {
        console.error('Erreur chargement tenants:', err);
      } finally {
        setLoading(false);
      }
    }
    loadTenants();
  }, []);


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
            Entreprises Clientes (Tenants)
          </h1>
          <p className="text-xs text-slate-400">
            Sélectionnez une entreprise cliente pour configurer ses accès, ses modèles IA et ses règles de chiffrage.
          </p>
        </div>

        <Link
          href="/admin"
          className="flex items-center gap-1.5 px-4 py-2.5 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-lg shadow-rose-900/30 transition-all"
        >
          <Plus className="w-4 h-4" />
          <span>Ajouter un client</span>
        </Link>
      </div>

      {loading ? (
        <div className="p-16 text-center space-y-3">
          <Loader2 className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Chargement des entreprises...</p>
        </div>
      ) : tenants.length === 0 ? (
        <div className="p-12 rounded-3xl bg-slate-900/40 border border-dashed border-slate-800 text-center space-y-4">
          <Building2 className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-white">Aucune entreprise cliente enregistrée</h3>
            <p className="text-xs text-slate-500">Ajoutez votre premier client depuis le tableau de bord.</p>
          </div>
          <Link
            href="/admin"
            className="inline-block px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold shadow-glow transition-all"
          >
            Créer une entreprise cliente
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {tenants.map((t) => (
            <Link
              key={t.id}
              href={`/admin/tenants/${t.id}`}
              className="p-5 rounded-2xl bg-slate-900/80 border border-slate-800 hover:border-rose-500/50 flex items-center justify-between transition-all group shadow-md"
            >
              <div className="flex items-center gap-3.5">
                <div className="w-11 h-11 rounded-2xl bg-slate-800 text-rose-400 font-black text-sm flex items-center justify-center border border-slate-700 group-hover:scale-105 transition-transform">
                  {t.name.substring(0, 2).toUpperCase()}
                </div>
                <div>
                  <h3 className="text-sm font-bold text-white group-hover:text-rose-300 transition-colors">
                    {t.name}
                  </h3>
                  <p className="text-xs text-slate-400 font-mono">
                    SIRET : {t.siret || 'Non renseigné'} • {t.contact_email || 'Sans email'}
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-4">
                <span className="text-[10px] font-bold px-2.5 py-1 rounded bg-sky-500/10 text-sky-400 border border-sky-500/20 uppercase">
                  Plan {t.plan}
                </span>
                <span className="text-xs text-slate-400 font-mono hidden sm:inline">
                  {t.used_this_month || 0} / {t.monthly_limit || 15} DCE
                </span>
                <ChevronRight className="w-4 h-4 text-slate-600 group-hover:text-rose-400 group-hover:translate-x-1 transition-all" />
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
