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
function useClippedEdges<T extends HTMLElement>() {
  const ref = React.useRef<T>(null);
  React.useEffect(() => {
    const box = ref.current;
    if (!box) return;
    const measure = () => {
      // A pixel of slack: sub-pixel layout leaves a fraction of overflow on tables that fit.
      const remaining = box.scrollWidth - box.clientWidth - box.scrollLeft;
      box.dataset.edgeStart = String(box.scrollLeft > 1);
      box.dataset.edgeEnd = String(remaining > 1);
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
  }, []);
  return ref;
}

function Table({ className, ...props }: React.ComponentProps<"table">) {
  const box = useClippedEdges<HTMLDivElement>();
  return (
    <div ref={box} data-slot="table-container" className="table-scroll">
      <table data-slot="table" className={cn("xh-table", className)} {...props} />
    </div>
  );
}

const TableHeader = (props: React.ComponentProps<"thead">) => <thead data-slot="table-header" {...props} />;
const TableBody = (props: React.ComponentProps<"tbody">) => <tbody data-slot="table-body" {...props} />;
const TableFooter = (props: React.ComponentProps<"tfoot">) => <tfoot data-slot="table-footer" {...props} />;
const TableRow = (props: React.ComponentProps<"tr">) => <tr data-slot="table-row" {...props} />;
const TableHead = (props: React.ComponentProps<"th">) => <th data-slot="table-head" {...props} />;
const TableCell = (props: React.ComponentProps<"td">) => <td data-slot="table-cell" {...props} />;
const TableCaption = (props: React.ComponentProps<"caption">) => <caption data-slot="table-caption" {...props} />;

export { Table, TableHeader, TableBody, TableFooter, TableHead, TableRow, TableCell, TableCaption };
