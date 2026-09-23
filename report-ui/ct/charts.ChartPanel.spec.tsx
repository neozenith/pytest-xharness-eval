/** The frame every chart sits in: glossary id on the root, the name beside the heading, an optional note. */
import { expect, test } from "@playwright/experimental-ct-react";
import { ChartPanel } from "../src/components/charts/common";

test.describe("ChartPanel", () => {
  test("a section carrying the glossary id, its title and the El name", async ({ mount }) => {
    const c = await mount(
      <ChartPanel id="SomeChart" title="Some title" note="Some note.">
        <div id="body">chart body</div>
      </ChartPanel>,
    );
    const section = c.locator("section#SomeChart");
    await expect(section).toHaveAttribute("data-el", "SomeChart");
    await expect(section).toContainText("Some title");
    await expect(section.locator(".el")).toHaveText("SomeChart");
    await expect(section).toContainText("Some note.");
    await expect(section.locator("#body")).toHaveText("chart body");
  });

  test("the title sits above the note, and the body below both", async ({ mount }) => {
    const c = await mount(
      <ChartPanel id="P" title="Heading" note="Explains it">
        <div id="body" style={{ height: 40 }}>
          body
        </div>
      </ChartPanel>,
    );
    const title = (await c.getByText("Heading").boundingBox())!;
    const note = (await c.getByText("Explains it").boundingBox())!;
    const body = (await c.locator("#body").boundingBox())!;
    expect(title.y).toBeLessThan(note.y);
    expect(note.y + note.height).toBeLessThanOrEqual(body.y);
  });

  test("without a note, no description is rendered", async ({ mount }) => {
    const c = await mount(
      <ChartPanel id="P" title="Only a title">
        <span>x</span>
      </ChartPanel>,
    );
    await expect(c.locator("section#P")).toHaveText(/^Only a titleP\s*x$/);
  });

  test("a rich note keeps its markup", async ({ mount }) => {
    const c = await mount(
      <ChartPanel
        id="P"
        title="T"
        note={
          <span id="n">
            Peak <b>12%</b>
          </span>
        }
      >
        <span>x</span>
      </ChartPanel>,
    );
    await expect(c.locator("#n b")).toHaveText("12%");
  });
});
