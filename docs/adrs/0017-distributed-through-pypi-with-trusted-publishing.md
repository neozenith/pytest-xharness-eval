# 0017: Distribute through PyPI with trusted publishing, released from a GitHub Release

Status: accepted, 2026-08-21; first release (0.1.0) published to PyPI the same
day from GitHub Release `v0.1.0`. Refines [0014](0014-register-through-the-pytest11-entry-point.md).

## Context

ADR 0014 made the plugin its own distribution but left installation at "an editable
path dependency during development". That works only on a machine that holds both
repositories side by side; it is not something a consumer's `pyproject.toml` can
record, and the README already instructs `uv add --dev pytest-xharness-eval`, which
resolves only against an index. The package follows the maintainer's standard packaging
conventions: a `uv_build` wheel, a `Makefile` as the command surface,
and publishing driven by CI rather than by a laptop.

A PyPI API token would work but is a long-lived secret to store and rotate. PyPI's
trusted publishing instead issues a short-lived upload token against an OpenID
Connect claim set that names the repository, the workflow file, and the environment.

## Decision

PyPI is the distribution channel and the only one a consumer is told about. A release
is a GitHub Release: publishing it triggers `.github/workflows/publish.yml`, which
builds the wheel with `uv build --wheel` and uploads with `uv publish` under the
`pypi` environment with `id-token: write`. The trusted publisher registered on PyPI
for `pytest-xharness-eval` names exactly that owner, repository, workflow filename,
and environment. No publishing token is stored anywhere.

The version is declared twice, `version` in `pyproject.toml` and `__version__` in the
package, and a unit test pins them equal, so a bump to one without the other fails
`make test` before a tag can be cut. Tags are `vX.Y.Z` and match the wheel's version.

The editable path dependency remains a development convenience for working on the
plugin against a live consumer; it is never what a consumer commits. `make
publish-test` against TestPyPI and `make publish` stay as the manual, token-based
fallback for when the OIDC path is unavailable.

## Consequences

A consumer pins a version from PyPI and gets the `pytest11` registration of ADR 0014
by installing it; the consuming repository no longer needs to know where the plugin's
source lives. Until the first release is cut, `uv add --dev pytest-xharness-eval`
fails with no matching version rather than installing something stale, which is the
loud failure this project prefers. Publishing has one silent coupling: if the
environment name on PyPI's publisher differs from the workflow's `pypi` environment,
the token exchange fails with a claims mismatch that is visible only in the Actions
log. Every release is a GitHub Release, which is also where the changelog lives
(`project.urls.Changelog`).

## Lens

Make the release path one trigger with one identity: a single event starts it, OIDC
proves who is publishing, and nothing long-lived has to be stored or rotated.
