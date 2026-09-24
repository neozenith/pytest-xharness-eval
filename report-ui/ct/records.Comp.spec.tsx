/**
 * `Comp`: the labelled frame every record-card renderer wraps its output in, so the HTML names
 * what drew it; and the four small wrappers beside it (`Muted`, `Notice`, `Mono`, `Tag`).
 */
import { expect, test } from "./test";
import { Comp, Mono, Muted, Notice, Tag } from "../src/components/records/Comp";

test("wraps its children under a hidden label naming the component", async ({ mount }) => {
  const c = await mount(
    <Comp el="V.text" className="extra">
      <span>body</span>
    </Comp>,
  );
  await expect(c.locator('[data-el="V.text"]')).toHaveCount(1);
  await expect(c.locator(".comp").first()).toHaveClass(/\bcomp\b.*\bextra\b/);
  await expect(c.locator('[data-el="V.text"] > .comp-label')).toHaveText("V.text");
  await expect(c.locator('[data-el="V.text"] > .comp-label')).toHaveCSS("opacity", "0");
  await c.locator(".comp").first().hover();
  await expect(c.locator('[data-el="V.text"] > .comp-label')).toHaveCSS("opacity", "1");
});

test("a fallback's label is always visible", async ({ mount }) => {
  const c = await mount(
    <Comp el="R.fallback">
      <span>json</span>
    </Comp>,
  );
  await expect(c.locator('[data-el="R.fallback"] > .comp-label')).toHaveCSS("opacity", "1");
});

test("empty children render nothing", async ({ mount, page }) => {
  await mount(<Comp el="V.x">{""}</Comp>);
  await expect(page.locator("#root")).toBeEmpty();
});

test("children that are all empty render nothing", async ({ mount, page }) => {
  await mount(
    <Comp el="V.x">
      {null}
      {false}
    </Comp>,
  );
  await expect(page.locator("#root")).toBeEmpty();
});

test("Muted, Notice, Mono and Tag carry their classes", async ({ mount }) => {
  const c = await mount(
    <div>
      <Muted>quiet</Muted>
      <Notice>loud</Notice>
      <Mono>code</Mono>
      <Tag tone="added">new</Tag>
      <Tag tone="removed">gone</Tag>
      <Tag>plain</Tag>
    </div>,
  );
  await expect(c.locator(".muted.note")).toHaveText("quiet");
  await expect(c.locator(".warn.note")).toHaveText("loud");
  await expect(c.locator("code.mono-sm")).toHaveText("code");
  await expect(c.locator(".tag.added")).toHaveText("new");
  await expect(c.locator(".tag.removed")).toHaveText("gone");
  await expect(c.locator(".tag:not(.added):not(.removed)")).toHaveText("plain");
});
