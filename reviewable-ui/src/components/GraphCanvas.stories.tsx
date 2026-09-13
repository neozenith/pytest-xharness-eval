import type { ElementDefinition } from "cytoscape";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { GraphCanvas } from "@/components/GraphCanvas";
import { DEFAULT_FILTERS } from "@/lib/graph";
import { BAND, sizeFor, type BandKey } from "@/lib/metrics";
import { emptyGraph, hubNode, sampleGraph, sliceOf } from "@/stories/fixtures";

/**
 * Owns a real cytoscape instance, so it needs a sized container -- `App.tsx` gives it
 * `<section className="middle">` inside a 100vh flex column; the story reproduces that
 * with an explicit height instead of relying on the viewport. The canvas itself is
 * `aria-hidden`; the accessible surface is the "view graph as table" toggle beside it,
 * which a11y checks exercise the same as the canvas.
 */
const meta = {
  title: "GraphCanvas",
  component: GraphCanvas,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <section className="middle" aria-labelledby="graph-heading" style={{ height: 480, width: "100%" }}>
        <h2 id="graph-heading" className="sr-only">
          Call graph
        </h2>
        <Story />
      </section>
    ),
  ],
  args: {
    selected: null,
    onSelect: fn(),
  },
} satisfies Meta<typeof GraphCanvas>;

export default meta;
type Story = StoryObj<typeof meta>;

/** File-boundary clusters, dagre layout: the default the app opens with. */
export const Small: Story = {
  args: {
    elements: sliceOf(sampleGraph, "file", "leverage", DEFAULT_FILTERS).elements,
    layout: "dagre",
  },
};

/** Class-boundary clusters, cose layout, coloured by lines instead of leverage. */
export const ClassBoundaryCose: Story = {
  args: {
    elements: sliceOf(sampleGraph, "class", "nloc", DEFAULT_FILTERS).elements,
    layout: "cose",
  },
};

/**
 * A node pre-selected: the selection ring on the canvas and the "Selected" row in the
 * accessible table both reflect it. `hubNode` (`Loader.run`) has 0 callers and 3
 * callees in this fixture, and `useWidget`/`format_label` elsewhere in the same table
 * carry different Callers/Callees counts -- so this one story already exercises both
 * the dual-tone selection ring (border+outline, WCAG 1.4.11) and non-uniform data in
 * the two edge-count columns, without needing separate stories for each.
 */
export const WithSelection: Story = {
  args: {
    elements: sliceOf(sampleGraph, "file", "leverage", DEFAULT_FILTERS).elements,
    layout: "dagre",
    selected: hubNode.id,
  },
};

/** No graph loaded yet, or every node filtered out: an empty canvas, not an error. */
export const Empty: Story = {
  args: {
    elements: sliceOf(emptyGraph, "file", "leverage", DEFAULT_FILTERS).elements,
    layout: "grid",
  },
};

/**
 * A chain of 40 definitions, hand-built here rather than drawn from
 * `@/stories/fixtures` (whose ten-node graph is sized for hand-verified metrics, not
 * for exercising the table at scale). This is the state the roving-tabindex fix
 * targets: only one Select button is a natural Tab stop; Arrow Up/Down/Home/End move
 * focus between the rest. A story cannot script key presses (no play function is used
 * anywhere in this file), so the interaction itself is pinned in
 * `e2e/canvas.spec.ts` -- this story exists so the "40 rows, one band each" table
 * layout itself has a rendered state to check by eye.
 */
const manyRowElements: ElementDefinition[] = (() => {
  const bands: BandKey[] = ["low", "mid", "high", "none"];
  const nodes: ElementDefinition[] = Array.from({ length: 40 }, (_, i) => {
    const band = bands[i % bands.length]!;
    return {
      data: {
        id: `n${i}`,
        parent: "C::chain",
        label: `definition_${i}`,
        kind: "def",
        band,
        colour: BAND[band],
        size: sizeFor(i, 40),
        value: i,
      },
    };
  });
  const edges: ElementDefinition[] = Array.from({ length: 39 }, (_, i) => ({
    data: { id: `n${i}->n${i + 1}`, source: `n${i}`, target: `n${i + 1}`, sites: 1 },
  }));
  return [
    { data: { id: "C::chain", label: "chain", kind: "cluster", phi: 0, band: "none", tint: BAND.none } },
    ...nodes,
    ...edges,
  ];
})();

export const ManyRows: Story = {
  args: {
    elements: manyRowElements,
    layout: "dagre",
  },
};

/**
 * `App.tsx` gives `.graph-panel` whatever height is left in a 100vh column, and
 * opening "View graph as table" shrinks `.canvas` further still (it is `flex: 1`
 * against a sibling that claims up to `max-height: 42%`) -- in the real app this can
 * leave the canvas well under half the height every other story here renders at. A
 * story cannot script the shrink-after-mount itself (no play function, per this
 * file's convention -- that half of the fix, the `ResizeObserver`, is pinned
 * dynamically in `e2e/graph-table-canvas.spec.ts`), but it can render at a
 * constrained height from the start the same way `App.tsx` can hand the component on
 * a small viewport or with the table already open. This is the visual check for the
 * other half of the fix: `.canvas{overflow:hidden}` (styles.css) keeps whatever
 * cytoscape draws clipped to this box's edge rather than spilling past it, at any
 * height -- not just the generous one the other stories use.
 */
export const ShortContainer: Story = {
  decorators: [
    (Story) => (
      <section className="middle" aria-labelledby="short-graph-heading" style={{ height: 160, width: "100%" }}>
        <h2 id="short-graph-heading" className="sr-only">
          Call graph
        </h2>
        <Story />
      </section>
    ),
  ],
  args: {
    elements: sliceOf(sampleGraph, "file", "leverage", DEFAULT_FILTERS).elements,
    layout: "dagre",
  },
};
