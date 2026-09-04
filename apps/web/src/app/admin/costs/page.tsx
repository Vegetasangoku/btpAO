'use client';

/**
 * Budgets & plafonds IA — console de pilotage du coût variable.
 *
 * Trois verrous, du plus large au plus fin : le fournisseur d'API protège la facture
 * globale, le forfait fixe la règle commerciale, le client porte l'exception négociée.
 * L'écran les met côte à côte parce que la question qu'on se pose devant n'est jamais
 * « quel est le plafond de X » mais « où suis-je en train de perdre ma marge ».
 *
 * Parti pris d'ergonomie : édition en ligne (aucune modale), actions secondaires
 * révélées au survol de la ligne, une seule action primaire par écran, navigation au
 * clavier. Conçu pour être lu d'un coup d'œil, pas parcouru.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from '@/lib/api';
import type {
  CostLimitsOverview,
  CostLimitPlanRow,
  CostLimitProviderRow,
  CostLimitState,
  CostLimitTenantRow,
} from '@/lib/types';
import { AlertTriangle, ArrowUpRight, Check, RotateCw, X } from 'lucide-react';

type Scope = 'providers' | 'plans' | 'tenants';
type Currency = 'EUR' | 'USD';

const SCOPES: { id: Scope; label: string; hint: string }[] = [
  { id: 'providers', label: 'Fournisseurs', hint: "Plafond de la facture d'API, tous clients confondus" },
  { id: 'plans', label: 'Forfaits', hint: 'Plafond appliqué par défaut à chaque client du forfait' },
  { id: 'tenants', label: 'Clients', hint: 'Plafond nominatif, prioritaire sur celui du forfait' },
];

const STATE_LABEL: Record<CostLimitState, string> = {
  ok: 'Sous contrôle',
  alerte: 'Seuil d’alerte franchi',
  bloque: 'Plafond atteint — appels bloqués',
  sans_plafond: 'Aucun plafond',
};

function money(amount: number | null | undefined, currency: Currency): string {
  if (amount === null || amount === undefined) return '—';
  return new Intl.NumberFormat('fr-FR', {
    style: 'currency',
    currency,
    maximumFractionDigits: amount < 10 ? 2 : 0,
  }).format(amount);
}

/** Barre de consommation : un trait de 2 px, pas une pilule arrondie. */
function UsageBar({ spend, cap, state }: { spend: number; cap: number | null; state: CostLimitState }) {
  if (cap === null || cap <= 0) {
    return <div className="h-[2px] w-full bg-[var(--rule)]" aria-hidden />;
  }
  const pct = Math.min(100, (spend / cap) * 100);
  const color =
    state === 'bloque' ? 'var(--friction)' : state === 'alerte' ? 'var(--friction)' : 'var(--ink-3)';
  return (
    <div className="h-[2px] w-full bg-[var(--rule)]" role="img" aria-label={`${Math.round(pct)} % du plafond`}>
      <div className="h-full transition-[width] duration-150" style={{ width: `${pct}%`, background: color }} />
    </div>
  );
}

function StateDot({ state }: { state: CostLimitState }) {
  const cls =
    state === 'bloque'
      ? 'bg-[var(--friction)]'
      : state === 'alerte'
        ? 'bg-[var(--friction)] opacity-60'
        : state === 'ok'
          ? 'bg-[var(--ink-3)]'
          : 'bg-transparent border border-[var(--rule-strong)]';
  return <span className={`inline-block w-[6px] h-[6px] rounded-full shrink-0 ${cls}`} title={STATE_LABEL[state]} />;
}

/** Champ de saisie du plafond, édité directement dans la ligne. */
function CapCell({
  valueUsd,
  valueEur,
  currency,
  placeholder,
  onSave,
  disabled,
  disabledReason,
}: {
  valueUsd: number | null;
  valueEur: number | null;
  currency: Currency;
  placeholder: string;
  onSave: (amount: number | null) => Promise<void>;
  disabled?: boolean;
  disabledReason?: string;
}) {
  const shown = currency === 'EUR' ? valueEur : valueUsd;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (editing) inputRef.current?.select();
  }, [editing]);

  const start = () => {
    if (disabled) return;
    setDraft(shown === null || shown === undefined ? '' : String(shown));
    setEditing(true);
  };

  const commit = async () => {
    const trimmed = draft.trim().replace(',', '.');
    const parsed = trimmed === '' ? null : Number(trimmed);
    if (parsed !== null && (Number.isNaN(parsed) || parsed < 0)) return;
    setBusy(true);
    try {
      await onSave(parsed);
      setEditing(false);
    } finally {
      setBusy(false);
    }
  };

  if (editing) {
    return (
      <div className="flex items-center gap-1">
        <input
          ref={inputRef}
          value={draft}
          autoFocus
          inputMode="decimal"
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') setEditing(false);
          }}
          className="w-24 bg-[var(--surface-2)] border border-hl rounded-[4px] px-2 py-1 text-[13px] font-mono text-[var(--ink-1)] outline-none tabular-nums"
          placeholder={placeholder}
        />
        <button
          type="button"
          onClick={commit}
          disabled={busy}
          className="p-1 rounded-[4px] text-[var(--ink-2)] hover:text-[var(--ink-1)] hover:bg-[var(--surface-2)] transition-colors duration-100"
          title="Enregistrer (Entrée)"
        >
          <Check className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
        <button
          type="button"
          onClick={() => setEditing(false)}
          className="p-1 rounded-[4px] text-[var(--ink-3)] hover:text-[var(--ink-1)] transition-colors duration-100"
          title="Annuler (Échap)"
        >
          <X className="w-3.5 h-3.5" strokeWidth={1.5} />
        </button>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={start}
      disabled={disabled}
      title={disabled ? disabledReason : 'Modifier le plafond'}
      className={`group/cap w-full text-left font-mono text-[13px] tabular-nums px-2 py-1 -mx-2 rounded-[4px] transition-colors duration-100 ${
        disabled
          ? 'text-[var(--ink-3)] cursor-not-allowed'
          : 'text-[var(--ink-1)] hover:bg-[var(--surface-2)] cursor-text'
      }`}
    >
      {shown === null || shown === undefined ? (
        <span className="text-[var(--ink-3)]">{placeholder}</span>
      ) : (
        money(shown, currency)
      )}
    </button>
  );
}

export default function CostLimitsPage() {
  const [data, setData] = useState<CostLimitsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scope, setScope] = useState<Scope>('providers');
  const [currency, setCurrency] = useState<Currency>('EUR');
  const [query, setQuery] = useState('');
  const [selectedTenant, setSelectedTenant] = useState<CostLimitTenantRow | null>(null);
  const [applying, setApplying] = useState(false);
  const [flash, setFlash] = useState<string | null>(null);
  const searchRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    try {
      const res = await api.getCostLimits();
      setData(res);
      setCurrency(res.settings.display_currency);
      setError(null);
    } catch (e: any) {
      setError(e?.message || 'Impossible de charger les plafonds.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!flash) return;
    const id = setTimeout(() => setFlash(null), 2600);
    return () => clearTimeout(id);
  }, [flash]);

  // Raccourcis clavier : « / » cherche, « Échap » referme le tiroir, 1–3 changent de vue.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const typing = target && ['INPUT', 'TEXTAREA'].includes(target.tagName);
      if (e.key === 'Escape') {
        setSelectedTenant(null);
        return;
      }
      if (typing) return;
      if (e.key === '/') {
        e.preventDefault();
        searchRef.current?.focus();
      }
      if (e.key === '1') setScope('providers');
      if (e.key === '2') setScope('plans');
      if (e.key === '3') setScope('tenants');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const filtered = useMemo(() => {
    if (!data) return { providers: [], plans: [], tenants: [] };
    const q = query.trim().toLowerCase();
    const match = (s: string) => !q || s.toLowerCase().includes(q);
    return {
      providers: data.providers.filter((p) => match(p.name) || match(p.id)),
      plans: data.plans.filter((p) => match(p.name) || match(p.id)),
      tenants: data.tenants.filter((t) => match(t.name) || match(t.plan_id)),
    };
  }, [data, query]);

  const saveProvider = async (row: CostLimitProviderRow, amount: number | null) => {
    await api.setProviderCostCap(row.id, amount, currency);
    setFlash(`Plafond ${row.name} enregistré.`);
    await load();
  };
  const savePlan = async (row: CostLimitPlanRow, amount: number | null) => {
    await api.setPlanCostCap(row.id, amount, currency);
    setFlash(`Plafond du forfait ${row.name} enregistré.`);
    await load();
  };
  const saveTenant = async (row: CostLimitTenantRow, amount: number | null) => {
    await api.setTenantCostCap(row.id, amount, currency);
    setFlash(`Plafond de ${row.name} enregistré.`);
    await load();
  };

  const applyRecommended = async () => {
    setApplying(true);
    try {
      const res = await api.applyRecommendedPlanCaps();
      setFlash(`${res.applied.length} forfaits alignés sur le plafond conseillé.`);
      await load();
    } catch (e: any) {
      setError(e?.message || 'Application des plafonds conseillés impossible.');
    } finally {
      setApplying(false);
    }
  };

  const saveSetting = async (patch: Parameters<typeof api.updateCostLimitSettings>[0]) => {
    await api.updateCostLimitSettings(patch);
    await load();
  };

  const activeScope = SCOPES.find((s) => s.id === scope)!;

  return (
    <div
      className="min-h-screen bg-[var(--surface-0)] text-[var(--ink-1)]"
      style={
        {
          // Palette locale de l'écran : neutres ardoise chauds, un seul accent
          // fonctionnel (bleu de plan) et une couleur de friction (ocre brûlé)
          // réservée au dépassement. Aucune ombre floue : des filets de 1 px.
          '--surface-0': 'var(--cost-surface-0)',
          '--surface-1': 'var(--cost-surface-1)',
          '--surface-2': 'var(--cost-surface-2)',
          '--rule': 'var(--cost-rule)',
          '--rule-strong': 'var(--cost-rule-strong)',
          '--ink-1': 'var(--cost-ink-1)',
          '--ink-2': 'var(--cost-ink-2)',
          '--ink-3': 'var(--cost-ink-3)',
          '--accent': 'var(--cost-accent)',
          '--friction': 'rgb(var(--accent-rgb))',
        } as React.CSSProperties
      }
    >
      {/* ── Barre de titre ───────────────────────────────────────────────── */}
      <header className="sticky top-0 z-20 bg-[var(--surface-0)] border-b border-[var(--rule)]">
        <div className="px-6 py-4 flex items-start justify-between gap-6">
          <div className="min-w-0">
            <h1 className="text-[15px] font-semibold tracking-tight text-[var(--ink-1)]">Budgets &amp; plafonds IA</h1>
            <p className="text-[12px] text-[var(--ink-2)] mt-0.5 max-w-2xl leading-relaxed">
              Le coût des appels aux modèles est le seul poste variable de la plateforme. Trois verrous
              indépendants l’encadrent : la facture d’un fournisseur, la règle d’un forfait, l’exception
              d’un client.
            </p>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <div className="flex items-center border border-[var(--rule-strong)] rounded-[4px] overflow-hidden text-[11px] font-mono">
              {(['EUR', 'USD'] as Currency[]).map((c) => (
                <button
                  key={c}
                  type="button"
                  onClick={() => {
                    setCurrency(c);
                    saveSetting({ display_currency: c });
                  }}
                  className={`px-2.5 py-1 transition-colors duration-100 ${
                    currency === c
                      ? 'bg-hl text-hl-contrast'
                      : 'text-[var(--ink-2)] hover:text-[var(--ink-1)] hover:bg-[var(--surface-2)]'
                  }`}
                >
                  {c === 'EUR' ? '€' : '$'}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={applyRecommended}
              disabled={applying || !data}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-[4px] bg-hl text-hl-contrast text-[12px] font-semibold hover:bg-hl-strong disabled:opacity-50 transition-colors duration-150"
            >
              {applying && <RotateCw className="w-3.5 h-3.5 animate-spin" strokeWidth={1.5} />}
              <span>Appliquer les plafonds conseillés</span>
            </button>
          </div>
        </div>

        {/* Bandeau de chiffres — texte aligné sur une ligne, pas des cartes */}
        {data && (
          <div className="px-6 pb-3 flex flex-wrap items-center gap-x-8 gap-y-2 text-[12px]">
            <Stat label="Dépense du mois" value={money(currency === 'EUR' ? data.totals.spend_eur : data.totals.spend_usd, currency)} strong />
            <Stat label="Fournisseurs sans plafond" value={String(data.totals.providers_without_cap)} warn={data.totals.providers_without_cap > 0} />
            <Stat label="Forfaits sans plafond" value={String(data.totals.plans_without_cap)} warn={data.totals.plans_without_cap > 0} />
            <Stat label="Clients sans plafond" value={String(data.totals.tenants_without_cap)} warn={data.totals.tenants_without_cap > 0} />
            <Stat label="Clients bloqués" value={String(data.totals.tenants_blocked)} warn={data.totals.tenants_blocked > 0} />
          </div>
        )}
      </header>

      {/* ── Réglages compacts ────────────────────────────────────────────── */}
      {data && (
        <div className="px-6 py-2.5 border-b border-[var(--rule)] bg-[var(--surface-1)] flex flex-wrap items-center gap-x-8 gap-y-2 text-[11.5px] text-[var(--ink-2)]">
          <InlineNumber
            label="Taux € → $"
            value={data.settings.eur_usd_rate}
            step={0.01}
            suffix=""
            onSave={(v) => saveSetting({ eur_usd_rate: v })}
          />
          <InlineNumber
            label="Part de l’abonnement allouée à l’IA"
            value={Math.round(data.settings.target_llm_share * 100)}
            step={1}
            suffix=" %"
            onSave={(v) => saveSetting({ target_llm_share: v / 100 })}
          />
          <InlineNumber
            label="Alerte à"
            value={data.settings.alert_threshold_pct}
            step={5}
            suffix=" % du plafond"
            onSave={(v) => saveSetting({ alert_threshold_pct: v })}
          />
          <span className="text-[var(--ink-3)]">{data.settings.rate_source}</span>
        </div>
      )}

      {/* ── Sélecteur de vue + recherche ─────────────────────────────────── */}
      <div className="px-6 pt-4 pb-2 flex items-end justify-between gap-6 border-b border-[var(--rule)]">
        <nav className="flex items-end gap-6" role="tablist">
          {SCOPES.map((s, i) => (
            <button
              key={s.id}
              role="tab"
              aria-selected={scope === s.id}
              onClick={() => setScope(s.id)}
              className={`relative pb-2 text-[13px] transition-colors duration-100 ${
                scope === s.id
                  ? 'text-[var(--ink-1)] font-semibold'
                  : 'text-[var(--ink-2)] hover:text-[var(--ink-1)] font-medium'
              }`}
            >
              <span>{s.label}</span>
              <kbd className="ml-1.5 text-[9px] font-mono text-[var(--ink-3)] align-middle">{i + 1}</kbd>
              {scope === s.id && <span className="absolute left-0 right-0 -bottom-px h-[2px] bg-hl" />}
            </button>
          ))}
        </nav>
        <div className="flex items-center gap-2 pb-2">
          <input
            ref={searchRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Filtrer"
            className="w-56 bg-transparent border-b border-[var(--rule-strong)] focus:border-hl px-1 py-1 text-[12.5px] text-[var(--ink-1)] placeholder:text-[var(--ink-3)] outline-none transition-colors duration-100"
          />
          <kbd className="text-[9px] font-mono text-[var(--ink-3)] border border-[var(--rule-strong)] rounded-[3px] px-1 py-px">/</kbd>
        </div>
      </div>

      <p className="px-6 pt-3 text-[11.5px] text-[var(--ink-2)]">{activeScope.hint}</p>

      {/* ── Contenu ──────────────────────────────────────────────────────── */}
      <main className="px-6 py-4">
        {loading && <p className="text-[12.5px] text-[var(--ink-2)]">Chargement des plafonds…</p>}

        {error && (
          <div className="flex items-start gap-2 border border-[var(--friction)] rounded-[4px] px-3 py-2.5 text-[12.5px] text-[var(--ink-1)]">
            <AlertTriangle className="w-3.5 h-3.5 mt-0.5 text-[var(--friction)] shrink-0" strokeWidth={1.5} />
            <div>
              <p>{error}</p>
              <button onClick={load} className="mt-1 text-hl hover:underline">
                Réessayer
              </button>
            </div>
          </div>
        )}

        {data && !loading && scope === 'providers' && (
          <Table
            head={['', 'Fournisseur', 'Modèle par défaut', 'Hébergement', 'Consommé ce mois', 'Plafond mensuel', '']}
            empty={
              <Empty
                title="Aucun fournisseur configuré"
                body="Ajoutez une clé d’API dans Réglages IA, puis revenez fixer son plafond mensuel."
                href="/admin"
                cta="Ouvrir les réglages IA"
              />
            }
            rows={filtered.providers.map((row) => (
              <tr key={row.id} className="group border-b border-[var(--rule)] hover:bg-[var(--surface-1)] transition-colors duration-100">
                <Td className="w-6"><StateDot state={row.state} /></Td>
                <Td>
                  <div className="font-medium text-[var(--ink-1)]">{row.name}</div>
                  {!row.has_api_key && (
                    <div className="text-[11px] text-[var(--ink-3)]">Clé non renseignée — aucun appel possible</div>
                  )}
                </Td>
                <Td className="font-mono text-[11.5px] text-[var(--ink-2)]">{row.litellm_id || '—'}</Td>
                <Td>
                  <span className={row.is_non_eu ? 'text-[var(--friction)]' : 'text-[var(--ink-2)]'}>{row.zone || 'non vérifié'}</span>
                </Td>
                <Td className="font-mono tabular-nums">
                  <div>{money(currency === 'EUR' ? row.spend_eur : row.spend_usd, currency)}</div>
                  <div className="mt-1.5 w-32"><UsageBar spend={row.spend_usd} cap={row.cap_usd} state={row.state} /></div>
                </Td>
                <Td className="w-40">
                  <CapCell
                    valueUsd={row.cap_usd}
                    valueEur={row.cap_eur}
                    currency={currency}
                    placeholder="Sans plafond"
                    onSave={(v) => saveProvider(row, v)}
                  />
                </Td>
                <Td className="w-28 text-right">
                  <span className="opacity-0 group-hover:opacity-100 transition-opacity duration-100 text-[11px] text-[var(--ink-3)]">
                    {STATE_LABEL[row.state]}
                  </span>
                </Td>
              </tr>
            ))}
          />
        )}

        {data && !loading && scope === 'plans' && (
          <Table
            head={['', 'Forfait', 'Prix mensuel', 'Dossiers inclus', 'Clients', 'Plafond conseillé', 'Plafond appliqué', '']}
            empty={<Empty title="Aucun forfait" body="Créez au moins un forfait pour pouvoir lui associer un plafond." />}
            rows={filtered.plans.map((row) => (
              <tr key={row.id} className="group border-b border-[var(--rule)] hover:bg-[var(--surface-1)] transition-colors duration-100">
                <Td className="w-6"><StateDot state={row.is_configured ? 'ok' : 'sans_plafond'} /></Td>
                <Td>
                  <div className="font-medium text-[var(--ink-1)]">{row.name}</div>
                  <div className="text-[11px] font-mono text-[var(--ink-3)]">{row.id}</div>
                </Td>
                <Td className="font-mono tabular-nums text-[var(--ink-2)]">
                  {row.price_monthly_eur > 0 ? money(row.price_monthly_eur, 'EUR') : 'sur devis'}
                </Td>
                <Td className="font-mono tabular-nums text-[var(--ink-2)]">{row.included_dossiers_month}</Td>
                <Td className="font-mono tabular-nums text-[var(--ink-2)]">{row.tenant_count}</Td>
                <Td className="font-mono tabular-nums text-[var(--ink-3)]">
                  {money(currency === 'EUR' ? row.recommended_cap_eur : row.recommended_cap_usd, currency)}
                </Td>
                <Td className="w-40">
                  <CapCell
                    valueUsd={row.cap_usd}
                    valueEur={row.cap_eur}
                    currency={currency}
                    placeholder="Sans plafond"
                    onSave={(v) => savePlan(row, v)}
                  />
                </Td>
                <Td className="w-32 text-right">
                  <button
                    type="button"
                    onClick={() =>
                      savePlan(row, currency === 'EUR' ? row.recommended_cap_eur : row.recommended_cap_usd)
                    }
                    className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity duration-100 text-[11.5px] text-hl hover:underline"
                  >
                    Appliquer le conseil
                  </button>
                </Td>
              </tr>
            ))}
          />
        )}

        {data && !loading && scope === 'tenants' && (
          <Table
            head={['', 'Client', 'Forfait', 'Consommé ce mois', 'Plafond effectif', 'Origine', 'Plafond nominatif', '']}
            empty={<Empty title="Aucun client" body="Les plafonds nominatifs apparaîtront ici dès qu’un client aura un abonnement." />}
            rows={filtered.tenants.map((row) => (
              <tr key={row.id} className="group border-b border-[var(--rule)] hover:bg-[var(--surface-1)] transition-colors duration-100">
                <Td className="w-6"><StateDot state={row.state} /></Td>
                <Td>
                  <button
                    type="button"
                    onClick={() => setSelectedTenant(row)}
                    className="text-left font-medium text-[var(--ink-1)] hover:text-hl transition-colors duration-100"
                  >
                    {row.name}
                  </button>
                </Td>
                <Td className="font-mono text-[11.5px] text-[var(--ink-2)]">{row.plan_id}</Td>
                <Td className="font-mono tabular-nums">
                  <div>{money(currency === 'EUR' ? row.spend_eur : row.spend_usd, currency)}</div>
                  <div className="mt-1.5 w-32"><UsageBar spend={row.spend_usd} cap={row.effective_cap_usd} state={row.state} /></div>
                </Td>
                <Td className="font-mono tabular-nums text-[var(--ink-2)]">
                  {money(currency === 'EUR' ? row.effective_cap_eur : row.effective_cap_usd, currency)}
                </Td>
                <Td className="text-[11.5px] text-[var(--ink-3)]">{row.source}</Td>
                <Td className="w-40">
                  <CapCell
                    valueUsd={row.custom_cap_usd}
                    valueEur={row.custom_cap_eur}
                    currency={currency}
                    placeholder="Hérite du forfait"
                    onSave={(v) => saveTenant(row, v)}
                  />
                </Td>
                <Td className="w-24 text-right">
                  <button
                    type="button"
                    onClick={() => setSelectedTenant(row)}
                    className="opacity-0 group-hover:opacity-100 focus:opacity-100 transition-opacity duration-100 inline-flex items-center gap-1 text-[11.5px] text-hl"
                  >
                    Détail <ArrowUpRight className="w-3 h-3" strokeWidth={1.5} />
                  </button>
                </Td>
              </tr>
            ))}
          />
        )}
      </main>

      {/* ── Tiroir de détail client (pas de modale : le tableau reste lisible) ── */}
      {selectedTenant && (
        <>
          <div
            className="fixed inset-0 z-30 bg-black/20"
            onClick={() => setSelectedTenant(null)}
            aria-hidden
          />
          <aside className="fixed top-0 right-0 bottom-0 z-40 w-[380px] bg-[var(--surface-0)] border-l border-[var(--rule-strong)] flex flex-col">
            <div className="px-5 py-4 border-b border-[var(--rule)] flex items-start justify-between gap-3">
              <div>
                <h2 className="text-[14px] font-semibold text-[var(--ink-1)]">{selectedTenant.name}</h2>
                <p className="text-[11.5px] text-[var(--ink-3)] font-mono mt-0.5">{selectedTenant.plan_id} · {selectedTenant.status}</p>
              </div>
              <button
                onClick={() => setSelectedTenant(null)}
                className="p-1 rounded-[4px] text-[var(--ink-3)] hover:text-[var(--ink-1)] hover:bg-[var(--surface-2)] transition-colors duration-100"
                title="Fermer (Échap)"
              >
                <X className="w-4 h-4" strokeWidth={1.5} />
              </button>
            </div>
            <div className="px-5 py-4 space-y-4 text-[12.5px] overflow-y-auto">
              <DetailRow label="Consommé ce mois" value={money(currency === 'EUR' ? selectedTenant.spend_eur : selectedTenant.spend_usd, currency)} />
              <DetailRow label="Plafond effectif" value={money(currency === 'EUR' ? selectedTenant.effective_cap_eur : selectedTenant.effective_cap_usd, currency)} />
              <DetailRow label="Origine du plafond" value={selectedTenant.source} />
              <div className="flex items-baseline justify-between gap-4">
                <span className="text-[var(--ink-3)]">État</span>
                <span
                  className="font-mono text-right"
                  style={{
                    color:
                      selectedTenant.state === 'bloque' || selectedTenant.state === 'alerte'
                        ? 'var(--friction)'
                        : 'var(--ink-1)',
                  }}
                >
                  {STATE_LABEL[selectedTenant.state]}
                </span>
              </div>
              <div className="pt-3 border-t border-[var(--rule)]">
                <p className="text-[11.5px] text-[var(--ink-2)] leading-relaxed">
                  Un plafond nominatif remplace celui du forfait. Le laisser vide fait retomber ce client
                  sur la règle commerciale de son forfait — c’est le comportement à préférer tant qu’une
                  négociation particulière ne l’impose pas.
                </p>
                <div className="mt-3">
                  <p className="text-[11.5px] font-medium text-[var(--ink-3)] mb-1">Plafond nominatif</p>
                  <CapCell
                    valueUsd={selectedTenant.custom_cap_usd}
                    valueEur={selectedTenant.custom_cap_eur}
                    currency={currency}
                    placeholder="Hérite du forfait"
                    onSave={async (v) => {
                      await saveTenant(selectedTenant, v);
                      setSelectedTenant(null);
                    }}
                  />
                </div>
              </div>
            </div>
          </aside>
        </>
      )}

      {/* ── Confirmation discrète ────────────────────────────────────────── */}
      {flash && (
        <div className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50 px-3 py-2 rounded-[4px] bg-[var(--ink-1)] text-[var(--surface-0)] text-[12px]">
          {flash}
        </div>
      )}
    </div>
  );
}

function Stat({ label, value, strong, warn }: { label: string; value: string; strong?: boolean; warn?: boolean }) {
  return (
    <div className="flex items-baseline gap-2">
      <span className="text-[var(--ink-3)]">{label}</span>
      <span
        className={`font-mono tabular-nums ${strong ? 'text-[15px] text-[var(--ink-1)]' : 'text-[13px]'} ${
          warn ? 'text-[var(--friction)]' : 'text-[var(--ink-1)]'
        }`}
      >
        {value}
      </span>
    </div>
  );
}

function InlineNumber({
  label,
  value,
  step,
  suffix,
  onSave,
}: {
  label: string;
  value: number;
  step: number;
  suffix: string;
  onSave: (v: number) => Promise<void> | void;
}) {
  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);
  return (
    <label className="flex items-baseline gap-1.5">
      <span className="text-[var(--ink-3)]">{label}</span>
      <input
        value={draft}
        step={step}
        inputMode="decimal"
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          const n = Number(draft.replace(',', '.'));
          if (!Number.isNaN(n) && n !== value) onSave(n);
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter') (e.target as HTMLInputElement).blur();
        }}
        className="w-14 bg-transparent border-b border-[var(--rule-strong)] focus:border-hl text-center font-mono tabular-nums text-[var(--ink-1)] outline-none transition-colors duration-100"
      />
      <span className="text-[var(--ink-3)]">{suffix}</span>
    </label>
  );
}

function Table({ head, rows, empty }: { head: string[]; rows: React.ReactNode[]; empty: React.ReactNode }) {
  if (rows.length === 0) return <>{empty}</>;
  return (
    <table className="w-full border-collapse">
      <thead>
        <tr className="border-b border-[var(--rule-strong)]">
          {head.map((h, i) => (
            <th
              key={i}
              className="text-left font-mono text-[10px] uppercase tracking-[0.12em] text-[var(--ink-3)] font-medium pb-2 px-3 first:pl-0 last:pr-0"
            >
              {h}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  );
}

function Td({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <td className={`py-2.5 px-3 first:pl-0 last:pr-0 align-top text-[12.5px] ${className}`}>{children}</td>;
}

function Empty({ title, body, href, cta }: { title: string; body: string; href?: string; cta?: string }) {
  return (
    <div className="border border-dashed border-[var(--rule-strong)] rounded-[4px] px-6 py-10 text-center">
      <p className="text-[13px] font-medium text-[var(--ink-1)]">{title}</p>
      <p className="mt-1 text-[12px] text-[var(--ink-2)] max-w-md mx-auto leading-relaxed">{body}</p>
      {href && cta && (
        <a href={href} className="mt-3 inline-block text-[12px] text-hl hover:underline">
          {cta}
        </a>
      )}
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-[var(--ink-3)]">{label}</span>
      <span className="font-mono tabular-nums text-[var(--ink-1)]">{value}</span>
    </div>
  );
}
