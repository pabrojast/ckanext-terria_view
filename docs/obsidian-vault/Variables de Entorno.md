# Variables de Entorno

## Variables de entorno observadas en código

### `TERRIA_DEBUG`

Uso:

- habilita logs `print()` de debug en varios módulos.

Impacta:

- `plugin.py`
- `terria_config_builder.py`
- `terria_json_generator.py`
- `sld_processor.py`
- `file_cache_manager.py`
- `cache_preloader.py`
- `action_filters.py`

Valor esperado:

- `true` para activar;
- cualquier otro valor se interpreta como desactivado.

### `TERRIA_PRELOAD_CACHE`

Uso:

- fuerza habilitar o deshabilitar el warmup de caché al arranque.

Valores observados:

- `true`, `1`, `yes`, `on`
- `false`, `0`, `no`, `off`

### `TERRIA_PRELOAD_DELAY`

Uso:

- delay en segundos antes de iniciar el preload en background.

## Configuración relevante en CKAN

Estas no son variables de entorno, pero sí parte del contrato operativo de la extensión.

### `ckan.site_url`

Crítica para:

- construir URLs de dataset;
- componer referencias a endpoints `/api/terria/*`;
- resolver origen del portal.

### `ckanext.terria_view.default_title`

Título por defecto de la vista Terria.

### `ckanext.terria_view.default_instance_url`

URL base de la instancia Terria a embeber.

Como se aplica (`plugin.py`):

- las vistas autocreadas en `resource_view_list` guardan el valor vigente en su campo `terria_instance_url`;
- en render, `view.get('terria_instance_url', default_instance_url)`: el default solo se usa cuando la vista **no** tiene `terria_instance_url` guardado;
- `private_catalog_mode=auto` se resuelve con esa URL efectiva (`resolve_private_catalog_mode` / `is_same_origin`): same-origin ⇒ lazy y URLs relativas; otro origen ⇒ inline y URLs absolutas.

Consecuencia operativa: cambiar este default **no** altera las vistas que ya tienen una URL de instancia guardada (siguen en el modo que les corresponda por su propia URL). Para que una vista existente pase a lazy hay que editar su `terria_instance_url` o crear una vista nueva. El default de codigo apunta a `https://ihp-wins.unesco.org/terria/`; para el entorno dev el plan fija `https://data.dev-wins.com/terria/` en el `production.ini` de `ckan-unesco-docker` (fuera de este repo; `Pendiente por confirmar` hasta que se despliegue).

### `ckanext.terria_view.preload_cache`

Flag equivalente en configuración CKAN para el preload de caché.

### `ckanext.terria_view.preload_delay`

Delay equivalente en configuración CKAN.

### `ckanext.terria_view.strip_resource_extras_enabled`

Activa o desactiva el recorte de extras pesados en `package_show` y `resource_show`.

### `ckanext.terria_view.strip_resource_extras_keys`

Lista separada por comas de extras a remover.

### `ckanext.terria_view.inject_private_catalog_on_public_views`

Si está en `true`, el catálogo de datasets privados del usuario logueado se inyecta en el `#start=` de **todas** las vistas Terria; si está en `false` (default), solo en vistas de datasets privados. Anónimo nunca recibe el catálogo privado, independientemente del flag. Ver [[Flujos Importantes]] (guardado de configuración) y [[Troubleshooting]] (crecimiento del config de la vista).

### `ckanext.terria_view.private_catalog_mode`

Controla cómo se carga el catálogo privado:

- `auto` (default): lazy cuando CKAN y Terria comparten esquema, host y puerto; inline en otro caso;
- `lazy`: inyecta una referencia pequeña y consulta el catálogo autenticado al abrirlo;
- `inline`: genera el catálogo completo en el render, preservando el comportamiento anterior.

El modo lazy requiere que la sesión CKAN alcance `/api/terria/user/private-catalog`; los despliegues IHP-WINS dev y producción sirven CKAN y `/terria` en el mismo origen. En lazy same-origin las URLs del catalogo y del proxy son relativas (`/api/terria/...`). Forzar `lazy` con un Terria de **otro** origen no esta soportado: el indice emite URLs relativas que ese Terria resolveria contra su propio origen (404) y la cookie CKAN no viaja cross-origin (401); usar `auto` o `inline`. El Terria standalone con `configParameters.ckanSession` (config de TerriaMap, no de CKAN) usa los mismos endpoints mas `GET /api/terria/user/session`; no necesita ninguna clave nueva en CKAN. Ver [[Flujos Importantes]] (flujos 5 y 10).

### `ckanext.terria_view.max_custom_config_bytes`

Tamaño máximo (bytes) del `custom_config_url` que `/api/terria/view/<id>/save-config` acepta; por encima responde 413. Default `4 * 1024 * 1024` (4 MB) — suficiente para una vista que hornea el catálogo de datasets privados del usuario (que puede rondar ~1 MB). Subirlo si una vista legítimamente necesita más; bajarlo para ser más estricto.

### `ckan.storage_path`

Usado por `FileCacheManager` como primera opción para guardar JSONs cacheados.

### `beaker.session.secret` / `SECRET_KEY`

Secret HMAC que `ResourceUtils.generate_resource_token` utiliza para firmar los tokens del proxy de recursos privados (`/api/terria/resource/<id>/content`).

- Debe estar seteado; en caso contrario hay un fallback inseguro (`ckanext-terria-view-proxy-fallback`) que invalidaría el propósito del token.
- Si se rota, todos los tokens emitidos antes del cambio dejan de verificar — las vistas privadas ya cargadas reintentarán con tokens nuevos al recargar.

## Dependencias opcionales

### `ckanext-datashare`

No es una dependencia de instalacion, pero el catalogo privado la detecta en runtime:

- accion `datashare_access_check` (`private_catalog.PrivateCatalogBuilder._access`): decide que datasets no publicos entran en el indice lazy y en la expansion por dataset. Solo se incluyen los que devuelven `can_download`. Si `toolkit.get_action` lanza `KeyError`/`ImportError` (plugin ausente) se vuelve al comportamiento historico private-only (`capacity == 'private'` en Solr, `private=True` en `package_show`); cualquier otra excepcion excluye el dataset (fail closed);
- auth `datashare_resource_download` (`ResourceUtils.user_may_download`): gate del proxy por sesion y del refresco de tokens. Si `check_access` lanza `ValueError` (auth no registrada) se prueba `resource_show`; `NotAuthorized` u otra excepcion deniegan.

Niveles reconocidos en el extra `access_level`: `public | confidential | findable | viewable | restricted` (`private=True` de CKAN core ⟺ `confidential`). El indice usa `fq = +(capacity:private OR (access_level:* AND NOT access_level:public))` y `fl` con `extras_access_level`; requiere que Solr indexe `access_level` (lo hace el schema del despliegue IHP-WINS).

## Defaults observados

- `default_title`: `Terria Viewer`
- `default_instance_url`: `https://ihp-wins.unesco.org/terria/`
- `preload_cache`: `True`
- `preload_delay`: `10`
- `cache_timeout`: `3600` segundos en caché de memoria y archivo
- `inject_private_catalog_on_public_views`: `False`
- `private_catalog_mode`: `auto`

## Inferencia

Si `ckan.storage_path` no es escribible, la extensión intenta degradar a `/tmp`, `/var/tmp` o el temp dir del sistema. Esto reduce el riesgo operativo, pero puede hacer la caché más efímera.

## Pendiente por confirmar

- valores efectivos usados en producción;
- si `strip_resource_extras_enabled` se deja encendido por defecto en todos los entornos.
