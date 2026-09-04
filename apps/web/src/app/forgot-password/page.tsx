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
import { useTranslation } from '@/components/i18n-provider';

export default function ForgotPasswordPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) {
      setErrorMsg(t('auth.forgot.error_email_required'));
      return;
    }

    setLoading(true);
    setErrorMsg(null);

    try {
      // 1. Dispatch real email via Supabase Auth mailer
      try {
        await supabase.auth.resetPasswordForEmail(email.trim(), {
          redirectTo: `${window.location.origin}/reset-password`,
        });
      } catch (sbErr: any) {
        console.warn('Supabase resetPasswordForEmail warning:', sbErr);
      }

      // 2. Also register in backend audit & token system
      try {
        await api.requestPasswordReset(email.trim());
      } catch (apiErr: any) {
        console.warn('Backend requestPasswordReset notice:', apiErr);
      }

      setSuccess(true);
    } catch (err: any) {
      setErrorMsg(err?.message || t('auth.forgot.error_generic'));
    } finally {
      setLoading(false);
    }
  }

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
            {t('auth.forgot.badge')}
          </span>
        </div>

        <h1 className="text-xl sm:text-2xl font-extrabold text-foreground tracking-tight font-heading">
          {t('auth.forgot.heading_prefix')} <span className="text-hl">{t('auth.forgot.heading_highlight')}</span>
        </h1>
        <p className="text-[13px] text-muted-foreground max-w-sm mx-auto">
          {t('auth.forgot.subtitle')}
        </p>
      </div>

      <div className="mt-6 sm:mx-auto sm:w-full sm:max-w-md relative z-10 px-4">
        <div className="card-elevated p-7 sm:p-8 space-y-5 rounded-2xl animate-fade-in-up">
          {errorMsg && (
            <div className="p-3.5 rounded-xl bg-danger/8 border border-danger/20 text-danger text-[13px] flex items-start gap-2.5">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <span className="font-medium">{errorMsg}</span>
            </div>
          )}

          {success ? (
            <div className="space-y-4 text-center py-2">
              <div className="w-12 h-12 rounded-xl bg-positive/10 border border-positive/30 text-positive flex items-center justify-center mx-auto shadow-xs">
                <CheckCircle2 className="w-6 h-6" />
              </div>

              <div className="space-y-1.5">
                <h2 className="text-sm font-bold text-foreground font-heading">{t('auth.forgot.success_title')}</h2>
                <p className="text-xs text-muted-foreground leading-relaxed">
                  {t('auth.forgot.success_body', { email })}
                </p>
              </div>

              <div className="p-3 rounded-xl bg-sunken border border-line text-[11px] text-muted-foreground text-left space-y-1 font-mono">
                <p className="font-semibold text-slate-800 dark:text-zinc-200">{t('auth.forgot.validity_note_label')}</p>
                <p>{t('auth.forgot.validity_note_body')}</p>
              </div>

              <Link
                href="/login"
                className="inline-flex items-center justify-center gap-1.5 w-full py-2.5 px-4 rounded-xl bg-hl hover:bg-hl-strong text-hl-contrast font-bold text-xs transition-colors cursor-pointer"
              >
                <ArrowLeft className="w-3.5 h-3.5" />
                <span>{t('auth.forgot.back_to_login')}</span>
              </Link>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-foreground mb-1.5">
                  {t('auth.forgot.label_email')}
                </label>
                <div className="relative">
                  <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-muted-foreground">
                    <Mail className="w-4 h-4" />
                  </div>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="directeur@eiffabtp.fr"
                    className="input-field-with-icon"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={loading}
                className="btn-primary w-full !py-3 cursor-pointer"
              >
                {loading ? (
                  <span>{t('auth.forgot.sending')}</span>
                ) : (
                  <>
                    <KeyRound className="w-3.5 h-3.5" />
                    <span>{t('auth.forgot.btn_submit')}</span>
                  </>
                )}
              </button>

              <div className="pt-2 border-t border-line flex items-center justify-between text-xs text-muted-foreground">
                <Link
                  href="/login"
                  className="inline-flex items-center gap-1 text-hl hover:underline transition-colors text-[11px] cursor-pointer"
                >
                  <ArrowLeft className="w-3 h-3" />
                  <span>{t('auth.forgot.back_to_login')}</span>
                </Link>

                <Link href="/register" className="text-slate-800 dark:text-zinc-200 hover:text-hl font-semibold text-[11px] cursor-pointer">
                  {t('auth.forgot.create_account')}
                </Link>
              </div>
            </form>
          )}
        </div>

        {/* Footer Security Badge */}
        <div className="mt-6 text-center flex items-center justify-center gap-2 text-[12px] text-muted-foreground">
          <ShieldCheck className="w-3.5 h-3.5 text-positive" />
          <span>{t('auth.forgot.footer_rgpd')}</span>
        </div>
      </div>
    </div>
  );
}
