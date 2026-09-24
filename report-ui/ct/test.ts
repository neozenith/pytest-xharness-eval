/**
 * The `test` every component spec imports: Playwright CT's, with the pointer parked first.
 *
 * CT reuses one page per worker, and the mouse stays wherever the previous test left it. A
 * component mounted under that stale pointer starts out `:hover`ed — a hidden-until-hover label
 * reads opacity 1, a tooltip is already open — and whether it does depends on which test the
 * worker happened to run before, which is exactly the order a different machine changes.
 */
import { expect, test as base } from "@playwright/experimental-ct-react";

export const test = base.extend<{ parkPointer: void }>({
  parkPointer: [
    async ({ page }, use) => {
      const size = page.viewportSize() ?? { width: 1280, height: 800 };
      await page.mouse.move(size.width - 1, size.height - 1);
      await use();
    },
    { auto: true },
  ],
});

export { expect };
