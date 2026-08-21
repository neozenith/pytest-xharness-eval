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

.PHONY: format check test show_coverage docs build publish publish-test clean agent-skills-update
