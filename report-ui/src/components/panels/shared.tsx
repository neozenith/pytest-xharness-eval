/**
 * Components shared by the SessionView panels: the key/value table the legacy page drew with
 * `kv()`, the category-coloured kind pill, the chip and the notice. Pure helpers are in helpers.ts.
 * Document content styles by the semantic classes in index.css; chrome is Tamagui.
 */
import type { ReactNode } from "react";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { categoryOfKind } from "./helpers";

/** The record-kind pill, coloured by its category's design token. */
export function Pill({ kind }: { kind: string }) {
  const category = categoryOfKind(kind);
  return (
    <span className="pill" style={{ background: `var(--xh-category-${category})` }} title={category}>
      {kind}
    </span>
  );
}

export function Chip({ label, children, on, onClick }: { label?: string; children?: ReactNode; on?: boolean; onClick?: () => void }) {
  const body = (
    <>
      {label ? <b>{label}</b> : null}
      {children}
    </>
  );
  if (onClick) {
    return (
      <button type="button" className="filter-chip" data-on={on ? "true" : undefined} onClick={onClick}>
        {body}
      </button>
    );
  }
  return <span className="filter-chip">{body}</span>;
}

export type KvRow = [ReactNode, ...ReactNode[]];

/** The legacy `table.kv`: the first cell is the key, the rest are right-aligned values. */
export function KvTable({ id, rows }: { id?: string; rows: KvRow[] }) {
  return (
    <Table id={id}>
      <TableBody>
        {rows.map(([k, ...vs], i) => (
          <TableRow key={i}>
            <TableCell className="key">{k}</TableCell>
            {vs.map((v, j) => (
              <TableCell key={j} className="num" style={{ verticalAlign: "top" }}>
                {v}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

export const Notice = ({ children }: { children: ReactNode }) => <span className="warn">{children}</span>;
