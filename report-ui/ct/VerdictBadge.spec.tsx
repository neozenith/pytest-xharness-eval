import { expect, test } from "@playwright/experimental-ct-react";
import { VerdictBadge } from "../src/components/VerdictBadge";

for (const verdict of ["pass", "fail", "error", null]) {
  test(`VerdictBadge renders ${verdict ?? "no history"}`, async ({ mount }) => {
    const c = await mount(<VerdictBadge verdict={verdict} />);
    await expect(c).toBeVisible();
    await expect(c).toContainText(verdict ?? "");
  });
}
