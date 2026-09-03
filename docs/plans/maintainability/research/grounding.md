# Grounding dossier — measurable maintainability gates in pytest-xharness-eval

## 1. Gates that exist today
pyproject.toml:72-83 ruff select = ["E","F","UP","B","SIM","PTH","TCH","C90","TID"]; ignore = []
pyproject.toml:127-128 [tool.ruff.lint.mccabe] max-complexity = 10
pyproject.toml:88-106 TID251 banned-api: harness.claude / harness.codex / harness / verify / emit / runtime unreachable from outside their layer. Each rule carries "Owner" + "Review by: 2027-08-28 -- delete this rule if the registry has been abandoned, rather than leaving it to mislead."
pyproject.toml:108-122 per-file-ignores exempting entry points / layer-self / tests from TID251
pyproject.toml:124-125 pydocstyle convention = "google"
pyproject.toml:139-153 coverage branch = true, patch = ["subprocess"]; pytest addopts includes --cov --cov-fail-under=90 --cov-report=json
pyproject.toml:155-163 [tool.mypy] strict = true
Makefile:22-25 check: uvx ruff check src/ tests/ ; uvx isort --check-only ; uv run mypy src/
Makefile:27-29 test: check; uv run pytest; uv run .github/scripts/update_coverage.py
Makefile:99-113 adrs / adrs-check: `git diff --quiet -- docs/adrs` -> "docs/adrs is stale or hand-edited"
.github/workflows/cicd.yml:14-33 basic-checks runs make check then make test
.github/workflows/cicd.yml:35-51 report-ui job: `cmp dist/index.html ../src/pytest_xharness_eval/assets/report.html` gates a stale promoted asset
No pre-commit config exists (verified by find).

## 2. Absence verified
radon / xenon / wily / lizard / cognitive-complexity / SonarQube appear ONLY as prose inside docs/plans/maintainable.md (lines 17, 94-95, 320-321, 323, 337-338, 356-357, 381-382, 386). Not in deps, CI, or scripts. `uvx radon ...` is quoted as an ad-hoc command, never wired into make check.

## 3. ADRs (docs/adrs/NNNN-slug.yml, markdown generated, ADR 0047)
0002 Every eval cell always invokes the real CLI. Lens: "Never let a cell report a verdict without a real session log behind it."
0034 A harness is a class, the registry is the only dispatch, and the layers are named. "The boundary is enforced, not just documented. A ruff TID251 banned-api rule fails the build if anything outside the harness package imports harness.claude or harness.codex by name." Lens: "When one axis is named but stays a string, its behaviour spreads into every module that has to ask what it is... Give the axis a type, make the registry the only way to reach an implementation, and let a linter keep the boundary you just drew."
0039 The package listing is the architecture. "Each layer depends only on the ones above it in that list, entry points last." "A fourth inversion fails the build." Lens: "the question 'may this import that?' has an answer before the import is written -- and the answer can be checked by a linter rather than by whoever reviews the diff."
0040 The plugin is a hook manifest, and each job behind it is a module. Context: plugin.py at 478 lines doing five jobs. Lens: "Push the expensive line down until the pragma fits it exactly."
0041 A shared vocabulary is a domain noun, and a manifest exports nothing of its own. Lens: "Which layer may everyone that needs it import? -- that is the only placement that can be enforced rather than agreed."
0045 The verifiers ship with the plugin. Lens: "withhold it and every consuming repository writes the vocabulary anyway, four times, and two of the copies rot into assertions that cannot fail."

## 4. docs/CONVENTIONS.md
:9-20 Glossary at root, one canonical term per concept, agents add terms in the same change. ADR layout file-per-decision docs/adrs/NNNN-slug.{yml,md}, generated index.md. ADR surface okf-yaml.
:31-34 ADR format: `# NNNN: Title`, `Status:`, `## Context`, `## Decision`, `## Consequences`, closing `## Lens` carrying the reusable rule.
:44-60 layout-map table (README, CONTRIBUTING, AGENTS, ARCHITECTURE, GLOSSARY, docs/adrs/*, docs/rollout.md, docs/token-accounting.md, report-ui/README.md, XHARNESS-REPORT-GLOSSARY.md). **docs/plans/ is not a row -- uncharted.**
:69-70 "Point-in-time documents carry an ISO date in the filename; living documents never do."

## 5. GLOSSARY.md
~45 terms: case, task, invocation, EvalSuite, cell, harness, matrix, skills root, fixture, workspace, session log, Harness, SessionLog, RunResult, Usage, CaseOutput, verifier, golden, CaseRef, CostEstimate/AppliedRates, CostStatus, Verdict, pipeline, settings, CellRun/Attempt, CacheLayout/SessionDir/LocatedSession, captured, CellMetrics/Outcome, history, call/turn, subagent, estimated cost, harness reported cost, total tokens, baseline tokens, report/IndexRow, RunSummary, LegacyCapture, SessionId/SessionTurnId, record kind, skill coverage, SkillFile/FileCoverage, CoverageSummary/SkillCoverage, IgnoreRules, context window, design tokens.
**No complexity / maintainability / fitness-function vocabulary present. Net-new.**

## 6. The one repo-statistic script
.github/scripts/update_coverage.py -- reads coverage.json, computes badge colour, rewrites README.md between `<!-- coverage-badge -->` markers. Invoked from Makefile:29 as part of `make test`.
:31-47 determine_coverage_color: >=90 brightgreen, >=80 yellow, >=70 orange, else red.
This is the existing precedent for "a script that computes a repo statistic and writes it into a doc".

## 7. Measured shape of src/ (2026-09-01)
`uvx ruff check src/ --select C901` -> "All checks passed!"  ZERO units over the gate of 10.
`uvx ruff check src/ --select C901 --config 'lint.mccabe.max-complexity=0'` -> 310 units scored (one line each).
`uvx radon cc src/ -s -a --total-average` -> "372 blocks (classes, functions, methods) analyzed. Average complexity: A (3.4193548387096775)"
radon non-A hotspots:
  harness/claude.py:308 ClaudeSessionLog.to_result   D (26)   <-- ruff C901 scores this **3**
  harness/claude.py:215 _Ledger.assistant            D (21)   <-- ruff C901 scores this **8**
  codex.py:416 _classify C(17); claude.py:397 _classify C(16); subagents_of C(16)/C(12);
  _Ledger.response_item C(13); _Ledger.token_count C(13); IndexRow.of C(19);
  parse_price_lines C(15); annotate C(16); SkillCoverage C(14); .over C(13); CellMetrics.of C(14)
`uvx radon mi src/ -s` -> every file grade A. Lowest: harness/codex.py A(29.52), harness/claude.py A(30.33), derive/skillcov.py A(43.02), model/runresult.py A(47.44). Many __init__.py at A(100.00).
Largest files: codex.py 478, claude.py 472, model/runresult.py 468, derive/skillcov.py 405, emit/metrics.py 301. src total 6882 lines.

Root cause of the ruff/radon gap (verified by reading installed mccabe 0.7.0 source): its AST visitor has NO handler for ternaries, comprehensions, or and/or. This codebase's comprehension- and ternary-heavy style therefore passes C901 cleanly while radon/lizard/complexipy flag the same functions as the repo's worst.

## 8. docs/plans/
docs/plans/maintainable.md -- 389 lines, an explainer/teaching guide, not a requirements plan. Opens "Cyclomatic complexity is a smoke alarm, not a target". Has a diagnosis table (:350-357), a three-tool comparison table (:323-338), References (McCabe 1976, Watson & McCabe NIST SP 500-235, Campbell 2018, ADR 0034).
docs/plans/2026-08-31-mermaid-edge-label-contrast.md -- dated finding writeup ("**Date:** 2026-08-31. **Found while:** authoring maintainable.md...").
=> docs/plans/ in practice holds point-in-time findings and explainers, not standing requirements plans. Observed practice, not a documented charter.
