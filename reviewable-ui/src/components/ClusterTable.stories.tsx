import type { Meta, StoryObj } from "@storybook/react-vite";
import { ClusterTable } from "@/components/Panels";
import { sampleGraph, sliceOf } from "@/stories/fixtures";

const roots = sampleGraph.sources.map((s) => s.root);

/**
 * Rendered inside the same `<aside className="right">`, after the same `<h3
 * className="panel-heading">` caption, `App.tsx` places it behind.
 */
const meta = {
  title: "Panels/ClusterTable",
  component: ClusterTable,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <aside className="right" style={{ width: 320 }}>
        <h3 className="panel-heading">Clusters at this boundary</h3>
        <Story />
      </aside>
    ),
  ],
  args: {
    roots,
  },
} satisfies Meta<typeof ClusterTable>;

export default meta;
type Story = StoryObj<typeof meta>;

/** File-boundary clusters: every one here clears the volume floor, phi spans low to mid. */
export const Measurable: Story = {
  args: {
    level: "file",
    clusters: sliceOf(sampleGraph, "file").clusters,
  },
};

/** Class-boundary clusters: two single- or near-empty classes fall below the volume floor
 * and read "not measurable" rather than a number, alongside ones that do clear it. */
export const MixedMeasurability: Story = {
  args: {
    level: "class",
    clusters: sliceOf(sampleGraph, "class").clusters,
  },
};
