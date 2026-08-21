const { chromium } = require('playwright');
const path = require('path');
const { execSync } = require('child_process');

const ARTIFACTS_DIR = '/Users/charbelakl/.gemini/antigravity-ide/brain/7535dce8-65df-4dc2-b448-058a8bb0f80c';

async function main() {
  const token = execSync(`python3 -c "
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
print(jwt.encode(claims, JWT_SECRET, algorithm='HS256'))
"`, { cwd: '/Users/charbelakl/Desktop/reponse au ao /apps/api' }).toString().trim();

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1366, height: 900 },
    extraHTTPHeaders: {
      'x-e2e-secret': 'btp-secret-e2e-key-98741',
    },
  });

  const page = await context.newPage();

  // Attach token to all /api/ requests
  await page.route('http://localhost:8000/api/**', async (route) => {
    const req = route.request();
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

  // ── Mode 1: CORPUS ────────────────────────────────────────────────────────
  console.log('Testing Mode: CORPUS...');
  await page.getByRole('button', { name: 'Corpus', exact: true }).click();
  await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les pénalités de retard selon le CCTP ?');
  await page.click('button[type="submit"]:has(svg)');
  await page.waitForSelector('text=Sources identifiées', { timeout: 10000 });
  await page.waitForTimeout(1000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_corpus.png') });
  console.log('-> Captured qa_assistant_mode_corpus.png');

  // ── Mode 2: WEB ───────────────────────────────────────────────────────────
  console.log('Testing Mode: WEB...');
  await page.getByRole('button', { name: 'Web', exact: true }).click();
  await page.fill('input[placeholder*="Poser une question"]', 'Quelles sont les exigences RE2020 pour le béton bas carbone ?');
  await page.click('button[type="submit"]:has(svg)');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_web.png') });
  console.log('-> Captured qa_assistant_mode_web.png');

  // ── Mode 3: CORPUS + WEB ──────────────────────────────────────────────────
  console.log('Testing Mode: CORPUS + WEB...');
  await page.getByRole('button', { name: 'Corpus + Web', exact: true }).click();
  await page.fill('input[placeholder*="Poser une question"]', 'Quel est le délai contractuel et le cadre technique de conformité ?');
  await page.click('button[type="submit"]:has(svg)');
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'qa_assistant_mode_corpus_web.png') });
  console.log('-> Captured qa_assistant_mode_corpus_web.png');


  await browser.close();
  console.log('Done!');
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
