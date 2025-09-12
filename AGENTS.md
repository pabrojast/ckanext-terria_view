# Repository Guidelines

## Project Structure & Module Organization
- Core extension: `ckanext/terria_view/` — main modules: `plugin.py`, `sld_processor.py`, `resource_utils.py`, `terria_config_builder.py`, `config_manager.py`.
- Templates: `ckanext/terria_view/templates/` (`terria.html`, `terria_instance_url.html`).
- Static assets: `ckanext/terria_view/public/` and `fanstatic/`.
- Tests: quick unit-style tests at repo root (`test_*.py`) and plugin tests in `ckanext/terria_view/tests/`.
- Packaging/config: `setup.py`, `setup.cfg` (Babel/i18n), `.coveragerc`, `test.ini`.

## Build, Test, and Development Commands
- Setup (editable install): `python -m venv .venv && source .venv/bin/activate && pip install -e .`
- Run fast tests (no CKAN stack): `pytest -q` (or `pytest -k sld` for SLD-only cases).
- Full integration (requires CKAN, Postgres, Solr): `nosetests --with-pylons=test.ini --with-coverage --cover-package=ckanext.terria_view`.
- i18n (per `setup.cfg`): `python setup.py extract_messages init_catalog update_catalog compile_catalog`.

## Coding Style & Naming Conventions
- Python 3.x, 4-space indentation, PEP 8/PEP 257. Use type hints where helpful.
- Modules and functions use `snake_case`; classes use `PascalCase` (e.g., `TerriaConfigBuilder`).
- Keep plugin wiring consistent with entry point `terria_view=ckanext.terria_view.plugin:Terria_ViewPlugin`.
- Do not print directly; guard debug output with `TERRIA_DEBUG=true`.

## Testing Guidelines
- Prefer `pytest` for quick iteration; use `nose` only when exercising CKAN integration via `test.ini`.
- Place new tests under `ckanext/terria_view/tests/` or root `test_*.py`. Name tests `test_<feature>.py` and functions `test_<behavior>()`.
- Aim to cover new/changed code; `.coveragerc` already omits CKAN internals.

## Commit & Pull Request Guidelines
- Commits: imperative present, scoped and small. Examples: `fix(sld): handle empty fill`, `feat(plugin): auto-create resource view`.
- PRs: describe problem, approach, and impacts; link related issues. Include test coverage and any config notes (`ckan.site_url`, `terria_instance_url`). Add screenshots for template/UI changes.

## Architecture Overview & Configuration Tips
- Flow: CKAN `Terria_ViewPlugin` → `ResourceUtils` (URLs/bounds) → `TerriaConfigBuilder` (catalog/config) → templates render TerriaJS instance; `SLDProcessor` parses SLD to styles.
- Required config: `ckan.site_url` (from CKAN), optional `TERRIA_DEBUG=true` for verbose logs. Ensure external `terria_instance_url` is reachable from the CKAN host.

