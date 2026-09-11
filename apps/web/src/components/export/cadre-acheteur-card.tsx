'use client';

/**
 * Cadre de réponse imposé par l'acheteur (11/09).
 *
 * Beaucoup de consultations imposent LEUR trame de mémoire technique (.docx) :
 * titres numérotés, consignes « Le candidat décrira… », tableaux à compléter.
 * Le service existait côté API mais n'était branché nulle part dans l'interface,
 * et ne savait remplir que des champs {{…}}. Il remplit désormais chaque partie
 * avec les sections rédigées, le tableau d'équipe avec l'organigramme, insère le
 * planning, et signale en rouge ce qui manque.
 */
import React, { useRef, useState } from 'react';
import { FileText, Upload, Download, CheckCircle2, AlertTriangle, RefreshCw } from 'lucide-react';
import { api, postFormForBlob } from '@/lib/api';
import { CadreRapport } from '@/lib/types';
import { useTranslation } from '@/components/i18n-provider';

export function CadreAcheteurCard({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [fichier, setFichier] = useState<File | null>(null);
  const [rapport, setRapport] = useState<CadreRapport | null>(null);
  const [etat, setEtat] = useState<'repos' | 'analyse' | 'remplissage'>('repos');
  const [erreur, setErreur] = useState<string | null>(null);

  const analyser = async (f: File) => {
    setEtat('analyse');
    setErreur(null);
    setRapport(null);
    try {
      setRapport(await api.analyserCadreAcheteur(projectId, f));
    } catch (e: any) {
      setErreur(e?.message || String(e));
    } finally {
      setEtat('repos');
    }
  };

  const remplir = async () => {
    if (!fichier) return;
    setEtat('remplissage');
    setErreur(null);
    try {
      const fd = new FormData();
      fd.append('file', fichier);
      const { blob } = await postFormForBlob(`/client-templates/${projectId}/fill`, fd);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = fichier.name.replace(/\.docx$/i, '') + '_rempli.docx';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setTimeout(() => URL.revokeObjectURL(url), 60000);
    } catch (e: any) {
      setErreur(e?.message || String(e));
    } finally {
      setEtat('repos');
    }
  };

  const manquants = rapport?.sections.filter((s) => s.status !== 'filled') || [];
  const remplis = rapport?.sections.filter((s) => s.status === 'filled') || [];

  return (
    <div className="card-modern p-6 sm:p-8 space-y-4">
      <div className="flex items-start gap-3 border-b border-line pb-4">
        <FileText className="w-5 h-5 text-hl mt-0.5" />
        <div>
          <h2 className="text-base font-bold text-foreground font-heading">{t('cadre.titre')}</h2>
          <p className="text-xs text-muted-foreground mt-0.5">{t('cadre.aide')}</p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <input
          ref={inputRef}
          type="file"
          accept=".docx"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0] || null;
            setFichier(f);
            if (f) analyser(f);
          }}
        />
        <button onClick={() => inputRef.current?.click()} className="btn-secondary !text-xs cursor-pointer">
          <Upload className="w-3.5 h-3.5" />
          {fichier ? fichier.name : t('cadre.choisir')}
        </button>
        <button
          onClick={remplir}
          disabled={!fichier || etat !== 'repos'}
          className="btn-primary !text-xs cursor-pointer disabled:opacity-50"
        >
          {etat === 'remplissage' ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          {etat === 'remplissage' ? t('cadre.remplissage') : t('cadre.remplir')}
        </button>
        {etat === 'analyse' && (
          <span className="text-xs text-muted-foreground flex items-center gap-1.5">
            <RefreshCw className="w-3 h-3 animate-spin" /> {t('cadre.analyse')}
          </span>
        )}
      </div>

      {erreur && (
        <div className="p-3 rounded-xl border border-danger/30 bg-danger/10 text-danger text-xs flex gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" /> {erreur}
        </div>
      )}

      {rapport && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <span className={`px-2.5 py-1 rounded-lg font-bold ${rapport.is_ready_for_submission ? 'bg-positive/15 text-positive' : 'bg-warning/15 text-warning'}`}>
              {t('cadre.score', { score: String(rapport.completeness_score_pct) })}
            </span>
            <span className="text-muted-foreground">
              {t('cadre.compte', { remplis: String(rapport.filled_fields), total: String(rapport.total_fields) })}
            </span>
          </div>
          {rapport.message && <p className="text-xs text-warning">{rapport.message}</p>}
          {manquants.length > 0 && (
            <div className="space-y-1">
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground font-bold">{t('cadre.a_completer')}</p>
              {manquants.map((s, i) => (
                <div key={i} className="text-xs flex gap-2 text-danger">
                  <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                  <span><strong>{s.section_name}</strong> — {s.missing_elements.join(' ; ')}</span>
                </div>
              ))}
            </div>
          )}
          {remplis.length > 0 && (
            <details className="text-xs">
              <summary className="cursor-pointer text-muted-foreground">{t('cadre.remplis', { n: String(remplis.length) })}</summary>
              <div className="mt-1.5 space-y-1">
                {remplis.map((s, i) => (
                  <div key={i} className="flex gap-2">
                    <CheckCircle2 className="w-3.5 h-3.5 text-positive shrink-0 mt-0.5" />
                    <span><strong>{s.section_name}</strong> <span className="text-muted-foreground">— {s.source_used}</span></span>
                  </div>
                ))}
              </div>
            </details>
          )}
        </div>
      )}
    </div>
  );
}
