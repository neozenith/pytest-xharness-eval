import type { Meta, StoryObj } from "@storybook/react-vite";
import { Legend } from "@/components/Panels";
import { metricById } from "@/lib/metrics";

/** Rendered inside the same `<aside className="left">` (with its heading) `App.tsx` places it in. */
const meta = {
  title: "Panels/Legend",
  component: Legend,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <aside className="left" aria-labelledby="legend-heading" style={{ width: 280 }}>
        <h2 id="legend-heading" className="panel-heading">
          Legend
        </h2>
        <Story />
      </aside>
    ),
  ],
} satisfies Meta<typeof Legend>;

export default meta;
type Story = StoryObj<typeof meta>;

/** The band swatches (shape and colour both encode band) and the uncalibrated-bands caveat. */
export const Leverage: Story = {
  args: { metric: metricById("leverage") },
};

/** A metric whose bands read low/mid/high on a size rather than a caller count. */
export const Lines: Story = {
  args: { metric: metricById("nloc") },
};
