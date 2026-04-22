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
- en datasets privados con `ckanext-cloudstorage`, confirmar que la URL resultante del recurso sea SAS directa de blob (no el endpoint `/dataset/.../download/...`), porque Terria carga desde otro dominio y un `download` protegido devuelve `401`.
- si se usa `custom_config`, verificar que en el `#start` final exista al menos un item de datos en `initSources[].workbench` (si queda vacío, el mapa no abre capas por defecto).
- en CSV con estilos custom, evitar combinaciones inconsistentes como `mapType: "continuous"` junto a paletas `Category*` para columnas categóricas; en ese caso usar `mapType: "enum"` y `colorColumn`.

## El estilo SLD no se aplica

Revisar:

- que `style` apunte a un SLD accesible por URL;
- si el recurso es `shp` o raster compatible con la lógica SLD actual;
- logs con `TERRIA_DEBUG=true`;
- tests en [[Testing]] orientados a SLD;
- si el problema está en el nombre de columna del shapefile.
- si el estilo cambió y no se refleja en `ihp-wins.json`, invalidar caché con `POST /api/terria/cache/invalidate` y reintentar.
- si se actualizó el archivo SLD en la misma URL, confirmar que se ejecutó una invalidación (los resultados SLD se cachean en memoria por URL).

## Error `KeyError: 'url'` en `resource_view_list`

Revisar:

- recursos incompletos o históricos sin `url`/`format` al pasar por `can_view_resource`;
- que la validación de formato no asuma siempre `resource['url']` presente;
- que la autogeneración de vista use el `resource_show` actual del recurso y no `context['resource'].__dict__`.

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
