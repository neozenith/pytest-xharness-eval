import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { Controls } from "@/components/Panels";
import { DEFAULT_FILTERS } from "@/lib/graph";
import { metricById } from "@/lib/metrics";
import { extremeFilters, sampleGraph } from "@/stories/fixtures";

/**
 * Rendered inside the same `<aside className="left">` (with its heading) `App.tsx`
 * places it in, so the panel background, padding and heading style are real, not
 * story chrome.
 */
const meta = {
  title: "Panels/Controls",
  component: Controls,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <aside className="left" aria-labelledby="controls-heading" style={{ width: 280 }}>
        <h2 id="controls-heading" className="panel-heading">
          Controls
        </h2>
        <Story />
      </aside>
    ),
  ],
  args: {
    graph: sampleGraph,
    onLevel: fn(),
    onMetric: fn(),
    onLayout: fn(),
    onFilters: fn(),
  },
} satisfies Meta<typeof Controls>;

export default meta;
type Story = StoryObj<typeof meta>;

/** The boundary/metric/layout selectors and the filter inputs at their initial values. */
export const Defaults: Story = {
  args: {
    level: "folder",
    metric: metricById("leverage"),
    layout: "dagre",
    filters: DEFAULT_FILTERS,
  },
};

/** Every range input pushed to its extreme, a language pinned, search filled, orphans hidden. */
export const AtExtremes: Story = {
  args: {
    level: "class",
    metric: metricById("nloc"),
    layout: "grid",
    filters: extremeFilters,
  },
};
