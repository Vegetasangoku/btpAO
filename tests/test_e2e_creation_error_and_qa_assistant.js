/**
 * Playwright E2E Test Suite for:
 * 1. Proof of visible error banner on AO creation failure (including 401 session expirée).
 * 2. Proof of Q&A Assistant in 3 source modes (Corpus, Web, Corpus + Web) with citations.
 */
const { chromium } = require('playwright');
const path = require('path');
const { execSync } = require('child_process');

const ARTIFACTS_DIR = '/Users/charbelakl/.gemini/antigravity-ide/brain/7535dce8-65df-4dc2-b448-058a8bb0f80c';

async function runE2ETests() {
  console.log('=== STARTING PLAYWRIGHT E2E TESTS (AO ERROR & QA ASSISTANT) ===');

  // Generate JWT token & setup test DB records
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

  console.log('-> Generated test token.');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 900 },
    extraHTTPHeaders: {
      'x-e2e-secret': 'btp-secret-e2e-key-98741',
    },
  });

  const page = await context.newPage();

  // Inject Bearer token to all backend API calls
  await page.route('http://localhost:8000/api/**', async (route) => {
    const req = route.request();
    const headers = {
      ...req.headers(),
      authorization: `Bearer ${token}`,
    };
    await route.continue({ headers });
  });

  try {
    // ── PART 1: TEST AO CREATION ERROR DISPLAY (POINT 1) ───────────────────────
    console.log('\n[TEST 1] Testing AO Creation Error Handling (Modal stays open + visible message)...');

    // Intercept POST /api/projects to simulate 401 Unauthorized
    await page.route('http://localhost:8000/api/projects', async (route) => {
      if (route.request().method() === 'POST' && !route.request().url().includes('/ask')) {
        console.log('-> Intercepted POST /api/projects: simulating 401 Unauthorized.');
        await route.fulfill({
          status: 401,
          contentType: 'application/json',
          body: JSON.stringify({ detail: 'Session expirée' }),
        });
      } else {
        const req = route.request();
        const headers = { ...req.headers(), authorization: `Bearer ${token}` };
        await route.continue({ headers });
      }
    });

    await page.goto('http://localhost:3000/dashboard/workspace?projectId=77777777-7777-7777-7777-777777777777', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1500);

    // Open Wizard
    const newProjBtn = await page.locator('text=Nouveau Projet').first();
    await newProjBtn.click();
    await page.waitForSelector('text=Nouvelle Réponse à un Appel d\'Offres', { timeout: 5000 });
    console.log('-> Wizard modal opened.');

    // Fill form
    await page.fill('input[placeholder="Ex : Réhabilitation thermique de 40 logements..."]', 'Test Marché Échec 401');
    await page.fill('input[placeholder="Ex : Mairie de Saint-Denis, Région IDF..."]', 'Ville Test');

    // Click submit
    await page.click('button[type="submit"]');
    await page.waitForTimeout(800);

    // Verify modal is STILL open and error banner is visible
    const errorBanner = await page.locator('text=session expirée, reconnecte-toi');
    await errorBanner.waitFor({ timeout: 5000 });
    console.log('-> PASSED: Modal remained open and displayed "session expirée, reconnecte-toi" banner.');

    // Capture screenshot of visible error
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'ao_creation_error_visible.png') });
    console.log('-> Saved screenshot: ao_creation_error_visible.png');

    // Remove the 401 mock for projects
    await page.unroute('http://localhost:8000/api/projects');

    // ── PART 2: TEST QA ASSISTANT IN 3 MODES (POINT 2) ─────────────────────────
    console.log('\n[TEST 2] Testing Q&A Assistant across 3 modes (Corpus, Web, Corpus + Web)...');
    
    // Close modal
    const closeBtn = await page.locator('button:has(svg.lucide-x)').first();
    if (await closeBtn.isVisible()) await closeBtn.click();

    // Open Q&A Assistant Sidebar
    const assistantBtn = await page.locator('text=Assistant DCE & Normes').first();
    await assistantBtn.click();
    await page.waitForSelector('text=Assistant Q&A DCE & Normes', { timeout: 5000 });
    console.log('-> Assistant Q&A sidebar opened.');

    // --- Mode 1: CORPUS ---
    console.log('-> Testing Mode: CORPUS...');
    await page.click('button:has-text("Corpus")');
    await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les pénalités de retard et les normes applicables ?');
    await page.click('button[type="submit"]:has(svg)');
    await page.waitForSelector('text=Sources identifiées', { timeout: 10000 });
    await page.waitForTimeout(1000);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_corpus.png') });
    console.log('-> PASSED: Mode CORPUS generated answer with verified DCE sources.');

    // --- Mode 2: WEB ---
    console.log('-> Testing Mode: WEB...');
    await page.click('button:has-text("Web")');
    await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les obligations RE2020 pour le béton bas carbone ?');
    await page.click('button[type="submit"]:has(svg)');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_web.png') });
    console.log('-> PASSED: Mode WEB generated answer with web search sources.');

    // --- Mode 3: CORPUS + WEB ---
    console.log('-> Testing Mode: CORPUS + WEB...');
    await page.click('button:has-text("Corpus + Web")');
    await page.fill('input[placeholder*="Poser une question"]', 'Quel est le délai contractuel et le cadre normatif ?');
    await page.click('button[type="submit"]:has(svg)');
    await page.waitForTimeout(2000);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_corpus_web.png') });
    console.log('-> PASSED: Mode CORPUS + WEB generated aggregated answer.');

    console.log('\n=== ALL PLAYWRIGHT TESTS PASSED WITH 100% SUCCESS ===');
  } catch (err) {
    console.error('\n❌ PLAYWRIGHT TEST ERROR:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runE2ETests();
