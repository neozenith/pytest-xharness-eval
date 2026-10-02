/**
 * The one reader of `rates_applied` tier values (ADR 0050). A result written since ADR 0050
 * states its rates in USD per million tokens and says so in `unit`; one written before it
 * has no `unit` and states USD per token. Everything that displays a rate or multiplies it
 * by a token count goes through `ratesPerMtok`, so the two vintages cannot be mixed up.
 */
import type { RatesApplied, Usage } from "./types";

/** The `unit` value the plugin writes beside per-MTok rates (`pricing.RATE_UNIT`). */
export const RATE_UNIT = "usd_per_mtok";

export const TIERS = ["input", "output", "cache_read", "cache_write", "cache_write_1h"] as const;
export type Tier = (typeof TIERS)[number];
export type TierRates = Partial<Record<Tier, number>>;

/** Whether this record predates ADR 0050: rates present but no `unit`, so they are per token. */
export const isLegacyRates = (ra: RatesApplied | null | undefined): boolean => !!ra && Object.keys(ra).length > 0 && ra.unit !== RATE_UNIT;

/** Each stated tier in USD per million tokens, whichever vintage the record is; absent tiers stay absent. */
export function ratesPerMtok(ra: RatesApplied | null | undefined): TierRates {
  if (!ra) return {};
  const scale = ra.unit === RATE_UNIT ? 1 : 1e6;
  const out: TierRates = {};
  for (const tier of TIERS) {
    const v = ra[tier];
    if (typeof v === "number") out[tier] = v * scale;
  }
  return out;
}

/** A long-context tier in USD per MTok, with the prompt-token threshold it applies above (ADR 0051). */
export interface LongContextTier {
  above: number;
  rates: TierRates;
}

/** The row's long-context tier, scaled like `ratesPerMtok`; null where the row has none (or predates ADR 0051). */
export function longContextPerMtok(ra: RatesApplied | null | undefined): LongContextTier | null {
  const lc = ra?.long_context;
  if (!lc || typeof lc.above_prompt_tokens !== "number") return null;
  const scale = ra?.unit === RATE_UNIT ? 1 : 1e6;
  const rates: TierRates = {};
  for (const tier of TIERS) {
    const v = lc[tier];
    if (typeof v === "number") rates[tier] = v * scale;
  }
  return { above: lc.above_prompt_tokens, rates };
}

/** The prompt one call sent: uncached input plus both cache tiers, as the provider's threshold counts it. */
export const promptTokens = (u: Usage): number => u.input_tokens + u.cache_read_tokens + u.cache_write_tokens;

/**
 * The tier one call is billed at: the long-context tier when its prompt is strictly over the
 * threshold, else the base tier. Evaluated per call, never on summed usage (ADR 0051).
 */
export function tierForCall(u: Usage, base: TierRates, long: LongContextTier | null): TierRates {
  return long && promptTokens(u) > long.above ? long.rates : base;
}

/** `from → to` for the interval the row was in effect; an open end reads as "open", an undated start as "any date". */
export function effectiveInterval(ra: RatesApplied): string | undefined {
  if (ra.unit !== RATE_UNIT) return undefined;
  return `${ra.effective_from ?? "any date"} → ${ra.effective_to ?? "open"}`;
}
