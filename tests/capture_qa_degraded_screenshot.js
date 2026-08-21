const { chromium } = require('playwright');
const path = require('path');
const { execSync } = require('child_process');

const ARTIFACTS_DIR = '/Users/charbelakl/.gemini/antigravity-ide/brain/7535dce8-65df-4dc2-b448-058a8bb0f80c';

async function main() {
  const token = execSync(`python3 -c "
import psycopg2
from jose import jwt
from app.core.config import settings

conn = psycopg2.connect(dbname='postgres')
cur = conn.cursor()
cur.execute('''
  INSERT INTO public.tenants (id, name, slug, plan, country_code)
  VALUES ('11111111-1111-1111-1111-111111111111', 'EiffaBTP Construction', 'eiffabtp', 'enterprise', 'FR')
  ON CONFLICT (id) DO NOTHING;
''')
cur.execute('''
  INSERT INTO public.users (id, tenant_id, email, full_name, role)
  VALUES ('22222222-2222-2222-2222-222222222222', '11111111-1111-1111-1111-111111111111', 'conducteur.travaux@eiffabtp-demo.fr', 'Michel Conducteur', 'owner')
  ON CONFLICT (id) DO UPDATE SET email = EXCLUDED.email;
''')
cur.execute('''
  INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, status)
  VALUES ('77777777-7777-7777-7777-777777777777', '11111111-1111-1111-1111-111111111111', 'Construction Pôle Scolaire HQE', 'AO-2026-HQE', 'Mairie de Bordeaux', 'draft')
  ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
''')
conn.commit()
conn.close()

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
claims = {
    'sub': '22222222-2222-2222-2222-222222222222',
    'email': 'conducteur.travaux@eiffabtp-demo.fr',
    'aud': 'authenticated',
    'role': 'authenticated',
    'app_metadata': {'tenant_id': '11111111-1111-1111-1111-111111111111', 'role': 'owner'},
    'user_metadata': {'tenant_id': '11111111-1111-1111-1111-111111111111', 'role': 'owner'}
}
print(jwt.encode(claims, JWT_SECRET, algorithm='HS256'))
"`, { cwd: '/Users/charbelakl/Desktop/reponse au ao /apps/api' }).toString().trim();


  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 900 },
    extraHTTPHeaders: {
      'x-e2e-secret': 'btp-e2e-strong-secret-prod-safe-2026',
    },
  });

  const page = await context.newPage();

  await page.route('**/api/**', async (route) => {
    const req = route.request();
    if (req.url().includes('/ask')) {
      console.log('-> Intercepted /ask request, returning degraded payload');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          question: 'Quelles sont les pénalités de retard ?',
          source_mode: 'corpus',
          answer_markdown: "D'après les éléments disponibles dans le mode **corpus** pour le projet **Construction Pôle Scolaire HQE** :\n\n- Article 4.2 : Pénalités de retard fixées à 1/1000ème du montant HT par jour calendaire.\n\n[Source : DCE CCTP Lot 01 - Gros Oeuvre, Page 18]",
          sources: [{
            type: 'dce',
            title: 'DCE CCTP Lot 01 - Gros Oeuvre',
            page: 18,
            citation: '[Source : DCE CCTP Lot 01 - Gros Oeuvre, Page 18]',
            snippet: 'Article 4.2 : Pénalités de retard fixées à 1/1000ème du montant HT par jour calendaire.'
          }],
          total_sources_found: 1,
          is_degraded: true,
          degraded_reason: 'Service IA temporairement indisponible (API Provider Timeout)',
          timestamp: new Date().toISOString()
        }),
      });
      return;
    }

    const headers = { ...req.headers(), authorization: `Bearer ${token}` };
    await route.continue({ headers });
  });


  console.log('Navigating to workspace...');
  await page.goto('http://localhost:3000/dashboard/workspace?projectId=77777777-7777-7777-7777-777777777777', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);

  // Open Q&A Assistant
  const assistantBtn = await page.locator('text=Assistant DCE & Normes').first();
  await assistantBtn.waitFor({ timeout: 5000 });
  await assistantBtn.click();
  await page.waitForSelector('text=Assistant Q&A DCE & Normes', { timeout: 5000 });
  console.log('Opened Assistant Q&A.');

  await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les pénalités de retard ?');
  await page.click('button[type="submit"]:has(svg)');

  await page.waitForSelector('text=Réponse simplifiée / extrait direct', { timeout: 5000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_degraded_alert_visible.png') });
  console.log('-> Captured qa_assistant_degraded_alert_visible.png');

  await browser.close();
  console.log('Done!');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
