/** The cytoscape canvas. Owns the instance; React owns only the container and the props. */
import { useEffect, useRef } from "react";
import cytoscape, {
  type Core,
  type ElementDefinition,
  type LayoutOptions,
} from "cytoscape";
import dagre from "cytoscape-dagre";

cytoscape.use(dagre);

const LAYOUTS: Record<string, LayoutOptions> = {
  dagre: {
    name: "dagre",
    rankDir: "LR",
    nodeSep: 16,
    rankSep: 90,
    padding: 20,
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
  } as LayoutOptions,
  grid: { name: "grid", padding: 20 } as LayoutOptions,
};

export interface GraphCanvasProps {
  elements: ElementDefinition[];
  layout: string;
  onSelect: (id: string | null) => void;
}

/**
 * A stylesheet built once. Node fill comes from `data(colour)` because it encodes a
 * metric band, not a theme; the chrome around it is CSS and re-skins freely.
 */
const STYLE: cytoscape.StylesheetJson = [
  {
    selector: "node[kind = 'def']",
    style: {
      "background-color": "data(colour)",
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
      "border-width": 1.5,
      "border-style": "dashed",
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
      "line-color": "#475569",
      width: "mapData(sites, 1, 6, 0.8, 3.5)",
      "target-arrow-shape": "triangle",
      "target-arrow-color": "#475569",
      "arrow-scale": 0.7,
      opacity: 0.55,
    },
  },
  {
    selector: "node:selected",
    style: { "border-width": 3, "border-color": "#7c3aed" },
  },
  { selector: ".faded", style: { opacity: 0.08 } },
  {
    selector: ".hot",
    style: {
      opacity: 1,
      "line-color": "#7c3aed",
      "target-arrow-color": "#7c3aed",
    },
  },
];

export const GraphCanvas = ({
  elements,
  layout,
  onSelect,
}: GraphCanvasProps) => {
  const box = useRef<HTMLDivElement>(null);
  const cy = useRef<Core | null>(null);

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
    run.one("layoutstop", () => c.fit(undefined, 30));
    run.run();
  }, [elements, layout]);

  return <div ref={box} data-testid="graph-canvas" className="canvas" />;
};

/** Dim everything not adjacent to `id`. Called from the app when a node is selected. */
export const useNeighbourhood = (cy: Core | null, id: string | null): void => {
  useEffect(() => {
    if (!cy) return;
    cy.elements().removeClass("faded hot");
    if (!id) return;
    const node = cy.getElementById(id);
    if (!node.length) return;
    const keep = node.closedNeighborhood();
    cy.elements().difference(keep).addClass("faded");
    keep.edges().addClass("hot");
  }, [cy, id]);
};
