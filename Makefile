######################################################################
# SETUP
######################################################################
.venv: pyproject.toml
	uv sync --all-groups

.venv/deps: .venv pyproject.toml
	uv sync --all-groups
	touch $@

agent-skills-update:
	npx skills@latest update

######################################################################
# QUALITY ASSURANCE
######################################################################

format: .venv/deps
	uvx ruff format src/ tests/ --respect-gitignore --line-length 120
	uvx isort src/ tests/ --profile 'black'

check: .venv/deps
	uvx ruff check src/ tests/
	uvx isort src/ tests/ --check-only
	uv run mypy src/

test: check .venv/deps
	uv run pytest
	uv run .github/scripts/update_coverage.py

show_coverage: test
	uv run -m http.server --directory htmlcov/

######################################################################
# DOCUMENTATION
######################################################################

docs:
	uvx --from md-toc md_toc --in-place github --header-levels 2 README.md
	uvx rumdl check . --fix --respect-gitignore -d MD013,MD033

######################################################################
# REPORT UI (report-ui/: the captured/report.html SPA, ADR 0028)
# bun is a build-time tool only; the built page is a committed asset and the
# Python package keeps its zero runtime dependencies.
######################################################################

# Serve the SPA with hot reload against a real captured directory.
#   make ui-dev CAPTURED=../agentic-dotfiles/skills/mermaidjs-diagrams/evals/captured
CAPTURED ?=

report-ui/node_modules: report-ui/package.json report-ui/bun.lock
	cd report-ui && bun install --frozen-lockfile
	touch $@

ui-install: report-ui/node_modules

ui-dev: report-ui/node_modules
	@test -n "$(CAPTURED)" || { echo "usage: make ui-dev CAPTURED=<skill>/evals/captured"; exit 1; }
	cd report-ui && XH_CAPTURED=$(abspath $(CAPTURED)) bun run dev

ui-format: report-ui/node_modules
	cd report-ui && bun run format

ui-check: report-ui/node_modules
	cd report-ui && bun run check

ui-test: report-ui/node_modules
	cd report-ui && bun run test

# One self-contained HTML file at report-ui/dist/index.html.
ui-build: report-ui/node_modules
	cd report-ui && bun run build

# Build, inject a captured directory the way `report.py --inline` does, and render the
# result headlessly: proves the bundle boots and the data binds without opening a browser.
ui-smoke: ui-build
	@test -n "$(CAPTURED)" || { echo "usage: make ui-smoke CAPTURED=<skill>/evals/captured"; exit 1; }
	uv run report-ui/scripts/inline.py $(abspath $(CAPTURED)) report-ui/dist/index.html report-ui/dist/inline.html
	cd report-ui && node scripts/smoke.mjs dist/inline.html

# Make the built SPA the page report.py ships; the Python tests then gate it, and CI fails
# when the committed asset is not the current build.
ui-promote: ui-check ui-test ui-build
	cp report-ui/dist/index.html src/pytest_xharness_eval/assets/report.html
	$(MAKE) test

######################################################################
# BUILD AND PUBLISHING
# https://docs.astral.sh/uv/guides/package/
######################################################################

build: .venv/deps test check
	rm -rf dist
	uv build --wheel

publish-test: build
	# export UV_PUBLISH_TOKEN=YOUR_TEST_PYPI_API_TOKEN_HERE
	uv publish --repository testpypi

publish: build
	uv publish

clean:
	rm -rf dist
	rm -rf .venv
	rm -rf htmlcov/
	rm -rf coverage.json
	rm -rf .*_cache
	rm -rf .coverage

.PHONY: format check test show_coverage docs build publish publish-test clean agent-skills-update ui-install ui-dev ui-format ui-check ui-test ui-build ui-smoke ui-promote
