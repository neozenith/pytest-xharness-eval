import { catalogueNote, tierBadge } from "@/lib/catalogue";

/**
 * The model's family tier (ADR 0057) as a compact `T3` mark, with the catalogue's line and release
 * date on its `title`: the cell of SessionTable's `tier` column, and a qualifier after the model
 * name in SessionSummaryTable. Nothing renders for a model the catalogue never described.
 */
export function TierBadge({ model }: { model: { family_tier: number | null; line: string | null; released: string | null } }) {
  if (model.family_tier == null) return null;
  return (
    <span className="tier-badge" data-tier={model.family_tier} title={catalogueNote(model)}>
      {tierBadge(model.family_tier)}
    </span>
  );
}
