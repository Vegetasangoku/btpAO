'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ShieldAlert,
  Activity,
  Building2,
  CreditCard,
  Server,
  HardHat,
  LogOut,
  ChevronRight,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';

export function SuperAdminSidebar() {
  const pathname = usePathname();

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.href = '/login';
  }

  const superAdminNav = [
    { name: 'Dashboard Global & Revenus', href: '/admin', icon: Activity },
    { name: 'Gestion des Entreprises (Tenants)', href: '/admin/tenants', icon: Building2 },
    { name: 'Facturation & Flux Stripe', href: '/admin/billing', icon: CreditCard },
    { name: 'Supervision Cluster OCR & RAG', href: '/admin/infrastructure', icon: Server },
  ];

  return (
    <aside className="w-72 bg-slate-950 border-r border-rose-950/60 flex flex-col h-screen sticky top-0 z-30">
      {/* Brand Super Admin */}
      <div className="p-5 border-b border-rose-950/60 bg-gradient-to-b from-rose-950/20 to-transparent">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-rose-600 to-amber-600 flex items-center justify-center shadow-lg shadow-rose-900/40">
            <ShieldAlert className="w-6 h-6 text-white" />
          </div>
          <div>
            <div className="font-black text-base text-white tracking-tight flex items-center gap-1.5">
              btp<span className="text-rose-400">AO</span>
              <span className="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                SUPER ADMIN
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono">charbelakl@gmail.com</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <div>
          <p className="px-3 text-[10px] font-extrabold uppercase tracking-widest text-rose-400 mb-2">
            Plateforme SaaS Master
          </p>
          <nav className="space-y-1">
            {superAdminNav.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-rose-600/20 text-rose-300 border border-rose-500/40 shadow-sm'
                      : 'text-slate-400 hover:text-white hover:bg-slate-900/80'
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-rose-400' : 'text-slate-500'}`} />
                    <span>{item.name}</span>
                  </div>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 text-rose-400" />}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Switch to Operational BTP Workspace */}
        <div className="p-3 rounded-2xl bg-slate-900/60 border border-slate-800 space-y-2">
          <p className="text-[11px] font-bold text-white flex items-center gap-1.5">
            <HardHat className="w-4 h-4 text-sky-400" />
            <span>Vue Opérationnelle</span>
          </p>
          <p className="text-[10px] text-slate-400">Accédez au workflow conducteur pour tester la création de mémoires.</p>
          <Link
            href="/dashboard"
            className="block text-center py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-sky-400 text-xs font-bold border border-slate-700 transition-colors"
          >
            Ouvrir l'Espace BTP →
          </Link>
        </div>
      </div>

      {/* Footer Logout */}
      <div className="p-4 border-t border-slate-900">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2 rounded-xl text-xs text-rose-400 hover:bg-rose-950/30 transition-colors"
        >
          <LogOut className="w-3.5 h-3.5" />
          <span>Déconnexion Plateforme</span>
        </button>
      </div>
    </aside>
  );
}
