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
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';

export function Header() {
  const router = useRouter();
  const [user, setUser] = useState<any>(null);
  const [companyName, setCompanyName] = useState<string>('EiffaBTP Construction');
  const [role, setRole] = useState<string>('Conducteur Principal');
  const [showDropdown, setShowDropdown] = useState(false);

  useEffect(() => {
    // 1. Initial user check
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        setUser(data.user);
        const meta = data.user.user_metadata || {};
        const appMeta = data.user.app_metadata || {};
        setCompanyName(meta.company_name || appMeta.company_name || 'Entreprise BTP');
        setRole(meta.role || appMeta.role || 'Admin BTP');
      }
    });

    // 2. Auth state change listener
    const { data: authListener } = supabase.auth.onAuthStateChange((event, session) => {
      if (session?.user) {
        setUser(session.user);
        const meta = session.user.user_metadata || {};
        const appMeta = session.user.app_metadata || {};
        setCompanyName(meta.company_name || appMeta.company_name || 'Entreprise BTP');
        setRole(meta.role || appMeta.role || 'Admin BTP');
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
    : 'JA';

  return (
    <header className="h-16 border-b border-slate-800/80 bg-slate-950/60 backdrop-blur-xl px-6 flex items-center justify-between sticky top-0 z-20">
      {/* Search & Quick Breadcrumb */}
      <div className="flex items-center gap-4 flex-1 max-w-lg">
        <div className="relative w-full">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Rechercher un appel d'offres, CCTP, critère RC ou matériel..."
            className="w-full bg-slate-900/80 border border-slate-800 rounded-lg pl-9 pr-4 py-1.5 text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
          />
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-3">
        {/* Security & RLS status */}
        <div className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-medium">
          <ShieldCheck className="w-3.5 h-3.5" />
          <span>Supabase IAM & RLS</span>
        </div>

        {/* Quick New Project Button */}
        <Link
          href="/projects"
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-semibold shadow-sm transition-all"
        >
          <Plus className="w-3.5 h-3.5" />
          <span>Nouvel AO</span>
        </Link>

        {/* User Profile / Auth Action */}
        {user ? (
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center gap-2.5 pl-2 border-l border-slate-800 hover:opacity-80 transition-opacity"
            >
              <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-sky-600 to-indigo-600 flex items-center justify-center font-bold text-xs text-white shadow-inner">
                {initials}
              </div>
              <div className="hidden md:block text-left">
                <p className="text-xs font-semibold text-slate-200 leading-tight truncate max-w-[140px]">
                  {user.email}
                </p>
                <p className="text-[10px] text-sky-400 truncate max-w-[140px]">{companyName}</p>
              </div>
            </button>

            {/* Dropdown Menu */}
            {showDropdown && (
              <div className="absolute right-0 mt-2 w-56 rounded-2xl bg-slate-900 border border-slate-800 shadow-2xl p-2 z-50 space-y-1">
                <div className="p-2 border-b border-slate-800">
                  <p className="text-xs font-bold text-white truncate">{companyName}</p>
                  <p className="text-[10px] text-slate-400 truncate">{user.email}</p>
                  <span className="inline-block mt-1 text-[9px] font-bold px-2 py-0.5 rounded bg-sky-500/10 text-sky-300 border border-sky-500/20">
                    Plan Pro BTP • Actif
                  </span>
                </div>

                <Link
                  href="/settings"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <Building className="w-3.5 h-3.5" />
                  <span>Mon Entreprise & Charte</span>
                </Link>

                <Link
                  href="/settings/ai-ocr"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <Sparkles className="w-3.5 h-3.5 text-sky-400" />
                  <span>Studio OCR & IA</span>
                </Link>

                <Link
                  href="/pricing"
                  onClick={() => setShowDropdown(false)}
                  className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
                >
                  <span>💳 Gérer mon Abonnement</span>
                </Link>

                <button
                  onClick={handleLogout}
                  className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs text-rose-400 hover:bg-rose-500/10 transition-colors text-left"
                >
                  <LogOut className="w-3.5 h-3.5" />
                  <span>Se déconnecter</span>
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center gap-2 pl-2 border-l border-slate-800">
            <Link
              href="/login"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold border border-slate-700 transition-colors"
            >
              <LogIn className="w-3.5 h-3.5" />
              <span>Connexion</span>
            </Link>
            <Link
              href="/register"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-sky-600 hover:bg-sky-500 text-white text-xs font-bold transition-all shadow-sm"
            >
              <span>Créer un compte</span>
            </Link>
          </div>
        )}
      </div>
    </header>
  );
}
