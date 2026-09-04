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
import { useTranslation } from '@/components/i18n-provider';
import { DismissibleNotice } from '@/components/ui/dismissible-notice';

export default function AdminTenantsListPage() {
  const { t } = useTranslation();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [planFilter, setPlanFilter] = useState<string>('all');

  async function loadTenants() {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await api.getTenants();
      setTenants(data || []);
    } catch (err: any) {
      // Ne jamais afficher silencieusement "aucune entreprise" quand c'est en
      // réalité l'appel réseau qui a échoué (base de données lente/injoignable) :
      // on distingue explicitement un vrai vide d'un échec de chargement.
      console.error('Erreur chargement tenants:', err);
      setTenants([]);
      setLoadError(String(err?.message || err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadTenants();
  }, []);

  async function handleQuickDelete(e: React.MouseEvent, tenant: Tenant) {
    e.preventDefault();
    e.stopPropagation();
    if (!confirm(t('admin.tenants_list.confirm_delete', { name: tenant.name }))) return;
    try {
      await api.deleteTenant(tenant.id);
      setTenants((prev) => prev.filter((t) => t.id !== tenant.id));
    } catch (err: any) {
      alert(t('admin.tenants_list.delete_error', { error: String(err?.message || err) }));
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
    <div className="space-y-6 pb-16">
      {/* ─── En-tête ─────────────────────────────────────────────────────── */}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0">
          <p className="eyebrow-mono">{t('admin.tenants_list.badge')}</p>
          <h1 className="mt-2 text-[22px] sm:text-[26px] font-bold text-foreground font-heading tracking-tight leading-tight">
            {t('admin.tenants_list.heading')}
          </h1>
          <p className="mt-1 text-[12.5px] text-[hsl(var(--muted-foreground))]">
            {t('admin.tenants_list.subtitle', { count: String(tenants.length) })}
          </p>
        </div>

        <Link href="/admin?create=1" className="btn-primary shrink-0">
          <Plus className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>{t('admin.tenants_list.btn_create')}</span>
        </Link>
      </div>

      {/* ─── Chiffres de tête ────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 sm:grid-cols-3 border-y border-[hsl(var(--border))]">
        {[
          {
            label: t('admin.tenants_list.kpi_accounts'),
            value: String(tenants.length),
            hint: t('admin.tenants_list.kpi_accounts_note'),
          },
          {
            label: t('admin.tenants_list.kpi_volume'),
            value: t('admin.tenants_list.kpi_volume_value', { count: String(totalDCE) }),
            hint: t('admin.tenants_list.kpi_volume_note'),
          },
          {
            label: t('admin.tenants_list.kpi_routing'),
            value: t('admin.tenants_list.kpi_routing_value'),
            hint: t('admin.tenants_list.kpi_routing_note'),
          },
        ].map((stat, i) => (
          <div
            key={stat.label}
            className={`py-4 px-4 ${i > 0 ? 'sm:border-s border-[hsl(var(--border))]' : ''} ${i === 0 ? 'sm:ps-0' : ''}`}
          >
            <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))]">
              {stat.label}
            </p>
            <p className="mt-1.5 font-mono text-[22px] leading-none tabular-nums text-foreground truncate">
              {stat.value}
            </p>
            <p className="mt-1.5 text-[11.5px] text-[hsl(var(--muted-foreground))]">{stat.hint}</p>
          </div>
        ))}
      </div>

      {/* ─── Filtres ─────────────────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-end gap-4">
        <label className="flex-1 min-w-0">
          <span className="block font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))] mb-1.5">
            {t('admin.tenants_list.search_placeholder')}
          </span>
          <div className="relative">
            <Search
              className="w-3.5 h-3.5 text-[hsl(var(--muted-foreground))] absolute start-0 top-1/2 -translate-y-1/2"
              strokeWidth={1.5}
            />
            <input
              type="search"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full ps-6 pe-2 py-1.5 bg-transparent border-b border-[hsl(var(--input))] focus:border-hl text-[13px] text-foreground outline-none transition-colors duration-150"
            />
          </div>
        </label>

        <label className="sm:w-56">
          <span className="block font-mono text-[10px] uppercase tracking-[0.14em] text-[hsl(var(--muted-foreground))] mb-1.5">
            {t('admin.tenants_list.plan_label')}
          </span>
          <select
            value={planFilter}
            onChange={(e) => setPlanFilter(e.target.value)}
            className="w-full py-1.5 bg-transparent border-b border-[hsl(var(--input))] focus:border-hl text-[13px] text-foreground outline-none cursor-pointer transition-colors duration-150"
          >
            <option value="all">{t('admin.tenants_list.plan_all', { count: String(tenants.length) })}</option>
            <option value="enterprise">Grand compte</option>
            <option value="pro">Entreprise générale</option>
            <option value="starter">PME &amp; artisan</option>
          </select>
        </label>
      </div>

      {loadError && (
        <div className="space-y-2">
          <DismissibleNotice
            variant="error"
            message={t('admin.tenants_list.load_error_title')}
            detail={loadError}
            onDismiss={() => setLoadError(null)}
          />
          <button
            type="button"
            onClick={loadTenants}
            className="text-[12.5px] font-semibold text-hl hover:underline cursor-pointer"
          >
            {t('admin.tenants_list.load_error_retry')}
          </button>
        </div>
      )}

      {/* ─── Liste ───────────────────────────────────────────────────────────
          Un tableau, pas une pile de cartes : on gère des dizaines de comptes et la
          question posée devant cet écran est comparative — qui est sur quel forfait,
          qui n'a pas de SIRET, qui vient d'arriver. */}
      {loading ? (
        <div className="py-16 flex items-center justify-center gap-2 text-[12.5px] text-[hsl(var(--muted-foreground))]">
          <Loader2 className="w-4 h-4 animate-spin" strokeWidth={1.5} />
          <span>{t('admin.tenants_list.loading')}</span>
        </div>
      ) : filteredTenants.length === 0 ? (
        <div className="border border-dashed border-[hsl(var(--hairline))] rounded-[5px] px-6 py-12 text-center">
          <p className="text-[13px] font-semibold text-foreground">{t('admin.tenants_list.empty_title')}</p>
          <p className="mt-1 text-[12px] text-[hsl(var(--muted-foreground))] max-w-md mx-auto leading-relaxed">
            {t('admin.tenants_list.empty_body')}
          </p>
          <Link href="/admin?create=1" className="mt-4 inline-block text-[12.5px] text-hl hover:underline">
            {t('admin.tenants_list.btn_create')}
          </Link>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="data-table min-w-[860px]">
            <thead>
              <tr>
                <th>{t('admin.tenants_list.col_company')}</th>
                <th>{t('admin.tenants_list.col_country')}</th>
                <th>{t('admin.tenants_list.col_plan')}</th>
                <th>{t('admin.tenants_list.col_siret')}</th>
                <th>{t('admin.tenants_list.col_created')}</th>
                <th aria-label={t('admin.tenants_list.col_actions')} />
              </tr>
            </thead>
            <tbody>
              {filteredTenants.map((tenant) => (
                <tr key={tenant.id} className="group">
                  <td>
                    <Link
                      href={`/admin/tenants/${tenant.id}`}
                      className="font-medium text-foreground hover:text-hl dark:hover:text-hl transition-colors duration-150"
                    >
                      {tenant.name}
                    </Link>
                    <div className="font-mono text-[11px] text-[hsl(var(--muted-foreground))] truncate max-w-[280px]">
                      {tenant.contact_email || t('admin.tenants_list.no_email')}
                    </div>
                  </td>
                  <td className="font-mono text-[11.5px] text-[hsl(var(--muted-foreground))]">
                    {tenant.country_code || 'FR'}
                  </td>
                  <td>
                    <span className={tenant.plan === 'enterprise' ? 'badge-pill-primary' : 'badge-pill'}>
                      {tenant.plan || 'starter'}
                    </span>
                  </td>
                  <td className="font-mono text-[11.5px] text-[hsl(var(--muted-foreground))]">
                    {tenant.siret || t('admin.tenants_list.no_siret')}
                  </td>
                  <td className="font-mono text-[11.5px] tabular-nums text-[hsl(var(--muted-foreground))]">
                    {tenant.created_at
                      ? new Date(tenant.created_at).toLocaleDateString('fr-FR')
                      : '—'}
                  </td>
                  <td className="text-end whitespace-nowrap">
                    {/* Actions secondaires révélées au survol : le tableau reste lisible. */}
                    <button
                      type="button"
                      onClick={(e) => handleQuickDelete(e, tenant)}
                      title={t('admin.tenants_list.delete_title')}
                      className="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1.5 rounded-[4px] text-[hsl(var(--muted-foreground))] hover:text-danger dark:hover:text-danger transition-opacity duration-150 cursor-pointer"
                    >
                      <Trash2 className="w-3.5 h-3.5" strokeWidth={1.5} />
                    </button>
                    <Link
                      href={`/admin/tenants/${tenant.id}`}
                      className="ms-1 inline-flex p-1.5 rounded-[4px] text-[hsl(var(--muted-foreground))] hover:text-foreground transition-colors duration-150"
                      aria-label={t('admin.tenants_list.col_actions')}
                    >
                      <ChevronRight className="w-4 h-4" strokeWidth={1.5} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
