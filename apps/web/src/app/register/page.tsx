'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import {
  Sparkles,
  Building,
  User,
  Mail,
  Lock,
  ArrowRight,
  Loader2,
  AlertCircle,
  CheckCircle2,
  ShieldCheck,
  Award,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';

const PLANS = [
  {
    id: 'starter',
    name: 'Starter BTP',
    price: '49 €',
    period: '/ mois',
    features: ['3 DCE / mois', 'Génération RAG IA', 'Export Word (.docx)', '1 utilisateur'],
  },
  {
    id: 'pro',
    name: 'Pro BTP (Recommandé)',
    price: '199 €',
    period: '/ mois',
    popular: true,
    features: ['15 DCE / mois', 'Gantt HD 300 DPI', 'Organigrammes', 'Export PDF LibreOffice', '5 utilisateurs'],
  },
  {
    id: 'enterprise',
    name: 'Entreprise Major',
    price: '499 €',
    period: '/ mois',
    features: ['DCE illimités', 'OCR Azure dédié', 'Multi-agences & filiales', 'Support 24/7 BTP'],
  },
];

export default function RegisterPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    fullName: '',
    companyName: '',
    siret: '',
    email: '',
    password: '',
    plan: 'pro',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.email || !formData.password || !formData.companyName) {
      setError('Veuillez remplir tous les champs obligatoires.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. Supabase Auth signup with custom metadata
      const { data, error: authError } = await supabase.auth.signUp({
        email: formData.email,
        password: formData.password,
        options: {
          data: {
            full_name: formData.fullName,
            company_name: formData.companyName,
            siret: formData.siret,
            plan: formData.plan,
            role: 'owner',
          },

          emailRedirectTo: `${window.location.origin}/projects`,
        },
      });

      if (authError) {
        throw authError;
      }

      setSuccess(true);
      setTimeout(() => {
        router.push('/projects');
      }, 1500);
    } catch (err: any) {
      setError(err?.message || "Erreur lors de la création de l'organisation.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 bg-slate-950 text-slate-100 relative overflow-hidden">
      {/* Glows */}
      <div className="absolute top-0 right-1/4 w-96 h-96 bg-sky-500/10 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-0 left-1/4 w-96 h-96 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />

      <div className="sm:mx-auto sm:w-full sm:max-w-2xl text-center space-y-3 relative z-10">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-400 text-xs font-semibold">
          <Sparkles className="w-3.5 h-3.5" />
          <span>Inscription Espace Entreprise Multi-Tenant</span>
        </div>
        <h1 className="text-3xl font-black text-white tracking-tight">
          Créez votre compte <span className="gradient-text-btp">btpAO</span>
        </h1>
        <p className="text-sm text-slate-400">
          Chaque entreprise dispose d'un espace sécurisé avec isolation totale des données (PostgreSQL RLS).
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-2xl relative z-10">
        <div className="bg-slate-900/90 py-8 px-6 sm:px-8 shadow-2xl rounded-3xl border border-slate-800 space-y-6 backdrop-blur-xl">
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{error}</span>
            </div>
          )}

          {success ? (
            <div className="p-6 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-center space-y-3">
              <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" />
              <h2 className="text-base font-bold text-emerald-300">Organisation créée avec succès !</h2>
              <p className="text-xs text-slate-300">
                Redirection automatique vers votre espace de travail <strong>{formData.companyName}</strong>...
              </p>
            </div>
          ) : (
            <form onSubmit={handleRegister} className="space-y-6">
              {/* Company & User Details */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Nom de l'entreprise BTP *
                  </label>
                  <div className="relative">
                    <Building className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="text"
                      required
                      placeholder="EiffaBTP Construction SAS"
                      value={formData.companyName}
                      onChange={(e) => setFormData({ ...formData, companyName: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    SIRET (Optionnel)
                  </label>
                  <input
                    type="text"
                    placeholder="452 871 609 00041"
                    value={formData.siret}
                    onChange={(e) => setFormData({ ...formData, siret: e.target.value })}
                    className="w-full px-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-500 font-mono focus:outline-none focus:border-sky-500 transition-colors"
                  />
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Votre Nom & Prénom *
                  </label>
                  <div className="relative">
                    <User className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="text"
                      required
                      placeholder="Jean-Marc Alibert"
                      value={formData.fullName}
                      onChange={(e) => setFormData({ ...formData, fullName: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    E-mail professionnel *
                  </label>
                  <div className="relative">
                    <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="email"
                      required
                      placeholder="contact@eiffabtp.fr"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                    />
                  </div>
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                  Mot de passe (8 caractères minimum) *
                </label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                  <input
                    type="password"
                    required
                    minLength={8}
                    placeholder="••••••••••••"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                  />
                </div>
              </div>

              {/* Plan Selection */}
              <div>
                <label className="block text-xs font-semibold text-slate-300 mb-2">
                  Formule d'Abonnement SaaS BTP (Essai 14 jours inclus)
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  {PLANS.map((plan) => (
                    <div
                      key={plan.id}
                      onClick={() => setFormData({ ...formData, plan: plan.id })}
                      className={`p-4 rounded-2xl border cursor-pointer transition-all relative ${
                        formData.plan === plan.id
                          ? 'bg-sky-500/10 border-sky-500 text-white shadow-lg'
                          : 'bg-slate-800/50 border-slate-700 text-slate-300 hover:border-slate-600'
                      }`}
                    >
                      {plan.popular && (
                        <span className="absolute -top-2.5 right-3 text-[9px] font-bold px-2 py-0.5 rounded-full bg-sky-600 text-white shadow">
                          POPULAIRE
                        </span>
                      )}
                      <p className="text-xs font-bold">{plan.name}</p>
                      <p className="text-lg font-black text-sky-400 mt-1">
                        {plan.price} <span className="text-[10px] font-normal text-slate-400">{plan.period}</span>
                      </p>
                      <ul className="mt-2 space-y-1 text-[11px] text-slate-400">
                        {plan.features.slice(0, 2).map((f, i) => (
                          <li key={i} className="flex items-center gap-1">
                            <CheckCircle2 className="w-3 h-3 text-emerald-400 shrink-0" />
                            <span>{f}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 rounded-xl bg-sky-600 hover:bg-sky-500 text-white text-sm font-bold shadow-glow hover:shadow-sky-500/40 transition-all disabled:opacity-60"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <span>Créer mon Espace Entreprise & Démarrer</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>
          )}

          <div className="pt-4 border-t border-slate-800 text-center space-y-2">
            <p className="text-xs text-slate-400">Vous avez déjà un compte ?</p>
            <Link href="/login" className="text-xs font-semibold text-sky-400 hover:underline">
              Se connecter à un compte existant →
            </Link>
          </div>
        </div>

        {/* Security badge */}
        <div className="mt-6 flex items-center justify-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Données BTP hébergées en France/UE avec chiffrement AES-256 & RLS</span>
        </div>
      </div>
    </div>
  );
}
