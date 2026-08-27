'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import {
  Building2,
  Plus,
  ShieldCheck,
  Loader2,
  Trash2,
  ChevronRight,
  Search,
  Users,
  Activity,
  Layers,
  Sparkles,
  ExternalLink,
  Sliders,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Tenant } from '@/lib/types';

export default function AdminTenantsListPage() {
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [planFilter, setPlanFilter] = useState<string>('all');

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

  async function handleQuickDelete(e: React.MouseEvent, tenant: Tenant) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(`Supprimer définitivement l'entreprise "${tenant.name}" et toutes ses données (RGPD) ?`)) return;
    try {
      await api.deleteTenant(tenant.id);
      setTenants((prev) => prev.filter((t) => t.id !== tenant.id));
    } catch (err: any) {
      alert('Erreur lors de la suppression : ' + (err?.message || err));
    }
  }

  const filteredTenants = tenants.filter((t) => {
    const matchesSearch =
      t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (t.siret && t.siret.includes(searchTerm)) ||
      (t.contact_email && t.contact_email.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesPlan = planFilter === 'all' || t.plan === planFilter;
    return matchesSearch && matchesPlan;
  });

  const totalDCE = tenants.reduce((acc, t) => acc + (t.used_this_month || 0), 0);

  return (
    <div className="space-y-8 pb-20 max-w-6xl mx-auto">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="text-[10px] font-extrabold uppercase tracking-widest px-2.5 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30">
              Super Administration • Multi-Tenants
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
            Entreprises Clientes & Espaces Tenants
          </h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Supervisez les 69 comptes d'entreprises BTP, configurez les modèles IA dédiés et gérez les quotas.
          </p>
        </div>

        <Link
          href="/admin"
          className="flex items-center gap-2 px-5 py-2.5 rounded-xl bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 text-white text-xs font-black shadow-lg shadow-rose-950/40 transition-all cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>Créer une Entreprise</span>
        </Link>
      </div>

      {/* KPI Stats Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="p-5 rounded-2xl bg-[#0F1422] border border-[#1E293F] space-y-1 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Comptes Entreprises</span>
            <Building2 className="w-4 h-4 text-rose-400" />
          </div>
          <p className="text-2xl font-black text-white font-mono">{tenants.length}</p>
          <p className="text-[11px] text-emerald-400 font-semibold">100% étanches sous Postgres RLS</p>
        </div>

        <div className="p-5 rounded-2xl bg-[#0F1422] border border-[#1E293F] space-y-1 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Volume DCE Consommé</span>
            <Activity className="w-4 h-4 text-amber-400" />
          </div>
          <p className="text-2xl font-black text-white font-mono">{totalDCE} DCE</p>
          <p className="text-[11px] text-slate-400">Total ce mois-ci sur la plateforme</p>
        </div>

        <div className="p-5 rounded-2xl bg-[#0F1422] border border-[#1E293F] space-y-1 shadow-lg">
          <div className="flex items-center justify-between text-slate-400 text-xs">
            <span>Routage IA Actif</span>
            <Sparkles className="w-4 h-4 text-sky-400" />
          </div>
          <p className="text-sm font-bold text-white mt-1">Tier Équilibré (Claude Sonnet 5)</p>
          <p className="text-[11px] text-slate-400">Hébergement certifié et RGPD</p>
        </div>
      </div>

      {/* Search & Filter Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 p-3 rounded-2xl bg-[#0F1422] border border-[#1E293F]">
        <div className="relative flex-1">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Rechercher une entreprise par nom, SIRET ou e-mail..."
            className="w-full pl-10 pr-4 py-2 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-white placeholder:text-slate-500 focus:border-rose-500 focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400 whitespace-nowrap pl-1 font-bold">Plan :</span>
          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            className="px-3 py-2 rounded-xl bg-slate-950/80 border border-slate-800 text-xs text-white focus:border-rose-500 focus:outline-none"
          >
            <option value="all">Tous les plans ({tenants.length})</option>
            <option value="enterprise">Enterprise</option>
            <option value="pro">Pro</option>
            <option value="starter">Starter</option>
          </select>
        </div>
      </div>

      {/* Tenants Cards Grid */}
      {loading ? (
        <div className="p-20 text-center space-y-3">
          <Loader2 className="w-8 h-8 text-rose-500 animate-spin mx-auto" />
          <p className="text-xs text-slate-400">Chargement de la liste des entreprises...</p>
        </div>
      ) : filteredTenants.length === 0 ? (
        <div className="p-16 rounded-3xl bg-[#0F1422]/60 border border-dashed border-[#1E293F] text-center space-y-4">
          <Building2 className="w-12 h-12 text-slate-600 mx-auto" />
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-white">Aucune entreprise trouvée</h3>
            <p className="text-xs text-slate-500">Modifiez vos critères de recherche ou ajoutez une nouvelle entreprise.</p>
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {filteredTenants.map((t) => (
            <div
              key={t.id}
              className="p-5 rounded-2xl bg-[#0F1422] border border-[#1E293F] hover:border-rose-500/50 flex items-center justify-between transition-all group shadow-md"
            >
              <Link
                href={`/admin/tenants/${t.id}`}
                className="flex items-center gap-4 flex-1 min-w-0"
              >
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-slate-800 to-slate-700 text-rose-300 font-black text-sm flex items-center justify-center border border-slate-700 group-hover:scale-105 transition-transform shrink-0 shadow-inner">
                  {t.name.substring(0, 2).toUpperCase()}
                </div>
                <div className="truncate space-y-0.5">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-white group-hover:text-rose-300 transition-colors truncate">
                      {t.name}
                    </h3>
                    <span className="text-[9px] font-mono px-1.5 py-0.2 rounded bg-slate-800 text-slate-400 border border-slate-700">
                      {t.country_code || 'FR'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 font-mono truncate">
                    SIRET : {t.siret || 'Non renseigné'} • {t.contact_email || 'Sans e-mail de contact'}
                  </p>
                </div>
              </Link>

              <div className="flex items-center gap-3 shrink-0 ml-4">
                <span className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase border ${
                  t.plan === 'enterprise'
                    ? 'bg-amber-500/10 text-amber-300 border-amber-500/30'
                    : t.plan === 'pro'
                    ? 'bg-sky-500/10 text-sky-300 border-sky-500/30'
                    : 'bg-slate-800 text-slate-300 border-slate-700'
                }`}>
                  Plan {t.plan}
                </span>

                <span className="text-xs text-slate-400 font-mono hidden md:inline">
                  {t.used_this_month || 0} / {t.monthly_limit || 15} DCE
                </span>

                <button
                  type="button"
                  onClick={(e) => handleQuickDelete(e, t)}
                  title="Supprimer définitivement ce compte (RGPD)"
                  className="p-2 rounded-xl text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 transition-colors cursor-pointer"
                >
                  <Trash2 className="w-4 h-4" />
                </button>

                <Link
                  href={`/admin/tenants/${t.id}`}
                  className="p-2 rounded-xl text-slate-600 group-hover:text-rose-400 group-hover:translate-x-0.5 transition-all"
                >
                  <ChevronRight className="w-5 h-5" />
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
