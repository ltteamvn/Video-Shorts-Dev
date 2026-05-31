import { test } from '@playwright/test';
import { STORYBOARD } from '../playwright.config';

test('record video', async ({ page }) => {
  console.log(`[TEST] Bắt đầu render storyboard: ${STORYBOARD}`);
  
  // Tải trang render với query param truyền đường dẫn storyboard
  // Do webServer chạy ở gốc (localhost:8787), ta gọi thẳng /engine/render.html
  await page.goto(`/engine/render.html?storyboard=../${STORYBOARD}`);
  
  // Đợi cho đến khi render.html set cờ window.__renderDone = true
  await page.waitForFunction('window.__renderDone === true', null, { timeout: 0 });
  
  console.log('[TEST] Render hoàn tất.');
});
