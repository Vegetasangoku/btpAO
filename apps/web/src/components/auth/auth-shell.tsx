'use client';

/**
 * Coquille des écrans d'authentification.
 *
 * Une photographie de chantier tient toute la moitié gauche, à fond perdu,
 * séparée du formulaire par un filet net d'un pixel — aucune ombre portée,
 * aucun fondu. C'est l'image qui porte l'envie ; le formulaire ne fait qu'une
 * chose et se tait.
 *
 * Ces écrans restent sur papier quel que soit le thème choisi par la personne :
 * ils sont donc posés dans le contexte `.on-paper`, qui fixe les valeurs claires
 * de la charte. Le vocabulaire est le même que partout ailleurs — `bg-hl`,
 * `text-corten`, `border-line` — et aucune couleur n'est écrite ici.
 */

import React from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { useTranslation, Language } from '@/components/i18n-provider';

export function AuthShell({
  eyebrow,
  title,
  intro,
  children,
  footer,
}: {
  eyebrow: string;
  title: string;
  intro: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}) {
  const { language, setLanguage, isRtl, t } = useTranslation();

  return (
    <div
      dir={isRtl ? 'rtl' : 'ltr'}
      className="on-paper min-h-screen grid lg:grid-cols-[minmax(0,44%)_minmax(0,56%)]"
    >
      {/* ── Panneau photographique ─────────────────────────────────────── */}
      <aside className="relative hidden lg:block border-e border-line">
        <Image
          src="/images/login-hero.jpg"
          alt="Construction d’un viaduc : poutres métalliques en cours de pose, grues et équipes au travail."
          fill
          priority
          sizes="44vw"
          className="object-cover"
        />
        {/* Assombrissement local, seulement sous le texte */}
        <div
          className="absolute inset-x-0 bottom-0 h-1/2"
          style={{ background: 'linear-gradient(to top, rgba(10,19,25,0.88), transparent)' }}
        />
        <div className="absolute inset-x-0 bottom-0 p-10">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-white/70">
            {t('home.photo.caption_kicker')}
          </p>
          <p className="mt-3 text-[22px] leading-[1.25] text-white font-heading font-semibold max-w-sm">
            {t('home.photo.caption')}
          </p>
        </div>
        <Link href="/" className="absolute top-8 start-10 font-heading font-black text-[18px] tracking-tight text-white">
          btp<span className="text-corten">AO</span>
        </Link>
      </aside>

      {/* ── Formulaire ─────────────────────────────────────────────────── */}
      <main className="flex flex-col min-h-screen">
        <div className="flex items-center justify-between px-6 sm:px-10 py-5">
          <Link href="/" className="lg:hidden font-heading font-black text-[17px] tracking-tight text-foreground">
            btp<span className="text-corten">AO</span>
          </Link>
          <div className="ms-auto flex items-center gap-0.5 font-mono text-[10px]">
            {(['fr', 'en', 'ar'] as Language[]).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLanguage(l)}
                aria-pressed={language === l}
                className={`px-2 py-1 rounded-[3px] uppercase font-semibold transition-colors duration-150 ${
                  language === l
                    ? 'bg-foreground text-background'
                    : 'text-muted-foreground hover:text-foreground'
                }`}
              >
                {l === 'ar' ? 'ع' : l}
              </button>
            ))}
          </div>
        </div>

        <div className="flex-1 flex items-center justify-center px-6 sm:px-10 pb-10">
          <div className="w-full max-w-[420px]">
            <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-corten">{eyebrow}</p>
            <h1 className="mt-3 font-heading text-[30px] leading-[1.1] font-bold tracking-tight text-foreground">
              {title}
            </h1>
            <p className="mt-2.5 text-[13.5px] leading-relaxed text-muted-foreground">{intro}</p>
            <div className="mt-7">{children}</div>
            {footer && <div className="mt-6 pt-5 border-t border-line">{footer}</div>}
          </div>
        </div>
      </main>
    </div>
  );
}

/** Champ de saisie : un filet sous le texte, pas une boîte. */
export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-[11.5px] font-medium text-muted-foreground">{label}</span>
        {hint}
      </div>
      <div className="mt-1">{children}</div>
    </label>
  );
}

export const inputClass =
  'w-full bg-transparent border-b border-line focus:border-hl px-0 py-2 text-[14px] text-foreground placeholder:text-muted-foreground/60 outline-none transition-colors duration-150';

export const primaryButtonClass =
  'w-full inline-flex items-center justify-center gap-2 px-4 py-2.5 rounded-[4px] bg-hl text-hl-contrast text-[13.5px] font-semibold hover:bg-hl-strong disabled:opacity-50 transition-colors duration-150';
