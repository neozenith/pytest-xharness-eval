import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { GraphCanvas } from "@/components/GraphCanvas";
import { DEFAULT_FILTERS } from "@/lib/graph";
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

/** A node pre-selected: the selection ring on the canvas and the "Selected" row in the
 * accessible table both reflect it. */
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
