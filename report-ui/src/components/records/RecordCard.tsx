/**
 * One session-log line as a card (glossary: `RecordCard`): a header with the
 * category-coloured kind pill, `L<line>`, the record's timestamp, its size, the context
 * annotation and a `raw`/`nice` flip; a body that is either the rendered view or the raw JSON.
 *
 * The two harnesses keep different session-log schemas (`claude/*` vs `codex/*` record
 * kinds, different envelopes), so each gets its own base: `RecordCardClaude` and
 * `RecordCardCodex` fix the harness and classify/render through that harness's catalogue;
 * `RecordCard` dispatches on the `harness` prop.
 */
import { Component, useState, type ReactNode } from "react";
import { Link as LinkIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { El } from "@/components/El";
import { fmt } from "@/lib/format";
import { categoryOf, classify, type Rec } from "@/lib/records";
import { Notice } from "./Comp";
import { RecordBody } from "./records";
import { Code, Json, categoryColour } from "./values";

import type { RecordView } from "@/lib/route";
export type { RecordView };

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

/**
 * The category pill, coloured from the design tokens (`--xh-category-<category>`). The kind
 * sits in its own span so a narrow card can cap it with an ellipsis (`.rec-head .pill-kind`):
 * `text-overflow` needs a box of its own, and the pill itself is a flex container. The full
 * kind stays readable in the tooltip whether or not it is elided.
 */
export function Pill({ kind }: { kind: string }) {
  const category = categoryOf(kind);
  return (
    <span className="pill" style={{ background: categoryColour(category) }} title={`${kind} · ${category}`}>
      <span className="pill-kind">{kind}</span>
    </span>
  );
}

/**
 * The head's two controls sit on the 11px tier the `.meta`, `.el` and `.ctx` beside them use,
 * not the button frame's 11.5px `xs` default — half a pixel off the card's 13/12/11/10 scale,
 * repeated on every one of a hundred cards. It is set here rather than in the stylesheet
 * because the frame writes its type size as an inline style.
 */
const HEAD_CONTROL_TYPE = { fontSize: 11, lineHeight: "14px" } as const;

/** The parsed record, or null when the line is not a JSON object. */
function parseRecord(raw: string): Rec | null {
  try {
    const v: unknown = JSON.parse(raw);
    return typeof v === "object" && v !== null && !Array.isArray(v) ? (v as Rec) : null;
  } catch {
    return null;
  }
}

export interface RecordCardProps {
  lineNo: number;
  raw: string;
  ctx?: CtxTag | null;
  /** The view every card follows (`RecordViewToggle`); a card's own flip overrides it until the next change. */
  view: RecordView;
  /** The `line=` deeplink to this record; renders the permalink button when given. */
  permalink?: string;
}

interface BaseProps extends RecordCardProps {
  harness: string;
}

function RecordCardBase({ harness, lineNo, raw, ctx, view, permalink }: BaseProps) {
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
    <div className="rec" data-kind={kind} data-harness={harness} data-el="RecordCard" id={`L${lineNo}`}>
      <div className="rec-head">
        <Pill kind={kind} />
        {/* The meta run is named part by part so a narrow card can drop the least load-bearing of them. */}
        <span className="meta line">L{lineNo}</span>
        <span className="meta clock">{clock(ts)}</span>
        <span className="meta chars">{fmt(raw.length)} chars</span>
        {ctx ? (
          <span className="ctx" title={ctx.title}>
            {ctx.text}
          </span>
        ) : null}
        <El name="RecordCard" />
        {/* The two controls are one cluster: tight to each other, clear of the label beside them. */}
        <span className="rec-actions">
          {permalink ? (
            <Button
              render={<button type="button" title="link to this record (copies the URL)" />}
              variant="ghost"
              size="xs"
              style={HEAD_CONTROL_TYPE}
              aria-label={`link to log line ${lineNo}`}
              onClick={() => {
                history.replaceState(null, "", permalink);
                try {
                  void navigator.clipboard?.writeText(location.href);
                } catch {
                  /* clipboard unavailable over plain http; the address bar already has the link */
                }
              }}
            >
              <LinkIcon size={12} />
            </Button>
          ) : null}
          <Button
            render={<button type="button" title={own === "nice" ? "show the raw log line" : "show the rendered view"} />}
            variant="outline"
            size="xs"
            style={HEAD_CONTROL_TYPE}
            className="flip"
            data-mode={own}
            onClick={() => setOwn(own === "nice" ? "raw" : "nice")}
          >
            {own === "nice" ? "raw" : "nice"}
          </Button>
        </span>
      </div>
      {own === "nice" ? (
        <div className="rec-body rec-nice">{rec ? <SafeBody harness={harness} rec={rec} kind={kind} raw={raw} /> : <Code lang="" text={raw} />}</div>
      ) : (
        <div className="rec-body rec-raw">
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

/** A Claude session-log line: classified and rendered through the `claude/*` record catalogue. */
export const RecordCardClaude = (props: RecordCardProps) => <RecordCardBase {...props} harness="claude" />;

/** A Codex session-log line: classified and rendered through the `codex/*` record catalogue. */
export const RecordCardCodex = (props: RecordCardProps) => <RecordCardBase {...props} harness="codex" />;

/** Dispatch by harness; an unknown harness still classifies through its own prefix. */
export const RecordCard = ({ harness, ...props }: BaseProps) => <RecordCardBase {...props} harness={harness} />;
