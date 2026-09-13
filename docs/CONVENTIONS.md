# Documentation Conventions

How this repository organises its documentation.
Agents and humans: consult this before creating, moving, or renaming any doc.

Written from the repository's observed practice, not imposed on it. Every line below
describes what the tree already did, except where marked *(baseline)*.

## Dialect

- **Flavour:** standard.
- **Docs taxonomy:** flat `docs/`, no Diátaxis folders. The tree is five living
  documents plus the ADR bundle (the two session-log references sit beside
  `token-accounting.md`, `rollout.md` and this file); Diátaxis folders arrive at
  about ten, so four near-empty buckets would still be premature.
- **Glossary:** `GLOSSARY.md` at root, one canonical term per concept. Agents add new
  domain terms in the same change that introduces them. *(baseline; extracted from
  `ARCHITECTURE.md#vocabulary`, 2026-08-31.)*
- **ADR layout:** file-per-decision at `docs/adrs/NNNN-slug.{yml,md}`, generated
  `index.md`.
- **ADR surface:** `okf-yaml`, **adopted strictly** (ADR 0048, superseding ADR 0047).
  Records are authored in `docs/adrs/NNNN-slug.yml` and their markdown is generated.
  `docs/adrs/record.schema.json` is the librarian's shipped record schema with nothing
  relaxed: every field it requires is required here. The only edits are the tightenings
  the convention asks an adopter to make — the `ADR-` id prefix, and `group`/`tags` drawn
  from this repository's closed domain enum.
- **Record domains:** every record declares one `group` (its primary domain, and the
  compound parent it sits in on the graph) and a `tags` list of one or two domains,
  primary first. Both are a closed enum in `record.schema.json`, so a typo fails the
  build rather than creating a group of one. The eleven domains are `accounting`,
  `architecture`, `collection`, `docs`, `evidence`, `grading`, `harness`, `packaging`,
  `pricing`, `report` and `storage`. A record needing a third tag has usually not been
  read closely enough to say what it is mainly about.
- **Record shape:** seventeen fields, all required. Identity (`id`, `slug`, `plan_id`),
  routing (`title`, `description`, `group`, `tags`), lifecycle (`status`, `accepted_on`,
  `last_changed_on`), the reusable rule (`lens`), the grounding (`provenance`,
  `enforced_in`), the typed edges (`relates_to`), and the argument in three decomposed
  parts: `problem` (`symptom`, `pain_point`), `decision` (`given`, `we_prefer`,
  `because`, `unless`, `in_practice`) and `consequences` (`pros`, `cons`, each with at
  least one entry). `we_prefer` names the rejected alternative; `unless` is the escape
  hatch or the word `never`. A clause that argued with a table or a fenced example keeps
  it, as a markdown block scalar inside `in_practice`.
- **ADR format:** the librarian's shipped record template. The title lives in
  frontmatter, the record opens with its **Lens** blockquote, then `## Relates to`,
  `## Problem`, `## Decision` and `## Consequences`. There is no H1 and no `Status:`
  sentence — the lifecycle word is `status`, and the scope of a supersession travels on
  the edge that caused it, in its `note`.
- **Generated paths:** `docs/adrs/*.md`, `docs/adrs/index.md`, `docs/adrs/graph.md`,
  `docs/adrs/graph.json`, `docs/adrs/graph.html`.
- **Regenerate:** `make adrs`. `make adrs-check` is the CI gate: it renders (which
  refuses a record that fails the schema or names a target that does not exist), runs
  `docs/adrs/okf_verify.py` for OKF conformance of the output, then fails on a dirty
  tree.
- **Prose:** the generated records pass `gooddocs`' `prose_gates.ts` with zero body
  findings: one sentence per line, a 25-word sentence budget, no em-dash, and no list
  disguised as comma- or semicolon-joined prose. The gate reads the generated markdown,
  so a finding is fixed in the `.yml` and the bundle is rebuilt, never in the `.md`. Two
  things the gate cannot see: it has no frontmatter parser, so it reads each record's
  YAML header as prose (those findings are not defects), and the record template adds
  `Lens :`, `Given :` or `We prefer :` to a field's first sentence, which counts against
  that sentence's budget.
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
| `docs/claude-session-log.md` | Diagram-led reference for what a `~/.claude` session log actually contains: structure (project dir, session file, subagent tree, workflow nesting), the record-kind catalogue by category, and the facts that have already cost debugging time (usage dedup, `contextWindow` null, thread nesting, timestamp ordering) | Both | `harness/claude.py`, `harness/records.py` or the real-corpus census they are checked against changes |
| `docs/codex-session-log.md` | Diagram-led reference for what a `~/.codex` rollout log actually contains: structure (date-partitioned rollouts, primary/thread split, `session_index.jsonl`), the record-kind catalogue by category, and the facts that have already cost debugging time (cumulative `token_count`, `session_id` non-identity, `compacted`, duplicate index ids) | Both | `harness/codex.py`, `harness/records.py` or the real-corpus census they are checked against changes |
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
- ADR conformance gate: `docs/adrs/okf_verify.py`, run by `make adrs-check`
- Docs site source: none
- Design tokens: `src/pytest_xharness_eval/assets/report.tokens.json`

## Required cross-links

- `AGENTS.md` → this file, and → `docs/adrs/index.md` with "check existing decisions
  before raising an open question".
- `AGENTS.md` → `GLOSSARY.md` with both standing instructions: use the canonical terms
  for all naming; add a new domain term in the same change that introduces it.
- `README.md` → `CONTRIBUTING.md`.
- Every ADR that supersedes or refines another declares a typed edge in `relates_to`,
  and carries the governing clause — which part was replaced, and which stands — in
  that edge's `note`. There is no `Status:` sentence for the relation to be inferred
  from: the edge and its note are where the phrasing now lives (ADR 0048).

## Split/merge triggers

- `docs/` adopts Diátaxis folders when the flat tree passes ~10 topic documents.
- A scoped `AGENTS.md` appears beside any subtree with rules that bind only it
  (`report-ui/` is the candidate if its conventions outgrow the root file's pointer).
- A twelfth `group` / `tags` domain is added to `record.schema.json` when two records
  would otherwise be filed under a domain that describes neither. Adding one is a
  deliberate edit to the enum, never a value a record introduces.
