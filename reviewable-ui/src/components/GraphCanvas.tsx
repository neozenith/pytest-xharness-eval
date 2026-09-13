/** The cytoscape canvas. Owns the instance; React owns only the container and the props. */
import {
  type KeyboardEvent,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import cytoscape, {
  type Core,
  type ElementDefinition,
  type LayoutOptions,
  type NodeSingular,
} from "cytoscape";
import dagre from "cytoscape-dagre";
import { BAND, BAND_SHAPE, type BandKey } from "@/lib/metrics";

cytoscape.use(dagre);

/**
 * None of these layouts animate. That is deliberate, not incidental: it is how this
 * component honours `prefers-reduced-motion` without needing to branch on it, since a
 * layout that never moves anything after it settles has nothing to reduce.
 */
const LAYOUTS: Record<string, LayoutOptions> = {
  dagre: {
    name: "dagre",
    rankDir: "LR",
    nodeSep: 16,
    rankSep: 90,
    padding: 20,
    animate: false,
  } as LayoutOptions,
  cose: {
    name: "cose",
    idealEdgeLength: 90,
    nodeRepulsion: 9000,
    padding: 20,
    animate: false,
  } as LayoutOptions,
  concentric: {
    name: "concentric",
    minNodeSpacing: 24,
    padding: 20,
    animate: false,
  } as LayoutOptions,
  grid: { name: "grid", padding: 20, animate: false } as LayoutOptions,
};

export interface GraphCanvasProps {
  elements: ElementDefinition[];
  layout: string;
  /**
   * The selected node id, or null. Drives both the selection ring and the
   * neighbourhood dim. Required, not optional: `null` and "not passed" would render
   * identically, so an optional prop would let a caller silently lose selection
   * rather than be told to decide.
   */
  selected: string | null;
  onSelect: (id: string | null) => void;
}

const bandOf = (ele: NodeSingular): BandKey => ele.data("band") as BandKey;

/**
 * A stylesheet built once. Node fill comes from `data(colour)` because it encodes a
 * metric band, not a theme; the chrome around it is CSS and re-skins freely.
 *
 * Band is never carried by colour alone (WCAG 1.4.1): shape is the second channel for a
 * definition's band (`BAND_SHAPE`), and border style/width is the second channel for a
 * cluster's conductance band.
 */
const STYLE: cytoscape.StylesheetJson = [
  {
    selector: "node[kind = 'def']",
    style: {
      "background-color": "data(colour)",
      shape: (ele) => BAND_SHAPE[bandOf(ele)] as cytoscape.Css.NodeShape,
      width: "data(size)",
      height: "data(size)",
      label: "data(label)",
      "font-size": "9px",
      color: "#e2e8f0",
      "text-outline-width": 2,
      "text-outline-color": "#0f172a",
      "text-valign": "center",
      "text-halign": "center",
      "text-max-width": "90px",
      "text-wrap": "ellipsis",
      "border-width": 1,
      "border-color": "#0f172a",
    },
  },
  {
    selector: ":parent",
    style: {
      "background-color": "data(tint)",
      "background-opacity": 0.1,
      "border-width": (ele) =>
        ({ low: 1.5, mid: 2, high: 2.5, none: 1 })[bandOf(ele)],
      "border-style": (ele) =>
        ({
          low: "dashed",
          mid: "dotted",
          high: "solid",
          none: "dashed",
        })[bandOf(ele)] as cytoscape.Css.LineStyle,
      "border-color": "data(tint)",
      label: "data(label)",
      "font-size": "11px",
      "font-weight": 600,
      color: "#cbd5e1",
      "text-valign": "top",
      "text-halign": "center",
      "text-margin-y": -4,
      // A cluster label is a path tail ("pkg_a/handlers"), not a short identifier, and
      // cytoscape draws label text with no box to be constrained by: without these two
      // it runs past the compound's own border and over whatever is drawn beside it.
      // The leaf selector above has carried them since it was written; the parent
      // selector inherits nothing from it, so "already handled" was never true here.
      "text-max-width": "180px",
      "text-wrap": "ellipsis",
      padding: "16px",
      shape: "round-rectangle",
    },
  },
  {
    selector: "edge",
    style: {
      "curve-style": "bezier",
      "line-color": "#64748b",
      width: "mapData(sites, 1, 6, 0.8, 3.5)",
      "target-arrow-shape": "triangle",
      "target-arrow-color": "#64748b",
      "arrow-scale": 0.7,
      opacity: 0.75,
    },
  },
  {
    /*
     * Two rings, not one (WCAG 1.4.11). A single facc15 border used to be the whole
     * selection indicator, and facc15 is bright for the same reason every BAND fill
     * is bright: the AAA text-contrast floor in metrics.ts pins every swatch above
     * L*~68. Measured (tmp/selection_ring_contrast.ts): facc15-on-band-fill contrast
     * ranged 1.10-1.39:1 across all four bands, not just the obviously-similar
     * "high" one -- a selection ring that was nearly invisible on every node it could
     * ever be drawn on, on the one canvas element sighted low-vision users actually
     * read state from. The dark inner border reproduces the huge fill contrast every
     * unselected node already gets "for free" (its own dark, unselected border is
     * the same colour); the bright outline sits outside it and gets its contrast
     * from the canvas background instead. Whichever surface a viewer's eye lands on
     * -- node fill or canvas background -- one of the two rings clears 3:1 there.
     */
    selector: "node:selected",
    style: {
      "border-width": 3,
      "border-color": "#0f172a",
      "outline-width": 3,
      "outline-color": "#facc15",
      "outline-style": "solid",
      "outline-offset": 0,
    },
  },
  { selector: ".faded", style: { opacity: 0.08 } },
  {
    selector: ".hot",
    style: {
      opacity: 1,
      "line-color": "#facc15",
      "target-arrow-color": "#facc15",
    },
  },
];

/** Dim everything not in `id`'s closed neighbourhood; clear the dim when `id` is null. */
const applyNeighbourhood = (cy: Core, id: string | null): void => {
  cy.elements().removeClass("faded hot");
  if (!id) return;
  const node = cy.getElementById(id);
  if (!node.length) return;
  const keep = node.closedNeighborhood();
  cy.elements().difference(keep).addClass("faded");
  keep.edges().addClass("hot");
};

/** Sync cytoscape's own `:selected` state to the app's `selected` id, whatever set it. */
const applySelection = (cy: Core, id: string | null): void => {
  cy.elements(":selected").unselect();
  if (!id) return;
  const node = cy.getElementById(id);
  if (node.length) node.select();
};

/**
 * One row of the text alternative to the canvas: a definition, as data.
 *
 * `callers`/`callees` are the second half of that alternative. A sighted reader
 * gets a definition's in/out edges for free -- arrows drawn straight at it -- but
 * the table used to stop at the node's own attributes and never mention edges at
 * all, which is not "the same nodes, same band, same value" the comment above the
 * table claims: it was the same nodes with the connections quietly dropped. Both
 * counts are scoped to THIS slice (the edges actually drawn), matching what the
 * canvas itself is showing rather than the whole graph's totals.
 */
interface DefRow {
  id: string;
  label: string;
  cluster: string;
  band: BandKey;
  value: number;
  callers: number;
  callees: number;
}

/** An edge element as `toElements` (lib/graph.ts) shapes it; nodes carry no `source`. */
const isEdge = (e: ElementDefinition): e is ElementDefinition & { data: { source: string; target: string } } =>
  typeof e.data.source === "string" && typeof e.data.target === "string";

const defRows = (elements: ElementDefinition[]): DefRow[] => {
  const callersOf = new Map<string, number>();
  const calleesOf = new Map<string, number>();
  for (const e of elements) {
    if (!isEdge(e)) continue;
    calleesOf.set(e.data.source, (calleesOf.get(e.data.source) ?? 0) + 1);
    callersOf.set(e.data.target, (callersOf.get(e.data.target) ?? 0) + 1);
  }
  return elements
    .filter((e) => e.data.kind === "def")
    .map((e) => {
      const id = e.data.id as string;
      return {
        id,
        label: (e.data.label as string | undefined) ?? id,
        cluster: ((e.data.parent as string | undefined) ?? "").replace(
          /^C::/,
          "",
        ),
        band: e.data.band as BandKey,
        value: (e.data.value as number | undefined) ?? 0,
        callers: callersOf.get(id) ?? 0,
        callees: calleesOf.get(id) ?? 0,
      };
    });
};

const BAND_WORD: Record<BandKey, string> = {
  low: "low band",
  mid: "mid band",
  high: "high band",
  none: "no callers",
};

export const GraphCanvas = ({
  elements,
  layout,
  selected = null,
  onSelect,
}: GraphCanvasProps) => {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);
  const selectedRef = useRef<string | null>(selected);
  const [showTable, setShowTable] = useState(false);
  // The zoom/pan an automatic `fit()` last left the viewport at -- read back from
  // cytoscape immediately after that `fit()`, not recomputed. Comparing a *later*
  // read of `zoom()`/`pan()` against this exact pair is how the resize handler
  // below tells "the user hasn't touched the viewport since" from "they have":
  // nothing sits between a `fit()` and this read that could change either value,
  // so if a later read still matches, cytoscape's own state says no pan or zoom
  // gesture happened in between. Null means no automatic fit has ever run yet
  // (still mid-mount, before the first layout settles).
  const lastAutoFitRef = useRef<{ zoom: number; pan: { x: number; y: number } } | null>(
    null,
  );

  useEffect(() => {
    selectedRef.current = selected;
  }, [selected]);

  useEffect(() => {
    if (!box.current) return;
    const instance = cytoscape({
      container: box.current,
      style: STYLE,
      wheelSensitivity: 0.2,
      maxZoom: 3,
      minZoom: 0.05,
    });
    cy.current = instance;
    instance.on("tap", "node[kind = 'def']", (evt) =>
      onSelect(evt.target.id() as string),
    );
    instance.on("tap", (evt) => {
      if (evt.target === instance) onSelect(null);
    });

    // `.graph-panel` is a column flexbox (styles.css), so opening the accessible
    // table beneath this container (a sibling, not a child) shrinks `.canvas`
    // well after mount -- and cytoscape's own layered <canvas> elements are sized
    // in absolute pixels at mount time, not "100%". Cytoscape ships its own
    // ResizeObserver on this same container (see cytoscape's
    // extensions/renderer/base/load-listeners.mjs), but it is debounced 100ms and,
    // more importantly, only ever calls `resize()` -- never `fit()` -- so even once
    // it fires, the pan/zoom stays calibrated to the box that no longer exists:
    // the same world-to-screen transform now draws into a shorter buffer, which
    // silently clips whatever no longer fits rather than reframing it. `.canvas`'s
    // own `overflow: hidden` (styles.css) is a first line of defence against the
    // symptom -- it keeps a stale, still-tall canvas layer from *painting* over
    // `.graph-table-wrap` and its Select buttons -- but it does nothing for the
    // layer's own pixel dimensions or hit-testing, which stay wrong until
    // something calls `resize()`. Reacting here, undebounced, closes both gaps:
    // `resize()` keeps the drawing buffer (and click coordinates) honest
    // immediately, rather than for up to 100ms after the CSS clip already hid the
    // symptom, and `fit()` (not a full layout rerun: the graph itself hasn't
    // changed, only the box around it) reframes the *same* node positions into
    // the new box the same way the effect below already does after every layout
    // run -- but only when nothing has moved the viewport since that automatic
    // fit ran. Calling `fit()` unconditionally on every resize -- including a
    // resize the user caused by toggling the accessible table, or by resizing
    // the browser window -- silently threw away a manual pan or zoom on every
    // one of those, which is the same "state a number/framing more confidently
    // than the interaction supports" failure this codebase's own comments call
    // out elsewhere, one level down from prose into the viewport itself. `resize()`
    // still always runs: the drawing buffer must stay correct regardless of
    // whether `fit()` also runs. Detecting "did the user do something" by reading
    // cytoscape's own DOM/gesture events was ruled out -- `node_modules/cytoscape`
    // ships only a bundled `dist/`, no readable `src/`, so which internal events
    // fire for a programmatic vs. a user-driven pan/zoom cannot be confirmed by
    // reading the library. Comparing the exact zoom/pan cytoscape reports now
    // against the exact pair `lastAutoFitRef` recorded right after the last
    // automatic `fit()` needs no such introspection: nothing but a user gesture
    // (or another `fit()`/`pan()`/`zoom()` call, and this file makes none besides
    // the two already tracked here) sits between those two reads.
    const observer = new ResizeObserver(() => {
      instance.resize();
      const last = lastAutoFitRef.current;
      const untouchedSinceLastFit =
        last === null ||
        (instance.zoom() === last.zoom &&
          instance.pan().x === last.pan.x &&
          instance.pan().y === last.pan.y);
      if (untouchedSinceLastFit) {
        instance.fit(undefined, 30);
        lastAutoFitRef.current = { zoom: instance.zoom(), pan: { ...instance.pan() } };
      }
    });
    observer.observe(box.current);

    return () => {
      observer.disconnect();
      instance.destroy();
      cy.current = null;
    };
  }, [onSelect]);

  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    c.batch(() => {
      c.elements().remove();
      c.add(elements);
    });
    // Fit AFTER the layout settles. cose is iterative, so fitting straight after
    // run() frames an intermediate state and the canvas renders as one flat fill.
    const run = c.layout(LAYOUTS[layout] ?? LAYOUTS.dagre!);
    run.one("layoutstop", () => {
      c.fit(undefined, 30);
      // Recorded so the ResizeObserver above can tell a resize-triggered `fit()`
      // apart from one that would discard a pan/zoom the user set up since this
      // layout ran -- see that observer's own comment for why an exact read-back,
      // rather than a gesture listener, is what it compares against.
      lastAutoFitRef.current = { zoom: c.zoom(), pan: { ...c.pan() } };
      // A rebuild (new filters, new metric, new boundary) drops cytoscape's own
      // selection and neighbourhood classes even when the app's `selected` id is
      // unchanged, so both are re-applied from the latest value here.
      applySelection(c, selectedRef.current);
      applyNeighbourhood(c, selectedRef.current);
    });
    run.run();
  }, [elements, layout]);

  // The two concerns a plain click already gets for free (cytoscape re-applies its own
  // `:selected` pseudo-class on tap); this makes both work identically when selection
  // instead arrives from the keyboard-operable table below.
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    applySelection(c, selected);
  }, [selected]);
  useEffect(() => {
    const c = cy.current;
    if (!c) return;
    applyNeighbourhood(c, selected);
  }, [selected]);

  // Filters, metric and boundary changes all rebuild `elements` from scratch each
  // render (App.tsx's own useMemo depends on the same inputs), so without this the
  // table's rows -- and every ref keyed by row id below -- would be new arrays and
  // new identities every render even when nothing the user did actually changed them.
  const rows = useMemo(() => defRows(elements), [elements]);

  // Roving tabindex (WAI-ARIA APG): only one Select button sits in the page's natural
  // Tab order at a time. Without this, a table of a few hundred definitions is a few
  // hundred tab stops -- technically reachable, not practically operable (WCAG 2.1.1
  // in letter but not in spirit). Arrow/Home/End move focus programmatically instead.
  const rowRefs = useRef(new Map<string, HTMLButtonElement>());
  const focusedRowIdRef = useRef<string | null>(null);
  const [activeRowId, setActiveRowId] = useState<string | null>(null);
  const activeId = useMemo(() => {
    if (activeRowId && rows.some((r) => r.id === activeRowId)) return activeRowId;
    return rows.find((r) => r.id === selected)?.id ?? rows[0]?.id ?? null;
  }, [rows, activeRowId, selected]);

  // A filter/metric/boundary change can remove the row a screen-reader or
  // keyboard user was focused on out from under them -- `elements` is rebuilt and
  // React unmounts that <button>. Left alone, focus silently falls back to
  // `<body>`, which reads to a screen reader as leaving the page entirely with no
  // announcement of where anything went. This recovers focus onto the new active
  // row, but only when focus actually landed on body: a user who deliberately
  // tabbed away to the toolbar or the inspector must not be yanked back.
  useLayoutEffect(() => {
    if (!showTable) return;
    if (!focusedRowIdRef.current) return;
    if (rows.some((r) => r.id === focusedRowIdRef.current)) return;
    if (document.activeElement !== document.body) return;
    const next = activeId ? rowRefs.current.get(activeId) : undefined;
    next?.focus();
  }, [rows, activeId, showTable]);

  const handleRowKeyDown = (
    event: KeyboardEvent<HTMLButtonElement>,
    rowId: string,
  ): void => {
    const i = rows.findIndex((r) => r.id === rowId);
    if (i === -1) return;
    let targetIndex: number | null = null;
    switch (event.key) {
      case "ArrowDown":
        targetIndex = Math.min(i + 1, rows.length - 1);
        break;
      case "ArrowUp":
        targetIndex = Math.max(i - 1, 0);
        break;
      case "Home":
        targetIndex = 0;
        break;
      case "End":
        targetIndex = rows.length - 1;
        break;
      default:
        return;
    }
    event.preventDefault();
    const target = rows[targetIndex];
    if (!target) return;
    setActiveRowId(target.id);
    rowRefs.current.get(target.id)?.focus();
  };

  return (
    <div className="graph-panel">
      <div className="graph-toolbar">
        <button
          type="button"
          className="table-toggle"
          aria-expanded={showTable}
          aria-controls="graph-table-region"
          onClick={() => setShowTable((s) => !s)}
        >
          {showTable ? "Hide" : "View"} graph as table
        </button>
        {/*
          role="status" + aria-live so a screen-reader user hears the count change
          as a filter, metric or boundary redraws the canvas underneath them --
          matching the aria-live pattern App.tsx already uses for its own "showing
          N of M" note (data-testid="shown"). Without this, the only way to learn
          the graph changed at all was to have the table open and re-scan it.
        */}
        <span className="note" role="status" aria-live="polite" data-testid="graph-note">
          {rows.length} definition{rows.length === 1 ? "" : "s"} drawn · keyboard
          and screen-reader equivalent of the canvas
        </span>
      </div>

      {/*
        The canvas draws pixels a screen reader cannot read and a keyboard cannot
        reach; it is marked decorative and `aria-hidden` on purpose. The table below
        is the real accessible surface: same nodes, same band, same value, same edges
        (as Callers/Callees counts), reachable with Tab and operable with Enter/Space
        (WCAG 1.1.1, 2.1.1).
      */}
      <div
        ref={box}
        data-testid="graph-canvas"
        className="canvas"
        aria-hidden="true"
      />

      <div
        id="graph-table-region"
        className="graph-table-wrap"
        hidden={!showTable}
      >
        {/*
          WCAG 2.4.1 (Bypass Blocks, Level A). Every row of this table holds a focusable
          Select button, so on the real graph the "accessible alternative to the canvas"
          is also 150 tab stops between the toolbar and the inspector. The alternative
          has to be escapable or it is a trap of its own making. The target carries
          `tabIndex={-1}` because an anchor jump moves the scroll position but not the
          focus ring unless the destination is focusable.
        */}
        <a className="skip-link" href="#graph-table-end">
          Skip past the graph table ({rows.length} row{rows.length === 1 ? "" : "s"})
        </a>
        <table className="graph-table" data-testid="graph-table">
          <caption>
            Every definition currently drawn on the graph canvas, as data. Selecting
            a row highlights that definition the same way tapping its node would.
          </caption>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Cluster</th>
              <th scope="col">Band</th>
              <th scope="col">Value</th>
              <th scope="col">Callers</th>
              <th scope="col">Callees</th>
              <th scope="col">
                <span className="sr-only">Select</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={r.id === selected ? "is-selected" : ""}>
                <td>{r.label}</td>
                <td className="mono small">{r.cluster}</td>
                <td>
                  <span
                    className={`band-chip band-${r.band}`}
                    style={{ color: BAND[r.band] }}
                  >
                    {BAND_WORD[r.band]}
                  </span>
                </td>
                <td className="mono">{r.value}</td>
                <td className="mono">{r.callers}</td>
                <td className="mono">{r.callees}</td>
                <td>
                  <button
                    type="button"
                    ref={(el) => {
                      if (el) rowRefs.current.set(r.id, el);
                      else rowRefs.current.delete(r.id);
                    }}
                    tabIndex={r.id === activeId ? 0 : -1}
                    onFocus={() => {
                      focusedRowIdRef.current = r.id;
                      setActiveRowId(r.id);
                    }}
                    onKeyDown={(e) => handleRowKeyDown(e, r.id)}
                    onClick={() => onSelect(r.id === selected ? null : r.id)}
                    aria-pressed={r.id === selected}
                  >
                    {r.id === selected ? "Selected" : "Select"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        <div id="graph-table-end" tabIndex={-1} className="skip-target">
          End of graph table.
        </div>
      </div>
    </div>
  );
};
