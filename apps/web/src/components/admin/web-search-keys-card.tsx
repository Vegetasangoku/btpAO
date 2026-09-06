'use client';

import React, { useCallback, useEffect, useState } from 'react';
import { Search, Loader2, CheckCircle2, AlertTriangle, Save, Plus, Trash2, ArrowUp, ArrowDown } from 'lucide-react';
import { api } from '@/lib/api';
import { SearchProviderConfig, SupportedSearchType } from '@/lib/types';

interface Row extends SearchProviderConfig {
  api_key_input?: string;
  test_running?: boolean;
  test_ok?: boolean;
  test_message?: string;
}

/**
 * Fournisseurs de recherche web, gerés comme une LISTE (04/09).
 *
 * Première version : deux champs figés Serper / Brave. Reproche justifié de Charbel --
 * « si je veux autre chose que Serper je peux ? ». On reprend donc la même logique que les
 * fournisseurs LLM personnalisés : une liste ordonnée, chaque entrée activable, testable
 * et supprimable, avec un ordre de priorité qui pilote la cascade de repli.
 *
 * Limite honnête : chaque moteur a une API différente, donc un type non couvert par un
 * adaptateur côté serveur ne peut pas fonctionner. La liste des types disponibles vient
 * du serveur (SUPPORTED_SEARCH_TYPES) : ajouter un moteur = un adaptateur + une entrée
 * dans ce registre, et il apparaît ici automatiquement.
 */
export function WebSearchKeysCard() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);
  const [types, setTypes] = useState<SupportedSearchType[]>([]);

  const load = useCallback(async () => {
    try {
      const d = await api.getPlatformLLMKeys();
      setRows((d.web_search_providers || []).map((p) => ({ ...p })));
      setTypes(d.supported_search_types || []);
    } catch (err) {
      console.error('Failed to load web search providers', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function update(idx: number, patch: Partial<Row>) {
    setRows((prev) => prev.map((r, i) => (i === idx ? { ...r, ...patch } : r)));
  }

  function move(idx: number, delta: number) {
    setRows((prev) => {
      const next = [...prev];
      const target = idx + delta;
      if (target < 0 || target >= next.length) return prev;
      [next[idx], next[target]] = [next[target], next[idx]];
      return next.map((r, i) => ({ ...r, priority: i + 1 }));
    });
  }

  function addRow() {
    const t = types[0];
    if (!t) return;
    const id = `${t.type}_${Date.now().toString(36).slice(-4)}`;
    setRows((prev) => [
      ...prev,
      { id, name: t.label, type: t.type, enabled: true, priority: prev.length + 1, api_key_configured: false, api_key_masked: '' },
    ]);
  }

  async function save() {
    setSaving(true);
    setSaved(false);
    try {
      await api.updatePlatformLLMKeys({
        web_search_providers: rows.map((r, i) => ({
          id: r.id,
          name: r.name,
          type: r.type,
          enabled: r.enabled,
          priority: i + 1,
          ...(r.api_key_input?.trim() ? { api_key: r.api_key_input.trim() } : {}),
        })),
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
      await load();
    } catch (err) {
      console.error('Failed to save web search providers', err);
    } finally {
      setSaving(false);
    }
  }

  async function test(idx: number) {
    const r = rows[idx];
    update(idx, { test_running: true, test_message: undefined });
    try {
      const res = await api.testSearchProvider({
        provider: r.type,
        provider_id: r.id,
        ...(r.api_key_input?.trim() ? { api_key: r.api_key_input.trim() } : {}),
      });
      update(idx, { test_running: false, test_ok: res.success, test_message: res.success ? res.message : res.error });
    } catch (err: any) {
      update(idx, { test_running: false, test_ok: false, test_message: err?.message || 'Échec du test' });
    }
  }

  if (loading) return null;

  const noneActive = !rows.some((r) => r.enabled && (r.api_key_configured || r.api_key_input?.trim()));

  return (
    <div className="p-6 rounded-2xl bg-card border border-line shadow-xs space-y-4">
      <div className="border-b border-line pb-4">
        <h3 className="text-sm font-bold text-foreground flex items-center gap-2 font-heading">
          <Search className="w-4 h-4 text-hl" />
          <span>Recherche web — sources officielles</span>
        </h3>
        <p className="text-xs text-muted-foreground mt-1 max-w-2xl">
          Moteurs utilisés pour interroger les sites officiels déclarés par pays, lorsque le corpus
          du client ne suffit pas. La recherche reste toujours bornée à la liste blanche du pays.
          Ils sont essayés dans l&apos;ordre ci-dessous : le premier qui répond gagne, les suivants
          servent de repli. La case <strong>Actif</strong> sert à couper temporairement un moteur
          (par exemple pour arrêter d&apos;en consommer le quota) sans effacer sa clé — elle se coche
          d&apos;elle-même dès que vous saisissez une clé.
        </p>
      </div>

      {noneActive && (
        <p className="text-[11px] text-warn flex items-start gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-px" />
          Aucun moteur actif : la recherche sur les sites officiels est inactive, la génération
          s&apos;appuiera uniquement sur les documents du client.
        </p>
      )}

      <div className="space-y-2.5">
        {rows.map((r, idx) => {
          const meta = types.find((t) => t.type === r.type);
          return (
            <div key={r.id} className="rounded-xl border border-line p-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-mono font-bold text-hl w-6">#{idx + 1}</span>
                <input
                  value={r.name}
                  onChange={(e) => update(idx, { name: e.target.value })}
                  className="w-40 bg-transparent text-xs font-semibold text-foreground border-b border-transparent hover:border-line focus:border-hl focus:outline-none"
                />
                <select
                  value={r.type}
                  onChange={(e) => update(idx, { type: e.target.value })}
                  className="bg-bg border border-line rounded-lg px-2 py-1 text-[11px] cursor-pointer"
                >
                  {types.map((t) => (
                    <option key={t.type} value={t.type}>{t.label}</option>
                  ))}
                </select>
                {meta && (
                  <span className="text-[10px] text-muted-foreground">
                    ≈ {meta.cost_per_query_usd} $ / requête
                  </span>
                )}
                {r.api_key_configured && (
                  <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-positive/15 text-positive">
                    {r.api_key_masked}
                  </span>
                )}
                <label className="text-[11px] text-muted-foreground inline-flex items-center gap-1 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    onChange={(e) => update(idx, { enabled: e.target.checked })}
                    className="cursor-pointer"
                  />
                  Actif
                </label>
                <div className="ml-auto flex items-center gap-1">
                  <button type="button" onClick={() => move(idx, -1)} disabled={idx === 0}
                    className="p-1 rounded hover:text-hl disabled:opacity-30 cursor-pointer" title="Monter">
                    <ArrowUp className="w-3 h-3" />
                  </button>
                  <button type="button" onClick={() => move(idx, 1)} disabled={idx === rows.length - 1}
                    className="p-1 rounded hover:text-hl disabled:opacity-30 cursor-pointer" title="Descendre">
                    <ArrowDown className="w-3 h-3" />
                  </button>
                  <button type="button" onClick={() => setRows((p) => p.filter((_, i) => i !== idx))}
                    className="p-1 rounded text-slate-300 dark:text-zinc-600 hover:text-danger cursor-pointer" title="Supprimer">
                    <Trash2 className="w-3 h-3" />
                  </button>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <input
                  type="password"
                  value={r.api_key_input || ''}
                  onChange={(e) =>
                    // Saisir une cle vaut activation : personne ne colle une cle pour
                    // laisser le moteur eteint. La case reste disponible pour couper
                    // temporairement un moteur payant sans effacer sa cle.
                    update(idx, { api_key_input: e.target.value, enabled: e.target.value.trim() ? true : r.enabled })
                  }
                  placeholder={r.api_key_configured ? 'Laisser vide pour conserver la clé actuelle' : (meta?.key_hint || 'Clé d’API')}
                  className="flex-1 min-w-[240px] bg-bg border border-line rounded-lg px-2.5 py-1.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-hl"
                />
                <button type="button" onClick={() => test(idx)} disabled={r.test_running}
                  className="px-2.5 py-1.5 rounded-lg border border-line text-[11px] font-semibold hover:text-hl disabled:opacity-50 cursor-pointer inline-flex items-center gap-1">
                  {r.test_running ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle2 className="w-3 h-3" />}
                  Tester
                </button>
              </div>

              <p className="text-[11px] text-muted-foreground">
                {!r.api_key_configured && !r.api_key_input?.trim()
                  ? 'Aucune clé — ce moteur ne peut pas être utilisé.'
                  : !r.enabled
                    ? 'Clé enregistrée, mais désactivé : ce moteur ne sera pas interrogé.'
                    : idx === 0
                      ? 'Actif — c’est ce moteur qui est interrogé en premier.'
                      : `Actif — utilisé en repli si les ${idx} moteur(s) au-dessus échouent.`}
              </p>

              {r.test_message && (
                <p className={`text-[11px] inline-flex items-center gap-1 ${r.test_ok ? 'text-positive' : 'text-danger'}`}>
                  {r.test_ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertTriangle className="w-3 h-3" />}
                  {r.test_message}
                </p>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex flex-wrap items-center gap-2 pt-1">
        <button type="button" onClick={addRow} disabled={!types.length}
          className="px-2.5 py-1.5 rounded-lg border border-line text-[11px] font-semibold hover:text-hl disabled:opacity-50 cursor-pointer inline-flex items-center gap-1">
          <Plus className="w-3 h-3" /> Ajouter un moteur
        </button>
        <button type="button" onClick={save} disabled={saving}
          className="ml-auto px-3 py-1.5 rounded-lg bg-hl hover:bg-hl-strong text-hl-contrast text-[11px] font-semibold disabled:opacity-50 cursor-pointer inline-flex items-center gap-1.5">
          {saving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
          Enregistrer
        </button>
        {saved && <span className="text-[11px] text-positive">Enregistré.</span>}
      </div>
    </div>
  );
}
