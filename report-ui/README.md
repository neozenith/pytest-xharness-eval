# report-ui

The source of `captured/report.html`, the static microsite `pytest-xharness-eval`
writes beside a skill's captured evidence (ADR 0020, ADR 0028, ADR 0031). A bun
workspace: Vite, React 19, TypeScript (strict), Tamagui (the UI and animation
framework), Plotly.js (every chart), one hand-written stylesheet for document
content, Vitest + Testing Library, Playwright, ESLint, Prettier. `bun run build`
emits one self-contained `dist/index.html`.

Run everything through the repository `Makefile`:

| Task                                         | Command                                                                              |
| -------------------------------------------- | ------------------------------------------------------------------------------------ |
| Develop against a real cache root (ADR 0032) | `make ui-dev CAPTURED=../agentic-dotfiles/.xharness_eval_cache`                      |
| Types, lint, formatting                      | `make ui-check` (`make ui-format` to fix)                                            |
| Component tests                              | `make ui-test`                                                                       |
| Build one file                               | `make ui-build` → `dist/index.html`                                                  |
| Sweep the deeplink permutation matrix (e2e)  | `make ui-e2e CAPTURED=… TIER=small\|medium\|large` (+`SAMPLE=<n>`, `E2E_TARGET=dev`) |
| Build, populate inline, boot over `file://`  | `make ui-smoke CAPTURED=…`                                                           |
| Ship the build as `assets/report.html`       | `make ui-promote`; CI fails when the committed asset is not the current build        |

The e2e suite needs Playwright's browser once: `cd report-ui && bunx playwright install chromium`.

## Layout

| Path                      | What                                                                                                                                                                                                                                      |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/lib/types.ts`        | The JSON contracts `report.py`, `history.py` and `runresult.py` write; names are the JSON keys                                                                                                                                            |
| `src/lib/data.ts`         | Inline payload (`window.__XH_DATA__`) or fetch from beside the page; tracks `window.__XH_PENDING__`                                                                                                                                       |
| `src/lib/tokens.ts`       | `report.tokens.json` → `--xh-*` custom properties; Tamagui themes and index.css consume them                                                                                                                                              |
| `src/lib/route.ts`        | The hash schema: every interactive state is addressable (`session`, `turn`, `view`, `axis`, `rec`, `line`, `sort`, `dir`, `ssort`, `sdir`, `skill`, `harness`, `model`, `theme`); `overviewWith` is how every overview control writes one |
| `src/lib/permutations.ts` | The covering matrix of deeplink states with deterministic slugs; the e2e sweep and the app share it                                                                                                                                       |
| `src/lib/format.ts`       | Number, money, percentage and window-label formatting; `–` is the one "no value" glyph                                                                                                                                                    |
| `src/lib/facets.ts`       | The overview's filter vocabulary: options, the AND-across / OR-within predicate, and the one `NO_MATCH` sentence (ADR 0042)                                                                                                               |
| `src/lib/summary.ts`      | `SessionSummaryTable`'s arithmetic: one row per skill × case × harness × model, every aggregate a named mean (ADR 0042)                                                                                                                   |
| `src/tamagui.config.ts`   | Tamagui themes whose every value is a `var(--xh-*)` reference (ADR 0031)                                                                                                                                                                  |
| `src/components/`         | Page components named after the glossary's element ids                                                                                                                                                                                    |
| `src/components/ui/`      | Hand-written Tamagui components (button, card, badge, switch, tooltip, toggle-group, collapsible)                                                                                                                                         |
| `src/components/charts/`  | Plotly charts; `Plot.tsx` is the one mount point, `plotly.ts` resolves the theme                                                                                                                                                          |
| `src/views/`              | `SweepOverview`, `SessionView`                                                                                                                                                                                                            |
| `src/__tests__/`          | Vitest; `render.tsx` wraps renders in the Tamagui provider                                                                                                                                                                                |
| `e2e/matrix.spec.ts`      | The singular permutation sweep: screenshot + console + network timings per slug under `tmp/e2e/`                                                                                                                                          |
| `e2e/inline.spec.ts`      | The inline smoke: the populated build over `file://`, glossary-id parity, zero console errors                                                                                                                                             |
| `scripts/inline.py`       | Populate a built page from a captured directory via `report.inline_page`                                                                                                                                                                  |

## Rules

- Keep the `<!--XHARNESS_INLINE_DATA-->` marker first in `<head>`; `report.py` replaces it.
- A new panel gets its glossary id as the element id, a glossary row, and a component, in one change.
- A new route param goes into `lib/permutations.ts` in the same change, or the e2e matrix silently stops covering it.
- Never show `total_tokens` (billed across turns) and a context figure as one number.
- No CDN: everything is inlined at build time so the page opens over `file://` when inline.
- Chrome styles with Tamagui props; only document content (tables, records, code) uses the
  semantic classes in `index.css` — no utility-class framework (ADR 0031).
