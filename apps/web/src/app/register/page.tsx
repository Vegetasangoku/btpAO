'use client';

import React, { Suspense, useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { supabase } from '@/lib/supabase/client';
import { api } from '@/lib/api';
import { useTranslation } from '@/components/i18n-provider';
import { AuthShell, Field, inputClass, primaryButtonClass } from '@/components/auth/auth-shell';

type Plan = 'starter' | 'pro' | 'enterprise';

function passwordScore(pwd: string) {
  let score = 0;
  if (pwd.length >= 8) score++;
  if (/[A-Z]/.test(pwd)) score++;
  if (/[0-9]/.test(pwd)) score++;
  if (/[^A-Za-z0-9]/.test(pwd)) score++;
  return score;
}

function RegisterForm() {
  const { t } = useTranslation();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [company, setCompany] = useState('');
  const [siret, setSiret] = useState('');
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [plan, setPlan] = useState<Plan>(((searchParams.get('plan') as Plan) || 'pro'));
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const score = passwordScore(password);
  const scoreLabel = [
    t('auth.register.strength_weak'),
    t('auth.register.strength_weak'),
    t('auth.register.strength_medium'),
    t('auth.register.strength_good'),
    t('auth.register.strength_strong'),
  ][score];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!company.trim() || !fullName.trim() || !email.trim() || !password) {
      setError(t('auth.register.error_required_fields'));
      return;
    }
    if (password.length < 8) {
      setError(t('auth.register.error_password_length'));
      return;
    }
    if (password !== confirm) {
      setError(t('auth.register.error_password_mismatch'));
      return;
    }

    setLoading(true);
    try {
      const { data: authData, error: authError } = await supabase.auth.signUp({
        email: email.trim(),
        password,
        options: {
          data: { full_name: fullName.trim(), company_name: company.trim(), plan },
          emailRedirectTo: `${window.location.origin}/dashboard`,
        },
      });
      if (authError) {
        if (authError.message.toLowerCase().includes('already registered')) {
          throw new Error(t('auth.register.error_already_registered'));
        }
        throw authError;
      }

      try {
        const slug =
          company.toLowerCase().replace(/[^a-z0-9]/g, '-') + '-' + Math.floor(Math.random() * 1000);
        await api.createTenant({
          name: company.trim(),
          slug,
          siret: siret.trim() || undefined,
          contact_email: email.trim(),
          plan,
          country_code: 'FR',
        });
      } catch {
        // Le compte existe déjà côté authentification ; l'espace entreprise sera
        // reprovisionné à la première connexion. Ne pas bloquer l'inscription ici.
      }

      setDone(true);
      if (authData.session) setTimeout(() => router.push('/dashboard'), 1400);
    } catch (err: any) {
      setError(err?.message || t('auth.register.error_generic'));
    } finally {
      setLoading(false);
    }
  };

  if (done) {
    return (
      <AuthShell
        eyebrow={t('home.brand.sector')}
        title={t('auth.register.success_title')}
        intro={t('auth.register.success_ready', { company: company.trim() })}
      >
        <p className="text-[13px] text-muted-foreground leading-relaxed">
          {t('auth.register.success_email_sent', { email: email.trim() })}
        </p>
        <Link href="/login" className={primaryButtonClass + ' mt-6'}>
          {t('auth.login.btn_login')}
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      eyebrow={t('home.brand.sector')}
      title={t('home.register.title')}
      intro={t('home.register.intro')}
      footer={
        <p className="text-[12.5px] text-muted-foreground">
          {t('auth.register.already_account')}{' '}
          <Link href="/login" className="text-corten font-medium hover:underline">
            {t('auth.login.btn_login')}
          </Link>
        </p>
      }
    >
      <form onSubmit={handleSubmit} className="space-y-5">
        <Field label={t('auth.register.label_company')}>
          <input value={company} onChange={(e) => setCompany(e.target.value)} className={inputClass} required />
        </Field>

        <div className="grid grid-cols-2 gap-5">
          <Field label={t('auth.register.label_siret')}>
            <input value={siret} onChange={(e) => setSiret(e.target.value)} className={inputClass} inputMode="numeric" />
          </Field>
          <Field label={t('auth.register.label_fullname')}>
            <input value={fullName} onChange={(e) => setFullName(e.target.value)} className={inputClass} required />
          </Field>
        </div>

        <Field label={t('auth.register.label_email')}>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className={inputClass}
            autoComplete="email"
            required
          />
        </Field>

        <div className="grid grid-cols-2 gap-5">
          <Field
            label={t('auth.register.label_password')}
            hint={
              password ? (
                <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{scoreLabel}</span>
              ) : undefined
            }
          >
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              autoComplete="new-password"
              required
            />
          </Field>
          <Field label={t('auth.register.label_confirm_password')}>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className={inputClass}
              autoComplete="new-password"
              required
            />
          </Field>
        </div>

        {/* Choix du forfait : trois lignes, une seule sélectionnée. */}
        <fieldset>
          <legend className="text-[11.5px] font-medium text-muted-foreground">{t('home.register.plan_label')}</legend>
          <div className="mt-2 border-t border-line">
            {(
              [
                { id: 'starter' as Plan, name: t('home.plan.starter_name'), price: '199 €', note: t('home.plan.starter_note') },
                { id: 'pro' as Plan, name: t('home.plan.pro_name'), price: '499 €', note: t('home.plan.pro_note') },
                { id: 'enterprise' as Plan, name: t('home.plan.enterprise_name'), price: t('home.plan.on_quote'), note: t('home.plan.enterprise_note') },
              ]
            ).map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => setPlan(p.id)}
                className={`w-full flex items-baseline justify-between gap-3 py-2.5 border-b border-line text-start transition-colors duration-100 ${
                  plan === p.id ? 'text-foreground' : 'text-muted-foreground hover:text-muted-foreground'
                }`}
              >
                <span className="flex items-baseline gap-2 min-w-0">
                  <span
                    className={`w-[6px] h-[6px] rounded-full shrink-0 ${
                      plan === p.id ? 'bg-corten' : 'border border-line'
                    }`}
                  />
                  <span className="text-[13px] font-medium">{p.name}</span>
                  <span className="text-[11.5px] truncate">{p.note}</span>
                </span>
                <span className="font-mono text-[12.5px] tabular-nums shrink-0">{p.price}</span>
              </button>
            ))}
          </div>
        </fieldset>

        {error && <p className="text-[12.5px] text-danger border-s-2 border-danger ps-3 py-1">{error}</p>}

        <button type="submit" disabled={loading} className={primaryButtonClass}>
          {loading ? t('auth.register.submitting') : t('auth.register.btn_submit')}
        </button>
      </form>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense fallback={null}>
      <RegisterForm />
    </Suspense>
  );
}
