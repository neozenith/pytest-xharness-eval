/**
 * The one global filter on the overview (glossary: `OverviewFilters`, ADR 0042): three facets —
 * skill, harness, model — held in the URL and rippling through the `TokenAccumulationChart`, the
 * `SessionSummaryTable` and the `SessionTable`.
 *
 * It is the *producer* of the filter state, not a consumer, so unlike those three it reads
 * `useRoute()` and writes `replaceRoute()` itself — the same shape as `SessionTable`'s sort and
 * `ChartAxisToggle`. `replace`, not `push`, because a filter refines the page the reader is
 * already on; `OverviewFiltersClear` is the undo.
 *
 * It is *chrome*, not a panel of data, and it is dressed as chrome: the eyebrow heading is the
 * page's eyebrow voice, 12/600/0.5 uppercase in `$muted` — the same spec the `NavSidebar` sets,
 * to the parameter — rather than a `CardTitle`, and there is no `CardHeader`.
 * The three data cards beneath it lead; a control strip that led with them would have pushed the
 * chart most of a fold down the page for a row of buttons.
 *
 * `cells` is always the whole sweep, never the filtered subset: the option list must not shrink
 * or reorder as you filter, so the control never moves under the reader's hand.
 *
 * Nothing in this bar changes size when it lights up, at any width, and four separate rules
 * enforce that because four separate reflows were found here: the always-present `.chip-dot` (a
 * chip is the same width lit or unlit), the always-rendered `OverviewFiltersClear` (hidden, not
 * unmounted, so its 102x28 box is reserved in both states), the sizer inside `OverviewFilterCount`
 * (the sentence's box is as wide unfiltered as filtered, so nothing left of it moves), and the
 * fixed key column (a wrapped chip line starts where every other chip line starts). Measured
 * before and after a chip click at 780/900/940/980/1440: the bar's height and every facet row's
 * y are unchanged, and the clicked chip is still under the pointer that clicked it.
 */
import { useRef } from "react";
import { X } from "lucide-react";
import { Text, XStack, YStack } from "tamagui";
import { El } from "@/components/El";
import { Card } from "@/components/ui/card";
import { facetCount, facetOptions, FACETS, filterCells, toggleFacet } from "@/lib/facets";
import { NO_FACETS, overviewWith, replaceRoute, useRoute, type FacetSelection } from "@/lib/route";
import type { Cell } from "@/lib/types";

/** The kit's control tier: the chips, the clear button and the status line all stand this tall. */
const CONTROL = 28;

export function OverviewFilters({ cells }: { cells: Cell[] }) {
  const route = useRoute();
  const facets = route.view === "overview" ? route.facets : NO_FACETS;
  const anySelected = FACETS.some((facet) => facets[facet] != null);
  /*
   * The bar states its own outcome. "12 of 24 sessions" beside the chips is the one line that
   * makes a filter legible at rest — before the reader has parsed which chips are lit, and
   * without scrolling to the `SessionTable`'s own count two cards below.
   */
  const visible = anySelected ? filterCells(cells, facets).length : cells.length;

  // A filter refines the state rather than replacing it: both sorts and the theme carry through.
  const go = (next: FacetSelection) => replaceRoute(overviewWith(route, { facets: next }));

  /*
   * `OverviewFiltersClear` goes `visibility: hidden` the instant it is used, and a hidden element
   * takes the focus with it — a keyboard reader who cleared the filter was dropped on `<body>`
   * and had to tab back in through the title, the theme toggle and every nav link. Focus is moved
   * to the first chip *before* the state write commits, so the browser never sees a focused node
   * disappear; the chip's DOM node survives the re-render, so the landing is stable.
   */
  const firstChip = useRef<HTMLButtonElement | null>(null);

  /*
   * The rows, resolved before render so the first chip in the bar is identifiable whichever
   * facet it belongs to (`skill` drops out of the bar entirely when every cell's is null).
   *
   * `options` unions the sweep's own values with any *selected* value the sweep does not
   * contain. A stale deeplink (`?skill=__gone__`) is a state the route grammar deliberately
   * round-trips, and without the union it produced the one thing this bar exists to prevent:
   * "0 of 24 sessions" and a clear button, with every chip unlit and nothing on screen naming
   * what was filtering. The extra ones come out selected, with a count of 0, at the end — data
   * options never move.
   */
  const rows = FACETS.map((facet) => {
    const present = facetOptions(cells, facet);
    const extra = (facets[facet] ?? []).filter((value) => !present.includes(value)).sort();
    return { facet, present, options: [...present, ...extra] };
  }).filter((row) => row.options.length > 0);

  return (
    <Card id="OverviewFilters" paddingVertical={14} gap={10}>
      {/*
       * The eyebrow row. It may still wrap — at 640px the status cluster takes a line of its own
       * rather than squeezing the subtitle into a five-line column — but *where* it wraps is now
       * a function of the viewport alone. Every reflow this bar has ever had came from the
       * cluster changing size with the filter state: it gained a 28px button on the first chip
       * click, the row broke, the bar grew 21px, and every facet row slid down out from under
       * the pointer that had just clicked one. The cluster is the same box in both states now —
       * the clear button is always rendered (hidden when idle) and the count reserves its widest
       * sentence — so the break point cannot move, and a click cannot change this bar's height.
       */}
      <XStack paddingHorizontal={20} alignItems="center" minHeight={CONTROL} columnGap={12} rowGap={4} flexWrap="wrap">
        <XStack flex={1} minWidth={0} alignItems="center" flexWrap="wrap" columnGap={10} rowGap={2}>
          {/* The page's eyebrow voice, shared verbatim with the `NavSidebar`'s: 12/600/0.5 uppercase. */}
          <Text
            render="h2"
            color="$muted"
            fontFamily="$body"
            fontSize={12}
            lineHeight={16}
            fontWeight="600"
            letterSpacing={0.5}
            textTransform="uppercase"
            margin={0}
          >
            Filters
            <El name="OverviewFilters" />
          </Text>
          <Text color="$muted" fontFamily="$body" fontSize={12} lineHeight={16} flexShrink={1}>
            narrows the chart and both tables below
          </Text>
        </XStack>
        {/*
         * `marginLeft: auto`, not a flex spacer: an auto margin absorbs the free space of
         * whichever line the cluster lands on, so the count stays set to the right edge on a
         * wrapped line exactly as it is on a shared one.
         */}
        <XStack alignItems="center" columnGap={8} flexShrink={0} marginLeft="auto">
          {/*
           * The undo sits *before* the count, not after it, so the count — the one part of this
           * cluster that is always there — holds the card's right edge in both states and the
           * reserved space for the button falls in the gap, where there is nothing to look at.
           */}
          <button
            type="button"
            id="OverviewFiltersClear"
            className="filter-clear"
            aria-hidden={anySelected ? undefined : true}
            tabIndex={anySelected ? undefined : -1}
            onClick={() => {
              firstChip.current?.focus();
              go(NO_FACETS);
            }}
          >
            <X size={12} aria-hidden />
            clear filters
          </button>
          {/*
           * `role="status"`: this is the one element that states the filter's outcome, and a
           * chip toggle otherwise announced only its own `aria-pressed` — the reader heard
           * "pressed" and never heard that they were now looking at 12 of 24 sessions.
           * `aria-atomic` so the whole sentence is spoken, not the digit that changed.
           */}
          <span id="OverviewFilterCount" className="filter-count tnum" role="status" aria-atomic="true">
            {/* The widest sentence this box can ever hold; it sets the width, and says nothing. */}
            <span className="sizer" aria-hidden>
              {`${cells.length} of ${cells.length} sessions`}
            </span>
            <span>
              {anySelected ? (
                <>
                  <span className="n">{visible}</span>
                  {` of ${cells.length} sessions`}
                </>
              ) : (
                `${cells.length} sessions`
              )}
            </span>
          </span>
        </XStack>
      </XStack>
      <YStack paddingHorizontal={20} gap={6}>
        {rows.map(({ facet, present, options }, rowIndex) => {
          const selected = facets[facet];
          return (
            <XStack key={facet} role="group" aria-label={`filter by ${facet}`} data-facet={facet} alignItems="flex-start" columnGap={6}>
              {/*
               * The facet key recedes: the chips carry the ink, and three quiet keys down the
               * left edge are the rhythm the eye enters each row on. It is a fixed column
               * *outside* the wrapping box for exactly that reason — when it wrapped with the
               * chips, an overflowing chip landed flush against the left edge, 70px out of the
               * chip column, and broke the rhythm the key exists to set. Its line box is the
               * chips' 28px tier, so it sits on their optical centre rather than their top.
               */}
              <Text color="$muted" fontFamily="$body" fontSize={12} lineHeight={CONTROL} fontWeight="600" width={64} flexShrink={0}>
                {facet}
              </Text>
              {/* One wrapping box: every wrapped line starts at the chip column's left edge. */}
              <XStack flex={1} minWidth={0} alignItems="center" flexWrap="wrap" columnGap={6} rowGap={6}>
                {options.map((value, chipIndex) => {
                  const on = selected?.includes(value) ?? false;
                  // The cross-filtered count: what clicking this chip would actually get you,
                  // given the other two facets. Zero is hollowed out but stays clickable — it is
                  // a legal way to reach the empty state, and hiding it would move the row.
                  const count = facetCount(cells, facets, facet, value);
                  return (
                    <button
                      key={value}
                      ref={rowIndex === 0 && chipIndex === 0 ? firstChip : undefined}
                      type="button"
                      className="filter-chip"
                      data-facet={facet}
                      data-value={value}
                      data-on={on ? "true" : undefined}
                      data-empty={count === 0 ? "true" : undefined}
                      aria-pressed={on}
                      onClick={() => go(toggleFacet(facets, facet, value))}
                    >
                      {/*
                       * The selected mark. Always in the DOM at a fixed size and only its opacity
                       * changes, so a chip is the same width lit or unlit and a click never
                       * reflows the row under the pointer that made it — the accent tint alone
                       * had to be read against seven neighbours to be believed.
                       */}
                      <span className="chip-dot" aria-hidden />
                      {value} <span className="muted">{count}</span>
                    </button>
                  );
                })}
                {present.length === 1 && options.length === 1 ? (
                  <Text color="$muted" fontFamily="$body" fontSize={12} lineHeight={CONTROL}>
                    only value in this sweep
                  </Text>
                ) : null}
              </XStack>
            </XStack>
          );
        })}
      </YStack>
    </Card>
  );
}
