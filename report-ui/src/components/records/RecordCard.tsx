/**
 * One session-log line as a card (glossary: `RecordCard`): a header with the
 * category-coloured kind pill, `L<line>`, the record's timestamp, its size, the context
 * annotation and a `raw`/`nice` flip; a body that is either the rendered view or the raw JSON.
 */
import { Component, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { El } from "@/components/El";
import { fmt } from "@/lib/format";
import { CATEGORIES, categoryOf, classify, type Rec } from "@/lib/records";
import { Notice } from "./Comp";
import { RecordBody } from "./records";
import { Code, Json } from "./values";

export type RecordView = "nice" | "raw";

export interface CtxTag {
  text: string;
  title: string;
}

/** `HH:MM:SS.mmm` of an ISO timestamp, or the text itself when it does not parse. */
export const clock = (iso: unknown): string => {
  if (!iso) return "–";
  const d = new Date(String(iso));
  return Number.isNaN(d.getTime()) ? String(iso) : `${d.toLocaleTimeString("en-GB", { hour12: false })}.${String(d.getMilliseconds()).padStart(3, "0")}`;
};

/** The category pill, coloured from the design tokens (`--xh-category-<category>`). */
export function Pill({ kind }: { kind: string }) {
  const category = categoryOf(kind);
  return (
    <span
      className="pill inline-block rounded-full px-[0.55rem] py-[0.05rem] font-mono text-[0.72rem] font-semibold whitespace-nowrap text-white"
      style={{ background: `var(--xh-category-${category}, ${CATEGORIES[category] ?? CATEGORIES.unknown})` }}
      title={category}
    >
      {kind}
    </span>
  );
}

/** The parsed record, or null when the line is not a JSON object. */
function parseRecord(raw: string): Rec | null {
  try {
    const v: unknown = JSON.parse(raw);
    return typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Rec) : null;
  } catch {
    return null;
  }
}

interface Props {
  harness: string;
  lineNo: number;
  raw: string;
  ctx?: CtxTag | null;
  /** The view every card follows (`RecordViewToggle`); a card's own flip overrides it until the next change. */
  view: RecordView;
}

export function RecordCard({ harness, lineNo, raw, ctx, view }: Props) {
  // A card's own flip lasts until the page-wide view next changes (state derived from a prop).
  const [own, setOwn] = useState<RecordView>(view);
  const [seen, setSeen] = useState<RecordView>(view);
  if (seen !== view) {
    setSeen(view);
    setOwn(view);
  }

  const rec = parseRecord(raw);
  const kind = rec ? classify(harness, rec) : `${harness}/unparseable`;
  const ts = rec?.timestamp ?? null;

  return (
    <div className="rec bg-card my-[0.45rem] rounded-lg border" data-kind={kind} data-el="RecordCard" id={`L${lineNo}`}>
      <div className="rec-head flex flex-wrap items-center gap-[0.6rem] border-b px-[0.6rem] py-[0.35rem] text-[0.8rem]">
        <Pill kind={kind} />
        <span className="text-muted-foreground font-mono text-[0.75rem]">L{lineNo}</span>
        <span className="text-muted-foreground font-mono text-[0.75rem]">{clock(ts)}</span>
        <span className="text-muted-foreground font-mono text-[0.75rem]">{fmt(raw.length)} chars</span>
        {ctx ? (
          <span className="ctx text-primary font-mono text-[0.75rem]" title={ctx.title}>
            {ctx.text}
          </span>
        ) : null}
        <span className="flex-1" />
        <El name="RecordCard" />
        <Button type="button" variant="outline" size="xs" className="flip" data-mode={own} onClick={() => setOwn(own === "nice" ? "raw" : "nice")}>
          {own === "nice" ? "raw" : "nice"}
        </Button>
      </div>
      {own === "nice" ? (
        <div className="rec-body rec-nice px-[0.7rem] py-2">
          {rec ? <SafeBody harness={harness} rec={rec} kind={kind} raw={raw} /> : <Code lang="" text={raw} />}
        </div>
      ) : (
        <div className="rec-body rec-raw px-[0.7rem] py-2">
          <Json value={rec ?? raw} />
        </div>
      )}
    </div>
  );
}

/** A renderer that throws must not take the page down: show the notice and the raw line instead. */
class SafeBody extends Component<{ harness: string; rec: Rec; kind: string; raw: string }, { error: string | null }> {
  state = { error: null as string | null };
  static getDerivedStateFromError(e: unknown) {
    return { error: e instanceof Error ? e.message : String(e) };
  }
  render(): ReactNode {
    if (this.state.error != null) {
      return (
        <>
          <Notice>renderer failed: {this.state.error}</Notice>
          <Code lang="" text={this.props.raw} />
        </>
      );
    }
    return <RecordBody harness={this.props.harness} rec={this.props.rec} kind={this.props.kind} />;
  }
}
