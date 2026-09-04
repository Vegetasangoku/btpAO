'use client';

/**
 * Page d'accueil.
 *
 * Direction : le tirage de plan. Fond encre de Prusse — jamais de noir pur —
 * sur lequel la photographie de chantier est la seule source de lumière.
 *
 * Aucune couleur n'est écrite ici. La page est posée dans le contexte `.on-ink`
 * (voir globals.css) : elle utilise les mêmes noms de rôle que le reste de
 * l'application — `bg-hl` pour l'action principale, `text-corten` pour l'accent
 * éditorial, `border-line` pour les filets — et c'est le contexte qui décide de
 * la valeur. Le bouton « Créer un compte » et l'onglet actif de l'admin sont
 * ainsi littéralement la même couleur.
 *
 * Rythme : deux blocs sombres encadrent une bande claire, et l'inversion tombe
 * sur la promesse de confidentialité, là où le propos demande de la clarté.
 *
 * Vocabulaire : pièces du marché, exigences, mémoire technique. Rien qui vienne
 * de l'implémentation.
 */

import React, { useState } from 'react';
import Link from 'next/link';
import Image from 'next/image';
import { useTranslation, Language } from '@/components/i18n-provider';

/** Bande de jalons — l'élément signature.
 *
 *  Répondre à un appel d'offres est une course contre une date de remise. La
 *  frise le dit en une ligne et situe l'outil dans cette course : repère plein
 *  sur les trois jalons pris en charge, repère effacé sur les deux extrêmes qui
 *  restent le fait de l'acheteur. Dessinée comme une réglette — un filet, des
 *  repères qui descendent, les libellés dessous.
 */
function MilestoneStrip({ labels, coveredFrom, coveredTo }: { labels: string[]; coveredFrom: number; coveredTo: number }) {
  return (
    <div className="w-full">
      <div className="h-px w-full bg-line" />
      <div className="grid" style={{ gridTemplateColumns: `repeat(${labels.length}, minmax(0, 1fr))` }}>
        {labels.map((label, i) => {
          const covered = i >= coveredFrom && i <= coveredTo;
          return (
            <div key={label} className="flex flex-col">
              {/* Hauteur de repère constante : seule la longueur du trait varie,
                  pour que tous les libellés partagent la même ligne de base. */}
              <span className="block w-px h-3">
                <span
                  className={`block w-px ${covered ? 'h-3 bg-corten' : 'h-1.5 bg-line'}`}
                />
              </span>
              <span
                className={`block font-mono text-[9px] uppercase leading-[1.5] tracking-[0.08em] pe-2 pt-1.5 min-h-[34px] ${
                  covered ? 'text-foreground' : 'text-muted-foreground'
                }`}
              >
                {label}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function LandingPage() {
  const { t, language, setLanguage, isRtl } = useTranslation();
  const [openQuestion, setOpenQuestion] = useState<number | null>(0);

  const stages = [
    { key: 'pieces', label: t('home.stage.pieces_label') },
    { key: 'exigences', label: t('home.stage.requirements_label') },
    { key: 'decision', label: t('home.stage.decision_label') },
    { key: 'memoire', label: t('home.stage.memo_label') },
  ];

  const milestones = [
    t('home.milestone.published'),
    t('home.milestone.analysis'),
    t('home.milestone.decision'),
    t('home.milestone.drafting'),
    t('home.milestone.submitted'),
  ];

  const questions = [0, 1, 2, 3, 4].map((i) => ({
    q: t(`home.faq.q${i + 1}`),
    a: t(`home.faq.a${i + 1}`),
  }));

  return (
    <div dir={isRtl ? 'rtl' : 'ltr'} className="on-ink min-h-screen">
      {/* ── En-tête ──────────────────────────────────────────────────────── */}
      <header className="sticky top-0 z-40 bg-background border-b border-line">
        <div className="mx-auto max-w-[1240px] px-6 lg:px-10 h-14 flex items-center justify-between gap-6">
          <Link href="/" className="font-heading font-black text-[17px] tracking-tight text-foreground">
            btp<span className="text-corten">AO</span>
          </Link>

          <nav className="hidden md:flex items-center gap-7 text-[12.5px] text-muted-foreground">
            {[
              ['#plateforme', t('home.nav.platform')],
              ['#garanties', t('home.nav.guarantees')],
              ['#tarifs', t('home.nav.pricing')],
              ['#questions', t('home.nav.questions')],
            ].map(([href, label]) => (
              <a key={href} href={href} className="transition-colors duration-150 hover:text-foreground">
                {label}
              </a>
            ))}
          </nav>

          <div className="flex items-center gap-3">
            <div className="hidden sm:flex items-center gap-px font-mono text-[10px]">
              {(['fr', 'en', 'ar'] as Language[]).map((l) => (
                <button
                  key={l}
                  onClick={() => setLanguage(l)}
                  aria-pressed={language === l}
                  className={`px-1.5 py-1 rounded-[3px] uppercase font-semibold transition-colors duration-150 ${
                    language === l
                      ? 'bg-foreground text-background'
                      : 'text-muted-foreground hover:text-foreground'
                  }`}
                >
                  {l === 'ar' ? 'ع' : l}
                </button>
              ))}
            </div>
            <Link
              href="/login"
              className="text-[12.5px] font-medium text-foreground transition-opacity duration-150 hover:opacity-70"
            >
              {t('home.cta.sign_in')}
            </Link>
            <Link
              href="/register"
              className="px-3.5 py-1.5 rounded-[4px] text-[12.5px] font-semibold bg-hl text-hl-contrast transition-colors duration-150 hover:bg-hl-strong"
            >
              {t('home.cta.create_account')}
            </Link>
          </div>
        </div>
      </header>

      {/* ── Ouverture ────────────────────────────────────────────────────── */}
      <section className="relative grid lg:grid-cols-[minmax(0,54%)_minmax(0,46%)]">
        {/* Trame de papier millimétré, à peine perceptible, sous la colonne de texte */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 lg:end-[46%] opacity-60"
          style={{
            backgroundImage:
              'linear-gradient(rgb(var(--line-rgb) / 0.55) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--line-rgb) / 0.55) 1px, transparent 1px)',
            backgroundSize: '34px 34px',
            maskImage: 'radial-gradient(120% 80% at 20% 40%, #000 25%, transparent 78%)',
            WebkitMaskImage: 'radial-gradient(120% 80% at 20% 40%, #000 25%, transparent 78%)',
          }}
        />

        <div className="relative px-6 lg:px-10 xl:ps-[max(2.5rem,calc((100vw-1240px)/2+2.5rem))] py-14 lg:py-24 flex flex-col justify-center">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-corten">
            {t('home.brand.sector')}
          </p>

          <h1
            className="mt-6 font-heading font-bold text-foreground"
            style={{ fontSize: 'clamp(38px, 5.2vw, 64px)', lineHeight: 1.02, letterSpacing: '-0.032em' }}
          >
            {t('home.hero.title_line1')}
            <br />
            <span className="text-muted-foreground">{t('home.hero.title_line2')}</span>
          </h1>

          <p className="mt-6 max-w-[46ch] text-[15px] leading-[1.7] text-muted-foreground">
            {t('home.hero.body')}
          </p>

          <div className="mt-8 flex flex-wrap items-center gap-5">
            <Link
              href="/register"
              className="px-5 py-2.5 rounded-[4px] text-[13.5px] font-semibold bg-hl text-hl-contrast transition-colors duration-150 hover:bg-hl-strong"
            >
              {t('home.cta.create_account')}
            </Link>
            <Link
              href="/login"
              className="text-[13.5px] font-medium text-foreground underline underline-offset-4 decoration-1 transition-opacity duration-150 hover:opacity-70"
            >
              {t('home.cta.sign_in')}
            </Link>
          </div>

          {/* Élément signature */}
          <div className="mt-14 max-w-xl">
            <MilestoneStrip labels={milestones} coveredFrom={1} coveredTo={3} />
            <p className="mt-4 text-[11.5px] text-muted-foreground">{t('home.milestone.legend')}</p>
          </div>
        </div>

        <div className="relative min-h-[380px] lg:min-h-[calc(100vh-3.5rem)] border-s border-line">
          <Image
            src="/images/login-hero.jpg"
            alt={t('home.photo.alt')}
            fill
            priority
            sizes="(max-width: 1024px) 100vw, 46vw"
            className="object-cover"
          />
          <div
            className="absolute inset-x-0 bottom-0 h-44"
            style={{ background: 'linear-gradient(to top, hsl(var(--background) / 0.94), transparent)' }}
          />
          <p className="absolute bottom-5 start-6 end-6 font-mono text-[9.5px] uppercase tracking-[0.18em] text-foreground/80">
            {t('home.photo.caption_kicker')}
          </p>
        </div>
      </section>

      {/* ── La plateforme ────────────────────────────────────────────────── */}
      <section id="plateforme" className="mx-auto max-w-[1240px] px-6 lg:px-10 py-20 lg:py-28">
        <div className="max-w-2xl">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-corten">
            {t('home.nav.platform')}
          </p>
          <h2
            className="mt-4 font-heading font-bold text-foreground"
            style={{ fontSize: 'clamp(26px, 3vw, 38px)', lineHeight: 1.1, letterSpacing: '-0.025em' }}
          >
            {t('home.platform.heading')}
          </h2>
        </div>

        <div className="mt-12 border-t border-line">
          {stages.map((stage) => (
            <div
              key={stage.key}
              className="grid md:grid-cols-[140px_minmax(0,1fr)_minmax(0,1.1fr)] gap-x-8 gap-y-2 py-7 border-b border-line"
            >
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] pt-1 text-corten">
                {stage.label}
              </span>
              <h3 className="font-heading text-[19px] font-semibold tracking-tight text-foreground">
                {t(`home.platform.${stage.key}_title`)}
              </h3>
              <p className="text-[13.5px] leading-[1.75] text-muted-foreground">
                {t(`home.platform.${stage.key}_body`)}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Ce qui reste à vous — l'unique bande claire de la page ───────── */}
      <section id="garanties" className="on-paper">
        <div className="mx-auto max-w-[1240px] px-6 lg:px-10 py-20 lg:py-24">
          <h2
            className="font-heading font-bold max-w-2xl text-foreground"
            style={{ fontSize: 'clamp(24px, 2.6vw, 34px)', lineHeight: 1.12, letterSpacing: '-0.022em' }}
          >
            {t('home.guarantees.heading')}
          </h2>
          <div className="mt-12 grid md:grid-cols-3 gap-px bg-line">
            {['references', 'templates', 'data'].map((k) => (
              <div key={k} className="p-7 bg-background">
                <h3 className="font-heading text-[16px] font-semibold text-foreground">
                  {t(`home.guarantees.${k}_title`)}
                </h3>
                <p className="mt-2.5 text-[13.5px] leading-[1.75] text-muted-foreground">
                  {t(`home.guarantees.${k}_body`)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Tarifs ───────────────────────────────────────────────────────── */}
      <section id="tarifs" className="mx-auto max-w-[1240px] px-6 lg:px-10 py-20 lg:py-28">
        <div className="max-w-2xl">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-corten">
            {t('home.nav.pricing')}
          </p>
          <h2
            className="mt-4 font-heading font-bold text-foreground"
            style={{ fontSize: 'clamp(26px, 3vw, 38px)', lineHeight: 1.1, letterSpacing: '-0.025em' }}
          >
            {t('home.pricing.heading')}
          </h2>
        </div>

        <div className="mt-12 overflow-x-auto">
          <table className="w-full min-w-[680px] border-collapse text-[13.5px]">
            <thead>
              <tr className="border-b border-muted-foreground/60">
                <th className="text-start pb-4 pe-6 font-mono text-[10px] uppercase tracking-[0.16em] font-medium text-muted-foreground">
                  {t('home.pricing.col_label')}
                </th>
                {(['starter', 'pro', 'enterprise'] as const).map((p) => (
                  <th key={p} className="text-start pb-4 pe-6 align-bottom">
                    <span className="block font-heading text-[17px] font-semibold tracking-tight text-foreground">
                      {t(`home.plan.${p}_name`)}
                    </span>
                    <span className="block text-[12px] mt-0.5 text-muted-foreground">
                      {t(`home.plan.${p}_note`)}
                    </span>
                    {p === 'pro' && (
                      <span className="inline-block mt-2 font-mono text-[9.5px] uppercase tracking-[0.16em] text-corten">
                        {t('home.pricing.recommended')}
                      </span>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                { k: 'price', values: ['199 €', '499 €', t('home.plan.on_quote')], mono: true },
                { k: 'dossiers', values: ['3', '10', t('home.pricing.custom_volume')], mono: true },
                { k: 'extra', values: ['99 €', '79 €', t('home.pricing.negotiated')], mono: true },
                {
                  k: 'library',
                  values: [
                    t('home.pricing.library_starter'),
                    t('home.pricing.library_pro'),
                    t('home.pricing.library_enterprise'),
                  ],
                },
                {
                  k: 'support',
                  values: [
                    t('home.pricing.support_starter'),
                    t('home.pricing.support_pro'),
                    t('home.pricing.support_enterprise'),
                  ],
                },
              ].map((row) => (
                <tr key={row.k} className="border-b border-line">
                  <th className="text-start py-3.5 pe-6 font-normal align-top text-muted-foreground">
                    {t(`home.pricing.row_${row.k}`)}
                  </th>
                  {row.values.map((v, i) => (
                    <td
                      key={i}
                      className={`py-3.5 pe-6 align-top text-foreground ${row.mono ? 'font-mono tabular-nums' : ''}`}
                    >
                      {v}
                    </td>
                  ))}
                </tr>
              ))}
              <tr>
                <td />
                {(['starter', 'pro', 'enterprise'] as const).map((p) => (
                  <td key={p} className="pt-5 pe-6">
                    <Link
                      href={`/register?plan=${p}`}
                      className={`inline-block px-4 py-2 rounded-[4px] text-[12.5px] font-semibold transition-colors duration-150 ${
                        p === 'pro'
                          ? 'bg-hl text-hl-contrast hover:bg-hl-strong'
                          : 'border border-line text-foreground hover:border-hl'
                      }`}
                    >
                      {t('home.pricing.choose')}
                    </Link>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
        <p className="mt-5 text-[12px] text-muted-foreground">{t('home.pricing.footnote')}</p>
      </section>

      {/* ── Questions ────────────────────────────────────────────────────── */}
      <section id="questions" className="mx-auto max-w-[1240px] px-6 lg:px-10 pb-24">
        <h2
          className="font-heading font-bold text-foreground"
          style={{ fontSize: 'clamp(24px, 2.6vw, 32px)', letterSpacing: '-0.022em' }}
        >
          {t('home.faq.heading')}
        </h2>
        <div className="mt-10 max-w-3xl border-t border-line">
          {questions.map((item, i) => (
            <div key={i} className="border-b border-line">
              <button
                type="button"
                onClick={() => setOpenQuestion(openQuestion === i ? null : i)}
                aria-expanded={openQuestion === i}
                className="w-full flex items-baseline justify-between gap-6 py-5 text-start transition-opacity duration-150 hover:opacity-80"
              >
                <span className="text-[15px] font-medium text-foreground">{item.q}</span>
                <span className="font-mono text-[13px] shrink-0 text-corten">
                  {openQuestion === i ? '−' : '+'}
                </span>
              </button>
              {openQuestion === i && (
                <p className="pb-6 pe-10 text-[13.5px] leading-[1.8] max-w-[62ch] text-muted-foreground">
                  {item.a}
                </p>
              )}
            </div>
          ))}
        </div>
      </section>

      {/* ── Pied de page ─────────────────────────────────────────────────── */}
      <footer className="bg-card border-t border-line">
        <div className="mx-auto max-w-[1240px] px-6 lg:px-10 py-10 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-5">
          <div>
            <p className="font-heading font-black text-[15px] tracking-tight text-foreground">
              btp<span className="text-corten">AO</span>
            </p>
            <p className="mt-1 text-[12px] text-muted-foreground">{t('home.footer.line')}</p>
          </div>
          <div className="flex items-center gap-6 text-[12px] text-muted-foreground">
            <Link href="/login" className="transition-colors duration-150 hover:text-foreground">
              {t('home.cta.sign_in')}
            </Link>
            <Link href="/register" className="transition-colors duration-150 hover:text-foreground">
              {t('home.cta.create_account')}
            </Link>
            <a href="#tarifs" className="transition-colors duration-150 hover:text-foreground">
              {t('home.nav.pricing')}
            </a>
          </div>
        </div>
      </footer>
    </div>
  );
}
