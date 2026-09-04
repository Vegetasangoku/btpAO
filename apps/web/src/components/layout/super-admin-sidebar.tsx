'use client';

/**
 * Barre latérale de la console plateforme.
 *
 * Traitée comme le cartouche d'un plan : en haut, qui regarde et sur quoi ; au
 * milieu, les feuilles disponibles ; en bas, les réglages de l'instrument. Le
 * repère de page active est un trait vertical de 2 px, pas un aplat coloré —
 * il situe sans repeindre le tiers de l'écran.
 */

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  Activity,
  Building2,
  CreditCard,
  Gauge,
  Globe,
  Laptop,
  LogOut,
  Moon,
  Server,
  Sun,
  Clock,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { useTheme } from '@/components/theme-provider';
import { useTranslation, Language } from '@/components/i18n-provider';

const ICON = 'w-[15px] h-[15px] shrink-0';

export function SuperAdminSidebar() {
  const pathname = usePathname();
  // L'adresse vient de la session, jamais d'une constante : c'est le seul
  // repère qui dit sous quelle identité les actions d'administration sont faites.
  const [userEmail, setUserEmail] = useState('');
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();

  useEffect(() => {
    supabase.auth
      .getUser()
      .then(({ data }) => setUserEmail(data?.user?.email || ''))
      .catch(() => setUserEmail(''));
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.href = '/login';
  }

  const nav = [
    { name: t('layout.admin_sidebar.nav_dashboard'), href: '/admin', icon: Activity },
    { name: t('layout.admin_sidebar.nav_tenants'), href: '/admin/tenants', icon: Building2 },
    { name: t('layout.admin_sidebar.nav_cost_limits'), href: '/admin/costs', icon: Gauge },
    { name: t('layout.admin_sidebar.nav_billing'), href: '/admin/billing', icon: CreditCard },
    { name: t('layout.admin_sidebar.nav_infra'), href: '/admin/infrastructure', icon: Server },
    { name: t('layout.admin_sidebar.nav_whitelist'), href: '/admin/whitelist', icon: Globe },
  ];

  const themes: { id: 'light' | 'dark' | 'schedule' | 'system'; icon: typeof Sun; title: string }[] = [
    { id: 'light', icon: Sun, title: 'Clair' },
    { id: 'dark', icon: Moon, title: 'Sombre' },
    { id: 'schedule', icon: Clock, title: 'Horaires de chantier' },
    { id: 'system', icon: Laptop, title: 'Système' },
  ];

  return (
    <aside className="w-[236px] shrink-0 bg-card border-e border-[hsl(var(--border))] flex flex-col h-screen sticky top-0 z-30 select-none">
      {/* ── Cartouche ─────────────────────────────────────────────────── */}
      <div className="px-4 pt-5 pb-4 border-b border-[hsl(var(--border))]">
        <Link href="/admin" className="font-heading font-black text-[17px] tracking-tight text-foreground">
          btp<span className="text-hl">AO</span>
        </Link>
        <p className="mt-1.5 font-mono text-[9.5px] uppercase tracking-[0.18em] text-[hsl(var(--muted-foreground))]">
          {t('layout.admin_sidebar.section_platform')}
        </p>
        <p
          className="mt-2 font-mono text-[10.5px] text-muted-foreground truncate"
          title={userEmail || undefined}
        >
          {userEmail || '—'}
        </p>
      </div>

      {/* ── Navigation ────────────────────────────────────────────────── */}
      <nav className="flex-1 overflow-y-auto px-2 py-3">
        <ul className="space-y-px">
          {nav.map((item) => {
            const isActive = pathname === item.href;
            const Icon = item.icon;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  prefetch={false}
                  aria-current={isActive ? 'page' : undefined}
                  className={isActive ? 'nav-link-active' : 'nav-link'}
                >
                  <span className="flex items-center gap-2.5 min-w-0">
                    <Icon
                      className={`${ICON} ${isActive ? 'text-hl' : 'text-[hsl(var(--muted-foreground))]'}`}
                      strokeWidth={1.5}
                    />
                    <span className="truncate">{item.name}</span>
                  </span>
                </Link>
              </li>
            );
          })}
        </ul>

        <div className="mt-6 pt-4 border-t border-[hsl(var(--border))]">
          <p className="px-3.5 font-mono text-[9.5px] uppercase tracking-[0.18em] text-[hsl(var(--muted-foreground))]">
            {t('layout.admin_sidebar.operational_space')}
          </p>
          <p className="px-3.5 mt-2 text-[11.5px] leading-relaxed text-muted-foreground">
            {t('layout.admin_sidebar.operational_desc')}
          </p>
          {/* La session ne change pas : on reste le même utilisateur, on regarde
              simplement son propre espace entreprise. Le dire évite de croire à
              une bascule de compte. */}
          {userEmail && (
            <p className="px-3.5 mt-1.5 text-[11px] leading-relaxed text-muted-foreground">
              {t('layout.admin_sidebar.same_session_notice', { email: userEmail })}
            </p>
          )}
          <Link
            href="/dashboard"
            prefetch={false}
            className="mt-3 mx-1.5 btn-secondary w-[calc(100%-0.75rem)] !text-[12.5px]"
          >
            {t('layout.admin_sidebar.open_btp_space')}
          </Link>
        </div>
      </nav>

      {/* ── Réglages de l'instrument ──────────────────────────────────── */}
      <div className="border-t border-[hsl(var(--border))] px-3 py-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
            {t('app.language')}
          </span>
          <div className="flex items-center gap-px">
            {(['fr', 'en', 'ar'] as Language[]).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLanguage(l)}
                title={l.toUpperCase()}
                aria-pressed={language === l}
                className={`px-1.5 py-1 rounded-[3px] font-mono text-[10px] font-semibold uppercase transition-colors duration-150 cursor-pointer ${
                  language === l
                    ? 'bg-hl text-hl-contrast'
                    : 'text-[hsl(var(--muted-foreground))] hover:text-foreground hover:bg-[hsl(var(--sunken))]'
                }`}
              >
                {l === 'ar' ? 'ع' : l}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="font-mono text-[9.5px] uppercase tracking-[0.16em] text-[hsl(var(--muted-foreground))]">
            {t('app.theme')}
          </span>
          <div className="flex items-center gap-px">
            {themes.map(({ id, icon: Icon, title }) => (
              <button
                key={id}
                type="button"
                onClick={() => setTheme(id)}
                title={title}
                aria-pressed={theme === id}
                className={`p-1.5 rounded-[3px] transition-colors duration-150 cursor-pointer ${
                  theme === id
                    ? 'bg-hl text-hl-contrast'
                    : 'text-[hsl(var(--muted-foreground))] hover:text-foreground hover:bg-[hsl(var(--sunken))]'
                }`}
              >
                <Icon className="w-3.5 h-3.5" strokeWidth={1.5} />
              </button>
            ))}
          </div>
        </div>

        <button
          onClick={handleLogout}
          className="w-full flex items-center gap-2 px-1 py-1.5 rounded-[4px] text-[12px] font-medium text-[hsl(var(--muted-foreground))] hover:text-danger dark:hover:text-danger transition-colors duration-150 cursor-pointer"
        >
          <LogOut className="w-3.5 h-3.5" strokeWidth={1.5} />
          <span>{t('layout.admin_sidebar.logout')}</span>
        </button>
      </div>
    </aside>
  );
}
