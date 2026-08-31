# Documentation Conventions

How this repository organises its documentation.
Agents and humans: consult this before creating, moving, or renaming any doc.

Written from the repository's observed practice, not imposed on it. Every line below
describes what the tree already did, except where marked *(baseline)*.

## Dialect

- **Flavour:** standard.
- **Docs taxonomy:** flat `docs/`, no Diátaxis folders. The tree is three living
  documents plus the ADR bundle; four near-empty buckets would be premature.
- **Glossary:** `GLOSSARY.md` at root, one canonical term per concept. Agents add new
  domain terms in the same change that introduces them. *(baseline; extracted from
  `ARCHITECTURE.md#vocabulary`, 2026-08-31.)*
- **ADR layout:** file-per-decision at `docs/adrs/NNNN-slug.{yml,md}`, generated
  `index.md`.
- **ADR surface:** `okf-yaml`. Records are authored in `docs/adrs/NNNN-slug.yml` and
  their markdown is generated (ADR 0047).
- **Record domains:** every record declares one `group` (its primary domain, and the
  compound parent it sits in on the graph) and a `tags` list of one or two domains,
  primary first. Both are a closed enum in `record.schema.json`, so a typo fails the
  build rather than creating a group of one. The eleven domains are `accounting`,
  `architecture`, `collection`, `docs`, `evidence`, `grading`, `harness`, `packaging`,
  `pricing`, `report` and `storage`. A record needing a third tag has usually not been
  read closely enough to say what it is mainly about. The schema is `docs/adrs/record.schema.json`, tightened to this
  repository's dialect: the argument is carried verbatim in `body`, and the fields the
  corpus does not supply (`description`, `tags`, `provenance`, `enforced_in`) are
  optional rather than invented.
- **ADR format:** `# NNNN: Title`, a `Status:` sentence, then `## Context`,
  `## Decision`, `## Consequences`, and a closing `## Lens` carrying the reusable rule.
  Four early records (0031, 0032, 0033, 0043) have no Lens; an absent Lens is a fact
  about the record, not a gap to fill.
- **Generated paths:** `docs/adrs/*.md`, `docs/adrs/index.md`, `docs/adrs/graph.md`,
  `docs/adrs/graph.json`, `docs/adrs/graph.html`.
- **Regenerate:** `make adrs`. `make adrs-check` is the CI gate.
- **Agent files:** `AGENTS.md` is canonical; `CLAUDE.md` is a symlink to it.
- **Changelog:** not used. Releases are GitHub Releases tagged `vX.Y.Z` (ADR 0017).
- **Proposals/RFCs:** not used. A decision is recorded once it is made, never before.

## Layout map

Path → what belongs there → who reads it → when it changes.
This table is the misplacement oracle: content that does not match its row's charter is
misfiled.

| Path | Charter (what belongs here) | Audience | Changes when |
|------|-----------------------------|----------|--------------|
| `README.md` | Orientation and routing: what the plugin is, the quickstart, the option tables, where to go next | Consumers | Purpose, options or entry points change |
| `CONTRIBUTING.md` | Setup, the `make` commands, the release procedure | Contributors | The dev workflow changes |
| `AGENTS.md` (`CLAUDE.md`) | Agent invariants and pointers: commands, layout by purpose, hard boundaries, the change map. No restated conventions another doc owns | Agents | Commands, layout or a hard boundary changes |
| `ARCHITECTURE.md` | How the system is put together and why: the pipeline, the layer stack, the capture contracts | Both | The structure changes |
| `GLOSSARY.md` | Ubiquitous language: one canonical term per concept | Both | A domain term enters the code or conversation |
| `docs/adrs/*.yml` | Immutable accepted decisions and their lenses: the authored source | Both | A binding decision is made |
| `docs/adrs/*.md`, `index.md`, `graph.*` | Generated from the records; never hand-edited. `graph.html` is the browsable viewer: cytoscape.js for the graph, marked.js for the record, both payloads embedded so it opens over `file://`. Records cluster into compound nodes by `group`; fill is the domain, size is in-degree, a red ring is a superseded record. Its default layout is computed deterministically, so a rebuild draws the same picture | Both | `make adrs` runs |
| `docs/rollout.md` | The grader surface: what a `CaseOutput` offers, the bundled verifiers, the goldens convention | Eval authors | A `RunResult` field, a verifier or a tolerance changes |
| `docs/token-accounting.md` | How the token and cost figures are derived, with provider sources | Both | A provider's reporting or the derivation changes |
| `report-ui/README.md` | The report SPA's own build, test and component conventions | Contributors to the page | The page's toolchain changes |
| `src/pytest_xharness_eval/assets/XHARNESS-REPORT-GLOSSARY.md` | Shipped asset: the report page's own element ids and metric definitions, distributed in the wheel beside the page | Report readers | A page id or metric name changes |

## Naming

- Root meta-files: UPPERCASE (`README.md`, `CONTRIBUTING.md`, `GLOSSARY.md`, …).
- Inside `docs/`: lowercase kebab-case.
- ADR records: `NNNN-slug`, four digits zero-padded, so lexical sort is chronological.
  Ids and slugs are **immutable**: every citation in the code and in prose resolves
  through them, so renumbering is forbidden.
- Point-in-time documents (findings, campaign logs, session notes) carry an ISO date in
  the filename; living documents never do.

## Pointers

- ADR directory: `docs/adrs/`
- ADR index: `docs/adrs/index.md` (generated)
- ADR schema: `docs/adrs/record.schema.json`
- ADR generator: `docs/adrs/okf_render.py`, run by `make adrs`
- Docs site source: none
- Design tokens: `src/pytest_xharness_eval/assets/report.tokens.json`

## Required cross-links

- `AGENTS.md` → this file, and → `docs/adrs/index.md` with "check existing decisions
  before raising an open question".
- `AGENTS.md` → `GLOSSARY.md` with both standing instructions: use the canonical terms
  for all naming; add a new domain term in the same change that introduces it.
- `README.md` → `CONTRIBUTING.md`.
- Every ADR that supersedes or refines another links it from its `Status:` sentence; the
  typed edge in the record's `relates_to` is inferred from that sentence, never a
  replacement for it (ADR 0047).

## Split/merge triggers

- `docs/` adopts Diátaxis folders when the flat tree passes ~10 topic documents.
- A scoped `AGENTS.md` appears beside any subtree with rules that bind only it
  (`report-ui/` is the candidate if its conventions outgrow the root file's pointer).
- A record's `description` and `tags` become required once enough records carry them
  that writing the rest is filling a gap rather than inventing a field.
