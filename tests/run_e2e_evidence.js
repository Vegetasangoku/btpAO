const { chromium } = require('playwright');
const path = require('path');
const { execSync } = require('child_process');

const ARTIFACTS_DIR = '/Users/charbelakl/.gemini/antigravity-ide/brain/7535dce8-65df-4dc2-b448-058a8bb0f80c';

async function main() {
  console.log('--- 1. Generating JWT Token & DB Seeds ---');
  const token = execSync(`python3 -c "
import psycopg2, bcrypt
from jose import jwt
from app.core.config import settings

JWT_SECRET = settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY
claims = {
    'sub': '22222222-2222-2222-2222-222222222222',
    'email': 'conducteur.travaux@eiffabtp-demo.fr',
    'aud': 'authenticated',
    'role': 'authenticated',
    'app_metadata': {'tenant_id': '11111111-1111-1111-1111-111111111111', 'role': 'owner'},
    'user_metadata': {'tenant_id': '11111111-1111-1111-1111-111111111111', 'role': 'owner'}
}
tok = jwt.encode(claims, JWT_SECRET, algorithm='HS256')

conn = psycopg2.connect(dbname='postgres')
cur = conn.cursor()
hp = bcrypt.hashpw(b'TestPassword123!', bcrypt.gensalt()).decode('utf-8')
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
  INSERT INTO auth.users (id, email, encrypted_password, raw_app_meta_data, raw_user_meta_data)
  VALUES ('22222222-2222-2222-2222-222222222222', 'conducteur.travaux@eiffabtp-demo.fr', %s, '{\\"tenant_id\\": \\"11111111-1111-1111-1111-111111111111\\", \\"role\\": \\"owner\\"}', '{\\"full_name\\": \\"Michel Conducteur\\"}')
  ON CONFLICT (id) DO UPDATE SET encrypted_password = EXCLUDED.encrypted_password;
''', (hp,))
cur.execute('''
  INSERT INTO public.projects (id, tenant_id, title, reference_code, client_name, status)
  VALUES ('77777777-7777-7777-7777-777777777777', '11111111-1111-1111-1111-111111111111', 'Construction Pôle Scolaire HQE', 'AO-2026-HQE', 'Mairie de Bordeaux', 'draft')
  ON CONFLICT (id) DO UPDATE SET title = EXCLUDED.title;
''')
cur.execute('''
  INSERT INTO public.dce_embeddings (id, tenant_id, project_id, section_title, page_number, content)
  VALUES ('88888888-8888-8888-8888-888888888888', '11111111-1111-1111-1111-111111111111', '77777777-7777-7777-7777-777777777777', 'CCTP Lot 01 - Gros Oeuvre', 18, 'Article 4.2 : Pénalités de retard fixées à 1/1000ème du montant HT par jour calendaire. Béton bas carbone CEM III/A obligatoire.')
  ON CONFLICT (id) DO NOTHING;
''')
conn.commit()
conn.close()

print(tok)
"`, { cwd: '/Users/charbelakl/Desktop/reponse au ao /apps/api' }).toString().trim();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 900 },
    extraHTTPHeaders: {
      'x-e2e-secret': 'btp-secret-e2e-key-98741',
    },
  });

  const page = await context.newPage();

  // Route backend API requests to attach the token
  await page.route('http://localhost:8000/api/**', async (route) => {
    const req = route.request();
    const headers = { ...req.headers(), authorization: `Bearer ${token}` };
    await route.continue({ headers });
  });

  console.log('--- 2. Navigating to Workspace ---');
  await page.goto('http://localhost:3000/dashboard/workspace?projectId=77777777-7777-7777-7777-777777777777', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(1500);

  // --- EVIDENCE 1: AO Creation Failure with 401 & Visible Error ---
  console.log('--- 3. Testing AO Creation Error with 401 Interception ---');
  await page.route('http://localhost:8000/api/projects', async (route) => {
    if (route.request().method() === 'POST' && !route.request().url().includes('/ask')) {
      console.log('-> Mocking 401 on POST /api/projects');
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Token has expired' }),
      });
    } else {
      const headers = { ...route.request().headers(), authorization: `Bearer ${token}` };
      await route.continue({ headers });
    }
  });

  // Open wizard
  const wizardBtn = (await page.locator('text=Nouveau Projet').isVisible())
    ? page.locator('text=Nouveau Projet').first()
    : page.locator('text=Créer une Réponse à Appel d\'Offres').first();

  await wizardBtn.click();
  await page.waitForSelector('text=Nouvelle Réponse à un Appel d\'Offres', { timeout: 5000 });

  await page.fill('input[placeholder*="Réhabilitation"]', 'AO Réhabilitation École - Test Erreur 401');
  await page.fill('input[placeholder*="Mairie"]', 'Ville de Paris');
  await page.click('button[type="submit"]');

  await page.waitForSelector('text=session expirée, reconnecte-toi', { timeout: 6000 });
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'ao_creation_error_visible.png') });
  console.log('-> Captured ao_creation_error_visible.png');

  // Close wizard and remove 401 route interception
  await page.unroute('http://localhost:8000/api/projects');
  const closeBtn = await page.locator('button:has(svg.lucide-x)').first();
  await closeBtn.click();
  await page.waitForTimeout(600);

  // --- EVIDENCE 2: Q&A Assistant across 3 modes ---
  console.log('--- 4. Testing Q&A Assistant ---');
  const assistantBtn = await page.locator('text=Assistant DCE & Normes').first();
  await assistantBtn.click();
  await page.waitForSelector('text=Assistant Q&A DCE & Normes', { timeout: 5000 });

  // Mode 1: Corpus
  console.log('-> Mode 1: Corpus');
  await page.click('button:has-text("Corpus")');
  await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les pénalités de retard selon le CCTP ?');
  await page.click('button[type="submit"]:has(svg.lucide-send)');
  await page.waitForSelector('text=Sources identifiées', { timeout: 10000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_corpus.png') });
  console.log('-> Captured qa_assistant_mode_corpus.png');

  // Mode 2: Web
  console.log('-> Mode 2: Web');
  await page.click('button:has-text("Web")');
  await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les obligations RE2020 pour le béton bas carbone ?');
  await page.click('button[type="submit"]:has(svg.lucide-send)');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_web.png') });
  console.log('-> Captured qa_assistant_mode_web.png');

  // Mode 3: Corpus + Web
  console.log('-> Mode 3: Corpus + Web');
  await page.click('button:has-text("Corpus + Web")');
  await page.fill('input[placeholder*="Poser une question"]', 'Quel est le délai contractuel et le cadre technique de conformité ?');
  await page.click('button[type="submit"]:has(svg.lucide-send)');
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_corpus_web.png') });
  console.log('-> Captured qa_assistant_mode_corpus_web.png');

  await browser.close();
  console.log('=== ALL EVIDENCE CAPTURED SUCCESSFULLY ===');
}

main().catch(err => {
  console.error('Error running evidence runner:', err);
  process.exit(1);
});
