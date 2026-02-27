# Copilot Instructions — ckanext-terria_view

## Build, Test, and Development

```bash
# Editable install (no CKAN needed for unit tests)
python -m venv .venv && source .venv/bin/activate && pip install -e .

# Fast unit tests (no CKAN stack required)
pytest -q

# Run a single test file or match pattern
pytest test_sld.py -q
pytest -k "test_colorcolumn" -q

# Full integration tests (requires running CKAN + Postgres + Solr)
nosetests --with-pylons=test.ini --with-coverage --cover-package=ckanext.terria_view

# i18n workflow
python setup.py extract_messages update_catalog compile_catalog
```

## Architecture

This is a CKAN extension that renders geospatial resources (Shapefiles, GeoJSON, WMS, COG/GeoTIFF, CSV, KML, etc.) in a TerriaJS map viewer.

**Data flow:** `Terria_ViewPlugin` → `ResourceUtils` (resolves resource URLs + geographic bounds) → `TerriaConfigBuilder` (builds TerriaJS catalog JSON) → Jinja templates embed the config into a TerriaJS iframe URL.

**Key modules in `ckanext/terria_view/`:**

- `plugin.py` — CKAN plugin entry point (`Terria_ViewPlugin`). Implements `IResourceView`, `IConfigurer`, `IBlueprint`, `IActions`. Auto-creates Terria views for supported formats by overriding `resource_view_list`.
- `config_manager.py` — Manages plugin settings, supported format list (`SUPPORTED_FORMATS`), and format validation regex.
- `sld_processor.py` — Parses OGC SLD/SE XML into TerriaJS-compatible style traits (simplestyle-spec colors, legend items, enum colors). Handles both vector `TableStyleTraits` and raster `renderOptions`.
- `terria_config_builder.py` — Builds the TerriaJS v8 JSON catalog config (`initSources`, `catalog` items). Merges SLD styles into the config.
- `resource_utils.py` — Resolves resource download URLs (handles CKAN storage vs external URLs), discovers SLD files within a dataset, and extracts geographic bounds from package metadata.
- `api_endpoints.py` — Flask Blueprint (`terria_api`) exposing JSON endpoints for Terria catalog generation.
- `terria_json_generator.py` — Generates complete Terria JSON catalogs for datasets/organizations.
- `cache_manager.py` / `file_cache_manager.py` — In-memory and file-based caching for generated Terria configs. Cache invalidation triggers on view create/update/delete.
- `cache_preloader.py` — Background thread that pre-warms the Terria JSON cache on plugin startup.
- `action_filters.py` — Wraps `package_show` and `resource_show` to strip oversized resource extras from API responses.

**Templates:** `terria.html` (viewer iframe), `terria_instance_url.html` (admin form for configuring the view).

**Plugin entry point:** `terria_view=ckanext.terria_view.plugin:Terria_ViewPlugin` (in `setup.py`).

## Conventions

- **Debug output:** Never use bare `print()`. Guard all debug output with `TERRIA_DEBUG=true` env var check (see `_debug_print` pattern used throughout).
- **Commit messages:** Imperative, scoped — e.g. `fix(sld): handle empty fill`, `feat(plugin): auto-create resource view`.
- **Supported formats** are defined in `ConfigManager.SUPPORTED_FORMATS`. Update there (not scattered checks) when adding format support.
- **SLD processing** follows QGIS-compatible XML namespace handling. The `SLDProcessor.NAMESPACES` dict covers `sld`, `se`, `ogc`, `gml`, `xlink` namespaces.
- **Cached config signature:** `plugin.py` computes an MD5 signature of view inputs to skip expensive SLD re-fetching when nothing changed. The signature and encoded config are persisted in the resource view via `resource_view_update`.
- **Config values** come from CKAN's ini file: `ckanext.terria_view.default_title`, `ckanext.terria_view.default_instance_url`, `ckan.site_url`.
- **Tests at repo root** (`test_*.py`) are fast standalone tests that don't require CKAN. Tests in `ckanext/terria_view/tests/` may need the full CKAN test harness.
