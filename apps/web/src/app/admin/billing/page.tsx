'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import {
  CreditCard,
  ArrowLeft,
  Building2,
  Loader2,
} from 'lucide-react';
import { api } from '@/lib/api';
import { Tenant } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

interface RevenueSummary {
  mrr_estimated_eur: number;
  arr_estimated_eur: number;
  billed_active_count: number;
  free_trial_count: number;
  custom_pricing_count: number;
  other_status_count: number;
  tenants_with_subscription_record: number;
  tenants_without_subscription_record: number;
  total_tenants: number;
  any_payment_processor_verified: boolean;
  by_tenant: Array<{
    tenant_id: string;
    plan_id: string;
    plan_name: string;
    price_monthly_eur: number;
    has_verified_payment_link: boolean;
  }>;
}

interface Plan {
  id: string;
  name: string;
  price_monthly_cents: number;
}

export default function AdminBillingPage() {
  const { t } = useTranslation();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [revenue, setRevenue] = useState<RevenueSummary | null>(null);
  const [plans, setPlans] = useState<Plan[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [tenantsData, revenueData, plansData] = await Promise.all([
          api.getTenants(),
          api.getRevenueSummary(),
          api.getPlans(),
        ]);
        setTenants(tenantsData);
        setRevenue(revenueData);
        setPlans(plansData || []);
      } catch (err) {
        console.error('Erreur chargement abonnements:', err);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

  // 01/09 : prix reel par palier (subscription_plans.price_monthly_cents) recupere
  // via /billing/plans -- remplace l'ancienne grille codee en dur (190/490/1490)
  // qui etait desynchronisee de la vraie table ET inventait un prix pour
  // "enterprise" alors que ce palier est explicitement a tarif negocie (0).
  const planPriceMap: Record<string, number> = {};
  for (const p of plans) {
    planPriceMap[p.id.toLowerCase()] = p.price_monthly_cents / 100;
  }

  const totalDossiersQuota = tenants.reduce(
    (acc, tn) => acc + (tn.monthly_limit || (tn.plan === 'enterprise' ? 50 : 15)),
    0
  );

  const gatewayVerified = revenue?.any_payment_processor_verified ?? false;

  return (
    <div className="space-y-8 pb-16 max-w-5xl">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1.5">
            <span className="badge-pill font-medium">
              {t('admin.common.badge_super_admin')}
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-extrabold text-foreground font-heading tracking-tight">
            {t('admin.billing.heading')}
          </h1>
          <p className="text-xs text-muted-foreground font-medium">
            {t('admin.billing.subtitle')}
          </p>
        </div>

        <Link
          href="/admin"
          className="inline-flex items-center gap-2 text-xs font-bold text-muted-foreground hover:text-slate-900 dark:hover:text-white transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>{t('admin.common.back_dashboard')}</span>
        </Link>
      </div>

      {loading ? (
        <div className="p-12 rounded-2xl bg-card border border-line flex items-center justify-center gap-3 shadow-xs">
          <Loader2 className="w-5 h-5 animate-spin text-hl" />
          <span className="text-xs font-mono text-muted-foreground">{t('admin.billing.loading')}</span>
        </div>
      ) : (
        <>
          {/* Metrics Row */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs hover:border-hl/40 transition-colors">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground font-mono">{t('admin.billing.metric_mrr')}</p>
              <p className="text-2xl sm:text-3xl font-black text-foreground font-mono tracking-tight">
                {(revenue?.mrr_estimated_eur ?? 0).toLocaleString('fr-FR')} €
              </p>
              <p className="text-[10px] font-mono text-muted-foreground flex items-center gap-1.5">
                <span className="w-1.5 h-1.5 rounded-full bg-positive"></span>
                <span>{t('admin.billing.billed_count', { count: String(revenue?.billed_active_count ?? 0) })}</span>
              </p>
              <p className="text-[10px] font-mono text-muted-foreground">
                {t('admin.billing.arr_note', { arr: (revenue?.arr_estimated_eur ?? 0).toLocaleString('fr-FR') })}
              </p>
            </div>

            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs hover:border-hl/40 transition-colors">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground font-mono">{t('admin.billing.metric_quota')}</p>
              <p className="text-2xl sm:text-3xl font-black text-hl font-mono tracking-tight">{t('admin.billing.quota_value', { quota: String(totalDossiersQuota) })}</p>
              <p className="text-[10px] text-muted-foreground font-mono">{t('admin.billing.quota_subscribed')}</p>
            </div>

            <div className="p-5 rounded-2xl bg-card border border-line space-y-2 shadow-xs hover:border-hl/40 transition-colors">
              <p className="text-[10px] font-bold uppercase tracking-wider text-muted-foreground font-mono">{t('admin.billing.metric_gateway')}</p>
              <p className="text-lg font-bold text-foreground flex items-center gap-2 font-heading">
                <CreditCard className="w-4 h-4 text-hl" /> Stripe
              </p>
              <p className="text-[10px] text-muted-foreground font-mono flex items-center gap-1.5">
                <span className={`w-1.5 h-1.5 rounded-full ${gatewayVerified ? 'bg-positive' : 'bg-corten'}`}></span>
                <span>{gatewayVerified ? t('admin.billing.gateway_active_note') : t('admin.billing.gateway_inactive_note')}</span>
              </p>
            </div>
          </div>

          {revenue && (revenue.free_trial_count > 0 || revenue.tenants_without_subscription_record > 0 || revenue.custom_pricing_count > 0) && (
            <p className="text-[11px] font-mono text-muted-foreground -mt-4">
              {t('admin.billing.excluded_note', {
                trials: String(revenue.free_trial_count),
                notrack: String(revenue.tenants_without_subscription_record),
              })}
            </p>
          )}

          {/* Tenants Subscription Table */}
          <div className="p-5 sm:p-6 rounded-2xl bg-card border border-line space-y-4 shadow-xs">
            <h2 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
              <Building2 className="w-4 h-4 text-hl" />
              <span>{t('admin.billing.subs_by_company', { count: String(tenants.length) })}</span>
            </h2>

            {tenants.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-6 font-mono">{t('admin.billing.no_tenants')}</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="text-[10px] text-muted-foreground uppercase tracking-wider border-b border-line font-mono">
                    <tr>
                      <th className="pb-3">{t('admin.billing.col_company')}</th>
                      <th className="pb-3">{t('admin.billing.col_plan')}</th>
                      <th className="pb-3">{t('admin.billing.col_amount')}</th>
                      <th className="pb-3">{t('admin.billing.col_quota')}</th>
                      <th className="pb-3">{t('admin.billing.col_signup_date')}</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-line font-mono">
                    {tenants.map((tenant) => {
                      const planKey = (tenant.plan || 'pro').toLowerCase();
                      const price = planPriceMap[planKey];
                      return (
                        <tr key={tenant.id} className="hover:bg-slate-50 dark:hover:bg-raised/50 transition-colors">
                          <td className="py-3 font-sans font-semibold text-foreground flex items-center gap-2">
                            <Building2 className="w-3.5 h-3.5 text-muted-foreground" />
                            {tenant.name}
                          </td>
                          <td className="py-3 font-sans">
                            <span className="badge-pill font-semibold uppercase">
                              {tenant.plan || 'Pro'}
                            </span>
                          </td>
                          <td className="py-3 text-slate-800 dark:text-zinc-200 font-bold">
                            {price ? t('admin.billing.price_per_month', { price: String(price) }) : t('admin.billing.custom_pricing')}
                          </td>
                          <td className="py-3 text-muted-foreground">{t('admin.billing.files_count', { count: String(tenant.monthly_limit || (tenant.plan === 'enterprise' ? 50 : 15)) })}</td>
                          <td className="py-3 text-muted-foreground text-[11px]">
                            {tenant.created_at ? new Date(tenant.created_at).toLocaleDateString('fr-FR') : '—'}
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
