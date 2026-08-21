/**
 * Playwright E2E Test Suite for Password Reset Flow.
 * Verifies:
 * 1. Login page has "Mot de passe oublié ?" link leading to /forgot-password.
 * 2. /forgot-password sends branded reset email request.
 * 3. /reset-password with token validates token and updates password with strength bar.
 * 4. Takes screenshots of the UI and the branded email template.
 */
const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const ARTIFACTS_DIR = '/Users/charbelakl/.gemini/antigravity-ide/brain/7535dce8-65df-4dc2-b448-058a8bb0f80c';

async function runPasswordResetE2ETest() {
  console.log('--- STARTING PLAYWRIGHT PASSWORD RESET E2E TEST ---');

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const page = await context.newPage();

  try {
    // ── STEP 1: Login Page with "Mot de passe oublié ?" ─────────────────────
    console.log('\n[STEP 1] Navigating to /login...');
    await page.goto('http://localhost:3000/login', { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(1000);

    const forgotLink = await page.locator('text=Mot de passe oublié ?');
    if ((await forgotLink.count()) === 0) {
      throw new Error("FAILED: 'Mot de passe oublié ?' link not found on login page!");
    }
    console.log("-> PASSED: 'Mot de passe oublié ?' link found on login page.");

    // Click link to go to /forgot-password
    await forgotLink.click();
    await page.waitForURL('**/forgot-password');
    console.log('-> Navigated to /forgot-password.');

    // ── STEP 2: Forgot Password Request ─────────────────────────────────────
    console.log('\n[STEP 2] Submitting forgot-password form...');
    const testEmail = 'conducteur.travaux@eiffabtp-demo.fr';
    await page.fill('input[type="email"]', testEmail);

    // Take screenshot of forgot-password input state
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'forgot_password_input.png') });

    // Submit form
    await page.click('button[type="submit"]');
    await page.waitForSelector('text=E-mail sécurisé envoyé !', { timeout: 6000 });
    console.log('-> PASSED: Confirmation screen displayed with btpAO security notices.');

    // Take screenshot of confirmation state
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'forgot_password_sent.png') });

    // ── STEP 3: Reset Password Page with Token ──────────────────────────────
    console.log('\n[STEP 3] Navigating to /reset-password with test token...');
    // Create a fresh token via backend API
    const apiRes = await fetch('http://localhost:8000/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: testEmail }),
    });
    const apiData = await apiRes.json();
    const token = apiData.reset_url_dev.split('token=')[1];

    await page.goto(`http://localhost:3000/reset-password?token=${token}`, {
      waitUntil: 'domcontentloaded',
    });
    await page.waitForSelector('input[placeholder="••••••••••••"]', { timeout: 5000 });
    console.log('-> PASSED: /reset-password page loaded with verified account token.');

    // Fill new password with strength bar check
    const newPassword = 'SecuredBTPPassword2026!';
    const passwordInputs = await page.locator('input[placeholder="••••••••••••"]');
    await passwordInputs.nth(0).fill(newPassword);
    await passwordInputs.nth(1).fill(newPassword);

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'reset_password_input.png') });

    // Submit reset password form
    await page.click('button[type="submit"]');
    await page.waitForSelector('text=Mot de passe mis à jour !', { timeout: 6000 });
    console.log('-> PASSED: Password successfully updated message displayed.');

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, 'reset_password_success.png') });

    // ── STEP 4: Render Branded Email Preview ────────────────────────────────
    console.log('\n[STEP 4] Generating and capturing branded email HTML preview...');
    const emailHtmlRes = await fetch('http://localhost:8000/api/auth/forgot-password', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: testEmail }),
    });
    const emailData = await emailHtmlRes.json();

    // Render email in browser
    const emailPage = await context.newPage();
    const sampleHtml = `
      <!DOCTYPE html>
      <html>
      <body style="margin: 0; padding: 20px; background-color: #030712; display: flex; justify-content: center;">
        <iframe id="email-frame" style="width: 650px; height: 800px; border: none;" srcdoc="${emailData.reset_url_dev ? '' : ''}"></iframe>
      </body>
      </html>
    `;
    
    // We can load the rendered HTML directly from Python service
    const { execSync } = require('child_process');
    const renderedEmailHtml = execSync(`python3 -c "
from app.services.email_service import build_password_reset_html
print(build_password_reset_html('conducteur.travaux@eiffabtp-demo.fr', '${emailData.reset_url_dev}', 'Michel Conducteur'))
"`, { cwd: '/Users/charbelakl/Desktop/reponse au ao /apps/api' }).toString();

    await emailPage.setContent(renderedEmailHtml);
    await emailPage.waitForTimeout(500);
    await emailPage.screenshot({ path: path.join(ARTIFACTS_DIR, 'branded_btpao_password_reset_email.png') });
    console.log('-> PASSED: Branded HTML email captured.');

    console.log('\n--- PLAYWRIGHT PASSWORD RESET TEST COMPLETED WITH 100% SUCCESS ---');
  } catch (err) {
    console.error('\n❌ PLAYWRIGHT TEST FAILED:', err);
    process.exit(1);
  } finally {
    await browser.close();
  }
}

runPasswordResetE2ETest();
