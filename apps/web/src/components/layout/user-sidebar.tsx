'use client';

import React, { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  HardHat,
  FileText,
  UploadCloud,
  Sliders,
  Edit3,
  Download,
  Building2,
  LogOut,
  ChevronRight,
  Sparkles,
  ShieldCheck,
  Award,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';

export function UserSidebar() {
  const pathname = usePathname();
  const [companyName, setCompanyName] = useState('EiffaBTP Construction');
  const [userEmail, setUserEmail] = useState('');
  const [isTenantAdmin, setIsTenantAdmin] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data }) => {
      if (data?.user) {
        setUserEmail(data.user.email || '');
        const meta = data.user.user_metadata || {};
        const appMeta = data.user.app_metadata || {};
        setCompanyName(appMeta.company_name || meta.company_name || 'Entreprise BTP');
        const role = appMeta.role || meta.role;
        setIsTenantAdmin(role === 'tenant_admin' || role === 'super_admin' || data.user.email === 'charbelakl@gmail.com');
      }
    });
  }, []);

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.href = '/login';
  }

  const btpSteps = [
    { name: '1. Ingestion DCE (CCTP & RC)', step: 'dce', icon: UploadCloud },
    { name: '2. Chiffrage & Données Chantier', step: 'decisions', icon: Sliders },
    { name: '3. Rédaction du Mémoire IA', step: 'editor', icon: Edit3 },
    { name: '4. Téléchargement Word & PDF', step: 'export', icon: Download },
  ];

  return (
    <aside className="w-72 bg-slate-950/90 border-r border-slate-800 flex flex-col h-screen sticky top-0 z-30">
      {/* Brand Header */}
      <div className="p-5 border-b border-slate-800/80">
        <Link href="/dashboard" className="flex items-center gap-3 group">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-sky-500 to-emerald-500 flex items-center justify-center shadow-glow group-hover:scale-105 transition-transform">
            <HardHat className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="font-bold text-base text-white tracking-tight flex items-center gap-1.5">
              btp<span className="text-sky-400">AO</span>
              <span className="text-[10px] uppercase tracking-wider font-semibold px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 border border-sky-500/30">
                BTP
              </span>
            </div>
            <p className="text-[11px] text-slate-400 font-medium">Générateur de Mémoires</p>
          </div>
        </Link>
      </div>

      {/* Tenant Context Pill */}
      <div className="px-4 py-3 mx-3 mt-3 rounded-xl bg-slate-900 border border-slate-800">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse shrink-0" />
          <div className="truncate">
            <p className="text-xs font-bold text-slate-200 truncate">{companyName}</p>
            <p className="text-[10px] text-slate-400 font-mono truncate">{userEmail || 'Conducteur de Travaux'}</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto p-3 space-y-6">
        {/* Workspace Workflow */}
        <div>
          <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
            Création de Mémoire Technique
          </p>
          <nav className="space-y-1">
            <Link
              href="/dashboard"
              className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-bold transition-all ${
                pathname === '/dashboard'
                  ? 'bg-sky-600 text-white shadow-glow'
                  : 'text-slate-300 hover:text-white hover:bg-slate-900'
              }`}
            >
              <HardHat className="w-4 h-4 text-sky-400" />
              <span>Nouveau Mémoire en 4 Étapes</span>
            </Link>

            <Link
              href="/dashboard/projects"
              className={`flex items-center gap-2.5 px-3 py-2.5 rounded-xl text-xs font-medium transition-all ${
                pathname === '/dashboard/projects'
                  ? 'bg-sky-500/15 text-sky-300 border border-sky-500/30'
                  : 'text-slate-400 hover:text-white hover:bg-slate-900'
              }`}
            >
              <FileText className="w-4 h-4 text-slate-400" />
              <span>Tous mes Appels d'Offres</span>
            </Link>
          </nav>
        </div>

        {/* Administration de l'entreprise (affiché seulement si tenant_admin) */}
        {isTenantAdmin && (
          <div>
            <p className="px-3 text-[10px] font-bold uppercase tracking-wider text-slate-400 mb-2">
              Gestion de l'Entreprise
            </p>
            <nav className="space-y-1">
              <Link
                href="/dashboard/settings"
                className={`flex items-center justify-between px-3 py-2 rounded-xl text-xs font-semibold transition-all ${
                  pathname.startsWith('/dashboard/settings')
                    ? 'bg-sky-600 text-white shadow-glow'
                    : 'text-slate-400 hover:text-white hover:bg-slate-900'
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <Building2 className="w-4 h-4 text-sky-400" />
                  <span>Paramètres & Équipe</span>
                </div>
                <ChevronRight className="w-3.5 h-3.5" />
              </Link>
            </nav>
          </div>
        )}
      </div>

      {/* Footer Logout */}
      <div className="p-3 border-t border-slate-800/80 bg-slate-950/60">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-xs text-slate-400 hover:text-rose-400 hover:bg-rose-950/20 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Déconnexion</span>
        </button>
      </div>
    </aside>
  );
}
