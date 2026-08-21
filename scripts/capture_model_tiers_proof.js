const { chromium } = require('playwright');
const path = require('path');

const ARTIFACTS_DIR = '/Users/charbelakl/.gemini/antigravity-ide/brain/7535dce8-65df-4dc2-b448-058a8bb0f80c';

async function captureScreenshots() {
  console.log('--- STARTING PLAYWRIGHT CAPTURE OF MODEL TIER DROPDOWNS ---');
  const browser = await chromium.launch({ headless: true });
  
  const context = await browser.newContext({
    viewport: { width: 1440, height: 950 },
    extraHTTPHeaders: {
      'x-e2e-secret': 'btp-e2e-strong-secret-prod-safe-2026',
      'x-e2e-admin': 'true',
    }
  });

  await context.addCookies([
    {
      name: 'btp_e2e_secret',
      value: 'btp-e2e-strong-secret-prod-safe-2026',
      domain: 'localhost',
      path: '/',
      httpOnly: false,
      secure: false,
      sameSite: 'Lax',
    },
    {
      name: 'btp_e2e_admin',
      value: 'true',
      domain: 'localhost',
      path: '/',
      httpOnly: false,
      secure: false,
      sameSite: 'Lax',
    }
  ]);

  const page = await context.newPage();

  // 1. CAPTURE 1: Super Admin /admin Master Keys Page
  console.log('[1/2] Navigating to http://localhost:3000/admin...');
  await page.goto('http://localhost:3000/admin', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Ensure tab 1 (master_keys) is active
  const masterKeysTab = await page.$('text=1. Clés API Master LLM');
  if (masterKeysTab) {
    await masterKeysTab.click();
    await page.waitForTimeout(600);
  }

  // Scroll platform select into view
  const platformSelect = await page.$('#platform-default-tier-select');
  if (platformSelect) {
    await platformSelect.scrollIntoViewIfNeeded();
  }

  const screenshot1Path = path.join(ARTIFACTS_DIR, 'admin_platform_default_model_dropdown.png');
  await page.screenshot({ path: screenshot1Path, fullPage: false });
  console.log(`✓ Screenshot 1 saved: ${screenshot1Path}`);

  // 2. CAPTURE 2: Navigate to /admin/tenants list and click on tenant
  console.log('[2/2] Navigating to http://localhost:3000/admin/tenants...');
  await page.goto('http://localhost:3000/admin/tenants', { waitUntil: 'networkidle' });
  await page.waitForTimeout(1500);

  // Click on the first tenant in the list
  const tenantCard = await page.$('a[href*="/admin/tenants/"]');
  if (tenantCard) {
    console.log('Clicking on tenant card...');
    await tenantCard.click();
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1500);
  } else {
    // Direct navigation fallback
    await page.goto('http://localhost:3000/admin/tenants/11111111-1111-1111-1111-111111111111', { waitUntil: 'networkidle' });
    await page.waitForTimeout(1500);
  }

  console.log('Current URL on tenant page:', page.url());

  // Click on routing tab
  const routingTab = await page.$('button:has-text("Routage"), button:has-text("routing")');
  if (routingTab) {
    await routingTab.click();
    await page.waitForTimeout(600);
  }

  const tenantSelect = await page.$('#tenant-model-tier-select');
  if (tenantSelect) {
    await tenantSelect.scrollIntoViewIfNeeded();
  }

  const screenshot2Path = path.join(ARTIFACTS_DIR, 'admin_tenant_client_model_dropdown.png');
  await page.screenshot({ path: screenshot2Path, fullPage: false });
  console.log(`✓ Screenshot 2 saved: ${screenshot2Path}`);

  await browser.close();
  console.log('--- SCREENSHOT CAPTURE COMPLETE ---');
}

captureScreenshots().catch(err => {
  console.error('Error during capture:', err);
  process.exit(1);
});
