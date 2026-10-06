import { catalogueNote, tierBadge } from "@/lib/catalogue";

/**
 * The model's family tier (ADR 0057) as a compact `T3` mark inside a table's model cell, with the
 * catalogue's line and release date on its `title`. A mark, not a column: the session table is at
 * its width budget, and the tier is a property of the model the cell already names, not a new
 * identity of its own. Nothing renders for a model the catalogue never described.
 */
export function TierBadge({ model }: { model: { family_tier: number | null; line: string | null; released: string | null } }) {
  if (model.family_tier == null) return null;
  return (
    <span className="tier-badge" data-tier={model.family_tier} title={catalogueNote(model)}>
      {tierBadge(model.family_tier)}
    </span>
  );
}
