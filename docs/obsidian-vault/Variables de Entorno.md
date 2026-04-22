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

### `ckanext.terria_view.preload_cache`

Flag equivalente en configuración CKAN para el preload de caché.

### `ckanext.terria_view.preload_delay`

Delay equivalente en configuración CKAN.

### `ckanext.terria_view.strip_resource_extras_enabled`

Activa o desactiva el recorte de extras pesados en `package_show` y `resource_show`.

### `ckanext.terria_view.strip_resource_extras_keys`

Lista separada por comas de extras a remover.

### `ckan.storage_path`

Usado por `FileCacheManager` como primera opción para guardar JSONs cacheados.

### `beaker.session.secret` / `SECRET_KEY`

Secret HMAC que `ResourceUtils.generate_resource_token` utiliza para firmar los tokens del proxy de recursos privados (`/api/terria/resource/<id>/content`).

- Debe estar seteado; en caso contrario hay un fallback inseguro (`ckanext-terria-view-proxy-fallback`) que invalidaría el propósito del token.
- Si se rota, todos los tokens emitidos antes del cambio dejan de verificar — las vistas privadas ya cargadas reintentarán con tokens nuevos al recargar.

## Defaults observados

- `default_title`: `Terria Viewer`
- `default_instance_url`: `https://ihp-wins.unesco.org/terria/`
- `preload_cache`: `True`
- `preload_delay`: `10`
- `cache_timeout`: `3600` segundos en caché de memoria y archivo

## Inferencia

Si `ckan.storage_path` no es escribible, la extensión intenta degradar a `/tmp`, `/var/tmp` o el temp dir del sistema. Esto reduce el riesgo operativo, pero puede hacer la caché más efímera.

## Pendiente por confirmar

- valores efectivos usados en producción;
- si `strip_resource_extras_enabled` se deja encendido por defecto en todos los entornos.
