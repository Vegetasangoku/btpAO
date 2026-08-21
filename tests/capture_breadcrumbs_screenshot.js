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
    const headers = { ...req.headers(), authorization: `Bearer ${token}` };
    await route.continue({ headers });
  });

  await page.goto('http://localhost:3000/dashboard/workspace?projectId=77777777-7777-7777-7777-777777777777', { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(2000);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'workspace_breadcrumbs_live.png') });
  console.log('-> Captured workspace_breadcrumbs_live.png');


  await browser.close();
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
