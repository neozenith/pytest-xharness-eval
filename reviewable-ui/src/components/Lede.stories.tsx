import type { Meta, StoryObj } from "@storybook/react-vite";
import { fn } from "storybook/test";
import { Lede } from "@/components/Panels";
import { DEFAULT_FILTERS } from "@/lib/graph";
import { sampleGraph, sliceOf } from "@/stories/fixtures";

/**
 * The header's one-line answer to "what am I looking at", rendered inside the same
 * `<header>` `App.tsx` places it in so its contrast is measured against `--panel`.
 *
 * Its whole job is finding #8 of the design review: the landing view used to be a
 * hairball and six dropdowns, answering nothing until you already knew what to ask.
 */
const fileSlice = sliceOf(sampleGraph, "file");

const meta = {
  title: "Panels/Lede",
  component: Lede,
  tags: ["autodocs"],
  decorators: [
    (Story) => (
      <header style={{ maxWidth: 900 }}>
        <h1>reviewable</h1>
        <Story />
      </header>
    ),
  ],
  args: {
    graph: sampleGraph,
    onSelect: fn(),
    // Every existing story is the unfiltered, uncapped view: everything survives,
    // so `shown`/`total` agree and `visibleIds`/`keptIds` hold every node id. Round
    // 3's finding was that these were the ONLY states any test ever exercised --
    // the three stories below this file's original four are what closes that gap.
    shown: fileSlice.shown,
    total: fileSlice.total,
    visibleIds: fileSlice.visibleIds,
    keptIds: fileSlice.keptIds,
  },
} satisfies Meta<typeof Lede>;

export default meta;
type Story = StoryObj<typeof meta>;

/** The file boundary, where the fixture's clusters genuinely differ (phi 0 / 0.2 / 0.333). */
export const FileBoundary: Story = {
  args: { level: "file", clusters: fileSlice.clusters },
};

/** The class boundary: two of the five clusters are below the volume floor and unmeasurable. */
export const ClassBoundary: Story = {
  args: { level: "class", clusters: sliceOf(sampleGraph, "class").clusters },
};

/**
 * A tie. Both folder clusters sit at phi 0, so the lede says so rather than naming a
 * "least" and a "most" -- which would be a ranking invented out of a tie.
 */
export const FlatDistribution: Story = {
  args: { level: "folder", clusters: sliceOf(sampleGraph, "folder").clusters },
};

/** No measurable cluster at all: the lede drops the conductance sentence entirely. */
export const NoMeasurableClusters: Story = {
  args: { level: "file", clusters: [] },
};

/**
 * Exactly one measurable cluster: filtering to typescript at the class boundary
 * leaves `Widget.tsx::Widget` (phi 0.6) as the only measurable cluster -- its
 * sibling `Widget.tsx::<module>` cluster is below the volume floor (phi null).
 * `lo` and `hi` are the same array entry when `measured.length === 1`, and the
 * flat-distribution branch used to compare that entry to itself and report a tie
 * -- "All 1 measurable class cluster drawn share the same conductance ... between
 * them" -- describing a population of one as a draw between two. This is the
 * screenshot in docs/plans/maintainability/img/reviewable-lede-off-slice.png.
 * `top` is excluded by the same language filter here too (see
 * TopExcludedByFilter below) -- expected, and not what this story is pinning.
 */
const soloClusterSlice = sliceOf(sampleGraph, "class", "leverage", {
  ...DEFAULT_FILTERS,
  langs: ["typescript"],
});
export const SingleMeasurableCluster: Story = {
  args: {
    level: "class",
    clusters: soloClusterSlice.clusters,
    shown: soloClusterSlice.shown,
    total: soloClusterSlice.total,
    visibleIds: soloClusterSlice.visibleIds,
    keptIds: soloClusterSlice.keptIds,
  },
};

/**
 * Design-review round 3, finding #1: `top` (the most-called definition) is picked
 * from the whole graph, not the current slice, so a language filter that excludes it
 * must not read as if nothing changed. `parse_config` is this graph's top by
 * leverage and is python; pinning the filter to typescript only reproduces the
 * reviewer's exact repro (untick the language TargetFn/parse_config belongs to).
 */
const filteredSlice = sliceOf(sampleGraph, "file", "leverage", {
  ...DEFAULT_FILTERS,
  langs: ["typescript"],
});
export const TopExcludedByFilter: Story = {
  args: {
    level: "file",
    clusters: filteredSlice.clusters,
    shown: filteredSlice.shown,
    total: filteredSlice.total,
    visibleIds: filteredSlice.visibleIds,
    keptIds: filteredSlice.keptIds,
  },
};

/**
 * Same definition, excluded by the node cap instead of a filter -- a different
 * remedy ("raise the cap", not "clear a filter"), which is the entire reason
 * `OffSlice` is a union rather than a boolean. Colouring by `nloc` instead of
 * `leverage` is what makes this reachable at all: ranked by its own leverage,
 * `parse_config` is always near the top of the cap, so the cap has to bite on a
 * metric it does not lead.
 */
const cappedSlice = sliceOf(sampleGraph, "file", "nloc", {
  ...DEFAULT_FILTERS,
  limit: 3,
});
export const TopExcludedByCap: Story = {
  args: {
    level: "file",
    clusters: cappedSlice.clusters,
    shown: cappedSlice.shown,
    total: cappedSlice.total,
    visibleIds: cappedSlice.visibleIds,
    keptIds: cappedSlice.keptIds,
  },
};

/**
 * Zero definitions survive the current view -- the reviewer's other repro (search
 * for a string nothing matches). Before this fix the lede still asserted a
 * confident "N callers, M call sites" here; the empty-graph screen refuses that
 * exact move at the whole-app level ("arithmetic over an empty set, not findings"),
 * and this is the same refusal one component down.
 */
const emptySlice = sliceOf(sampleGraph, "file", "leverage", {
  ...DEFAULT_FILTERS,
  search: "zzznomatchxyz",
});
export const EmptySlice: Story = {
  args: {
    level: "file",
    clusters: emptySlice.clusters,
    shown: emptySlice.shown,
    total: emptySlice.total,
    visibleIds: emptySlice.visibleIds,
    keptIds: emptySlice.keptIds,
  },
};
