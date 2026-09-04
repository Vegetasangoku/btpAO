import { createServerClient } from '@supabase/ssr';
import { NextResponse, type NextRequest } from 'next/server';

export async function middleware(request: NextRequest) {
  let response = NextResponse.next({
    request: {
      headers: request.headers,
    },
  });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://ykdbjsvwzxeftlddubgy.supabase.co',
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlrZGJqc3Z3enhlZnRsZGR1Ymd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNDE0MTQsImV4cCI6MjEwMjcxNzQxNH0.aeE6paE278N4ZFamvfpIaiIJurzWKRT4hpYXfzToQM8',
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({
            request,
          });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  // 30/08 (bug signalé : clic sur "Infrastructure" en /admin -> renvoyé vers /login) :
  // `supabase.auth.getUser()` fait un aller-retour réseau réel vers le serveur Auth Supabase à
  // CHAQUE navigation protégée (contrairement à getSession(), getUser() revalide le JWT côté
  // serveur au lieu de faire confiance au cookie local -- c'est volontaire et recommandé pour du
  // code middleware). Ce projet a déjà démontré des latences/erreurs réseau réelles vers son
  // instance Supabase (cf. /admin/infrastructure : SELECT 1 jusqu'à ~1900ms mesurés). Un unique
  // hoquet réseau transitoire sur CET appel précis suffisait auparavant à traiter à tort un
  // utilisateur pourtant authentifié comme non connecté, et donc à le rediriger vers /login. Un
  // seul retry immédiat absorbe la quasi-totalité de ces échecs transitoires, sans coût
  // perceptible sur le chemin normal (déjà authentifié : aucun retry déclenché).
  async function resolveUser() {
    try {
      const { data, error } = await supabase.auth.getUser();
      if (data?.user) return data.user;
      if (!error) return null;
    } catch {
      // Échec réseau dès la 1ère tentative : on retente une fois ci-dessous plutôt que
      // de conclure immédiatement à une session absente.
    }
    try {
      const { data } = await supabase.auth.getUser();
      return data?.user ?? null;
    } catch {
      return null;
    }
  }

  const user = await resolveUser();

  let effectiveUser = user;

  // Strictly non-production and server-side guarded secret for automated Playwright E2E tests (Fail-closed)
  const configuredE2ESecret = process.env.E2E_TEST_SECRET;
  if (!effectiveUser && process.env.NODE_ENV !== 'production' && Boolean(configuredE2ESecret)) {
    const e2eSecret = request.headers.get('x-e2e-secret') || request.cookies.get('btp_e2e_secret')?.value;
    if (e2eSecret && e2eSecret === configuredE2ESecret) {
      const isAdmin = request.headers.get('x-e2e-admin') === 'true' || request.cookies.get('btp_e2e_admin')?.value === 'true';
      effectiveUser = {
        id: isAdmin ? '99999999-9999-9999-9999-999999999999' : '22222222-2222-2222-2222-222222222222',
        email: isAdmin ? 'charbelakl@gmail.com' : 'conducteur.travaux@eiffabtp-demo.fr',
        app_metadata: {
          tenant_id: '11111111-1111-1111-1111-111111111111',
          role: isAdmin ? 'super_admin' : 'owner',
          is_platform_admin: isAdmin,
        },
        user_metadata: {
          tenant_id: '11111111-1111-1111-1111-111111111111',
          role: isAdmin ? 'super_admin' : 'owner',
          is_platform_admin: isAdmin,
        },
      } as any;
    }
  }



  const pathname = request.nextUrl.pathname;

  // Extraction du rôle utilisateur depuis les claims JWT (app_metadata injecté par le trigger SQL)
  const userRole = (effectiveUser?.app_metadata?.role as string) || (effectiveUser?.user_metadata?.role as string) || '';
  const userEmail = effectiveUser?.email || '';

  const isSuperAdmin = userRole === 'super_admin' || userRole === 'platform_admin' || userEmail === 'charbelakl@gmail.com';
  const isTenantAdmin = userRole === 'tenant_admin' || userRole === 'owner' || userRole === 'admin' || isSuperAdmin;
  const isBTPUser = Boolean(effectiveUser);



  // ── 1. ZONE SUPER ADMIN (/admin) ──────────────────────────────────────────
  // STRICTEMENT RÉSERVÉ au rôle 'super_admin' (Propriétaire du SaaS)
  if (pathname.startsWith('/admin')) {
    if (!effectiveUser) {
      const url = request.nextUrl.clone();
      url.pathname = '/login';
      url.searchParams.set('redirect', pathname);
      return NextResponse.redirect(url);
    }


    if (!isSuperAdmin) {
      // Un tenant_admin ou un simple conducteur est banni de /admin -> renvoyé vers /dashboard
      const url = request.nextUrl.clone();
      url.pathname = '/dashboard';
      return NextResponse.redirect(url);
    }
  }

  // ── 2. ZONE ADMIN LOCAL / ENTREPRISE (/dashboard/settings) ────────────────
  // STRICTEMENT RÉSERVÉ au rôle 'tenant_admin' (ou super_admin)
  if (pathname.startsWith('/dashboard/settings')) {
    if (!effectiveUser) {
      const url = request.nextUrl.clone();
      url.pathname = '/login';
      url.searchParams.set('redirect', pathname);
      return NextResponse.redirect(url);
    }

    if (!isTenantAdmin) {
      // Un simple conducteur de travaux ('user') n'a pas accès à la facturation / RH -> renvoyé à son espace de travail
      const url = request.nextUrl.clone();
      url.pathname = '/dashboard';
      return NextResponse.redirect(url);
    }
  }

  // ── 3. ZONE ESPACE UTILISATEUR BTP (/dashboard) ───────────────────────────
  // Accessible aux conducteurs de travaux ('user'), chefs d'entreprise ('tenant_admin') et super_admin
  if (pathname.startsWith('/dashboard')) {
    if (!effectiveUser) {
      // Redirection vers login pour toute personne non authentifiée
      const url = request.nextUrl.clone();

      url.pathname = '/login';
      url.searchParams.set('redirect', pathname);
      return NextResponse.redirect(url);
    }
  }

  return response;
}

export const config = {
  matcher: [
    '/admin/:path*',
    '/dashboard/:path*',
  ],
};
