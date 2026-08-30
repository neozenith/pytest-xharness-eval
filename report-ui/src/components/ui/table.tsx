/**
 * Semantic HTML tables styled by `index.css` (`.xh-table`). Real `<table>` markup stays —
 * tabular data wants the browser's table semantics — and the cells accept the stylesheet's
 * class vocabulary (`num`, `key`, `strong`) through `className`.
 */
import * as React from "react";

import { cn } from "@/lib/utils";

/**
 * Flag which horizontal edges of a scroll box are actually clipping, as `data-edge-start` /
 * `data-edge-end`. `.table-scroll` in index.css fades the content out on exactly those sides,
 * so a table that fits keeps every glyph at full strength and one that does not can never
 * show a half-cut number as if it were whole. It has to be measured: the equivalent
 * background trick relies on `background-attachment: local`, and masks have no attachment.
 */
function useClippedEdges<T extends HTMLElement>(focusable: boolean) {
  const ref = React.useRef<T>(null);
  React.useEffect(() => {
    const box = ref.current;
    if (!box) return;
    const measure = () => {
      // A pixel of slack: sub-pixel layout leaves a fraction of overflow on tables that fit.
      const overflow = box.scrollWidth - box.clientWidth;
      const remaining = overflow - box.scrollLeft;
      box.dataset.edgeStart = String(box.scrollLeft > 1);
      box.dataset.edgeEnd = String(remaining > 1);
      /*
       * The tab stop is *measured*, not declared: a box wide enough for its table has nothing
       * to scroll and must not cost the reader a Tab press to walk past. It appears the moment
       * the same measurement says columns are clipped.
       */
      if (focusable) box.tabIndex = overflow > 1 ? 0 : -1;
    };
    measure();
    box.addEventListener("scroll", measure, { passive: true });
    // The table's own width changes when a detail row opens, which the box's size may not.
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(measure) : undefined;
    observer?.observe(box);
    for (const child of box.children) observer?.observe(child);
    return () => {
      box.removeEventListener("scroll", measure);
      observer?.disconnect();
    };
  }, [focusable]);
  return ref;
}

/**
 * `scrollLabel` makes the scroll box itself keyboard-operable, and is required of any table
 * whose rows hold nothing focusable: without it the columns past the clipped right edge can
 * only be reached with a pointer (WCAG 2.1.1). `SessionTable` does not need it — every row is
 * a tab stop, so arrowing down the table scrolls it — but `SessionSummaryTable`, a pure
 * readout, has no focusable descendant at all.
 */
function Table({ className, scrollLabel, ...props }: React.ComponentProps<"table"> & { scrollLabel?: string }) {
  const box = useClippedEdges<HTMLDivElement>(scrollLabel != null);
  const scroller = (
    <div ref={box} data-slot="table-container" className="table-scroll" role={scrollLabel ? "region" : undefined} aria-label={scrollLabel}>
      <table data-slot="table" className={cn("xh-table", className)} {...props} />
    </div>
  );
  /*
   * The focus ring cannot be drawn on the scroll box itself: that box masks its own left and
   * right edges to fade clipped content out, and a mask takes the outline with it — the ring
   * came out as two disconnected horizontal rules. So a focusable box gets one unmasked
   * wrapper whose only job is to carry the ring (`.table-scroll-ring` in index.css).
   */
  return scrollLabel ? <div className="table-scroll-ring">{scroller}</div> : scroller;
}

const TableHeader = (props: React.ComponentProps<"thead">) => <thead data-slot="table-header" {...props} />;
const TableBody = (props: React.ComponentProps<"tbody">) => <tbody data-slot="table-body" {...props} />;
const TableFooter = (props: React.ComponentProps<"tfoot">) => <tfoot data-slot="table-footer" {...props} />;
const TableRow = (props: React.ComponentProps<"tr">) => <tr data-slot="table-row" {...props} />;
const TableHead = (props: React.ComponentProps<"th">) => <th data-slot="table-head" {...props} />;
const TableCell = (props: React.ComponentProps<"td">) => <td data-slot="table-cell" {...props} />;
const TableCaption = (props: React.ComponentProps<"caption">) => <caption data-slot="table-caption" {...props} />;

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption };
