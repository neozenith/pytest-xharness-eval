/**
 * Components shared by the SessionView panels: the key/value table the legacy page drew with
 * `kv()`, the category-coloured kind pill, the chip and the notice. Pure helpers are in helpers.ts.
 */
import type { ReactNode } from "react";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import { categoryOfKind } from "./helpers";

/** The record-kind pill, coloured by its category's design token. */
export function Pill({ kind }: { kind: string }) {
  const category = categoryOfKind(kind);
  return (
    <span
      className="inline-block rounded-full px-2 py-px font-mono text-[0.72rem] font-semibold whitespace-nowrap text-white"
      style={{ background: `var(--xh-category-${category})` }}
      title={category}
    >
      {kind}
    </span>
  );
}

export function Chip({
  label,
  children,
  on,
  onClick,
  className,
}: {
  label?: string;
  children?: ReactNode;
  on?: boolean;
  onClick?: () => void;
  className?: string;
}) {
  const body = (
    <>
      {label ? <b className="text-muted-foreground mr-1 font-semibold">{label}</b> : null}
      {children}
    </>
  );
  const base = "bg-muted inline-block max-w-full rounded-lg border px-2.5 py-1 text-[0.8rem] [overflow-wrap:anywhere]";
  if (onClick) {
    return (
      <button type="button" className={cn(base, "cursor-pointer", on && "border-primary text-foreground bg-primary/15", className)} onClick={onClick}>
        {body}
      </button>
    );
  }
  return <span className={cn(base, className)}>{body}</span>;
}

export type KvRow = [ReactNode, ...ReactNode[]];

/** The legacy `table.kv`: the first cell is the key, the rest are right-aligned values. */
export function KvTable({ id, rows, className }: { id?: string; rows: KvRow[]; className?: string }) {
  return (
    <Table id={id} className={cn("text-sm", className)}>
      <TableBody>
        {rows.map(([k, ...vs], i) => (
          <TableRow key={i}>
            <TableCell className="text-muted-foreground w-56 align-top font-mono text-xs whitespace-nowrap">{k}</TableCell>
            {vs.map((v, j) => (
              <TableCell key={j} className="text-right align-top tabular-nums">
                {v}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export const Notice = ({ children }: { children: ReactNode }) => <span className="text-warn">{children}</span>;
