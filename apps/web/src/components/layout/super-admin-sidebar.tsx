'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  ShieldCheck,
  Activity,
  Building2,
  CreditCard,
  Server,
  HardHat,
  LogOut,
  ChevronRight,
  Sparkles,
  KeyRound,
  Layers,
  Cpu,
  Globe,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';

export function SuperAdminSidebar() {
  const pathname = usePathname();

  async function handleLogout() {
    await supabase.auth.signOut();
    window.location.href = '/login';
  }

  const superAdminNav = [
    { name: 'Dashboard Global & IA', href: '/admin', icon: Activity, badge: 'Direct' },
    { name: 'Entreprises Clientes (Tenants)', href: '/admin/tenants', icon: Building2, badge: '69' },
    { name: 'Facturation & Flux Stripe', href: '/admin/billing', icon: CreditCard },
    { name: 'Infrastructure OCR & RAG', href: '/admin/infrastructure', icon: Server },
    { name: 'Whitelist Réglementaire', href: '/admin/whitelist', icon: Globe },
  ];

  return (
    <aside className="w-72 bg-[#090D16] border-r border-[#1B2335] flex flex-col h-screen sticky top-0 z-30 select-none">
      {/* Brand Super Admin */}
      <div className="p-5 border-b border-[#1B2335] bg-gradient-to-b from-rose-950/20 via-transparent to-transparent">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-2xl bg-gradient-to-tr from-rose-600 via-rose-500 to-amber-500 flex items-center justify-center shadow-lg shadow-rose-950/50 ring-1 ring-white/10">
            <ShieldCheck className="w-5 h-5 text-white" />
          </div>
          <div>
            <div className="font-black text-base text-white tracking-tight flex items-center gap-1.5">
              btp<span className="text-amber-400">AO</span>
              <span className="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                ADMIN
              </span>
            </div>
            <p className="text-[10px] text-slate-400 font-mono truncate max-w-[150px]">charbelakl@gmail.com</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        <div>
          <p className="px-3 text-[10px] font-extrabold uppercase tracking-widest text-slate-500 mb-2">
            Gestion Plateforme
          </p>
          <nav className="space-y-1">
            {superAdminNav.map((item) => {
              const isActive = pathname === item.href;
              const Icon = item.icon;
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`flex items-center justify-between px-3.5 py-2.5 rounded-xl text-xs font-bold transition-all ${
                    isActive
                      ? 'bg-rose-500/10 text-rose-300 border border-rose-500/30 shadow-sm'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-[#111726]'
                  }`}
                >
                  <div className="flex items-center gap-3">
                    <Icon className={`w-4 h-4 ${isActive ? 'text-rose-400' : 'text-slate-500'}`} />
                    <span>{item.name}</span>
                  </div>
                  {isActive && <ChevronRight className="w-3.5 h-3.5 text-rose-400" />}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Operational View Banner */}
        <div className="p-4 rounded-2xl bg-gradient-to-br from-[#121829] to-[#0D1220] border border-[#1E293F] space-y-2.5 shadow-lg">
          <div className="flex items-center justify-between">
            <p className="text-xs font-bold text-white flex items-center gap-1.5">
              <HardHat className="w-4 h-4 text-amber-400" />
              <span>Espace Opérationnel</span>
            </p>
            <span className="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20">
              BTP
            </span>
          </div>
          <p className="text-[11px] text-slate-400 leading-relaxed">
            Basculez sur la vue conducteur de travaux pour tester le workflow de génération de mémoires.
          </p>
          <Link
            href="/dashboard"
            className="flex items-center justify-center gap-1.5 w-full py-2 px-3 rounded-xl bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-extrabold transition-all shadow-md shadow-amber-500/20"
          >
            <span>Ouvrir l'Espace BTP</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      </div>

      {/* Footer Logout */}
      <div className="p-4 border-t border-[#1B2335]">
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-bold text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
        >
          <LogOut className="w-4 h-4" />
          <span>Déconnexion Plateforme</span>
        </button>
      </div>
    </aside>
  );
}
