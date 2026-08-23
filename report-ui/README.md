# report-ui

The source of `captured/report.html`, the static microsite `pytest-xharness-eval`
writes beside a skill's captured evidence (ADR 0020, ADR 0028). A bun workspace:
Vite, React 19, TypeScript (strict), Tailwind v4, shadcn/ui, Vitest + Testing
Library, ESLint, Prettier. `bun run build` emits one self-contained `dist/index.html`.

Run everything through the repository `Makefile`:

| Task                                      | Command                                                                             |
| ----------------------------------------- | ----------------------------------------------------------------------------------- |
| Develop against a real captured directory | `make ui-dev CAPTURED=../agentic-dotfiles/skills/mermaidjs-diagrams/evals/captured` |
| Types, lint, formatting                   | `make ui-check` (`make ui-format` to fix)                                           |
| Component tests                           | `make ui-test`                                                                      |
| Build one file                            | `make ui-build` → `dist/index.html`                                                 |
| Build, populate inline, render headlessly | `make ui-smoke CAPTURED=…`                                                          |
| Ship the build as `assets/report.html`    | `make ui-promote`; CI fails when the committed asset is not the current build       |

## Layout

| Path                 | What                                                                                              |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| `src/lib/types.ts`   | The JSON contracts `report.py`, `history.py` and `runresult.py` write; names are the JSON keys    |
| `src/lib/data.ts`    | Inline payload (`window.__XH_DATA__`) or fetch from beside the page; components never know which  |
| `src/lib/tokens.ts`  | `report.tokens.json` → `--xh-*` custom properties; `index.css` aliases shadcn's variables to them |
| `src/lib/route.ts`   | `#session/<id>[/turn/<n>]` hash routes                                                            |
| `src/lib/format.ts`  | Number, money, percentage and window-label formatting; `–` is the one "no value" glyph            |
| `src/components/`    | Page components named after the glossary's element ids                                            |
| `src/components/ui/` | shadcn/ui generated code: add with `bunx shadcn@latest add <name>`, never hand-edit               |
| `src/views/`         | `SweepOverview`, `SessionView`                                                                    |
| `src/__tests__/`     | Vitest                                                                                            |
| `scripts/inline.py`  | Populate a built page from a captured directory via `report.inline_page`                          |
| `scripts/smoke.mjs`  | Render a built page in jsdom and print what mounted                                               |

## Rules

- Keep the `<!--XHARNESS_INLINE_DATA-->` marker first in `<head>`; `report.py` replaces it.
- A new panel gets its glossary id as the element id, a glossary row, and a component, in one change.
- Never show `total_tokens` (billed across turns) and a context figure as one number.
- No CDN: everything is inlined at build time so the page opens over `file://` when inline.
