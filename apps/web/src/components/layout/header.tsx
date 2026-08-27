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

export function Header() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [companyName, setCompanyName] = useState<string>('Entreprise BTP');
  const [role, setRole] = useState<string>('Conducteur Principal');
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        setUser(data.user);
        const meta = data.user.user_metadata || {};
        const appMeta = data.user.app_metadata || {};
        setCompanyName(meta.company_name || appMeta.company_name || 'Entreprise BTP');
        setRole(meta.role || appMeta.role || 'Conducteur BTP');
      }
    });

    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
      if (session?.user) {
        setUser(session.user);
        const meta = session.user.user_metadata || {};
        const appMeta = session.user.app_metadata || {};
        setCompanyName(meta.company_name || appMeta.company_name || 'Entreprise BTP');
        setRole(meta.role || appMeta.role || 'Conducteur BTP');
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

  return (
    <header className="h-16 border-b border-slate-200 dark:border-[#1E2638] bg-white/80 dark:bg-[#0C0F17]/80 backdrop-blur-xl px-6 flex items-center justify-between sticky top-0 z-20 transition-colors duration-200">
      {/* Search & Global Context */}
      <div className="flex items-center gap-4 flex-1 max-w-md">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-slate-400 dark:text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Rechercher un AO, CCTP, RC ou critère..."
            className="w-full bg-slate-100/90 dark:bg-[#121622] border border-slate-200 dark:border-[#1E2638] rounded-xl pl-10 pr-4 py-2 text-xs text-slate-900 dark:text-slate-200 placeholder:text-slate-400 dark:placeholder:text-slate-500 focus:outline-none focus:border-amber-500 transition-colors"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Security badge */}
        <div className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-700 dark:text-emerald-400 text-xs font-bold">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Espace Sécurisé</span>
        </div>

        {/* Quick New Project Button */}
        <Link
          href="/dashboard/wizard"
          className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black shadow-sm shadow-amber-500/20 transition-all cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Nouvel AO</span>
        </Link>

        {/* User Profile / Auth Action */}
        {user ? (
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-2.5 pl-3 border-l border-slate-200 dark:border-slate-800 hover:opacity-85 transition-opacity cursor-pointer"
            >
              <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-600 flex items-center justify-center font-black text-xs text-slate-950 shadow-sm ring-1 ring-white/20">
                {initials}
              </div>
              <div className="hidden md:block text-left">
                <p className="text-xs font-bold text-slate-900 dark:text-slate-200 leading-tight truncate max-w-[140px]">
                  {user.email}
                </p>
                <p className="text-[10px] font-semibold text-amber-600 dark:text-amber-400 truncate max-w-[140px]">{companyName}</p>
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-slate-400 hidden md:block" />
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div className="absolute right-0 mt-2 w-60 rounded-2xl bg-white dark:bg-[#121622] border border-slate-200 dark:border-[#1E2638] shadow-2xl p-2 z-50 space-y-1 animate-in fade-in">
                <div className="p-2.5 border-b border-slate-100 dark:border-slate-800">
                  <p className="text-xs font-bold text-slate-900 dark:text-white truncate">{companyName}</p>
                  <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{user.email}</p>
                  <span className="inline-block mt-1.5 text-[9px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/30">
                    Plan Entreprise BTP • Actif
                  </span>
                </div>

                <Link
                  href="/dashboard/company"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <Building className="w-3.5 h-3.5 text-amber-500" />
                  <span>Mon Entreprise & Moyens</span>
                </Link>

                <Link
                  href="/dashboard/branding"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5 text-amber-500" />
                  <span>Charte & Modèles</span>
                </Link>

                <Link
                  href="/dashboard/settings"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white hover:bg-slate-100 dark:hover:bg-slate-800 transition-colors"
                >
                  <User className="w-3.5 h-3.5 text-slate-400" />
                  <span>Paramètres du compte</span>
                </Link>

                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold text-rose-600 dark:text-rose-400 hover:bg-rose-500/10 transition-colors text-left cursor-pointer"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Se déconnecter</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 pl-3 border-l border-slate-200 dark:border-slate-800">
            <Link
              href="/login"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 text-xs font-bold border border-slate-200 dark:border-slate-700 transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Connexion</span>
            </Link>
            <Link
              href="/register"
              className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-black transition-all shadow-sm"
            >
              <span>Créer un compte</span>
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
