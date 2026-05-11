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

## Dataset privado: el item aparece en `models` pero `workbench` y `timeline` quedan vacíos

Síntoma: al abrir una vista de un dataset **privado**, Terria recibe el config pero el CSV/SHP/COG no carga; el `shareData` muestra el modelo con `show: true` y `url` SAS, pero `workbench: []`, `timeline: []` y faltan `currentTime`/`startTime`/`stopTime`.

Causa: Terria (en otro dominio) intenta hacer `fetch` directo a la URL SAS de Azure. Si el Storage Account no tiene configurado CORS para el origin del iframe Terria, la carga del contenido falla y Terria no completa la inicialización del modelo.

Fix en el plugin:

- `ResourceUtils.get_resource_url()` devuelve una URL proxy CKAN firmada en lugar de la SAS directa. Flujo: `GET /api/terria/resource/<id>/content/<filename>?token=<token>` → CKAN resuelve la SAS server-side y stremea el contenido con `Access-Control-Allow-Origin: *`.
- El segmento `<filename>` se conserva intencionalmente en el path para que pase la validación cliente de TerriaJS (p. ej. `shp` exige `.zip`, `geojson` exige `.geojson`). La autorización no depende del filename, solo del token.
- Verificar que el endpoint esté accesible y responda `200` al hacer `GET` con token válido. Si devuelve `401` con `Invalid or expired token`, revisar `beaker.session.secret`/`SECRET_KEY` y que el mismo proceso CKAN haya generado el token (tokens firmados con otro secret no verifican).
- Si responde `502`, es que Azure rechazó la SAS: token del uploader expirado, permisos cambiados, o el blob fue movido.

Alternativa sin cambios en código: configurar CORS en el Storage Account (allowed origins = dominio del Terria) para que la URL SAS directa funcione. En ese caso el proxy queda como defensa en profundidad.

## Dataset privado con shapefile: "Invalid URL: Only zipped shapefiles are supported"

Síntoma: al cargar un `.zip` shapefile privado aparece en el iframe Terria el error `Invalid URL: Only zipped shapefiles are supported (the extension must be '.zip')`.

Causa: TerriaJS valida **la extensión de la URL** antes de intentar fetchear. Si el recurso se sirve vía el proxy, la URL debe terminar en `.zip` (o `.geojson`, `.csv`, etc. según el tipo).

Fix: asegurarse de que `ResourceUtils.build_proxy_resource_url` esté emitiendo el filename en el path (`/api/terria/resource/<id>/content/<filename.ext>?token=...`). `get_resource_url` usa `_extract_upload_filename(resource, resource_url)` para obtenerlo; si el resource tiene `url_type: upload` pero la URL no expone `/download/<filename>`, `_extract_upload_filename` puede devolver vacío y caer al path sin extensión. En ese caso, verificar que el recurso tenga una URL válida con el archivo en el path.

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

## La vista Terria de un recurso se vuelve lentísima / el formulario de editar vista tarda 30-60 s

Síntoma: `resource_view.config` crece a varios MB; `GET /dataset/.../edit_view/<id>` tarda 30-60 s y devuelve varios MB de HTML (a veces termina en `SIGPIPE` / `Broken pipe` en uWSGI porque el navegador se rinde); el `#start=` guardado en `custom_config` es una URL de >1 MB que el navegador apenas acepta.

Causa: `setup_template_variables` inyecta el catálogo de **datasets privados del usuario logueado** dentro de `encoded_config` para que el árbol de catálogo del iframe los muestre (`_merge_private_catalog_into_encoded_config`). Por defecto solo en vistas de datasets **privados**; con `ckanext.terria_view.inject_private_catalog_on_public_views = true` también en vistas de datasets públicos. Si el usuario pulsa "Save Configuration" (o vuelve a guardar la vista desde el formulario con esa URL del iframe en el campo), `getShareData` serializa todo ese árbol y queda horneado en `custom_config` — y se re-inyecta en el siguiente render, así que crece sin límite. Además los items privados llevan tokens firmados del proxy que **caducan**, rompiendo la vista guardada; y en una vista pública eso filtra la lista de datasets privados de ese usuario.

Fix en el plugin (`terria_config_builder.strip_private_catalog_*`):

- al procesar un `custom_config` (`process_custom_config`) y al guardarlo (`save_view_config`, `_process_form_data`) se eliminan las ramas `Private Datasets (...)` del estado TerriaJS antes de persistir/re-renderizar;
- `save_view_config` rechaza configs > `MAX_CUSTOM_CONFIG_BYTES` (512 KB) tras la limpieza;
- `_CONFIG_PROCESSING_VERSION` se subió para invalidar `cached_config` viejos.

Limpiar las vistas ya infladas (no lo hace el plugin solo): `scripts/strip_private_catalog_from_views.py` recorre los `resource_view` `terria_view`, quita las ramas privadas de `config.custom_config` y borra la copia obsoleta `config.__extras.custom_config_url`. Se ejecuta contra la BD de CKAN (`--apply` para escribir; sin él es dry-run); por ejemplo dentro de un pod CKAN con `CKAN_SQLALCHEMY_URL` en el entorno.

Nota: desde este fix, `ckanext.terria_view.inject_private_catalog_on_public_views` por defecto es `false` (el catálogo privado solo se inyecta en vistas de datasets privados). Ponerlo en `true` si se quiere que también aparezca en vistas de datasets públicos para usuarios logueados.

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
