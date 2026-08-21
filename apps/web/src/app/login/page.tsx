'use client';

import React, { useState, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  HardHat,
  Lock,
  Mail,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Building,
} from 'lucide-react';
import { supabase } from '@/lib/supabase/client';

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get('redirect') || '/dashboard';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [useMagicLink, setUseMagicLink] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);

    try {
      if (useMagicLink) {
        const { error } = await supabase.auth.signInWithOtp({
          email,
          options: {
            emailRedirectTo: `${window.location.origin}/dashboard`,
          },
        });
        if (error) throw error;
        setSuccessMsg('Un lien de connexion sécurisé vous a été envoyé par e-mail.');
      } else {
        const { data, error } = await supabase.auth.signInWithPassword({
          email,
          password,
        });

        if (error) throw error;

        if (data.user) {
          const role = (data.user.app_metadata?.role as string) || (data.user.user_metadata?.role as string);
          if (role === 'super_admin' || data.user.email === 'charbelakl@gmail.com') {
            router.push('/admin');
          } else {
            router.push(redirectUrl);
          }
        }
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Erreur lors de la connexion. Veuillez vérifier vos identifiants.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 py-8 px-6 sm:px-10 rounded-3xl shadow-2xl space-y-6">
      {errorMsg && (
        <div className="p-3 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {successMsg && (
        <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 text-xs flex items-start gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{successMsg}</span>
        </div>
      )}

      <form onSubmit={handleLogin} className="space-y-4">
        <div>
          <label className="block text-xs font-bold text-slate-300 mb-1.5">
            Adresse e-mail professionnelle
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
              placeholder="contact@votre-entreprise.fr"
              className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-sky-500 text-white text-xs placeholder:text-slate-600 focus:outline-none transition-colors"
            />
          </div>
        </div>

        {!useMagicLink && (
          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-bold text-slate-300">
                Mot de passe
              </label>
              <Link
                href="/forgot-password"
                className="text-[11px] font-medium text-sky-400 hover:text-sky-300 transition-colors"
              >
                Mot de passe oublié ?
              </Link>
            </div>

            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-4 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-sky-500 text-white text-xs placeholder:text-slate-600 focus:outline-none transition-colors"
              />
            </div>
          </div>
        )}

        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow-glow hover:shadow-sky-500/40 transition-all disabled:opacity-50"
        >
          {loading ? (
            <span>Connexion en cours...</span>
          ) : (
            <>
              <span>{useMagicLink ? 'Recevoir le lien par e-mail' : 'Se connecter'}</span>
              <ArrowRight className="w-4 h-4" />
            </>
          )}
        </button>
      </form>

      <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
        <button
          type="button"
          onClick={() => setUseMagicLink(!useMagicLink)}
          className="text-sky-400 hover:text-sky-300 transition-colors"
        >
          {useMagicLink ? 'Connexion avec mot de passe' : 'Connexion par lien e-mail'}
        </button>

        <Link href="/register" className="text-slate-300 hover:text-white font-semibold">
          Créer un compte
        </Link>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center py-12 sm:px-6 lg:px-8 relative overflow-hidden">
      {/* Background Ambience */}
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
            Plateforme Réponse aux Marchés Publics
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Connexion à btp<span className="text-sky-400">AO</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 max-w-sm mx-auto">
          Analysez vos dossiers et générez vos mémoires techniques et plannings en quelques clics.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <Suspense fallback={<div className="p-8 text-center text-slate-500 text-xs">Chargement...</div>}>
          <LoginForm />
        </Suspense>

        {/* Footer Security Badge */}
        <div className="mt-8 text-center flex items-center justify-center gap-2 text-xs text-slate-500">
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Données chiffrées & hébergement sécurisé conforme RGPD</span>
        </div>
      </div>
    </div>
  );
}
