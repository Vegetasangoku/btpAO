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
    features: ['3 DCE / mois', 'Rédaction assistée par IA', 'Export Word (.docx)', '1 utilisateur'],
  },
  {
    id: 'pro',
    name: 'Pro BTP (Recommandé)',
    price: '199 €',
    period: '/ mois',
    popular: true,
    features: ['15 DCE / mois', 'Plannings Gantt HD & Organigrammes', 'Export PDF & Word', '5 utilisateurs'],
  },
  {
    id: 'enterprise',
    name: 'Entreprise Major',
    price: '499 €',
    period: '/ mois',
    features: ['DCE illimités', 'Analyse documentaire haute précision', 'Multi-agences & filiales', 'Support prioritaire 24/7'],
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
    confirmPassword: '',
    plan: 'pro',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleRegister(e: React.FormEvent) {
    e.preventDefault();
    if (!formData.email || !formData.password || !formData.confirmPassword || !formData.companyName) {
      setError('Veuillez remplir tous les champs obligatoires.');
      return;
    }

    if (formData.password.length < 8) {
      setError('Le mot de passe doit comporter au moins 8 caractères.');
      return;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Les deux mots de passe ne correspondent pas.');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // 1. Supabase Auth signup with custom metadata
      const { data, error: authError } = await supabase.auth.signUp({
        email: formData.email.trim(),
        password: formData.password,
        options: {
          data: {
            full_name: formData.fullName.trim(),
            company_name: formData.companyName.trim(),
            siret: formData.siret.trim(),
            plan: formData.plan,
            role: 'owner',
          },

          emailRedirectTo: `${window.location.origin}/projects`,
        },
      });

      if (authError) {
        throw authError;
      }

      if (data?.user && (!data.user.identities || data.user.identities.length === 0)) {
        throw new Error('Cette adresse e-mail est déjà enregistrée. Veuillez vous connecter.');
      }

      setSuccess(true);

      // Si Supabase a la confirmation d'email activée, data.session sera null.
      // Dans ce cas on ne redirige pas vers /projects (l'user n'a pas de session active).
      // On laisse le message de succès visible et on redirige seulement si session active.
      if (data?.session) {
        setTimeout(() => {
          router.push('/projects');
        }, 1500);
      }
      // Sinon : le message "check your email" reste affiché (setSuccess(true) suffit)
    } catch (err: any) {
      console.error('Signup error:', err);
      let message = "Erreur lors de la création de l'organisation.";
      if (typeof err === 'string' && err !== '{}') {
        message = err;
      } else if (err?.message && typeof err.message === 'string' && err.message !== '{}') {
        message = err.message;
      } else if (err?.error_description && typeof err.error_description === 'string') {
        message = err.error_description;
      } else if (err?.error && typeof err.error === 'string') {
        message = err.error;
      } else if (err?.msg && typeof err.msg === 'string') {
        message = err.msg;
      } else if (err?.statusText && typeof err.statusText === 'string') {
        message = err.statusText;
      }

      // Friendly translations
      if (message.includes('User already registered') || message.includes('already registered')) {
        message = 'Cette adresse e-mail est déjà associée à un compte. Veuillez vous connecter.';
      } else if (message.includes('Password should be at least')) {
        message = 'Le mot de passe doit comporter au moins 8 caractères.';
      } else if (message.includes('rate limit') || message.includes('security purposes')) {
        message = 'Trop de tentatives. Veuillez patienter quelques instants avant de réessayer.';
      } else if (message.includes('Database error saving new user')) {
        message = "Erreur lors de l'enregistrement de l'entreprise. Veuillez vérifier les informations saisies.";
      } else if (message === '{}' || !message.trim()) {
        message = "Erreur lors de la création du compte. Veuillez vérifier vos informations ou vous connecter.";
      }

      setError(message);
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
          <span>Création de votre Espace Entreprise</span>
        </div>
        <h1 className="text-3xl font-black text-white tracking-tight">
          Créez votre compte <span className="gradient-text-btp">btpAO</span>
        </h1>
        <p className="text-sm text-slate-400">
          Votre espace dédié et vos données d'entreprise sont 100% confidentiels et sécurisés.
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
                Votre espace entreprise <strong>{formData.companyName}</strong> est prêt.
              </p>
              <p className="text-xs text-sky-300 font-semibold">
                📧 Un e-mail de confirmation vous a été envoyé à <strong>{formData.email}</strong>.<br />
                Cliquez sur le lien pour activer votre compte et accéder à votre espace.
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

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Mot de passe (8 caractères min.) *
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

                <div>
                  <label className="block text-xs font-semibold text-slate-300 mb-1.5">
                    Confirmer le mot de passe *
                  </label>
                  <div className="relative">
                    <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                    <input
                      type="password"
                      required
                      minLength={8}
                      placeholder="••••••••••••"
                      value={formData.confirmPassword}
                      onChange={(e) => setFormData({ ...formData, confirmPassword: e.target.value })}
                      className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-800 border border-slate-700 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-sky-500 transition-colors"
                    />
                  </div>
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
          <span>Données BTP hébergées en France/UE • Confidentialité et sécurité maximale garanties</span>
        </div>
      </div>
    </div>
  );
}
