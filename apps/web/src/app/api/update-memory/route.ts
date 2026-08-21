import { NextResponse } from 'next/server';
import { createServerClient } from '@supabase/ssr';
import { cookies } from 'next/headers';

export async function POST(request: Request) {
  try {
    const body = await request.json();
    const { tenantId, newRule } = body;

    if (!newRule) {
      return NextResponse.json({ success: false, error: 'Règle vide' }, { status: 400 });
    }

    const cookieStore = cookies();
    const supabase = createServerClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://ykdbjsvwzxeftlddubgy.supabase.co',
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlrZGJqc3Z3enhlZnRsZGR1Ymd5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODcxNDE0MTQsImV4cCI6MjEwMjcxNzQxNH0.aeE6paE278N4ZFamvfpIaiIJurzWKRT4hpYXfzToQM8',
      {
        cookies: {
          getAll() {
            return cookieStore.getAll();
          },
          setAll(cookiesToSet) {
            try {
              cookiesToSet.forEach(({ name, value, options }) =>
                cookieStore.set(name, value, options)
              );
            } catch {}
          },
        },
      }
    );

    let targetTenantId = tenantId;
    if (!targetTenantId) {
      const { data: { user } } = await supabase.auth.getUser();
      targetTenantId = user?.app_metadata?.tenant_id || user?.user_metadata?.tenant_id;
      if (!targetTenantId) {
        const { data: firstTenant } = await supabase.from('tenants').select('id').limit(1).single();
        targetTenantId = firstTenant?.id;
      }
    }

    if (!targetTenantId) {
      return NextResponse.json({ success: false, error: 'Tenant introuvable' }, { status: 400 });
    }

    // Récupération de la mémoire actuelle
    const { data: currentSettings } = await supabase
      .from('tenants_settings')
      .select('system_prompt_memory')
      .eq('tenant_id', targetTenantId)
      .single();

    const existingMemory = currentSettings?.system_prompt_memory || '';
    const formattedRule = newRule.trim().startsWith('-') ? newRule.trim() : `- ${newRule.trim()}`;
    const updatedMemory = existingMemory ? `${existingMemory}\n${formattedRule}` : formattedRule;

    const { error: updateErr } = await supabase
      .from('tenants_settings')
      .upsert({
        tenant_id: targetTenantId,
        system_prompt_memory: updatedMemory,
        mis_a_jour_le: new Date().toISOString(),
      }, { onConflict: 'tenant_id' });

    if (updateErr) throw updateErr;

    return NextResponse.json({
      success: true,
      message: 'Règle ajoutée avec succès à la mémoire de l\'entreprise',
      updatedMemory,
    });
  } catch (error: any) {
    console.error('Erreur update-memory:', error);
    return NextResponse.json({ success: false, error: error.message }, { status: 500 });
  }
}
