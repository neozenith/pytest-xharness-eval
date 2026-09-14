import type { Meta, StoryObj } from "@storybook/react-vite";
import { BandCaveat } from "@/components/Panels";

/**
 * The caveat that the bands rank rather than grade.
 *
 * It is its own component, and its own story, because of where it is *not*: it used to
 * sit at the foot of the legend inside `aside.left`, which scrolls. Finding #3 of the
 * design review is that a claim this load-bearing cannot live somewhere the reader may
 * never reach. It now renders in the main column, directly above the canvas, on `--bg`.
 */
const meta = {
  title: "Panels/BandCaveat",
  component: BandCaveat,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <div className="graph-status" style={{ maxWidth: 640 }}>
        <p className="note">showing 10 of 10</p>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof BandCaveat>;

export default meta;
type Story = StoryObj<typeof meta>;

/** As the app renders it: beneath the slice count, above the canvas. */
export const InTheStatusStrip: Story = {};
