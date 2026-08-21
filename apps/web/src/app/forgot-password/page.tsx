'use client';

import React, { useState } from 'react';
import Link from 'next/link';
import {
  HardHat,
  Mail,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Building,
  ArrowLeft,
  KeyRound,
} from 'lucide-react';
import { api } from '@/lib/api';
import { supabase } from '@/lib/supabase/client';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) {
      setErrorMsg('Veuillez saisir votre adresse e-mail professionnelle.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // 1. Try Supabase Auth password reset in parallel if configured
      try {
        await supabase.auth.resetPasswordForEmail(email, {
          redirectTo: `${window.location.origin}/reset-password`,
        });
      } catch (sbErr) {
        // Fallback gracefully to backend password reset service
        console.info('Supabase email dispatch skipped or rate-limited, relying on backend service.');
      }

      // 2. Call backend transactional email reset service
      const res = await api.requestPasswordReset(email);
      setSuccess(true);
      if (res.reset_url_dev) {
        setDevResetUrl(res.reset_url_dev);
      }
    } catch (err: any) {
      setErrorMsg(err?.message || "Une erreur est survenue lors de l'envoi de l'e-mail.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Ambient background glow */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-sky-500/10 blur-[120px] pointer-events-none rounded-full" />
      <div className="absolute bottom-0 right-1/4 w-[400px] h-[300px] bg-emerald-500/10 blur-[100px] pointer-events-none rounded-full" />

      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10 text-center space-y-3">
        {/* Brand Icon */}
        <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-gradient-to-tr from-sky-500 to-emerald-500 shadow-glow mb-1">
          <HardHat className="w-8 h-8 text-white" />
        </div>

        {/* Top Badge */}
        <div>
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-sky-500/10 border border-sky-500/30 text-sky-300 text-xs font-semibold">
            <Building className="w-3.5 h-3.5" />
            Sécurité des Accès Entreprise
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Mot de passe <span className="text-sky-400">oublié</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 max-w-sm mx-auto">
          Saisissez votre e-mail professionnel pour recevoir un lien de réinitialisation sécurisé.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <div className="bg-slate-900/90 border border-slate-800 py-8 px-6 sm:px-10 rounded-3xl shadow-2xl space-y-6">
          {errorMsg && (
            <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{errorMsg}</span>
            </div>
          )}

          {success ? (
            <div className="space-y-5 text-center py-2">
              <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto shadow-glow">
                <CheckCircle2 className="w-8 h-8" />
              </div>

              <div className="space-y-2">
                <h2 className="text-lg font-bold text-white">E-mail sécurisé envoyé !</h2>
                <p className="text-xs text-slate-300 leading-relaxed">
                  Si un compte est associé à <strong className="text-white">{email}</strong>, un e-mail officiel <strong>btpAO</strong> vient de vous être expédié avec vos instructions de réinitialisation.
                </p>
              </div>

              <div className="p-3 rounded-xl bg-slate-950/80 border border-slate-800 text-[11px] text-slate-400 text-left space-y-1">
                <p className="font-semibold text-slate-200">⏱️ Durée de validité :</p>
                <p>Le lien est utilisable pendant <strong>1 heure</strong>. Pensez à vérifier vos courriers indésirables (spams) si nécessaire.</p>
              </div>

              {devResetUrl && (
                <div className="p-3 rounded-xl bg-sky-950/40 border border-sky-800/60 text-left space-y-1.5">
                  <span className="text-[10px] font-bold text-sky-400 uppercase tracking-wider">Lien direct de test :</span>
                  <a
                    href={devResetUrl}
                    className="block text-xs font-mono text-sky-300 hover:text-sky-200 underline break-all"
                  >
                    {devResetUrl}
                  </a>
                </div>
              )}

              <Link
                href="/login"
                className="inline-flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-white font-bold text-xs transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                <span>Retour à la connexion</span>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-300 mb-1.5">
                  Adresse e-mail du compte entreprise
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="directeur@eiffabtp.fr"
                    className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-sky-500 text-white text-xs placeholder:text-slate-600 focus:outline-none transition-colors"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow-glow hover:shadow-sky-500/40 transition-all disabled:opacity-50"
              >
                {loading ? (
                  <span>Envoi en cours...</span>
                ) : (
                  <>
                    <KeyRound className="w-4 h-4" />
                    <span>Envoyer le lien de réinitialisation</span>
                  </>
                )}
              </button>

              <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-1.5 text-sky-400 hover:text-sky-300 transition-colors"
                >
                  <ArrowLeft className="w-3.5 h-3.5" />
                  <span>Retour à la connexion</span>
                </Link>

                <Link href="/register" className="text-slate-300 hover:text-white font-semibold">
                  Créer un compte
                </Link>
              </div>
            </form>
          )}
        </div>

        {/* Footer Security Badge */}
        <div className="mt-8 text-center flex items-center justify-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Données chiffrées & réinitialisation sécurisée conforme RGPD</span>
        </div>
      </div>
    </div>
  );
}
