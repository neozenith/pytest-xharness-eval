import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { Detail } from "@/components/Panels";
import { calledNode, hubNode, orphanNode, sampleGraph } from "@/stories/fixtures";

/** Rendered inside the same `<aside className="right">` (with its heading) `App.tsx` places it in. */
const meta = {
  title: "Panels/Detail",
  component: Detail,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <aside className="right" aria-labelledby="inspector-heading" style={{ width: 320 }}>
        <h2 id="inspector-heading" className="sr-only">
          Inspector
        </h2>
        <Story />
      </aside>
    ),
  ],
  args: {
    graph: sampleGraph,
    onSelect: fn(),
  },
} satisfies Meta<typeof Detail>;

export default meta;
type Story = StoryObj<typeof meta>;

/** Nothing tapped yet: the prompt copy, not a blank panel. */
export const NoSelection: Story = {
  args: { node: null },
};

/** A hub: calls three other definitions, is called by none. Every "Calls" row is a button. */
export const Hub: Story = {
  args: { node: hubNode },
};

/** Called from two places, calls out to nothing -- both lists render, one of them empty. */
export const Called: Story = {
  args: { node: calledNode },
};

/** A true orphan: no caller and no callee in the graph. Both "Called by" and "Calls" read (0). */
export const Orphan: Story = {
  args: { node: orphanNode },
};
