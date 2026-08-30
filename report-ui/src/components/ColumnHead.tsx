import { ArrowDown, ArrowUp } from "lucide-react";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

interface Props {
  /** The id of the visually-hidden definition this head is described by; unique on the page. */
  defId: string;
  /** The canonical field name: the tooltip's first line and half the accessible name. */
  name: string;
  /** What the head prints: the shortest form that still reads at 11px. */
  label: string;
  title: string;
  /** True when the table is currently sorted by this column. */
  active: boolean;
  /** Which way the arrow points: the direction a click would leave the column in. */
  ascending: boolean;
  onSort: () => void;
}

/**
 * One sortable column head — shared by `SessionTable` and `SessionSummaryTable`, so the pair's
 * heads are literally one object rather than two that happen to agree today.
 *
 * The definition reaches a pointer through the tooltip and a screen reader through
 * `aria-describedby` on a visually-hidden span. Tamagui's `Tooltip` opens on pointer events
 * only, so a keyboard reader who tabbed to a head got a focus ring and nothing else (WCAG
 * 2.1.1) — and these heads are the only place `accumulative_billed_tokens` and its siblings are
 * spelled out. The span costs no tab stop and is announced with the button's own name.
 *
 * The arrow is always in the DOM: an active column that grew one on click shifted every column
 * to its right, and a sortable column that showed nothing until you hovered it never said it was
 * sortable. Inactive arrows point where a click goes.
 */
export function ColumnHead({ defId, name, label, title, active, ascending, onSort }: Props) {
  const Arrow = ascending ? ArrowUp : ArrowDown;
  return (
    <>
      <Tooltip>
        <TooltipTrigger asChild>
          {/*
           * The accessible name keeps the printed label *and* the canonical field name (WCAG
           * 2.5.3: what you can say has to be what you can see), so an abbreviated head still
           * answers to `estimated_cost_usd`.
           */}
          <button type="button" aria-label={label === name ? undefined : `${label} — ${name}`} aria-describedby={defId} onClick={onSort}>
            {label}
            <Arrow className="sort-ico" data-active={active || undefined} size={11} aria-hidden />
          </button>
        </TooltipTrigger>
        <TooltipContent>
          <span className="mono">{name}</span> — {title}
        </TooltipContent>
      </Tooltip>
      <span id={defId} className="sr-only">
        {name} — {title}
      </span>
    </>
  );
}
