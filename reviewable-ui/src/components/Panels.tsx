/** The controls, the selected-node detail, and the cluster table. */
import {
  BAND,
  BAND_SHAPE,
  METRICS,
  type BandKey,
  type Metric,
  type PhiScale,
} from "@/lib/metrics";
import { shortCluster, type Filters } from "@/lib/graph";
import {
  LEVELS,
  type Cluster,
  type Graph,
  type GraphNode,
  type Level,
} from "@/lib/types";

export interface ControlsProps {
  graph: Graph;
  level: Level;
  metric: Metric;
  layout: string;
  filters: Filters;
  onLevel: (l: Level) => void;
  onMetric: (id: string) => void;
  onLayout: (l: string) => void;
  onFilters: (f: Filters) => void;
}

const LAYOUT_IDS = ["dagre", "cose", "concentric", "grid"];

export const Controls = ({
  graph,
  level,
  metric,
  layout,
  filters,
  onLevel,
  onMetric,
  onLayout,
  onFilters,
}: ControlsProps) => {
  const langs = [...new Set(graph.nodes.map((n) => n.lang))].sort();
  const set = (patch: Partial<Filters>) => onFilters({ ...filters, ...patch });

  return (
    <div className="controls" data-testid="controls">
      <label>
        Boundary
        <select
          data-testid="level"
          value={level}
          onChange={(e) => onLevel(e.target.value as Level)}
        >
          {LEVELS.map((l) => (
            <option key={l} value={l}>
              {l} · Q {graph.summary[l].modularity} ·{" "}
              {graph.summary[l].insidePct}% inside
            </option>
          ))}
        </select>
      </label>

      <label>
        Colour by
        <select
          data-testid="metric"
          value={metric.id}
          onChange={(e) => onMetric(e.target.value)}
        >
          {METRICS.map((m) => (
            <option key={m.id} value={m.id}>
              {m.label}
            </option>
          ))}
        </select>
      </label>

      <label>
        Layout
        <select
          data-testid="layout"
          value={layout}
          onChange={(e) => onLayout(e.target.value)}
        >
          {LAYOUT_IDS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </label>

      <label>
        Search
        <input
          data-testid="search"
          type="search"
          placeholder="name or file"
          value={filters.search}
          onChange={(e) => set({ search: e.target.value })}
        />
      </label>

      <label>
        Min edge weight{" "}
        <span className="mono" aria-hidden="true">
          {filters.minWeight}
        </span>
        <input
          data-testid="min-weight"
          type="range"
          min={1}
          max={6}
          value={filters.minWeight}
          // The visible value span is `aria-hidden` and this carries the number
          // instead: a range input's accessible *name* is "Min edge weight" full
          // stop, and embedding the live value in it (the un-`aria-valuetext`
          // version of this control) makes the name itself change on every drag
          // step, which is not what AT users expect a name change to mean.
          // `aria-valuetext` is the channel built for a changing value instead.
          aria-valuetext={`${filters.minWeight} of 6`}
          onChange={(e) => set({ minWeight: Number(e.target.value) })}
        />
      </label>

      <label>
        Max nodes{" "}
        <span className="mono" aria-hidden="true">
          {filters.limit}
        </span>
        <input
          data-testid="limit"
          type="range"
          min={50}
          max={800}
          step={50}
          value={filters.limit}
          aria-valuetext={`${filters.limit} nodes`}
          onChange={(e) => set({ limit: Number(e.target.value) })}
        />
      </label>

      <fieldset className="langs">
        <legend>Language</legend>
        {langs.map((l) => (
          <label key={l} className="chip">
            <input
              type="checkbox"
              checked={filters.langs.length === 0 || filters.langs.includes(l)}
              onChange={(e) => {
                const on = e.target.checked;
                const cur = filters.langs.length === 0 ? langs : filters.langs;
                const next = on
                  ? [...new Set([...cur, l])]
                  : cur.filter((x) => x !== l);
                set({ langs: next.length === langs.length ? [] : next });
              }}
            />
            {l}
          </label>
        ))}
        <label className="chip">
          <input
            type="checkbox"
            checked={filters.hideOrphans}
            onChange={(e) => set({ hideOrphans: e.target.checked })}
          />
          hide orphans
        </label>
      </fieldset>

      <p className="note">{metric.note}</p>
    </div>
  );
};

/** Each band's shape, rendered as a small CSS icon so colour is never the only channel. */
const ShapeIcon = ({ band }: { band: BandKey }) => (
  <i
    className={`swatch-shape shape-${BAND_SHAPE[band]}`}
    style={{ background: BAND[band] }}
    aria-hidden="true"
  />
);

export const Legend = ({ metric }: { metric: Metric }) => (
  <div className="legend" data-testid="legend">
    <p className="note">
      Colour <em>and</em> shape both encode <strong>{metric.label}</strong>.
    </p>
    {(["low", "mid", "high", "none"] as const).map((b) => (
      <span key={b} className="swatch">
        <ShapeIcon band={b} />
        {b === "none" ? "no callers" : `${b} band`}
      </span>
    ))}
  </div>
);

/**
 * The one thing a reader must know before trusting any colour on this page — so it is
 * its own component, rendered beside the graph rather than inside the Legend.
 *
 * It used to live at the foot of the legend, in a sidebar that scrolls. A caveat you
 * have to scroll to is a caveat the page has decided is optional, and this one is not:
 * the bands are terciles of whatever graph you loaded, and a reader who takes "high"
 * for "bad" has misread every glyph on screen.
 */
export const BandCaveat = () => (
  <p className="caveat" data-testid="caveat">
    Bands rank, they do not grade. Larger values band higher; whether that is
    good is yours to judge, not this tool&rsquo;s.
  </p>
);

/**
 * Why a selected definition is not on the canvas, or null when it is.
 *
 * `null` and `"filtered"` are different answers to different questions, so this is a
 * union rather than a boolean: the reader's next action is "clear the filter" in one
 * case and "raise the cap" in the other, and a bare "not shown" tells them neither.
 */
export type OffSlice = "filtered" | "capped" | null;

export const Detail = ({
  node,
  graph,
  onSelect,
  offSlice = null,
}: {
  node: GraphNode | null;
  graph: Graph;
  /** Optional: lets "called by" / "calls" entries jump the selection there too. */
  onSelect?: (id: string) => void;
  /**
   * Defaults to null — "it is drawn" — because that is true of every selection made
   * by tapping the canvas, which is where most of them come from.
   */
  offSlice?: OffSlice;
}) => {
  // The empty state keeps the same testid as the populated one. A panel that changes
  // its identity with its state ("I am `detail` when full, an anonymous <p> when
  // empty") makes the empty state unaddressable -- to a test runner, and to anything
  // else that wants to point at the inspector regardless of what is in it.
  // Deselecting is a change too: without `aria-live` here, a screen-reader user who
  // just heard a node's identity announced (below) gets silence on the click that
  // clears it, and has no way to tell "cleared" from "nothing happened". `polite`
  // matches the populated branch's own live region so neither transition is louder
  // than the other.
  if (!node)
    return (
      <p className="empty" data-testid="detail" role="status" aria-live="polite">
        Tap a node to inspect it.
      </p>
    );
  const callers = graph.edges.filter((e) => e.target === node.id);
  const callees = graph.edges.filter((e) => e.source === node.id);
  const byId = (id: string) => graph.nodes.find((n) => n.id === id)?.name ?? id;
  return (
    <div className="detail" data-testid="detail">
      {/* Only the identity line is announced on selection change (WCAG 4.1.3):
          the full metric dump below would make every click read out a wall of
          text, which is worse than saying nothing. */}
      <div aria-live="polite">
        <h3>{node.name}</h3>
        <p className="mono small">
          {node.file}:{node.line}
        </p>
        {/*
          Inside the same live region as the identity line on purpose: "you are now
          inspecting something you cannot see" is part of what changed, and announcing
          the name without it would be announcing half the truth. It is also the one
          case where a sighted user is no better off than a screen-reader one — the
          canvas simply says nothing about a node it never drew.
        */}
        {offSlice && (
          <p className="note banner warn" data-testid="off-slice">
            Not drawn in the current view —{" "}
            {offSlice === "filtered"
              ? "a filter excludes it. Clear the search, language or orphan filters to see it on the canvas."
              : "it falls outside the node cap. Raise “Max nodes” to see it on the canvas."}
          </p>
        )}
      </div>
      <dl>
        <dt>leverage</dt>
        <dd>
          {node.leverage} caller{node.leverage === 1 ? "" : "s"},{" "}
          {node.callSites} site{node.callSites === 1 ? "" : "s"}
        </dd>
        <dt>fan out</dt>
        <dd>{node.fanOut}</dd>
        <dt>lines</dt>
        <dd>{node.nloc}</dd>
        <dt>depth</dt>
        <dd>{node.depth}</dd>
        <dt>class</dt>
        <dd>{node.cls ?? "—"}</dd>
      </dl>
      <h4>Called by ({callers.length})</h4>
      {/*
        The heading already prints the true count, so a list that quietly renders
        fewer rows than that number is the same silent truncation the node-cap banner
        exists to refuse one panel over ("this is data loss, not a footnote") -- just
        without a banner to say so. Twelve rows stays the render cap (a fixed-width
        sidebar cannot usefully show forty jump buttons), but what got cut is now
        named instead of hidden, matching the app's rule everywhere else.
      */}
      <ul className="jump-list" data-testid="callers-list">
        {callers.slice(0, 12).map((e) => (
          <li key={e.source}>
            <button type="button" onClick={() => onSelect?.(e.source)}>
              {byId(e.source)}
            </button>
          </li>
        ))}
        {callers.length > 12 && (
          <li className="more" data-testid="callers-more">
            +{callers.length - 12} more, not shown here
          </li>
        )}
      </ul>
      <h4>Calls ({callees.length})</h4>
      <ul className="jump-list" data-testid="callees-list">
        {callees.slice(0, 12).map((e) => (
          <li key={e.target}>
            <button type="button" onClick={() => onSelect?.(e.target)}>
              {byId(e.target)}
            </button>
          </li>
        ))}
        {callees.length > 12 && (
          <li className="more" data-testid="callees-more">
            +{callees.length - 12} more, not shown here
          </li>
        )}
      </ul>
    </div>
  );
};

export const ClusterTable = ({
  clusters,
  level,
  roots,
  phiScale,
}: {
  clusters: [string, Cluster][];
  level: Level;
  roots: string[];
  /** Built once per slice so the table and the canvas tint rank on one distribution. */
  phiScale: PhiScale;
}) => (
  <table className="clusters" data-testid="cluster-table">
    {/*
      A relative band that does not say what it is relative to is just a threshold
      wearing a disguise, so the caption states the population and the cut points
      outright. It is a <caption>, not a <p> beside the table, so a screen reader
      hears the basis before it reads the first phi.
    */}
    <caption>
      {phiScale.cuts ? (
        <>
          phi is banded by tercile of this graph&rsquo;s {phiScale.n} measurable
          clusters at this boundary &mdash; cuts at{" "}
          <span className="mono">{phiScale.cuts[0].toFixed(3)}</span> and{" "}
          <span className="mono">{phiScale.cuts[1].toFixed(3)}</span>. Conductance
          has no absolute threshold, so these bands rank, they do not grade.
        </>
      ) : (
        <>
          {/*
            `phiScale` is built from every cluster at this boundary across the WHOLE
            graph (lib/graph.ts's `toElements` scales it over `graph.clusters[level]`,
            not over the `used` set this table's own rows are narrowed to -- see that
            function's own comment on why), so `phiScale.n` can legitimately exceed
            `clusters.length` once a filter has narrowed which clusters are drawn
            below. The cuts-branch above already says "this graph's N measurable
            clusters" for exactly this reason; stating a bare count here reads as a
            claim about the rows in this table, which it is not.
          */}
          This graph has {phiScale.n} measurable cluster
          {phiScale.n === 1 ? "" : "s"} at this boundary &mdash; too few to rank, so
          every measured cluster shows the same band.
        </>
      )}
    </caption>
    <thead>
      <tr>
        <th scope="col">cluster</th>
        <th scope="col">names</th>
        <th scope="col">internal</th>
        <th scope="col">cut</th>
        <th scope="col">phi</th>
      </tr>
    </thead>
    <tbody>
      {clusters.map(([key, c]) => {
        const band = phiScale.band(c.phi, c.measurable);
        const phi =
          c.measurable && c.phi !== null ? c.phi.toFixed(3) : "not measurable";
        return (
          <tr key={key}>
            <td title={key}>{shortCluster(key, level, roots)}</td>
            <td>{c.names}</td>
            <td>{c.internal}</td>
            <td>{c.cut}</td>
            {/*
              Every cell in this table is ellipsis-truncated at 130px, which turns
              "not measurable" -- the one value here that is a sentence rather than a
              number -- into "not me...". The title restores it on hover, the way the
              cluster-name cell above already does for its own truncated path.
            */}
            <td
              className={`phi-cell band-${band}`}
              style={{ color: BAND[band] }}
              title={phi}
            >
              {phi}
            </td>
          </tr>
        );
      })}
    </tbody>
  </table>
);

/**
 * What the default view answers before you touch a control.
 *
 * The app opened on a force-directed hairball and a set of dropdowns: every question it
 * could answer required knowing which question to ask it first. This states two facts
 * outright — the most-called definition, and the two extremes of the conductance
 * distribution at the current boundary — so the landing view is worth the ten seconds
 * before a reader decides whether to keep going.
 *
 * Every number here is a rank within the loaded graph, never a grade against a
 * threshold: "calls cross this boundary least/most" is a literal reading of what
 * conductance measures, and is true whether or not the value is a problem.
 * See docs/plans/maintainability/README.md, "Conductance has no fixed threshold".
 *
 * Design-review round 3, finding #1: `top` (below) is picked from the whole loaded
 * graph, while the lo/hi conductance clause is scoped to the current slice -- one
 * sentence, two scopes, and nothing in the copy said which was which. A reader could
 * untick every language but one, or search for a string nothing matches, and still
 * read a confident "N callers, M call sites" for a definition the canvas and the
 * accessible table both show zero rows for.
 *
 * Two designs were on the table: (a) scope `top` to the slice too, so both halves
 * describe the same view, or (b) keep it whole-graph but say so and caveat it when
 * it disagrees with the view. (a) is simpler, but it throws away a fact (a)
 * cannot express: "busiest definition in the codebase" is a real, useful, different
 * question from "busiest definition drawn right now", and it is the more informative
 * of the two exactly when a filter has hidden it -- an aggressive search or a small
 * node cap would otherwise make (a) answer with whatever survived the narrowing,
 * silently re-defining "most-called" as "most-called among what I happened to keep
 * in view". This picks (b): keep the whole-graph fact, but never let it pass as
 * slice-scoped. `App` already computes the on/off-slice status for a selected node
 * (`OffSlice`, used by `Detail` below) for exactly this reason -- reusing it here
 * instead of inventing a second vocabulary means "filtered" and "capped" mean the
 * same thing, with the same remedy, everywhere they appear on this page.
 */
export const Lede = ({
  graph,
  level,
  clusters,
  shown,
  total,
  visibleIds,
  keptIds,
  onSelect,
}: {
  graph: Graph;
  level: Level;
  /** The slice's clusters, already sorted ascending by phi with the unmeasurable last. */
  clusters: [string, Cluster][];
  /** `slice.shown` -- how many definitions the current filters and cap actually draw. */
  shown: number;
  /** `slice.total` -- how many survive the filters, before the cap. */
  total: number;
  /** `slice.visibleIds` -- which of those are actually drawn. */
  visibleIds: Set<string>;
  /** `slice.keptIds` -- which survive the filters at all, cap or not. */
  keptIds: Set<string>;
  onSelect?: (id: string) => void;
}) => {
  const roots = graph.sources.map((s) => s.root);
  // `reduce` with no initial value throws on an empty array, and `graph.nodes` being
  // empty is a state App refuses to render at all -- but a component that only works
  // when something upstream is careful is a component with a hidden precondition.
  const top = graph.nodes.length
    ? graph.nodes.reduce((a, b) => (b.leverage > a.leverage ? b : a))
    : null;
  const measured = clusters.filter(([, c]) => c.measurable && c.phi !== null);
  const lo = measured[0];
  const hi = measured[measured.length - 1];

  if (!top) return null;

  // Same three-way answer `App` computes for a selected node, over `top` instead of
  // `selected`: is it on screen, missing because a filter dropped it, or missing
  // because the cap did?
  const topOffSlice: OffSlice = visibleIds.has(top.id)
    ? null
    : keptIds.has(top.id)
      ? "capped"
      : "filtered";

  return (
    <p className="lede" data-testid="lede">
      {shown === 0 ? (
        // Zero definitions survive the current view. A "most-called definition"
        // sentence over that is the empty-graph screen's refused move -- arithmetic
        // (here, a `reduce`) over an empty set, dressed as a finding -- one sentence
        // smaller, so this names the absence instead of inventing a number for it.
        <>
          No definitions are in the current view (0 of {total}); there is
          nothing to name as most-called until a filter, the search box or the
          node cap is loosened.
        </>
      ) : (
        <>
          Most-called definition in the loaded graph:{" "}
          {onSelect ? (
            <button type="button" className="link" onClick={() => onSelect(top.id)}>
              {top.name}
            </button>
          ) : (
            <b>{top.name}</b>
          )}{" "}
          &mdash; {top.leverage} caller{top.leverage === 1 ? "" : "s"},{" "}
          {top.callSites} call site{top.callSites === 1 ? "" : "s"}, in{" "}
          <span className="mono small">{top.file}</span>.
          {topOffSlice && (
            <span data-testid="lede-off-slice">
              {" "}
              Not drawn in the current view —{" "}
              {topOffSlice === "filtered"
                ? "a filter excludes it."
                : "it falls outside the node cap."}
            </span>
          )}
          {lo && hi && measured.length > 1 && lo[1].phi !== hi[1].phi && (
            <>
              {" "}
              Across the {measured.length} measurable {level} clusters drawn, calls
              cross the boundary least at{" "}
              <b>{shortCluster(lo[0], level, roots)}</b> (phi{" "}
              <span className="mono">{lo[1].phi!.toFixed(3)}</span>) and most at{" "}
              <b>{shortCluster(hi[0], level, roots)}</b> (phi{" "}
              <span className="mono">{hi[1].phi!.toFixed(3)}</span>).
            </>
          )}
          {/*
            A flat distribution is a real answer, not a missing one. The naive version
            of this sentence still names a "least" and a "most" when every cluster sits
            at the same value, which invents a ranking out of a tie -- the same failure
            as banding uncalibrated numbers, one sentence smaller.

            That reasoning needs two or more clusters to hold, though: at exactly one,
            `lo` and `hi` are `measured[0]` and `measured[measured.length - 1]` -- the
            same array entry, compared to itself. `lo[1].phi === hi[1].phi` is then
            trivially true, and is not evidence of a tie at all: a tie needs a second
            value to be tied *with*, and there isn't one. The branch this replaced
            rendered that case as "All 1 ... cluster drawn share the same conductance
            ... between them" -- a subject/verb/pronoun mismatch on the surface, and
            underneath it the exact failure the paragraph above names: a ranking (here,
            a *draw*) invented for a population of one. `measured.length === 1` gets its
            own sentence below instead, so singular actually means singular.
          */}
          {lo && hi && measured.length > 1 && lo[1].phi === hi[1].phi && (
            <>
              {" "}
              All {measured.length} measurable {level} clusters drawn share the same
              conductance (phi <span className="mono">{lo[1].phi!.toFixed(3)}</span>),
              so there is nothing to rank between them at this boundary.
            </>
          )}
          {lo && measured.length === 1 && (
            <>
              {" "}
              Only 1 measurable {level} cluster is drawn,{" "}
              <b>{shortCluster(lo[0], level, roots)}</b> (phi{" "}
              <span className="mono">{lo[1].phi!.toFixed(3)}</span>) &mdash; alone, not
              tied, so there is nothing else at this boundary to rank it against.
            </>
          )}
        </>
      )}
    </p>
  );
};
