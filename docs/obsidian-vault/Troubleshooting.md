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

## Share de Terria rompe con "Failed to load shapefile - no URL of file has been defined"

Síntoma: una share antigua (`https://<host>/terria/#share=g-...`) que antes cargaba un recurso del catálogo IHP-WINS ahora falla. Inspeccionando el `initSource.models` se ve un item con clave igual al UUID del recurso (`3129297e-4183-4b61-b564-561c1a0abae6`, etc.) sin campo `url`. Terria reporta:

```
Failed to load <uuid> mapItems
Failed to load shapefile - no URL of file has been defined
```

Causa: el id del item en el catálogo cambió de `<resource_uuid>` a `<resource_uuid>-0` porque el recurso ganó una **segunda vista Terria** en CKAN. El share antiguo fue creado cuando el recurso tenía una sola vista (id plano), pero `format_dataset_item` (en `terria_json_generator.py`) sufijaba con `-{view_index}` el id de **todas** las vistas, incluida la primera (`view_index == 0`), cuando `total_views > 1`. Cuando Terria resuelve la share, busca el id plano en el catálogo cargado vía `terria-reference` (`init/simple-modular.json` → `https://<host>/api/terria/file/full`), no lo encuentra y materializa el modelo desde el estado guardado sin `url`.

Fix aplicado: `format_dataset_item` mantiene `id == resource_id` para el primer view (`view_index == 0`) incluso cuando hay múltiples vistas; solo los views adicionales reciben sufijo `-1`, `-2`, …. El nombre sigue llevando el sufijo " - <view title>" en multi-view para diferenciar visualmente.

Además, el primer view multi-view emite `shareKeys: ["<resource_id>-0"]`. Esto es un fallback para shares creadas en la ventana en que el catálogo emitió `<uuid>-0` como id (entre que el recurso ganó una segunda vista y este fix). TerriaJS soporta `shareKeys` nativamente: cuando una share apunta a un id que no existe directamente en el catálogo, recorre los items buscando `shareKeys` que coincidan. Así ambos formatos (`<uuid>` y `<uuid>-0`) resuelven al mismo item canónico, sin duplicar entradas en el árbol del catálogo.

Verificación post-deploy:

- regenerar el catálogo cacheado: `curl -X POST https://<host>/api/terria/cache/invalidate` (o esperar a que expire);
- comprobar que `GET /api/terria/file/full` devuelve el recurso con `"id": "<uuid>"` (sin `-0`) y `"url": "<download URL>"`;
- reabrir la share original — Terria debe encontrar el item por UUID y resolver el shapefile.

Para diagnosticar otros casos: contar las vistas Terria del recurso (`POST /api/3/action/resource_view_list` con `{"id": "<uuid>"}`). Si devuelve `count > 1`, esta es la causa.

Ver también: [[Modulos]] (`TerriaJSONGenerator.format_dataset_item`).

## El estilo SLD no se aplica

Revisar:

- que `style` apunte a un SLD accesible por URL;
- si el recurso es `shp` o raster compatible con la lógica SLD actual;
- logs con `TERRIA_DEBUG=true`;
- tests en [[Testing]] orientados a SLD;
- si el problema está en el nombre de columna del shapefile.
- si el estilo cambió y no se refleja en `ihp-wins.json`, invalidar caché con `POST /api/terria/cache/invalidate` y reintentar.
- si se actualizó el archivo SLD en la misma URL, confirmar que se ejecutó una invalidación (los resultados SLD se cachean en memoria por URL).

## SLD con filtros compuestos (`unit_code AND unit_sub`): coloreado parcial / valores fantasma

Síntoma: una capa shp con estilo SLD que internamente discrimina sub-tipos vía dos atributos combinados con `<ogc:And>` (típico de cartografía geológica QGIS/GeoServer — `unit_code = X AND unit_sub = Y`) se renderiza con colores incorrectos: muchos polígonos quedan grises o reciben el color de otro grupo, y el panel de estilo muestra entradas raras (`plain`, `yellow`, `dotted`, …) que no son códigos de unidad reales.

Causa: `colorColumn` de TerriaJS solo soporta una columna. `sld_processor._extract_fallback_values` recogía todos los `<ogc:Literal>` dentro del `<ogc:And>` — el de `unit_sub` se colaba en el `enumColors` como un valor que ninguna feature del shp puede tener. Además, varias reglas con el mismo `unit_code` pero diferente `unit_sub` emitían múltiples `(value, color)` para el mismo `value`; TerriaJS se quedaba con el último.

Fix aplicado:

- `_extract_fallback_values` ahora empareja cada `<ogc:Literal>` con su `<ogc:PropertyName>` dentro de cada comparación (`PropertyIsEqualTo`, etc.) y solo conserva los literales asociados al `property_name` primario; los de la propiedad secundaria se descartan.
- `_process_rules_qgis_style` deduplica `enum_colors` por `value` (gana el primero, orden determinista por aparición en el SLD) y descarta reglas cuya `property_name` no coincide con la del primer match (evita mezclar columnas si el SLD es inconsistente).
- La sub-discriminación por la segunda columna no se reproduce visualmente — es una limitación del shp viewer de TerriaJS. Las tramas (`<se:GraphicFill>` con `WellKnownName` `horline`, `slash`, `brush://dense*`) tampoco; se aproximan con el color sólido del `Fill`.

Tests: `ckanext/terria_view/tests/test_sld_compound_filter.py` cubre la regresión con un SLD mínimo equivalente al patrón Kenia/Etiopía.

Verificación post-deploy:

- invalidar cache: `POST /api/terria/cache/invalidate` (los `cached_config` viejos guardan el `enumColors` con valores fantasma);
- regenerar la vista del recurso afectado y revisar que el `enumColors` resultante solo contenga códigos de unidad reales y sin duplicados.

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

Si la consola muestra `Error saving configuration: Failed to execute 'postMessage' on 'Window': [object Array] could not be cloned` (típico al guardar vistas de datasets **privados**): el error lo emitía el handler `requestShareData` de la instancia Terria embebida, que devolvía el objeto de `getShareData()` tal cual; ese objeto puede traer arrays/maps observables de MobX que el structured clone de `postMessage` no puede clonar. Arreglado en TerriaJS (`updateApplicationOnMessageFromParentWindow.js`) haciendo `JSON.parse(JSON.stringify(shareData))` antes de responder — hay que rebuildear/redesplegar la imagen Terria (`pabrojast/terriamap`). Si el error persiste solo en un navegador concreto, sospechar además una extensión/polyfill que instaló SES/lockdown y rompió structured clone; la template `terria.html` ya prueba varias formas de payload objeto para el request antes de fallar con un mensaje explícito.

## La vista Terria de un recurso se vuelve lentísima / el formulario de editar vista tarda 30-60 s

Síntoma: `resource_view.config` crece a varios MB; `GET /dataset/.../edit_view/<id>` tarda 30-60 s y devuelve varios MB de HTML (a veces termina en `SIGPIPE` / `Broken pipe` en uWSGI porque el navegador se rinde); el `#start=` guardado en `custom_config` es una URL de >1 MB que el navegador apenas acepta.

Causa: `setup_template_variables` inyecta el catálogo de **datasets privados del usuario logueado** dentro de `encoded_config` para que el árbol de catálogo del iframe los muestre (`_merge_private_catalog_into_encoded_config`). Por defecto solo en vistas de datasets **privados**; con `ckanext.terria_view.inject_private_catalog_on_public_views = true` también en vistas de datasets públicos. Si el usuario pulsa "Save Configuration" (o vuelve a guardar la vista desde el formulario con esa URL del iframe en el campo), `getShareData` serializa parte de ese árbol y queda horneado en `custom_config`.

Comportamiento actual (los datasets privados **se conservan** en la config guardada a propósito, para poder compartir la vista entre usuarios con acceso):

- al guardar (`save_view_config`, `_process_form_data`) se llama a `prepare_saved_custom_config_url`: poda la rama `Private Datasets (...)` a solo los items mostrados (`workbench`/`timeline`/`preview`) + sus grupos ancestros con `members` recortados (`prune_private_catalog_to_used`) y quita el `?token=` firmado (`strip_proxy_tokens`). Esto evita que TerriaJS hornee ~1 MB de árbol de catálogo en el `custom_config`;
- en render, `_refresh_proxy_tokens_in_encoded_config` recorre el `encoded_config` y emite un token fresco por recurso privado **solo si el usuario actual pasa `check_access('resource_show')`**; si no, deja la URL sin token (el proxy responde 401 para ese item) y marca `private_resources_blocked`, con lo que `terria.html` muestra un aviso encima del mapa ("inicia sesión" si es anónimo, o "tu cuenta no tiene acceso");
- si la config guardada ya trae un catálogo privado, no se vuelve a inyectar el del usuario actual (evita duplicados / crecimiento entre re-guardados);
- `process_custom_config` solo reescribe la URL del modelo del recurso principal de la vista (por su `resource_id` en la ruta del proxy, o el único item de datos en configs de un solo recurso);
- `save_view_config` sigue rechazando configs > `max_custom_config_bytes` (4 MB por defecto, configurable);
- `_CONFIG_PROCESSING_VERSION` se subió en su momento para invalidar `cached_config` viejos.

`scripts/strip_private_catalog_from_views.py` sigue disponible para *eliminar por completo* las ramas privadas de vistas concretas si hace falta (recorre los `resource_view` `terria_view` y borra también la copia obsoleta `config.__extras.custom_config_url`); ya no es necesario por defecto. Se ejecuta contra la BD de CKAN (`--apply` para escribir; sin él es dry-run).

Nota: desde este fix, `ckanext.terria_view.inject_private_catalog_on_public_views` por defecto es `false` (el catálogo privado solo se inyecta en vistas de datasets privados). Ponerlo en `true` si se quiere que también aparezca en vistas de datasets públicos para usuarios logueados.

## `cached_config` queda vacío en casi todas las vistas Terria

Síntoma: la tabla `resource_view` muestra `config.cached_config = ""` y `cached_config_signature = ""` para la inmensa mayoría de las vistas `terria_view` aunque el render funciona correctamente. Cada page-load reprocesa el SLD, refetchea el archivo y reconstruye el config completo (más latencia y CPU, sobre todo en SLDs grandes con muchas reglas).

Causa: `Terria_ViewPlugin._update_view_cached_config` enrutaba la persistencia por la acción `resource_view_update`. Esa acción exige un payload completo (`title`, `view_type`, `terria_instance_url`, `style`, etc.) y, cuando alguno de esos validadores falla en este despliegue (p. ej. con campos extra que el schema de `terria_view` no declara o cuando hay otros plugins enganchados al `before_update`), el chain devuelve error. El bloque `try/except` solo loggeaba la falla vía `_debug_print` (gated en `TERRIA_DEBUG=true`), así que el problema quedaba invisible y los `cached_config` jamás se escribían.

Fix:

- `_update_view_cached_config` ahora actualiza la columna JSON `ResourceView.config` directamente vía SQLAlchemy (`session.query(model.ResourceView).get(view_id)` → mutar `config` → `flag_modified` → `commit`). Sólo toca los dos campos de cache; el resto de la fila queda intacto.
- Cualquier excepción se reporta con `log.exception(...)` en el logger estándar (visible sin necesidad de `TERRIA_DEBUG`), de modo que regresiones futuras se detectan en uwsgi log.
- Cota defensiva `_MAX_PERSISTED_CACHED_CONFIG_BYTES = 2 MiB`: si el `encoded_config` supera ese tamaño se omite la persistencia y se loggea (evita guardar megabytes en la tabla cuando algo se descontroló — el `max_custom_config_bytes` del save endpoint cubre el lado del usuario; este cubre el lado del render).
- `_CONFIG_PROCESSING_VERSION` subió a `5` para invalidar firmas viejas y forzar la regeneración de los 1235 `cached_config` de vistas públicas en el próximo render.

Verificación post-deploy:

- consultar la BD: `SELECT count(*) FROM resource_view WHERE view_type='terria_view' AND (config::jsonb)->>'cached_config' <> '';` — debería crecer rápidamente con el tráfico normal;
- abrir una vista de un dataset público; `resource_view_show` debería devolver `cached_config_signature` no vacío;
- monitorear `uwsgi` log por `terria_view: failed to persist cached_config` — debería estar limpio. Si aparece, el mensaje incluye el error completo (traceback) para diagnosticar.

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
