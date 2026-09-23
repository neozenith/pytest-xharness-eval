/**
 * Components shared by the SessionView panels: the key/value table the legacy page drew with
 * `kv()`, the category-coloured kind pill, the chip and the notice. Pure helpers are in helpers.ts.
 * Document content styles by the semantic classes in index.css; chrome is Tamagui.
 */
import { Fragment, type ReactNode } from "react";
import { Table, TableBody, TableCell, TableRow } from "@/components/ui/table";
import { categoryOfKind } from "./helpers";

/**
 * The record-kind pill, coloured by its category's design token. Unlike a record head's pill it
 * never elides: here the kind *is* the datum. So it may wrap, preferably after a `/` (the `<wbr>`
 * after each), else anywhere, rather than `.pill`'s `nowrap` pushing a phone-width page sideways
 * with a kind like `codex/event_msg/item_completed/UserMessage/injected`.
 */
export function Pill({ kind }: { kind: string }) {
  const category = categoryOfKind(kind);
  const parts = kind.split("/");
  return (
    <span
      className="pill"
      style={{ background: `var(--xh-category-${category})`, whiteSpace: "normal", overflowWrap: "anywhere", minWidth: 0 }}
      title={category}
    >
      {parts.map((p, i) => (
        <Fragment key={i}>
          {p}
          {i < parts.length - 1 ? (
            <>
              /<wbr />
            </>
          ) : null}
        </Fragment>
      ))}
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

/**
 * The legacy `table.kv`: the first cell is the key, the rest are right-aligned values. Its rows
 * are text only, so `label` is required: it names the scroll box that becomes a tab stop when a
 * narrow viewport clips the value columns (`scrollLabel`, ui/table.tsx; WCAG 2.1.1).
 */
export function KvTable({ id, rows, label }: { id?: string; rows: KvRow[]; label: string }) {
  return (
    <Table id={id} scrollLabel={label}>
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
