import { test, expect } from '@playwright/test';

const workflowUrl = process.env.MOLD_COOK_BROWSER_URL;

if (!workflowUrl) {
  throw new Error('MOLD_COOK_BROWSER_URL must point at the temporary workflow repository');
}

test('observes the approved feature through a real browser', async ({ page }) => {
  await page.goto(workflowUrl);
  await expect(page.getByRole('heading', { name: 'Mold to Cook fixture' })).toBeVisible();
  await expect(page.getByTestId('feature-state')).toHaveText('ready');
  await page.getByRole('button', { name: 'Run feature' }).click();
  await expect(page.getByTestId('feature-result')).toHaveText('Feature executed');
});
