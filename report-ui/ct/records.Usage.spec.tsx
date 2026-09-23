/** `Usage`: either dialect's usage object as one token grid. */
import { expect, test } from "@playwright/experimental-ct-react";
import { Usage } from "../src/components/records/values";

test("a Claude usage object, with thinking tokens and the cache split", async ({ mount }) => {
  const c = await mount(
    <Usage
      usage={{
        input_tokens: 2,
        cache_read_input_tokens: 35_865,
        cache_creation_input_tokens: 4_234,
        cache_creation: { ephemeral_1h_input_tokens: 4_000, ephemeral_5m_input_tokens: 234 },
        output_tokens: 264,
        output_tokens_details: { thinking_tokens: 42 },
      }}
    />,
  );
  await expect(c.locator('[data-el="V.usage"]')).toHaveCount(1);
  await expect(c.locator(".kvs b")).toHaveText(["input", "cache read", "cache write", "1h / 5m", "output", "thinking"]);
  await expect(c.locator(".val")).toHaveText(["2", "35,865", "4,234", "4,000 / 234", "264", "42"]);
});

test("a Codex usage object, with reasoning tokens and a total; the tier Codex never reports reads as a dash", async ({ mount }) => {
  const c = await mount(
    <Usage usage={{ input_tokens: 10_000, cached_input_tokens: 8_000, output_tokens: 120, reasoning_output_tokens: 64, total_tokens: 10_120 }} />,
  );
  await expect(c.locator(".kvs b")).toHaveText(["input", "cache read", "cache write", "output", "thinking", "total"]);
  await expect(c.locator(".val")).toHaveText(["10,000", "8,000", "–", "120", "64", "10,120"]);
});

test("no usage object, nothing", async ({ mount, page }) => {
  await mount(<Usage usage={null} />);
  await expect(page.locator("#root")).toBeEmpty();
});
