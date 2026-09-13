import type { Meta, StoryObj } from "@storybook/react-vite";
import { ClusterTable } from "@/components/Panels";
import { DEFAULT_FILTERS } from "@/lib/graph";
import { phiScale } from "@/lib/metrics";
import { sampleGraph, sliceOf } from "@/stories/fixtures";

const roots = sampleGraph.sources.map((s) => s.root);
const fileSlice = sliceOf(sampleGraph, "file");
const classSlice = sliceOf(sampleGraph, "class");

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
    clusters: fileSlice.clusters,
    phiScale: fileSlice.phiScale,
  },
};

/** Class-boundary clusters: two single- or near-empty classes fall below the volume floor
 * and read "not measurable" rather than a number, alongside ones that do clear it. */
export const MixedMeasurability: Story = {
  args: {
    level: "class",
    clusters: classSlice.clusters,
    phiScale: classSlice.phiScale,
  },
};

/**
 * The degenerate case the relative banding has to survive: fewer than three
 * measurable clusters, so there is no distribution to take terciles of. The caption
 * says so and every measured cluster bands the same, rather than the table inventing
 * a spread out of one or two points. Worth a story of its own because it is the
 * branch a real repository with a single dominant package actually lands on.
 */
export const TooFewToRank: Story = {
  args: {
    level: "file",
    clusters: fileSlice.clusters.slice(0, 2),
    phiScale: phiScale(fileSlice.clusters.slice(0, 2).map(([, c]) => c)),
  },
};

/**
 * `phiScale` is built from every cluster at this boundary across the WHOLE graph
 * (`toElements` in lib/graph.ts scales it over `graph.clusters[level]`, not over the
 * `used` set this table's rows are narrowed to), so its `n` can legitimately exceed
 * `clusters.length` once a filter narrows which clusters are actually drawn below.
 * Filtering to typescript at the folder boundary is the fixture's own repro: the
 * graph has 2 measurable folder clusters overall (below the tercile floor, so
 * `cuts` is null) but the filter leaves only "web/app/components" to draw a row
 * for. The caption used to state its count with nothing marking it as a
 * graph-wide figure -- reading as a claim about the one row in the table beneath
 * it, which it was not.
 */
const filteredFolderSlice = sliceOf(sampleGraph, "folder", "leverage", {
  ...DEFAULT_FILTERS,
  langs: ["typescript"],
});
export const TooFewToRankNarrowedByFilter: Story = {
  args: {
    level: "folder",
    clusters: filteredFolderSlice.clusters,
    phiScale: filteredFolderSlice.phiScale,
  },
};
