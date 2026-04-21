# Troubleshooting

## La vista Terria no aparece en un recurso

Revisar:

- que `terria_view` esté en `ckan.plugins`;
- que el formato del recurso sea compatible según `ConfigManager.SUPPORTED_FORMATS`;
- que la acción `resource_view_list` del plugin esté activa;
- que no exista ya una vista Terria previa;
- que la request no incluya `activity_id`.

Ver también:

- [[Modulos]]
- [[Flujos Importantes]]

## El iframe carga Terria, pero no muestra datos

Revisar:

- `ckan.site_url`;
- URL real del recurso;
- bounds del dataset;
- `custom_config` guardado;
- instancia Terria configurada en `terria_instance_url`;
- CORS entre CKAN y Terria.
- en datasets privados, que la URL final del recurso no quede relativa (`/dataset/...`) y que se esté resolviendo vía uploader con URL absoluta de `ckan.site_url`.

## El estilo SLD no se aplica

Revisar:

- que `style` apunte a un SLD accesible por URL;
- si el recurso es `shp` o raster compatible con la lógica SLD actual;
- logs con `TERRIA_DEBUG=true`;
- tests en [[Testing]] orientados a SLD;
- si el problema está en el nombre de columna del shapefile.

## El catálogo completo responde `202 generating`

Esto es normal si:

- todavía no existe caché inicial;
- se disparó una regeneración en background.

Acciones:

- esperar y reintentar;
- revisar `/api/terria/cache/stats`;
- revisar permisos del directorio de caché.

## No se generan archivos cacheados

Revisar:

- `ckan.storage_path`;
- permisos de escritura;
- fallback a `/tmp` o temp dir;
- respuesta de `/api/terria/cache/stats`.

## El guardado de configuración falla

Revisar:

- que el usuario esté autenticado;
- que `view_id` exista;
- que la instancia Terria responda al protocolo de `postMessage` esperado;
- que `custom_config_url` sea HTTP(S).

## `pytest` falla por falta de CKAN

Esperable si no está instalado CKAN en el entorno.

Opciones:

- usar un virtualenv de CKAN;
- ejecutar solo tests raíz no acoplados;
- usar `nosetests` con `test.ini` en entorno completo.

## El catálogo incluye o excluye datasets de forma inesperada

Revisar:

- filtros de `private` y `state`;
- wrappers en `action_filters.py`;
- permisos del usuario en endpoints privados;
- datos devueltos por `package_search`.

## Pendiente por confirmar

- runbook operativo oficial;
- ubicación de logs de producción más usados por el equipo.
