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
import { useTranslation } from '@/components/i18n-provider';

function ResetPasswordForm() {
  const { t } = useTranslation();
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
              setErrorMsg(t('auth.reset.error_invalid_link'));
            }
            setVerifying(false);
          }
        } catch (err: any) {
          if (mounted) {
            setErrorMsg(err?.message || t('auth.reset.error_invalid_link_retry'));
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
            setErrorMsg(t('auth.reset.error_missing_link'));
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
      setErrorMsg(t('auth.reset.error_required'));
      return;
    }

    if (password.length < 8) {
      setErrorMsg(t('auth.reset.error_password_length'));
      return;
    }

    if (password !== confirmPassword) {
      setErrorMsg(t('auth.reset.error_password_mismatch'));
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
      setErrorMsg(err?.message || t('auth.reset.error_generic'));
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
      <div className="card-elevated py-10 px-6 sm:px-8 text-center space-y-3 rounded-2xl">
        <div className="w-8 h-8 border-2 border-hl border-t-transparent rounded-full animate-spin mx-auto" />
        <p className="text-[13px] text-muted-foreground font-mono">{t('auth.reset.verifying')}</p>
      </div>
    );
  }

  return (
    <div className="card-elevated p-7 sm:p-8 space-y-5 rounded-2xl animate-fade-in-up">
      {errorMsg && (
        <div className="p-3.5 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] flex items-start gap-2.5">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
          <span className="font-medium">{errorMsg}</span>
        </div>
      )}

      {success ? (
        <div className="space-y-4 text-center py-2">
          <div className="w-12 h-12 rounded-xl bg-positive/10 border border-positive/30 text-positive flex items-center justify-center mx-auto shadow-sm">
            <CheckCircle2 className="w-6 h-6" />
          </div>

          <div className="space-y-1.5">
            <h2 className="text-[15px] font-bold text-foreground font-heading">{t('auth.reset.success_title')}</h2>
            <p className="text-[13px] text-muted-foreground">
              {t('auth.reset.success_body', { email: userEmail || '' })}
            </p>
          </div>

          <Link
            href="/login"
            className="btn-primary w-full !py-3 cursor-pointer"
          >
            <span>{t('auth.reset.btn_login_now')}</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : !token || !userEmail ? (
        <div className="space-y-4 text-center py-3">
          <p className="text-[13px] text-muted-foreground">
            {t('auth.reset.no_token_message')}
          </p>
          <Link
            href="/forgot-password"
            className="btn-primary cursor-pointer"
          >
            <span>{t('auth.reset.btn_request_new_link')}</span>
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      ) : (
        <form onSubmit={handleReset} className="space-y-4">
          <div className="p-3.5 rounded-xl bg-hl/8 border border-hl/20 flex items-center justify-between text-[13px]">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-hl/15 text-hl flex items-center justify-center font-bold text-xs font-mono">
                @
              </div>
              <div className="min-w-0">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground block">{t('auth.reset.account_label')}</span>
                <span className="font-bold text-foreground font-mono text-[13px] truncate block">{userEmail}</span>
              </div>
            </div>
            <span className="badge-pill-emerald text-[9px] shrink-0">
              {t('auth.reset.token_verified_badge')}
            </span>
          </div>

          <div>
            <label className="block text-[12px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              {t('auth.reset.label_new_password')}
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-muted-foreground">
                <Lock className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="input-field-with-icon"
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-foreground cursor-pointer"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>

          {/* Password strength bar */}
          {password.length > 0 && (
            <div className="space-y-1.5">
              <div className="flex gap-1.5 h-1.5 w-full">
                {[1, 2, 3, 4].map((step) => (
                  <div
                    key={step}
                    className={`h-full flex-1 rounded-full transition-colors duration-200 ${
                      strengthScore >= step
                        ? strengthScore === 4
                          ? 'bg-positive'
                          : strengthScore >= 2
                          ? 'bg-hl'
                          : 'bg-danger'
                        : 'bg-slate-200 dark:bg-raised'
                    }`}
                  />
                ))}
              </div>
              <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                <span>{t('auth.reset.strength_min_chars')}</span>
                <span>{t('auth.reset.strength_recommend')}</span>
              </div>
            </div>
          )}

          <div>
            <label className="block text-[12px] font-semibold uppercase tracking-wider text-muted-foreground mb-1.5">
              {t('auth.reset.label_confirm_password')}
            </label>
            <div className="relative">
              <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-muted-foreground">
                <KeyRound className="w-4 h-4" />
              </div>
              <input
                type={showPassword ? 'text' : 'password'}
                required
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="••••••••••••"
                className="input-field-with-icon"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full !py-3 !text-[14px] cursor-pointer"
          >
            {loading ? (
              <span>{t('auth.reset.saving')}</span>
            ) : (
              <>
                <span>{t('auth.reset.btn_submit')}</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>

          <div className="pt-2 border-t border-line text-center">
            <Link
              href="/login"
              className="text-[13px] text-muted-foreground hover:text-hl transition-colors cursor-pointer"
            >
              {t('auth.reset.cancel_link')}
            </Link>
          </div>
        </form>
      )}
    </div>
  );
}

export default function ResetPasswordPage() {
  const { t } = useTranslation();
  return (
    <div className="min-h-screen bg-hl-soft dark:bg-sunken flex flex-col justify-center py-12 px-4 sm:px-6 lg:px-8 relative overflow-hidden transition-colors duration-200 font-sans">
      <div className="sm:mx-auto sm:w-full sm:max-w-md relative z-10 text-center space-y-3">
        {/* Brand Icon */}
        <div className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-hl text-hl-contrast shadow-sm mb-1">
          <HardHat className="w-5 h-5" />
        </div>

        {/* Top Badge */}
        <div>
          <span className="badge-pill text-[10px]">
            <Building className="w-3 h-3 text-hl" />
            {t('auth.reset.badge')}
          </span>
        </div>

        <h1 className="text-xl sm:text-2xl font-extrabold text-foreground tracking-tight font-heading">
          {t('auth.reset.heading_prefix')} <span className="text-hl">{t('auth.reset.heading_highlight')}</span>
        </h1>
        <p className="text-[13px] text-muted-foreground max-w-sm mx-auto">
          {t('auth.reset.subtitle')}
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <Suspense fallback={<div className="p-8 text-center text-muted-foreground text-[13px] font-mono">{t('auth.reset.loading_suspense')}</div>}>
          <ResetPasswordForm />
        </Suspense>

        {/* Footer Security Badge */}
        <div className="mt-6 text-center flex items-center justify-center gap-2 text-[12px] text-muted-foreground">
          <ShieldCheck className="w-3.5 h-3.5 text-positive" />
          <span>{t('auth.reset.footer_rgpd')}</span>
        </div>
      </div>
    </div>
  );
}
