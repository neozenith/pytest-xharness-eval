/**
 * Pieces every per-session chart shares: the panel frame that carries the glossary id and the
 * dotted turn-start markers of the per-line axis (ADR 0025).
 */
import { ReferenceLine } from "recharts";
import { El } from "@/components/El";
import { GRID } from "@/components/charts/chartStyle";

/** Dotted vertical lines at each turn's measuring log line, labelled `t<n>` (per-line axis only). */
export function TurnMarks({ starts }: { starts: number[] }) {
  return (
    <>
      {starts.map((s, i) => (
        <ReferenceLine
          key={`t${i + 1}`}
          x={s}
          stroke={GRID}
          strokeDasharray="2 3"
          ifOverflow="extendDomain"
          label={{ value: `t${i + 1}`, position: "top", fill: "var(--xh-muted)", fontSize: 10 }}
        />
      ))}
    </>
  );
}

interface PanelProps {
  id: string;
  title: string;
  note?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
}

/** The panel frame: the glossary id on the root, the name beside the heading, an optional note. */
export function ChartPanel({ id, title, note, children, className }: PanelProps) {
  return (
    <section id={id} data-el={id} className={className}>
      <h2 className="text-base font-semibold">
        {title}
        <El name={id} />
      </h2>
      {note ? <p className="text-muted-foreground mb-2 text-sm">{note}</p> : null}
      {children}
    </section>
  );
}
