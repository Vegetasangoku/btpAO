'use client';

import Link from 'next/link';

import React from 'react';
import { FileWarning, ImageIcon, ShieldAlert, CheckCircle2, Gauge, ArrowRight, ChevronDown, ChevronRight } from 'lucide-react';
import { useTranslation } from '@/components/i18n-provider';
import { TexteAvecAcronymes } from '@/components/ui/acronyme';

/**
 * Diagnostic d'une section générée (10/09).
 *
 * Répond à une question que l'utilisateur ne pouvait pas trancher jusqu'ici :
 * « une section faible, est-ce le modèle ou est-ce mon jeu de données ? ».
 * Le backend renseigne désormais, dans `visual_placeholders` :
 *   - un bloc "lacunes"          : ce qui a manqué au modèle, et comment y remédier ;
 *   - un bloc "rapport_visuels"  : les schémas créés, conservés en l'état, ou écartés.
 * On affiche les deux sous la section, sans jamais les inventer : rien à dire,
 * rien d'affiché.
 */

type Lacune = { missing?: string; impact?: string; how_to_fix?: string; lien?: string; lien_libelle?: string };

type BlocLacunes = { type: 'lacunes'; items?: Lacune[] };
type BlocConso = {
  type: 'consommation';
  modele?: string;
  repli_utilise?: boolean;
  usage?: { prompt_tokens?: number; completion_tokens?: number; total_tokens?: number };
  contexte?: Record<string, number>;
};
type BlocVisuels = {
  type: 'rapport_visuels';
  created?: string[];
  skipped?: string[];
  rejected?: string[];
};
type Bloc = BlocLacunes | BlocVisuels | BlocConso | { type?: string };

export function SectionDiagnostics({ placeholders }: { placeholders: unknown }) {
  const { t } = useTranslation();
  const [detailOuvert, setDetailOuvert] = React.useState(false);
  if (!Array.isArray(placeholders) || placeholders.length === 0) return null;

  const blocs = placeholders.filter(
    (b): b is Bloc => typeof b === 'object' && b !== null,
  );
  const lacunes = (blocs.find((b) => b.type === 'lacunes') as BlocLacunes | undefined)?.items ?? [];
  const visuels = blocs.find((b) => b.type === 'rapport_visuels') as BlocVisuels | undefined;
  const conso = blocs.find((b) => b.type === 'consommation') as BlocConso | undefined;

  const cree = visuels?.created ?? [];
  const conserve = visuels?.skipped ?? [];
  const ecarte = visuels?.rejected ?? [];
  const tokensEntree = conso?.usage?.prompt_tokens;
  const tokensSortie = conso?.usage?.completion_tokens;
  const aConso = Boolean(conso && (tokensEntree || tokensSortie));
  const aQuelqueChose =
    lacunes.length > 0 || cree.length > 0 || conserve.length > 0 || ecarte.length > 0 || aConso;
  if (!aQuelqueChose) return null;

  // Ce que pèse réellement chaque bloc de contexte, en caractères. Sert à
  // comprendre ce qui gonfle la facture plutôt qu'à le subir.
  const contexte = conso?.contexte || {};
  const LIBELLES: Record<string, string> = {
    dce_chars: 'pièces du marché',
    anciens_memoires_chars: 'anciens mémoires',
    savoir_faire_chars: 'savoir-faire',
    apprentissages_chars: 'enseignements',
    web_chars: 'sources officielles',
    sites_client_chars: 'sites de référence',
    consignes_chars: 'consignes de rédaction',
  };
  const blocsContexte = Object.entries(LIBELLES)
    .map(([cle, libelle]) => [libelle, contexte[cle] || 0] as const)
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);

  return (
    <div className="space-y-3">
      {lacunes.length > 0 && (
        <div className="card-modern p-4 space-y-3">
          <div className="flex items-center gap-2">
            <FileWarning className="w-4 h-4 text-hl shrink-0" />
            <h3 className="text-[13px] font-bold text-foreground font-heading">
              {t('diag.lacunes_titre')}
            </h3>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">{t('diag.lacunes_desc')}</p>
          {/* Le plan d'action en tête de dossier dit QUOI faire et OÙ. Ce bloc-ci
              garde le détail brut du moteur pour cette section précise : utile,
              mais replié par défaut pour ne pas répéter neuf fois la même chose. */}
          <button
            type="button"
            onClick={() => setDetailOuvert((v) => !v)}
            aria-expanded={detailOuvert}
            className="inline-flex items-center gap-1 text-[11px] font-semibold text-hl hover:underline"
          >
            {detailOuvert ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            {detailOuvert ? t('diag.masquer_detail') : `${t('diag.voir_detail')} (${lacunes.length})`}
          </button>
          <ul className={`space-y-2.5 ${detailOuvert ? '' : 'hidden'}`}>
            {lacunes.map((l, i) => (
              <li key={i} className="border-l-2 border-hl/40 pl-3 py-0.5">
                <p className="text-[12px] font-semibold text-foreground"><TexteAvecAcronymes texte={l.missing || '—'} /></p>
                {l.impact && (
                  <p className="text-[11px] text-muted-foreground mt-0.5">
                    {t('diag.consequence')} <TexteAvecAcronymes texte={l.impact} />
                  </p>
                )}
                {l.how_to_fix && (
                  <p className="text-[11px] text-hl mt-0.5">{t('diag.a_faire')} <TexteAvecAcronymes texte={l.how_to_fix} /></p>
                )}
                {/* Dire quoi faire sans dire OÙ le faire laisse l'utilisateur
                    chercher l'écran. Le bouton l'y emmène directement. */}
                {l.lien && (
                  <Link
                    href={l.lien}
                    className="inline-flex items-center gap-1 mt-1.5 text-[11px] font-semibold text-hl hover:underline"
                  >
                    <span>{l.lien_libelle || t('diag.a_faire')}</span>
                    <ArrowRight className="w-3 h-3" />
                  </Link>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {aConso && (
        <div className="card-modern p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-muted-foreground shrink-0" />
            <h3 className="text-[13px] font-bold text-foreground font-heading">Ce que cette section a consommé</h3>
          </div>
          <p className="text-[11px] text-muted-foreground">
            <span className="font-mono text-foreground">{(tokensEntree ?? 0).toLocaleString('fr-FR')}</span> tokens envoyés,{' '}
            <span className="font-mono text-foreground">{(tokensSortie ?? 0).toLocaleString('fr-FR')}</span> tokens produits
            {conso?.modele && <> · modèle <span className="font-mono">{conso.modele}</span></>}
            {conso?.repli_utilise && <> · <span className="text-hl">via un fournisseur de repli</span></>}
          </p>
          {blocsContexte.length > 0 && (
            <p className="text-[10px] text-muted-foreground leading-relaxed">
              Contexte envoyé :{' '}
              {blocsContexte
                .map(([libelle, n]) => `${libelle} ${Math.round(n / 1000)} k`)
                .join(' · ')}{' '}
              caractères.
            </p>
          )}
        </div>
      )}

      {(cree.length > 0 || conserve.length > 0 || ecarte.length > 0) && (
        <div className="card-modern p-4 space-y-2.5">
          <div className="flex items-center gap-2">
            <ImageIcon className="w-4 h-4 text-hl shrink-0" />
            <h3 className="text-[13px] font-bold text-foreground font-heading">{t('diag.schemas')}</h3>
          </div>
          {cree.map((c, i) => (
            <p key={`c${i}`} className="text-[11px] text-positive flex items-start gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-px" />
              <span>{c} {t('diag.modifiable_visuels')}</span>
            </p>
          ))}
          {conserve.map((s, i) => (
            <p key={`s${i}`} className="text-[11px] text-muted-foreground flex items-start gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-px" />
              <span>{s}</span>
            </p>
          ))}
          {ecarte.map((r, i) => (
            <p key={`r${i}`} className="text-[11px] text-danger flex items-start gap-1.5">
              <ShieldAlert className="w-3.5 h-3.5 shrink-0 mt-px" />
              <span>{r}</span>
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
