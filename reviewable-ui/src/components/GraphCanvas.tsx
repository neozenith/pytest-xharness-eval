/** The cytoscape canvas. Owns the instance; React owns only the container and the props. */
import { useEffect, useRef, useState } from "react";
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
    selector: "node:selected",
    style: { "border-width": 4, "border-color": "#facc15" },
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

/** One row of the text alternative to the canvas: a definition, as data. */
interface DefRow {
  id: string;
  label: string;
  cluster: string;
  band: BandKey;
  value: number;
}

const defRows = (elements: ElementDefinition[]): DefRow[] =>
  elements
    .filter((e) => e.data.kind === "def")
    .map((e) => ({
      id: e.data.id as string,
      label: (e.data.label as string | undefined) ?? (e.data.id as string),
      cluster: ((e.data.parent as string | undefined) ?? "").replace(
        /^C::/,
        "",
      ),
      band: e.data.band as BandKey,
      value: (e.data.value as number | undefined) ?? 0,
    }));

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
    return () => {
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

  const rows = defRows(elements);

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
        <span className="note">
          {rows.length} definitions drawn · keyboard and screen-reader
          equivalent of the canvas
        </span>
      </div>

      {/*
        The canvas draws pixels a screen reader cannot read and a keyboard cannot
        reach; it is marked decorative and `aria-hidden` on purpose. The table below
        is the real accessible surface: same nodes, same band, same value, reachable
        with Tab and operable with Enter/Space (WCAG 1.1.1, 2.1.1).
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
                <td>
                  <button
                    type="button"
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
      </div>
    </div>
  );
};
