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
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { useTheme } from '@/components/theme-provider';
import { useTranslation, Language } from '@/components/i18n-provider';

export function UserSidebar() {
  const pathname = usePathname();
  const { theme, setTheme } = useTheme();
  const { language, setLanguage, t } = useTranslation();
  const [companyName, setCompanyName] = useState('BTP Entreprise & Travaux Publics');
  const [userEmail, setUserEmail] = useState('');

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        setUserEmail(data.user.email || '');
        const meta = data.user.user_metadata || {};
        const appMeta = data.user.app_metadata || {};
        setCompanyName(appMeta.company_name || meta.company_name || 'BTP Entreprise & Travaux Publics');
      }
    });
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
    <aside className="w-72 bg-white dark:bg-[#0C0F17] border-r border-slate-200 dark:border-[#1E2638] flex flex-col h-screen sticky top-0 z-30 transition-colors duration-200">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-200 dark:border-[#1E2638]">
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-tr from-amber-600 to-amber-500 text-white flex items-center justify-center shadow-subtle group-hover:scale-105 transition-transform shrink-0">
            <HardHat className="w-5 h-5 text-white" />
          </div>
          <div className="min-w-0">
            <div className="font-heading font-extrabold text-base text-slate-900 dark:text-white tracking-tight flex items-center gap-1.5">
              btp<span className="text-amber-500">AO</span>
              <span className="text-[10px] uppercase font-mono font-bold px-1.5 py-0.2 rounded bg-amber-500/15 text-amber-500 dark:text-amber-400 border border-amber-500/30">
                {t('app.badge')}
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 truncate">
              {t('app.tagline')}
            </p>
          </div>
        </Link>
      </div>

      {/* Tenant Context Pill */}
      <div className="px-3.5 py-2.5 mx-3.5 mt-3.5 rounded-lg bg-slate-100 dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638]">
        <div className="flex items-center gap-2.5">
          <div className="w-2 h-2 rounded-full bg-emerald-500 shrink-0" />
          <div className="truncate">
            <p className="text-xs font-bold text-slate-800 dark:text-slate-200 truncate font-heading">
              {companyName}
            </p>
            <p className="text-[10px] text-slate-500 dark:text-slate-400 font-mono truncate">
              {userEmail || 'conducteur@btp-france.fr'}
            </p>
          </div>
        </div>
      </div>

      {/* Main Navigation (6 entries with clean, unified design) */}
      <div className="flex-1 overflow-y-auto p-3 space-y-1.5 mt-2">
        <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 mb-1.5 font-heading">
          {t('nav.main_menu')}
        </p>

        <nav className="space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = item.exact
              ? pathname === item.href
              : pathname === item.href || pathname.startsWith(`${item.href}/`);

            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all ${
                  isActive
                    ? 'bg-slate-200 dark:bg-[#1E2638] text-slate-900 dark:text-white font-bold border-l-2 border-amber-500 pl-2.5 shadow-subtle'
                    : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-[#131823]'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <Icon className={`w-4 h-4 shrink-0 ${isActive ? 'text-amber-500 dark:text-amber-400' : 'text-slate-400 dark:text-slate-500'}`} />
                  <span className="truncate">{item.name}</span>
                </div>
                {isActive && <ChevronRight className="w-3.5 h-3.5 text-amber-500 dark:text-amber-400 shrink-0" />}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer: Language + Theme + Logout */}
      <div className="p-3 border-t border-slate-200 dark:border-[#1E2638] bg-white dark:bg-[#0C0F17] space-y-2">
        {/* Quick Language Switcher (FR / EN / AR) */}
        <div className="flex items-center justify-between px-2 py-1 rounded-lg bg-slate-100 dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] text-[11px]">
          <div className="flex items-center gap-1 text-slate-500 dark:text-slate-400 text-[10px] font-semibold pl-1">
            <Globe className="w-3 h-3 text-amber-500" />
            <span>{t('app.language')}</span>
          </div>
          <div className="flex gap-1">
            {(['fr', 'en', 'ar'] as Language[]).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLanguage(l)}
                title={l.toUpperCase()}
                className={`px-1.5 py-0.5 rounded text-[10px] font-bold font-mono transition-colors ${
                  language === l
                    ? 'bg-amber-600 text-white shadow-subtle'
                    : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
                }`}
              >
                {l.toUpperCase()}
              </button>
            ))}
          </div>
        </div>

        {/* Quick Theme Switcher */}
        <div className="flex items-center justify-between px-2 py-1 rounded-lg bg-slate-100 dark:bg-[#131823] border border-slate-200 dark:border-[#1E2638] text-[11px]">
          <span className="text-slate-500 dark:text-slate-400 text-[10px] font-semibold pl-1">{t('app.theme')}</span>
          <div className="flex gap-1">
            <button
              type="button"
              onClick={() => setTheme('light')}
              title="Mode Clair (Journée)"
              className={`p-1 rounded transition-colors ${
                theme === 'light'
                  ? 'bg-amber-500 text-white'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
              }`}
            >
              <Sun className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setTheme('dark')}
              title="Mode Sombre (Nuit)"
              className={`p-1 rounded transition-colors ${
                theme === 'dark'
                  ? 'bg-amber-500 text-white'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
              }`}
            >
              <Moon className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setTheme('schedule')}
              title="Horaires Chantier (07h30-20h30 Clair / Nuit Sombre)"
              className={`p-1 rounded transition-colors ${
                theme === 'schedule'
                  ? 'bg-amber-500 text-white'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
              }`}
            >
              <Clock className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setTheme('system')}
              title="Thème Système (OS)"
              className={`p-1 rounded transition-colors ${
                theme === 'system'
                  ? 'bg-amber-500 text-white'
                  : 'text-slate-400 hover:text-slate-600 dark:hover:text-slate-200'
              }`}
            >
              <Laptop className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Logout */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-lg text-xs font-semibold text-slate-500 dark:text-slate-400 hover:text-rose-500 hover:bg-rose-50 dark:hover:bg-rose-950/20 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>{t('app.logout')}</span>
        </button>
      </div>
    </aside>
  );
}
