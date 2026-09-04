'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase/client';
import { useTranslation } from '@/components/i18n-provider';
import { AuthShell, Field, inputClass, primaryButtonClass } from '@/components/auth/auth-shell';

function LoginForm() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirect = searchParams.get('redirect');

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [magicLink, setMagicLink] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      if (magicLink) {
        const { error: otpError } = await supabase.auth.signInWithOtp({
          email: email.trim(),
          options: { emailRedirectTo: `${window.location.origin}${redirect || '/dashboard'}` },
        });
        if (otpError) throw otpError;
        setNotice(t('auth.login.success_magic_link'));
      } else {
        const { data, error: pwdError } = await supabase.auth.signInWithPassword({
          email: email.trim(),
          password,
        });
        if (pwdError) throw pwdError;
        if (data.session) {
          router.push(redirect || '/dashboard');
        }
      }
    } catch (err: any) {
      setError(err?.message || t('auth.login.error_generic'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell
      eyebrow={t('home.brand.sector')}
      title={t('home.login.title')}
      intro={t('home.login.intro')}
      footer={
        <p className="text-[12.5px] text-muted-foreground">
          {t('home.login.no_account')}{' '}
          <Link href="/register" className="text-corten font-medium hover:underline">
            {t('auth.login.create_account_link')}
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <Field label={t('auth.login.label_email')}>
          <input
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder={t('auth.login.placeholder_email')}
            className={inputClass}
          />
        </Field>

        {!magicLink && (
          <Field
            label={t('auth.login.label_password')}
            hint={
              <Link href="/forgot-password" className="text-[11px] text-muted-foreground hover:text-foreground transition-colors duration-100">
                {t('auth.login.forgot_password_link')}
              </Link>
            }
          >
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder={t('auth.login.placeholder_password')}
                className={inputClass + ' pe-16'}
              />
              <button
                type="button"
                onClick={() => setShowPassword((v) => !v)}
                className="absolute end-0 top-1.5 text-[10.5px] font-mono uppercase tracking-wider text-muted-foreground hover:text-foreground transition-colors duration-100"
              >
                {showPassword ? t('home.login.hide') : t('home.login.show')}
              </button>
            </div>
          </Field>
        )}

        {error && (
          <p className="text-[12.5px] text-danger border-s-2 border-danger ps-3 py-1">{error}</p>
        )}
        {notice && (
          <p className="text-[12.5px] text-positive border-s-2 border-positive ps-3 py-1">{notice}</p>
        )}

        <button type="submit" disabled={loading} className={primaryButtonClass}>
          {loading
            ? t('auth.login.connecting')
            : magicLink
              ? t('auth.login.btn_magic_link')
              : t('auth.login.btn_login')}
        </button>

        <button
          type="button"
          onClick={() => {
            setMagicLink((v) => !v);
            setError(null);
            setNotice(null);
          }}
          className="w-full text-center text-[12px] text-muted-foreground hover:text-foreground transition-colors duration-100"
        >
          {magicLink ? t('auth.login.toggle_to_password') : t('auth.login.toggle_to_magic')}
        </button>
      </form>
    </AuthShell>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
