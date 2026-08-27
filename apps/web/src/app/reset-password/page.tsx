'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import {
  HardHat,
  Lock,
  ArrowRight,
  ShieldCheck,
  AlertCircle,
  CheckCircle2,
  Building,
  KeyRound,
  Eye,
  EyeOff,
} from 'lucide-react';
import { api } from '@/lib/api';
import { supabase } from '@/lib/supabase/client';

function ResetPasswordForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [verifying, setVerifying] = useState(true);
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  useEffect(() => {
    let mounted = true;

    // 1. Subscribe to Supabase auth state changes (catches #access_token=...&type=recovery hash parsing)
    const { data: authListener } = supabase.auth.onAuthStateChange(async (event, session) => {
      if (event === 'PASSWORD_RECOVERY' || event === 'SIGNED_IN' || event === 'USER_UPDATED') {
        if (mounted && session?.user?.email) {
          setUserEmail(session.user.email);
          setErrorMsg(null);
          setVerifying(false);
        }
      }
    });

    async function checkAuth() {
      // 2. Custom backend token in query (?token=...)
      const customToken = searchParams.get('token');
      if (customToken) {
        try {
          const res = await api.verifyResetToken(customToken);
          if (mounted) {
            if (res.valid) {
              setUserEmail(res.email);
              setErrorMsg(null);
            } else {
              setErrorMsg("Ce lien de réinitialisation est invalide ou a expiré.");
            }
            setVerifying(false);
          }
        } catch (err: any) {
          if (mounted) {
            setErrorMsg(err?.message || "Ce lien de réinitialisation est invalide ou a expiré. Veuillez refaire une demande.");
            setVerifying(false);
          }
        }
        return;
      }

      // 3. Supabase PKCE code exchange (?code=...)
      const code = searchParams.get('code');
      if (code) {
        try {
          const { data, error } = await supabase.auth.exchangeCodeForSession(code);
          if (!error && data?.session?.user?.email && mounted) {
            setUserEmail(data.session.user.email);
            setErrorMsg(null);
            setVerifying(false);
            return;
          }
        } catch (err) {
          console.warn('PKCE code exchange notice:', err);
        }
      }

      // 4. Supabase token_hash (?token_hash=...&type=recovery)
      const tokenHash = searchParams.get('token_hash');
      const type = searchParams.get('type');
      if (tokenHash && type === 'recovery') {
        try {
          const { data, error } = await supabase.auth.verifyOtp({
            token_hash: tokenHash,
            type: 'recovery',
          });
          if (!error && data?.session?.user?.email && mounted) {
            setUserEmail(data.session.user.email);
            setErrorMsg(null);
            setVerifying(false);
            return;
          }
        } catch (err) {
          console.warn('verifyOtp notice:', err);
        }
      }

      // 5. Active session check
      try {
        const { data } = await supabase.auth.getSession();
        if (data?.session?.user?.email && mounted) {
          setUserEmail(data.session.user.email);
          setErrorMsg(null);
          setVerifying(false);
          return;
        }
      } catch {}

      // 6. If no credentials found after a brief delay for hash parsing
      setTimeout(() => {
        if (mounted) {
          const hash = typeof window !== 'undefined' ? window.location.hash : '';
          const hasRecoveryHash = hash.includes('access_token') || hash.includes('type=recovery');
          if (!hasRecoveryHash && !userEmail) {
            setErrorMsg("Lien de réinitialisation manquant ou invalide. Veuillez cliquer sur le lien sécurisé reçu par e-mail.");
            setVerifying(false);
          }
        }
      }, 1000);
    }

    checkAuth();

    return () => {
      mounted = false;
      authListener?.subscription?.unsubscribe();
    };
  }, [searchParams, token, userEmail]);

  async function handleReset(e: React.FormEvent) {
    e.preventDefault();
    if (!password || !confirmPassword) {
      setErrorMsg('Veuillez renseigner et confirmer votre nouveau mot de passe.');
      return;
    }

    if (password.length < 8) {
      setErrorMsg('Le mot de passe doit comporter au moins 8 caractères.');
      return;
    }

    if (password !== confirmPassword) {
      setErrorMsg('Les deux mots de passe ne correspondent pas.');
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      if (token) {
        // 1. Reset via Backend Secure Token API (atomic PostgreSQL apply_password_reset)
        await api.resetPassword(token, password);
      } else {
        // 2. Reset via Supabase Auth Recovery Session
        const { error } = await supabase.auth.updateUser({
          password: password,
        });
        if (error) throw error;
      }

      // Clear any cached session
      try {
        await supabase.auth.signOut();
      } catch {}

      setSuccess(true);
      setTimeout(() => {
        router.push('/login');
      }, 2500);
    } catch (err: any) {
      setErrorMsg(err?.message || "Erreur lors de la mise à jour du mot de passe.");
    } finally {
      setLoading(false);
    }
  }

  // Password Strength Score (0 to 4)
  const hasLength = password.length >= 8;
  const hasUpper = /[A-Z]/.test(password);
  const hasNumber = /[0-9]/.test(password);
  const hasSpecial = /[^A-Za-z0-9]/.test(password);
  const strengthScore = [hasLength, hasUpper, hasNumber, hasSpecial].filter(Boolean).length;

  if (verifying) {
    return (
      <div className="bg-slate-900/90 border border-slate-800 py-12 px-6 sm:px-10 rounded-3xl shadow-2xl text-center space-y-4">
        <div className="w-10 h-10 border-2 border-sky-500 border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-xs text-slate-400">Vérification de la sécurité de votre lien...</p>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 py-8 px-6 sm:px-10 rounded-3xl shadow-2xl space-y-6">
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-rose-500/10 border border-rose-500/30 text-rose-300 text-xs flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span>{errorMsg}</span>
        </div>
      )}

      {success ? (
        <div className="space-y-4 text-center py-2">
          <div className="w-16 h-16 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 flex items-center justify-center mx-auto shadow-glow">
            <CheckCircle2 className="w-8 h-8" />
          </div>

          <div className="space-y-1.5">
            <h2 className="text-lg font-bold text-white">Mot de passe mis à jour !</h2>
            <p className="text-xs text-slate-300">
              Votre nouveau mot de passe a été enregistré avec succès pour <strong className="text-sky-300">{userEmail}</strong>.
            </p>
          </div>

          <Link
            href="/login"
            className="inline-flex items-center justify-center gap-2 w-full py-3 px-4 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow-glow transition-all"
          >
            <span>Se connecter maintenant</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : !token || !userEmail ? (
        <div className="space-y-4 text-center py-4">
          <p className="text-xs text-slate-400">
            Pour réinitialiser votre mot de passe, veuillez utiliser le lien envoyé à votre adresse e-mail.
          </p>
          <Link
            href="/forgot-password"
            className="inline-flex items-center justify-center gap-2 py-2.5 px-4 rounded-xl bg-sky-600 hover:bg-sky-500 text-white font-bold text-xs shadow-glow transition-all"
          >
            <span>Demander un nouveau lien</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <form onSubmit={handleReset} className="space-y-4">
          <div className="p-3.5 rounded-2xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-sky-500/20 text-sky-300 flex items-center justify-center font-bold">
                @
              </div>
              <div>
                <span className="text-[10px] font-semibold text-slate-400 block uppercase tracking-wider">Compte concerné</span>
                <span className="font-bold text-white font-mono text-xs">{userEmail}</span>
              </div>
            </div>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">
              Jeton vérifié
            </span>
          </div>

          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1.5">
              Nouveau mot de passe
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full pl-10 pr-10 py-2.5 rounded-xl bg-slate-950/80 border border-slate-800 focus:border-sky-500 text-white text-xs placeholder:text-slate-600 focus:outline-none transition-colors"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-500 hover:text-slate-300"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Password strength bar */}
          {password.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex gap-1 h-1.5 w-full">
                {[1, 2, 3, 4].map((step) => (
                  <div
                    key={step}
                    className={`h-full flex-1 rounded-full transition-colors ${
                      strengthScore >= step
                        ? strengthScore === 4
                          ? 'bg-emerald-500'
                          : strengthScore >= 2
                          ? 'bg-amber-500'
                          : 'bg-rose-500'
                        : 'bg-slate-800'
                    }`}
                  />
                ))}
              </div>
              <div className="flex justify-between text-[10px] text-slate-500">
                <span>Min. 8 caractères</span>
                <span>Majuscules & Chiffres recommandés</span>
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-bold text-slate-300 mb-1.5">
              Confirmer le nouveau mot de passe
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-500">
                <KeyRound className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
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
              <span>Enregistrement...</span>
            ) : (
              <>
                <span>Valider le nouveau mot de passe</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>

          <div className="pt-2 border-t border-slate-800/80 text-center">
            <Link
              href="/login"
              className="text-xs text-slate-400 hover:text-white transition-colors"
            >
              Annuler et revenir à la connexion
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
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
            Nouveau Mot de Passe Sécurisé
          </span>
        </div>

        <h1 className="text-2xl sm:text-3xl font-black text-white tracking-tight">
          Réinitialisation du <span className="text-sky-400">mot de passe</span>
        </h1>
        <p className="text-xs sm:text-sm text-slate-400 max-w-sm mx-auto">
          Définissez un mot de passe robuste pour accéder à votre espace de travail.
        </p>
      </div>

      <div className="mt-8 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <Suspense fallback={<div className="p-8 text-center text-slate-500 text-xs">Chargement...</div>}>
          <ResetPasswordForm />
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
