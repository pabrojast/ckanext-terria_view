# Flujos Importantes

## 1. Auto-creación de una vista Terria

Entrada:

- CKAN invoca la acción `resource_view_list`.

Secuencia:

1. `plugin.py` envuelve `resource_view_list`.
2. Busca el recurso por `resource_id`.
3. Revisa si ya existe una vista `terria_view`.
4. Si no existe y el formato es compatible, crea una vista automáticamente usando `resource_view_create`.

Resultado:

- el recurso termina con una vista Terria disponible sin intervención manual.

Notas:

- se omite creación si detecta `activity_id` en request;
- requiere contexto CKAN con `model` y `session`.

## 2. Render de la vista dentro de CKAN

Entrada:

- un usuario abre la vista `terria_view` de un recurso.

Secuencia:

1. `setup_template_variables()` obtiene `package`, `resource` y `resource_view`.
2. Resuelve nombre seguro y URL efectiva del recurso.
3. Calcula bounds desde `spatial` o campos `xmin/xmax/ymin/ymax`.
4. Si existe `cached_config` y la firma coincide, reutiliza esa configuración.
5. Si no, genera configuración automática o adapta una configuración custom.
6. Guarda la configuración serializada en la propia vista.
7. Renderiza `terria.html`, que embebe un iframe hacia la instancia Terria.

Resultado:

- Terria carga con `#start=<encoded_config>` o con la URL directa configurada.

## 3. Configuración custom + SLD

Entrada:

- el usuario edita la vista desde el formulario CKAN.

Secuencia:

1. `before_create()` o `before_update()` procesan campos temporales del formulario.
2. Se persiste `custom_config` como `NA` o URL real.
3. Se persiste `style` como `NA`, URL custom o URL de un SLD detectado en el dataset.
4. En render posterior, `TerriaConfigBuilder` toma esa config y la adapta al recurso actual.
5. Si hay SLD, `SLDProcessor` genera estilos/leyendas y se inyectan a la config.
6. La configuración adaptada garantiza que los modelos de datos queden en `workbench` y normaliza estilos incompletos (por ejemplo `enumColors` sin `mapType`/`colorColumn`) para evitar fallos de parseo en Terria.
7. `process_custom_config` conserva las ramas `Private Datasets (...)` que hubieran quedado horneadas en un `custom_config` previo (para poder compartir la vista con otros usuarios con acceso); el `?token=` caducado se quita al guardar y se vuelve a emitir por visor en render (`refresh_proxy_tokens`). Solo se reescribe la URL del modelo del recurso principal de la vista (identificado por su `resource_id` en la ruta del proxy, o el único item de datos en configs legacy de un solo recurso); el resto de items se deja intacto.
8. La inyección inline del catálogo privado del usuario actual solo ocurre en vistas de datasets privados por defecto (configurable con `ckanext.terria_view.inject_private_catalog_on_public_views`); ver [[Variables de Entorno]]. Si la config guardada ya trae un catálogo privado, no se vuelve a inyectar (evita duplicados y crecimiento sin límite entre re-guardados).

## 4. Guardar configuración desde la UI

Entrada:

- un usuario autenticado pulsa `Save Configuration` en la vista.

Secuencia:

1. `terria.html` envía `postMessage` al iframe Terria pidiendo `shareData` (la instancia Terria embebida responde con `shareDataResponse` vía `updateApplicationOnMessageFromParentWindow`).
2. Construye una URL `#start=...`.
3. Hace `POST /api/terria/view/<view_id>/save-config`.
4. El endpoint valida la URL HTTP(S), **quita solo el `?token=` firmado** de las URLs proxy del `#start=` (`strip_proxy_tokens_from_terria_url`) —las ramas `Private Datasets (...)` se conservan— y rechaza si tras la limpieza supera `MAX_CUSTOM_CONFIG_BYTES` (512 KB).
5. La vista CKAN se actualiza con el nuevo `custom_config`. El mismo strip de tokens se aplica en `before_create`/`before_update` cuando la URL llega por el formulario.
6. En cada render, `setup_template_variables()` recorre el `encoded_config` y, por cada recurso privado referenciado vía el proxy, emite un token fresco **solo si el usuario actual tiene acceso** (`check_access('resource_show')`); si no, deja la URL sin token (el proxy responderá 401 para ese item) — `_refresh_proxy_tokens_in_encoded_config` + `refresh_proxy_tokens`.

Resultado:

- la próxima carga reutiliza el estado guardado del mapa, incluidos los datasets privados que se habían añadido; otros usuarios con acceso ven esos datasets con un token renovado; los que no tienen acceso ven ese item con error 401 y un aviso encima del mapa ("inicia sesión" si son anónimos, o "tu cuenta no tiene acceso") — `private_resources_blocked` en `terria.html`.

> [!note] Lado TerriaJS
> El handler `requestShareData` (`updateApplicationOnMessageFromParentWindow.js`) hace `JSON.parse(JSON.stringify(shareData))` antes del `postMessage`: `getShareData()` puede devolver arrays/maps observables de MobX que el structured clone no puede clonar (`"[object Array] could not be cloned"`), error que aparecía al guardar vistas de datasets privados.

## 5. Generación de catálogo por dataset

Entrada:

- `GET /api/terria/dataset/<dataset_id>`.

Secuencia:

1. `TerriaAPIController` llama a `TerriaJSONGenerator.generate_dataset_json`.
2. El generador consulta el dataset en CKAN.
3. Filtra datasets privados/inactivos para endpoints públicos.
4. Recorre recursos compatibles.
5. Para cada recurso busca vistas `terria_view`.
6. Genera uno o varios items Terria, uno por vista.
7. Cachea la respuesta en memoria.

## 6. Generación de catálogo completo

Entrada:

- `GET /api/terria/full` o `GET /api/terria/file/full`.

Secuencia:

1. Se intenta servir caché de archivo.
2. Si la caché es fresca, se devuelve.
3. Si es stale, se sirve y se dispara regeneración en background.
4. Si no existe, se responde `202 generating` y se dispara regeneración.
5. La regeneración construye el catálogo agregando organizaciones con datasets válidos.

Resultado:

- el endpoint evita bloquear la request en regeneraciones pesadas.

## 7. Invalidación de caché

Disparadores:

- creación, actualización o borrado de una vista;
- cambios detectados por hash de dataset/organización/tag/catálogo completo.

Secuencia:

1. Las acciones encadenadas `resource_view_create`, `resource_view_update` y `resource_view_delete` invalidan caché por `resource_id`.
2. Se limpian entradas de dataset, organización, tags y catálogo completo.
3. Los endpoints regeneran a demanda en la siguiente solicitud.

## 8. Preload de caché al arranque

Secuencia:

1. `configure()` inicializa `CachePreloader`.
2. Se espera un delay configurable.
3. Se intentan precargar catálogo modular, organizaciones, datasets recientes, tags populares y catálogo completo.

## 9. Inyección de datasets privados en la vista

Entrada:

- un usuario autenticado abre una vista `terria_view`.

Secuencia:

1. `setup_template_variables()` detecta el usuario autenticado (CKAN 2.10+ compatible).
2. Llama a `_get_private_datasets_catalog(user_context)`.
3. Este método ejecuta `package_search(include_private=True)` con el contexto del usuario.
4. Filtra recursos compatibles y genera items Terria usando `format_dataset_item(package=..., user_context=...)`.
5. Las URLs de recursos privados subidos se resuelven vía `resource_utils.get_resource_url()`, que devuelve una URL **proxy firmada** `GET /api/terria/resource/<id>/content/<filename>?token=<token>`. El proxy vive en el mismo dominio que CKAN, descarga el blob desde Azure server-side con el uploader y responde con `Access-Control-Allow-Origin: *`, evitando depender de la configuración CORS del Storage Account.
6. Si hay catálogo privado habilitado para esa vista —y la config guardada no trae ya uno—, `setup_template_variables()` fusiona server-side el catálogo privado del usuario actual dentro de `encoded_config` como entradas extra en `initSources[0].catalog` (`_merge_private_catalog_into_encoded_config`). Si la config guardada ya incluía datasets privados, se omite esta fusión y solo se renuevan sus tokens (ver flujo 4).
7. `terria.html` carga el iframe con `#start={{ encoded_config }}` **también en modo privado** — de ese modo el recurso actual y el catálogo privado llegan juntos en la misma inicialización y el `workbench`/`timeline` se comportan igual que en vistas públicas.
8. No hay un `postMessage` adicional para poblar el catálogo privado. El único `postMessage` de esta pantalla es el de `Save Configuration`, que pide `shareData` al iframe Terria.

Resultado:

- el usuario ve sus datasets privados integrados en la vista del mapa junto con los públicos.
- la información privada no se cachea ni se persiste en la vista del recurso.

Notas:

- el catálogo privado no depende de `postMessage`; queda embebido en `encoded_config` y no se cachea;
- `Save Configuration` sí usa `postMessage`: resuelve `targetOrigin` desde `terria_instance_url` y, si la URL no puede parsearse, cae a `'*'` porque ese request no transporta datos privados;
- el catálogo privado se genera on-demand por request, no se cachea;
- los tokens del proxy expiran en 1h por defecto y están firmados con el secret CKAN (`beaker.session.secret` o `SECRET_KEY`);
- el proxy ejecuta `resource_show` con `ignore_auth=True` porque la autorización ya fue validada vía el token firmado;
- el segmento `<filename>` en la URL del proxy preserva la extensión para que TerriaJS acepte el recurso (shapefiles exigen `.zip`, GeoJSON exige `.geojson`).

## Pendiente por confirmar

- si el warmup corre de forma fiable bajo todos los servidores WSGI usados por CKAN.

Confirmado: el botón `Save Configuration` sí requiere que la instancia Terria embebida implemente el handler `requestShareData` → `shareDataResponse` (`updateApplicationOnMessageFromParentWindow.js`); la imagen `pabrojast/terriamap` lo trae.
