'use client';

import React, { useEffect, useState } from 'react';
import { CheckCircle2, Loader2, Save } from 'lucide-react';
import { Project } from '@/lib/types';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';
import { OutcomeSelect } from '@/components/projects/outcome-select';

/**
 * 11/09 : « Compléter le projet » renvoyait vers une page où rien n'était
 * modifiable (acheteur, lot, budget, date limite ne se saisissaient que dans
 * l'assistant de création). Cette carte permet de les corriger ici.
 * Les valeurs par défaut de l'assistant sont présentées comme telles.
 */
const ACHETEUR_DEFAUT = ['acheteur public détecté', 'acheteur public detecte'];
const LOT_DEFAUT = ['lot 01 - gros œuvre', 'lot 01 - gros oeuvre'];
const BUDGET_DEFAUT = 3_500_000;

function versDate(v?: string | null) {
  if (!v) return '';
  const d = new Date(v);
  return isNaN(d.getTime()) ? '' : d.toISOString().slice(0, 10);
}

export function ProjectInfoCard({ project, onSaved }: { project: Project; onSaved?: (p: Project) => void }) {
  const { t } = useTranslation();
  const estDefaut = (v: string | undefined, liste: string[]) => !v || liste.includes(v.trim().toLowerCase());
  const [f, setF] = useState({
    client_name: estDefaut(project.client_name, ACHETEUR_DEFAUT) ? '' : project.client_name,
    reference_code: project.reference_code || '',
    lot_number: estDefaut(project.lot_number, LOT_DEFAUT) ? '' : project.lot_number || '',
    location: project.location || '',
    budget: project.budget_estimate != null ? String(project.budget_estimate) : '',
    deadline: versDate(project.submission_deadline),
    output_language: (project.output_language as string) || 'fr',
  });
  const [etat, setEtat] = useState<'idle' | 'saving' | 'ok' | 'err'>('idle');
  const [erreur, setErreur] = useState<string | null>(null);

  useEffect(() => {
    if (typeof window !== 'undefined' && window.location.hash === '#infos') {
      document.getElementById('infos')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  }, []);

  const budgetDefaut = Number(f.budget) === BUDGET_DEFAUT;

  async function enregistrer() {
    setEtat('saving');
    setErreur(null);
    try {
      const data: Partial<Project> & Record<string, unknown> = {
        client_name: f.client_name.trim() || project.client_name,
        reference_code: f.reference_code.trim() || undefined,
        lot_number: f.lot_number.trim() || project.lot_number,
        location: f.location.trim() || undefined,
        budget_estimate: f.budget.trim() ? Number(f.budget.replace(/\s/g, '').replace(',', '.')) : undefined,
        submission_deadline: f.deadline ? new Date(`${f.deadline}T12:00:00Z`).toISOString() : undefined,
        output_language: f.output_language,
      };
      const p = await api.updateProject(project.id, data as Partial<Project>);
      setEtat('ok');
      onSaved?.(p);
      setTimeout(() => setEtat('idle'), 2500);
    } catch (e) {
      setEtat('err');
      setErreur(e instanceof Error ? e.message : String(e));
    }
  }

  const champ = (cle: keyof typeof f, label: string, props: React.InputHTMLAttributes<HTMLInputElement> = {}, aide?: string | null) => (
    <label className="space-y-1 block">
      <span className="text-[12px] font-medium text-foreground">{label}</span>
      <input
        value={f[cle]}
        onChange={(e) => setF({ ...f, [cle]: e.target.value })}
        className="input-field"
        {...props}
      />
      {aide && <span className="text-[11px] text-warning block">{aide}</span>}
    </label>
  );

  return (
    <div id="infos" className="card-modern p-5 sm:p-6 space-y-4 rounded-2xl scroll-mt-20">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-[14px] font-bold text-foreground font-heading">{t('infos.titre')}</h2>
          <p className="text-[12px] text-muted-foreground">{t('infos.sous_titre')}</p>
        </div>
        <button onClick={enregistrer} disabled={etat === 'saving'} className="btn-primary !py-1.5 !text-[12px]">
          {etat === 'saving' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : etat === 'ok' ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />}
          {etat === 'ok' ? t('infos.enregistre') : t('infos.enregistrer')}
        </button>
      </div>
      {erreur && <p className="text-[12px] text-danger">{erreur}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {champ('client_name', t('infos.acheteur'), { placeholder: t('infos.acheteur_ph') },
          estDefaut(project.client_name, ACHETEUR_DEFAUT) && !f.client_name ? t('infos.a_completer') : null)}
        {champ('reference_code', t('infos.reference'))}
        {champ('lot_number', t('infos.lot'), { placeholder: t('infos.lot_ph') },
          estDefaut(project.lot_number, LOT_DEFAUT) && !f.lot_number ? t('infos.a_completer') : null)}
        {champ('location', t('infos.lieu'))}
        {champ('budget', t('infos.budget'), { inputMode: 'decimal' }, budgetDefaut ? t('infos.budget_defaut') : null)}
        {champ('deadline', t('infos.date_limite'), { type: 'date' }, !f.deadline ? t('infos.date_limite_aide') : null)}
        <label className="space-y-1 block">
          <span className="text-[12px] font-medium text-foreground">{t('infos.langue_document')}</span>
          <select value={f.output_language} onChange={(e) => setF({ ...f, output_language: e.target.value })} className="input-field">
            <option value="fr">Français</option>
            <option value="en">English</option>
            <option value="ar">العربية</option>
          </select>
        </label>
        <div className="space-y-1">
          <span className="text-[12px] font-medium text-foreground block">{t('infos.issue')}</span>
          <OutcomeSelect projectId={project.id} value={project.outcome_status} />
        </div>
      </div>
    </div>
  );
}
