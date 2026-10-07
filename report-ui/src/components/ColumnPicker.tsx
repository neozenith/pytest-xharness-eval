import { ALWAYS_SHOWN, allHidden, toggled } from "@/lib/columnPrefs";

/** One column the picker can offer: its key, the head it prints, and its canonical field name. */
export interface PickableColumn {
  key: string;
  label: string;
  name: string;
  title: string;
}

/**
 * The SessionTable's column picker (ADR 0061): a reader turns off the columns they are not
 * reading, so the table they keep fits the screen they have. "Select all" and "Deselect all"
 * reset it in one click; the always-shown columns (`verdict`, `case`) are listed but locked,
 * because without them a row cannot be read.
 *
 * A native `<details>` disclosure and native checkboxes, so it opens from the keyboard and
 * reads as a group of checkboxes to a screen reader without any of that being re-implemented.
 */
export function ColumnPicker({
  columns,
  hidden,
  onChange,
}: {
  columns: readonly PickableColumn[];
  hidden: ReadonlySet<string>;
  onChange: (hidden: Set<string>) => void;
}) {
  const shown = columns.filter((c) => !hidden.has(c.key)).length;
  return (
    <details id="SessionTableColumns" className="column-picker">
      <summary>
        columns{" "}
        <span className="muted">
          {shown}/{columns.length}
        </span>
      </summary>
      <div className="column-picker-panel" role="group" aria-label="SessionTable columns">
        <div className="column-picker-actions">
          <button type="button" data-action="select-all" onClick={() => onChange(new Set())}>
            Select all
          </button>
          <button type="button" data-action="deselect-all" onClick={() => onChange(allHidden(columns.map((c) => c.key)))}>
            Deselect all
          </button>
        </div>
        <ul>
          {columns.map((c) => {
            const locked = ALWAYS_SHOWN.includes(c.key);
            return (
              <li key={c.key}>
                <label title={c.title}>
                  <input type="checkbox" data-k={c.key} checked={!hidden.has(c.key)} disabled={locked} onChange={() => onChange(toggled(hidden, c.key))} />
                  {c.label}
                  {c.label !== c.name ? <span className="muted"> {c.name}</span> : null}
                  {locked ? <span className="muted"> (always shown)</span> : null}
                </label>
              </li>
            );
          })}
        </ul>
      </div>
    </details>
  );
}
