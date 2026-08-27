# 0006: A local prices.toml is authoritative, with an optional upstream seed

Status: accepted, 2026-08-21; `--seed-prices` not yet built. The table is now
bundled inside the package and layered with the consumer's optional
`xharness_prices` file ([0014](0014-register-through-the-pytest11-entry-point.md)).
The project-level override moved from a rootdir `prices.toml` into `xharness_prices`
ini lines with [0030](0030-price-rows-live-in-the-pytest-config.md); the bundled
table is unchanged.

## Context

Neither CLI's session log carries cost, and Codex reports none anywhere. The
LiteLLM feed was fetched and carries per-token input, output, cache-read, and
cache-write rates for Anthropic models. Its coverage of Codex's aliased model
names (for example `gpt-5.6-sol`) is unconfirmed.

## Decision

A committed `prices.toml` is the single authority for rates. A `--seed-prices`
command will populate and refresh rows from upstream, never overwrite a row
marked as a local override, and report every model it could not match.

## Consequences

Claude rates can be refreshed from a real upstream; Codex aliases stay
hand-entered. Until the seed command exists, every row is maintained by hand, and
absolute USD figures lag provider changes. Relative comparison across cells stays
robust regardless.

## Lens

Keep the price table owned, not generated. An upstream is a convenience for
filling it, never the thing the harness reads.
