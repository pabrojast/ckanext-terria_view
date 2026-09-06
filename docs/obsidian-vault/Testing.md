# Testing

## Resumen

El repositorio tiene una estrategia de pruebas mixta.

Hay tres capas distintas:

1. tests formales CKAN bajo `ckanext/terria_view/tests/`;
2. tests y scripts raíz orientados a SLD y compatibilidad;
3. scripts manuales contra endpoints remotos.

## Estado observado

Para el catálogo privado lazy, la sesion same-origin y el proxy se ejecuta (sin CKAN instalado; `test_private_datasets.py` mockea `ckan.*` y `flask` via `sys.modules`):

```bash
pytest -q test_private_datasets.py test_strip_private_catalog.py test_process_custom_config_sld.py
```

Resultado en la ultima actualizacion de esta nota: `86 passed` (67 en `test_private_datasets.py`, 13 en `test_strip_private_catalog.py`, 6 en `test_process_custom_config_sld.py`).

Cobertura de `test_private_datasets.py`:

- selección de modo, referencia inicial, índice modular, expansión por dataset, namespace de modelos, guardado idempotente y eliminación de tokens (existente);
- `GET /api/terria/user/session`: anonimo `200` sin usuario, autenticado con URLs relativas y `catalog_id`, ruta registrada, nunca lanza (payload anonimo ante error interno);
- `_get_user_context` con el `AnonymousUser` truthy de CKAN 2.10; `_create_private_json_response` fija `request.environ['__no_cache__']` y ya no envia `Pragma`;
- `_api_url` relativa/absoluta, `is_same_origin`, `build_proxy_resource_url(absolute=False)`, `format_dataset_item(relative_urls=)` y que `_proxy_resource_id`/`strip_proxy_tokens`/`refresh_proxy_tokens` aceptan URLs relativas;
- indice lazy: una sola `package_search` con `NON_PUBLIC_FQ` y `extras_access_level` en `fl`, grupos `isOpen`/`shareable: false`, solo datasets con `can_download`, fallback private-only sin datashare;
- expansion por dataset: rechaza nivel `public` y `viewable` sin descarga, acepta legacy `private=True` sin nivel, lee `access_level` desde `extras`, exige `private=True` sin datashare;
- `get_resource_url` acuna token para datasets con `access_level` no publico **solo si `user_may_download` lo permite**: un logueado sin `can_download` (p. ej. `viewable` sin autorizacion) recibe la URL de descarga normal y tampoco se le resuelve la SAS; datasets publicos y anonimos no ejecutan la comprobacion. `user_may_download` prefiere `datashare_resource_download`; `_refresh_proxy_tokens_in_encoded_config` usa ese helper;
- `setup_template_variables` real (colaboradores mockeados via `_render_terria_view`) nunca persiste `cached_config` para datasets no publicos (`access_level` top-level o en `extras`, `private=True`) ni cuando la URL calculada apunta al proxy con token; un dataset publico con URL plana si se cachea (`_may_persist_cached_config`);
- proxy `resource_content`: token valido reenvia `Range`/`If-None-Match` con `Accept-Encoding: identity` y pasa `206` + `Content-Range`; `304` sin cuerpo y cierre del upstream; `HEAD` cierra de inmediato; sesion sin token (`no-store`, `Vary: Cookie`); `401` anonimo / `403` sin permiso; token caducado con sesion valida; los errores nunca devuelven la URL upstream; `Content-Disposition` saneado; `416` pasa `Content-Range` sin cuerpo y cierra el upstream; `Content-Encoding` y el `Content-Length` comprimido se reenvian tal cual;
- rutas: `user/session` y el preflight `OPTIONS` se comprueban sobre el Blueprint mockeado (`_registered_routes()` devuelve regla → metodos y `_route_function(nombre)` recupera la funcion real que se registro), llamando a la funcion y mirando las cabeceras, no leyendo el fuente.

Fakes del harness: `FakeUser`, `FakeAnonymousUser`, `FakeResponse` (parcheado sobre `api_endpoints.Response`), `FakeUpstream` (`raw.stream`, `text`, `close`), `_flask_request` (parcheado sobre `api_endpoints.request`, con `environ`), `_registered_routes`/`_route_function` (leen las llamadas grabadas en el `Blueprint` mockeado) y `_render_terria_view` (ejecuta `setup_template_variables` con `Terria_ViewPlugin.__new__` y colaboradores `MagicMock`). `toolkit.url_for` es un `MagicMock`, asi que `_ckan_path` siempre usa sus fallbacks en tests.

Durante la primera version de esta nota se ejecutó:

```bash
pytest --collect-only -q
```

Resultado:

- 22 tests raíz fueron colectados;
- la colección falló en `ckanext/terria_view/tests/test_plugin.py` por ausencia del módulo `ckan` en el entorno local.

Esto confirma que la suite no está completamente desacoplada del runtime CKAN.

## Qué tests existen

### Tests del plugin CKAN

Ruta:

- `ckanext/terria_view/tests/test_plugin.py`

Observación:

- actualmente es un placeholder con `pass`.

### Tests raíz orientados a SLD

Ejemplos:

- `test_sld_robust.py`
- `test_sld_final.py`
- `test_sld_corrections.py`
- `test_problematic_sld.py`
- `test_terria_compliance.py`
- `test_process_custom_config_sld.py`

Cobertura funcional:

- parseo SLD;
- robustez ante XML defectuoso;
- normalización de colores;
- compliance de salida para TerriaJS;
- casos específicos de columnas y reglas;
- `process_custom_config` no pisa leyendas/`renderOptions`/`styles` ya guardados cuando hay SLD (COG y SHP, `tif`/`TIF`/`SHP`).

### Tests raíz orientados a endpoints y compatibilidad

Ejemplos:

- `test_private_datasets.py` (catalogo privado lazy, whoami, proxy; deterministas, sin red)
- `test_strip_private_catalog.py`
- `test_cache_preload.py`
- `test_fixes.py`
- `test_import_fix.py`

Observación:

- algunos llaman endpoints remotos hardcodeados;
- no todos son adecuados para CI determinista.

## Comandos relevantes

Tests rápidos:

```bash
pytest -q
pytest -k sld -q
```

Tests integrados CKAN:

```bash
nosetests --with-pylons=test.ini --with-coverage --cover-package=ckanext.terria_view
```

## Limitaciones actuales de la suite

- falta una suite formal más robusta para `plugin.py`, `api_endpoints.py` y `terria_json_generator.py`;
- varios tests son más scripts de exploración que unit tests aislados;
- hay dependencia en servicios externos y URLs concretas;
- el test del plugin no aporta cobertura real todavía.

## Recomendación práctica

Para iterar por áreas:

- cambios en SLD: ejecutar primero tests raíz `test_sld_*`;
- cambios en el catalogo privado, el whoami o el proxy: `pytest -q test_private_datasets.py` primero, y despues `curl` contra CKAN real (con la cookie `ckan`) para comprobar cabeceras efectivas (`Cache-Control`, `Vary`, `206`), porque el middleware de CKAN no esta en el harness;
- cambios en otros endpoints o caché: validar manualmente con `curl` y, si es posible, CKAN real;
- cambios en integración CKAN: ejecutar `nosetests` con entorno completo.

## Pendiente por confirmar

- qué subconjunto de tests se considera oficialmente soportado;
- si hay una suite CI moderna fuera de Travis;
- si los scripts raíz deben seguir siendo tests o migrarse a `scripts/` o `examples/`.
