'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Bell,
  Search,
  ShieldCheck,
  Plus,
  LogOut,
  LogIn,
  User,
  Building,
  Sparkles,
  ChevronDown,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';
import { useTranslation } from '@/components/i18n-provider';

export function Header() {
  const router = useRouter();
  const { t } = useTranslation();
  const [user, setUser] = useState<any>(null);
  const [companyName, setCompanyName] = useState<string>(t('layout.header.default_company'));
  const [role, setRole] = useState<string>(t('layout.header.default_role_1'));
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        setUser(data.user);
        const meta = data.user.user_metadata || {};
        const appMeta = data.user.app_metadata || {};
        setCompanyName(meta.company_name || appMeta.company_name || t('layout.header.default_company'));
        setRole(meta.role || appMeta.role || t('layout.header.default_role_2'));
      }
    });

    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
      if (session?.user) {
        setUser(session.user);
        const meta = session.user.user_metadata || {};
        const appMeta = session.user.app_metadata || {};
        setCompanyName(meta.company_name || appMeta.company_name || t('layout.header.default_company'));
        setRole(meta.role || appMeta.role || t('layout.header.default_role_2'));
      } else {
        setUser(null);
      }
    });

    return () => {
      authListener.subscription.unsubscribe();
    };
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    setUser(null);
    router.push('/login');
    router.refresh();
  }

  const initials = user?.email
    ? user.email.substring(0, 2).toUpperCase()
    : 'BTP';

  const isSuperAdmin = (user?.email || '').toLowerCase() === 'charbelakl@gmail.com' || role === 'platform_admin' || role === 'super_admin';

  return (
    <header className="h-14 border-b border-slate-200/70 dark:border-zinc-800/50 bg-white/80 dark:bg-[hsl(225,20%,5%)]/80 backdrop-blur-xl px-5 flex items-center justify-between sticky top-0 z-20 transition-colors duration-200">
      {/* Search */}
      <div className="flex items-center gap-3 flex-1 max-w-lg">
        <div className="relative w-full group">
          <Search className="w-4 h-4 text-muted-foreground group-focus-within:text-hl absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200" />
          <input
            type="text"
            placeholder={t('layout.header.search_placeholder')}
            className="input-field-with-icon !py-2 !rounded-lg !bg-slate-100/60 dark:!bg-raised !border-slate-200/80 dark:!border-line !text-[13px]"
          />
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 hidden sm:inline-flex items-center px-1.5 py-0.5 text-[9px] font-mono font-semibold text-muted-foreground bg-slate-200/50 dark:bg-card rounded border border-slate-300/50 dark:border-line">
            ⌘K
          </kbd>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Super Admin Quick Switcher */}
        {isSuperAdmin && (
          <Link
            href="/admin"
            className="hidden sm:inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-hl hover:bg-hl-strong text-hl-contrast text-[11px] font-semibold transition-all shadow-xs"
          >
            <ShieldCheck className="w-3.5 h-3.5" />
            <span>Super Admin</span>
          </Link>
        )}

        {/* Security badge */}
        <div className="hidden sm:inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-sunken border border-line text-slate-600 dark:text-zinc-300 text-[11px] font-medium">
          <span className="relative flex h-1.5 w-1.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-positive opacity-75"></span>
            <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-positive"></span>
          </span>
          <ShieldCheck className="w-3 h-3 text-hl" />
          <span>{t('layout.header.secure_space')}</span>
        </div>

        {/* Quick New Project Button */}
        <Link
          href="/dashboard/wizard"
          className="btn-secondary !py-1.5 !px-3 !text-xs"
        >
          <Plus className="w-3.5 h-3.5 text-hl" />
          <span className="hidden sm:inline">{t('layout.header.new_tender')}</span>
        </Link>

        {/* User Profile / Auth Action */}
        {user ? (
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-2.5 pl-3 border-l border-slate-200/60 dark:border-line hover:opacity-90 transition-opacity cursor-pointer"
            >
              <div className="w-8 h-8 rounded-xl bg-hl text-hl-contrast flex items-center justify-center font-mono font-bold text-[12px] shadow-xs">
                {initials}
              </div>
              <div className="hidden md:block text-left min-w-0">
                <p className="text-[13px] font-semibold text-slate-800 dark:text-zinc-200 leading-none truncate max-w-[140px]">
                  {user.email}
                </p>
                <p className="text-[11px] text-hl truncate max-w-[140px] mt-0.5 font-medium">{isSuperAdmin ? 'Super Admin BTP' : companyName}</p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden md:block" />
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div className="absolute right-0 mt-2 w-64 card-drafted !shadow-floating p-1.5 z-50 space-y-0.5 animate-scale-in">
                <div className="p-3 border-b border-line mb-1">
                  <p className="text-[13px] font-semibold text-foreground truncate">{companyName}</p>
                  <p className="text-[11px] text-muted-foreground truncate mt-0.5 font-mono">{user.email}</p>
                  {isSuperAdmin ? (
                    <span className="badge-pill mt-2 text-[9px] font-bold">
                      <ShieldCheck className="w-3 h-3 text-hl mr-1 inline" />
                      Super Administrateur Plateforme
                    </span>
                  ) : (
                    <span className="badge-pill mt-2 text-[9px]">
                      <span className="h-1 w-1 rounded-full bg-hl"></span>
                      {t('layout.header.plan_active')}
                    </span>
                  )}
                </div>

                {isSuperAdmin && (
                  <Link
                    href="/admin"
                    onClick={() => setShowDropdown(false)}
                    className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-bold text-foreground hover:bg-slate-100 dark:hover:bg-raised transition-colors"
                  >
                    <ShieldCheck className="w-4 h-4 text-hl" />
                    <span>Panneau Super Admin</span>
                  </Link>
                )}

                <Link
                  href="/dashboard/company"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-raised transition-colors"
                >
                  <Building className="w-4 h-4 text-hl" />
                  <span>{t('layout.header.my_company')}</span>
                </Link>

                <Link
                  href="/dashboard/branding"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-raised transition-colors"
                >
                  <Sparkles className="w-4 h-4 text-hl" />
                  <span>{t('layout.header.charter_templates')}</span>
                </Link>

                <Link
                  href="/dashboard/settings"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-foreground hover:text-slate-900 dark:hover:text-white hover:bg-slate-50 dark:hover:bg-raised transition-colors"
                >
                  <User className="w-4 h-4 text-muted-foreground" />
                  <span>{t('layout.header.account_settings')}</span>
                </Link>

                <div className="divider !my-1" />

                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-[13px] font-medium text-danger hover:bg-danger/8 transition-colors text-left cursor-pointer"
                >
                  <LogOut className="w-4 h-4" />
                  <span>{t('layout.header.sign_out')}</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2.5 pl-3 border-l border-slate-200/60 dark:border-zinc-800/50">
            <Link
              href="/login"
              className="btn-secondary !py-2 !px-3.5 !text-[13px]"
            >
              <LogIn className="w-4 h-4" />
              <span>{t('layout.header.sign_in')}</span>
            </Link>
            <Link
              href="/register"
              className="btn-primary !py-2 !px-3.5 !text-[13px]"
            >
              <span>{t('layout.header.create_account')}</span>
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
