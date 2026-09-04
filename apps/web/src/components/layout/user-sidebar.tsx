'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  HardHat,
  LayoutDashboard,
  Sparkles,
  FolderKanban,
  Building2,
  Palette,
  Settings,
  LogOut,
  ChevronRight,
  Sun,
  Moon,
  Laptop,
  Globe,
  Clock,
  ShieldCheck,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { useTheme } from '@/components/theme-provider';
import { useTranslation, Language } from '@/components/i18n-provider';

export function UserSidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const [companyName, setCompanyName] = useState('');
  const [userEmail, setUserEmail] = useState('');
  const [isPlatformAdmin, setIsPlatformAdmin] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        const email = (data.user.email || '').toLowerCase();
        setUserEmail(email);
        if (email === 'charbelakl@gmail.com') {
          setIsPlatformAdmin(true);
        }
      }
    });

    api.getProfile()
      .then((profile) => {
        if (profile.role === 'platform_admin' || profile.role === 'super_admin') {
          setIsPlatformAdmin(true);
        }
      })
      .catch(() => {});

    api.getTenant()
      .then((tenant) => setCompanyName(tenant.name))
      .catch(() => setCompanyName(''));
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.href = '/login';
  }

  const navItems = [
    {
      key: 'nav.dashboard',
      name: t('nav.dashboard'),
      href: '/dashboard',
      icon: LayoutDashboard,
      exact: true,
    },
    {
      key: 'nav.wizard',
      name: t('nav.wizard'),
      href: '/dashboard/wizard',
      icon: Sparkles,
      exact: false,
    },
    {
      key: 'nav.projects',
      name: t('nav.projects'),
      href: '/dashboard/projects',
      icon: FolderKanban,
      exact: false,
    },
    {
      key: 'nav.company',
      name: t('nav.company'),
      href: '/dashboard/company',
      icon: Building2,
      exact: false,
    },
    {
      key: 'nav.branding',
      name: t('nav.branding'),
      href: '/dashboard/branding',
      icon: Palette,
      exact: false,
    },
    {
      key: 'nav.settings',
      name: t('nav.settings'),
      href: '/dashboard/settings',
      icon: Settings,
      exact: false,
    },
  ];

  return (
    <aside className="w-[260px] bg-card border-r border-line flex flex-col h-screen sticky top-0 z-30 transition-colors duration-200 select-none">
      {/* ─── Brand Header ─── */}
      <div className="px-5 py-4 border-b border-line">
        <Link href="/dashboard" prefetch={false} className="flex items-center gap-3 group">
          <div className="w-9 h-9 rounded-xl bg-hl text-hl-contrast flex items-center justify-center shadow-xs group-hover:bg-hl-strong transition-all duration-200 shrink-0">
            <HardHat className="w-5 h-5" />
          </div>
          <div className="min-w-0">
            <div className="font-heading font-extrabold text-[15px] text-foreground tracking-tight flex items-center gap-2">
              <span>btp</span><span className="text-hl">AO</span>
              <span className="text-[9px] font-bold px-1.5 py-0.2 rounded bg-hl/10 text-hl border border-hl/20">
                {t('app.badge')}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 dark:text-zinc-400 truncate mt-0.5">
              {t('app.tagline')}
            </p>
          </div>
        </Link>
      </div>

      {/* ─── Tenant Context ─── */}
      <div className="px-4 pt-4 pb-2">
        <div className="relative px-3 py-2.5 card-drafted">
          <div className="flex items-center gap-2.5">
            <span className="relative flex h-2 w-2 shrink-0">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-positive opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-positive"></span>
            </span>
            <div className="truncate min-w-0">
              <p className="font-mono text-[8px] font-bold uppercase tracking-[0.12em] text-muted-foreground leading-none mb-1">Espace actif</p>
              <p className="text-[13px] font-semibold text-slate-800 dark:text-zinc-200 truncate leading-none mb-0.5">
                {companyName || '—'}
              </p>
              <p className="text-[11px] text-slate-400 dark:text-zinc-400 truncate font-mono">
                {userEmail || 'conducteur@btp-france.fr'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* ─── Super Admin Access Banner ─── */}
      {isPlatformAdmin && (
        <div className="px-4 pb-2">
          <Link
            href="/admin"
            prefetch={false}
            className="flex items-center justify-between p-3 rounded-xl bg-hl/10 hover:bg-hl/15 border border-hl/25 hover:border-hl/50 shadow-xs transition-all duration-200 group"
          >
            <div className="flex items-center gap-2.5 min-w-0">
              <div className="w-8 h-8 rounded-lg bg-hl text-hl-contrast flex items-center justify-center font-bold shadow-xs shrink-0 group-hover:scale-105 transition-transform">
                <ShieldCheck className="w-4 h-4" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <p className="text-[12px] font-bold text-hl truncate leading-none">
                    Espace Super Admin
                  </p>
                  <span className="text-[8px] font-extrabold uppercase px-1 rounded bg-hl text-hl-contrast">PRO</span>
                </div>
                <p className="text-[10px] text-muted-foreground truncate mt-0.5">
                  Gestion LLM & Clients
                </p>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-hl group-hover:translate-x-0.5 transition-transform shrink-0" />
          </Link>
        </div>
      )}

      {/* ─── Main Navigation ─── */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-0.5">
        <p className="eyebrow-mono !text-slate-400 dark:!text-zinc-500 px-3 mb-2">
          {t('nav.main_menu')}
        </p>

        <nav className="space-y-0.5">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.exact
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.href}
                href={item.href}
                prefetch={false}
                className={isActive ? 'nav-link-active' : 'nav-link'}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`w-[18px] h-[18px] shrink-0 transition-colors duration-200 ${isActive ? 'text-white' : 'text-muted-foreground'}`} />
                  <span className="truncate">{item.name}</span>
                </div>
                {isActive && <ChevronRight className="w-3.5 h-3.5 text-white/80 shrink-0" />}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* ─── Footer: Language + Theme + Logout ─── */}
      <div className="p-3 border-t border-line space-y-2">
        {/* Language Switcher */}
        <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-sunken border border-line text-[11px]">
          <div className="flex items-center gap-1.5 text-muted-foreground font-medium">
            <Globe className="w-3.5 h-3.5 text-muted-foreground" />
            <span>{t('app.language')}</span>
          </div>
          <div className="tab-group !p-0.5 !gap-0.5">
            {(['fr', 'en', 'ar'] as Language[]).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLanguage(l)}
                title={l.toUpperCase()}
                className={`px-2 py-0.5 rounded text-[10px] font-bold transition-all duration-200 cursor-pointer ${
                  language === l
                    ? 'bg-hl text-hl-contrast shadow-xs'
                    : 'text-muted-foreground hover:text-slate-800 dark:hover:text-white'
                }`}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Theme Switcher */}
        <div className="flex items-center justify-between px-3 py-1.5 rounded-lg bg-sunken border border-line text-[11px]">
          <span className="text-muted-foreground font-medium">{t('app.theme')}</span>
          <div className="tab-group !p-0.5 !gap-0">
            {([
              { mode: 'light' as const, icon: Sun },
              { mode: 'dark' as const, icon: Moon },
              { mode: 'schedule' as const, icon: Clock },
              { mode: 'system' as const, icon: Laptop },
            ]).map(({ mode, icon: ModeIcon }) => (
              <button
                key={mode}
                type="button"
                onClick={() => setTheme(mode)}
                title={mode}
                className={`p-1.5 rounded transition-all duration-200 cursor-pointer ${
                  theme === mode
                    ? 'bg-hl text-hl-contrast shadow-xs'
                    : 'text-muted-foreground hover:text-slate-700 dark:hover:text-zinc-200'
                }`}
              >
                <ModeIcon className="w-3 h-3" />
              </button>
            ))}
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-[13px] font-medium text-muted-foreground hover:text-danger dark:hover:text-danger hover:bg-danger/8 transition-all duration-200 cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
          <span>{t('app.logout')}</span>
        </button>
      </div>
    </aside>
  );
}
