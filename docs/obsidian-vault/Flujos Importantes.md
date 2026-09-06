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
6. Guarda la configuracion serializada en la propia vista solo si el dataset es publico y la URL calculada no apunta al proxy con token (`_may_persist_cached_config`); `cached_config` es legible via `resource_view_show`.
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
5. Si hay SLD y el modelo **no** trae ya `legends` / `styles` / `renderOptions`, `SLDProcessor` rellena esos campos. Si el usuario ya guardó ediciones del visor (títulos de leyenda, unidades, `displayRange`), esas claves se conservan: el SLD es semilla, no override.
6. La configuración adaptada garantiza que los modelos de datos queden en `workbench` y normaliza estilos incompletos (por ejemplo `enumColors` sin `mapType`/`colorColumn`) para evitar fallos de parseo en Terria.
7. En modo lazy, las ramas privadas guardadas se normalizan a un único grupo `Saved private layers`; sólo conserva los items mostrados y se les renueva el token por visor. Las configuraciones inline legacy mantienen la poda anterior.
8. El catálogo privado se habilita sólo en vistas privadas por defecto (`inject_private_catalog_on_public_views` permite públicas). En mismo origen, el `#start` recibe únicamente un `terria-reference`; el índice y cada dataset se resuelven on-demand. En cross-origin, `auto` usa el fallback inline.

## 4. Guardar configuración desde la UI

Entrada:

- un usuario autenticado pulsa `Save Configuration` en la vista.

Secuencia:

1. `terria.html` envía `postMessage` al iframe Terria pidiendo `shareData` (la instancia Terria embebida responde con `shareDataResponse` vía `updateApplicationOnMessageFromParentWindow`).
2. Construye una URL `#start=...`.
3. Hace `POST /api/terria/view/<view_id>/save-config`.
4. El endpoint valida la URL HTTP(S) y llama a `prepare_saved_custom_config_url`. En lazy elimina organizaciones/referencias no usadas y agrupa las capas mostradas en `Saved private layers`; en inline poda la rama legacy. Siempre quita el `?token=` firmado. Rechaza con 413 si supera `max_custom_config_bytes`.
5. La vista CKAN se actualiza con el nuevo `custom_config`. El mismo strip de tokens se aplica en `before_create`/`before_update` cuando la URL llega por el formulario.
6. En cada render, `setup_template_variables()` recorre el `encoded_config` y, por cada recurso privado referenciado vía el proxy, emite un token fresco **solo si el usuario actual tiene acceso** (`ResourceUtils.user_may_download`: `datashare_resource_download`, y `resource_show` solo si esa auth no existe); si no, deja la URL sin token (el proxy responderá 401 para ese item, o lo servira por cookie si el visor es same-origin y el usuario si esta autorizado) — `_refresh_proxy_tokens_in_encoded_config` + `refresh_proxy_tokens`. Las URLs del proxy pueden ser relativas (lazy same-origin) o absolutas; `_proxy_resource_id`, `strip_proxy_tokens` y `refresh_proxy_tokens` reconocen ambas.

Resultado:

- la próxima carga reutiliza el estado guardado del mapa, incluidos los datasets privados que se habían añadido; otros usuarios con acceso ven esos datasets con un token renovado; los que no tienen acceso ven ese item con error 401 y un aviso encima del mapa ("inicia sesión" si son anónimos, o "tu cuenta no tiene acceso") — `private_resources_blocked` en `terria.html`.
- las ediciones de estilo hechas en el visor (leyenda, `displayRange`, estilos de tabla) persisten aunque la vista siga teniendo un SLD en `style`. Para forzar un SLD nuevo hay que quitar o regenerar la `custom_config`.

## 5. Catálogo privado lazy

Entrada:

- una vista `terria_view` same-origin abre la referencia privada inyectada en `#start=`, o el Terria standalone carga su `ckan-private-catalog-reference` (flujo 10). Ambos consumen los mismos endpoints.

Secuencia:

1. El render inyecta una `terria-reference` con id `__ckan_private_catalog__/<nonce>/browser` (`build_private_catalog_reference`). Su `url` es relativa (`/api/terria/user/private-catalog?catalog_id=<nonce>`) cuando `is_same_origin(site_url, terria_instance_url)`; absoluta en cross-origin.
2. Al abrirla, `GET /api/terria/user/private-catalog` (`PrivateCatalogBuilder.build_index`) ejecuta **una** `package_search` paginada con `include_private=True`, `fq = NON_PUBLIC_FQ` (`capacity:private` ∪ `access_level` distinto de `public`) y `fl = INDEX_FL` (campos minimos mas `extras_access_level`). Solr aplica las permission labels del usuario, asi que `findable`/`restricted` son descubribles por cualquier logueado y se estrechan en el paso siguiente.
3. Cada fila pasa por `datashare_access_check` y solo entra si `can_download` es verdadero. Si la accion no esta registrada (`ckanext-datashare` ausente) se conserva el filtro historico private-only (`capacity == 'private'`); cualquier otra excepcion excluye la fila (fail closed). Se devuelve Organizacion (`isOpen: true`, `shareable: false`) → referencias de dataset con URL relativa y `description: "Access level: <nivel>"`.
4. Al abrir un dataset, `GET /api/terria/user/private-catalog/dataset/<id>` (`build_dataset`) hace `package_show`, exige `state=active`, `is_non_public_dataset` (`private=True`, `capacity=private` o `access_level != public`, leido tambien desde `extras`) y `can_download` (sin datashare: `private=True`); si falla responde `404`. Formatea solo sus recursos con `format_dataset_item(..., relative_urls=True)`.
5. `ResourceUtils.get_resource_url` devuelve, para recursos subidos de datasets no publicos y usuario logueado, la URL del proxy con token (`build_proxy_resource_url(absolute=False)` → `/api/terria/resource/<id>/content/<file>?token=`); datasets publicos, anonimos o `url_type=link` nunca acunan token.
6. Los IDs de recursos se namespacian con el nonce para coexistir con capas guardadas de sesiones anteriores.

Notas:

- por que `can_download` y no `can_view_resources`: Terria descarga el archivo crudo; en `ckanext-datashare` un `viewable` da a los no autorizados `can_view_resources=True, can_download=False`, asi que no aparece en Terria (desvio deliberado por seguridad);
- coste: `datashare_access_check` ejecuta un `package_show` por candidato del indice. `Inferencia`: si el volumen crece, la alternativa es evaluar `ckanext.datashare.core.get_access` sobre la fila Solr; no esta implementado;
- los catalogos publicos (`/api/terria/full`), el modo inline y `private-datasets` siguen emitiendo URLs absolutas.

> [!note] Lado TerriaJS
> El handler `requestShareData` (`updateApplicationOnMessageFromParentWindow.js`) hace `JSON.parse(JSON.stringify(shareData))` antes del `postMessage`: `getShareData()` puede devolver arrays/maps observables de MobX que el structured clone no puede clonar (`"[object Array] could not be cloned"`), error que aparecía al guardar vistas de datasets privados.

## 6. Generación de catálogo por dataset

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

## 7. Generación de catálogo completo

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

## 8. Invalidación de caché

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
5. Las URLs de recursos privados subidos se resuelven vía `resource_utils.get_resource_url()`, que devuelve una URL **proxy firmada** `GET /api/terria/resource/<id>/content/<filename>?token=<token>`. El proxy vive en el mismo dominio que CKAN, descarga el blob desde Azure server-side con el uploader y responde con `Access-Control-Allow-Origin: *`, evitando depender de la configuración CORS del Storage Account. El proxy autoriza por token **o** por sesion CKAN same-origin (`user_may_download`), reenvia `Range`/condicionales y pasa `206`/`304` (ver [[API y Endpoints]]).
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
- el proxy resuelve la URL upstream con `ignore_auth=True` porque la autorización ya fue validada antes, vía el token firmado o vía la sesión CKAN (`ResourceUtils.user_may_download`: `datashare_resource_download`, con `resource_show` solo si esa auth no esta registrada); un anonimo sin token recibe `401` y un usuario sin `can_download` recibe `403`;
- "privado" en este flujo significa no publico: `private=True` de CKAN core o cualquier `access_level` de `ckanext-datashare` distinto de `public` (`is_non_public_dataset`); en modo inline las URLs siguen siendo absolutas;
- `get_resource_url` solo acuna el token si `ResourceUtils.user_may_download` lo permite: un logueado sin `can_download` (p. ej. `viewable` sin autorizacion, cuya vista si puede abrir) recibe la URL de descarga normal de CKAN y ninguna SAS;
- el segmento `<filename>` en la URL del proxy preserva la extensión para que TerriaJS acepte el recurso (shapefiles exigen `.zip`, GeoJSON exige `.geojson`).

## 10. Sesion CKAN desde Terria standalone

Entrada:

- un Terria standalone que comparte origen con CKAN (por ejemplo `https://data.dev-wins.com/terria`) arranca con `configParameters.ckanSession` en su `config.json`. La logica de cliente vive en TerriaJS (`lib/Models/CkanSession.ts`, `CkanPrivateCatalogReference.ts`, panel `CkanSessionPanel`); aqui se documenta lo que el plugin ve y sirve.

Secuencia:

1. Terria hace `GET /api/terria/user/session` al arrancar y cada vez que la pestana recupera foco o visibilidad (con throttle), o cuando el usuario pulsa "Refresh session". La URL es relativa con `/` inicial: el XHR es same-origin, lleva la cookie `ckan` y **no** pasa por el proxy de terriajs-server (que descarta `Cookie`).
2. Anonimo → `authenticated: false` + `login_url`. Terria muestra "Log in", que abre `/user/login?came_from=<pathname>` en una pestana nueva (el mapa no se recarga); al volver, el siguiente whoami detecta la sesion.
3. Autenticado → `user`, `private_catalog_url` (relativa, con un `catalog_id` nuevo por llamada), `logout_url`, `profile_url`. Terria anade un grupo raiz `ckan-private-catalog` con una `ckan-private-catalog-reference` que carga el indice del flujo 5 de forma ansiosa; conserva el primer `catalog_id` mientras no cambie el usuario.
4. Datasets y recursos se resuelven con los endpoints lazy del flujo 5 (URLs relativas). Los bytes salen por el proxy con token; si el token caduca con la sesion viva, el proxy autoriza por cookie (`Cache-Control: private, no-store`, `Vary: Cookie`). Los COG piden rangos y reciben `206` + `Content-Range`.
5. Logout (`/user/_logout` en pestana nueva) → el siguiente whoami devuelve anonimo y Terria retira el grupo, sus descendientes y las capas privadas del workbench. Un `401`/`403` al cargar el indice tambien dispara un re-check de sesion y muestra un mensaje traducido.
6. En la vista embebida en CKAN el `#start=` ya inyecta `__ckan_private_catalog__/<nonce>/browser`; Terria no anade un segundo grupo y "Open my private datasets" abre el inyectado.

Notas:

- `user/session` nunca falla hacia el cliente: cualquier error interno responde `200` anonimo. Si el CKAN desplegado no tiene el endpoint (plugin anterior), Terria muestra "Session unavailable" con reintento y nada mas cambia;
- todas las URLs devueltas deben ser rutas relativas seguras (`/...`, nunca `//` ni absolutas); Terria las valida y cae a sus defaults si no lo son;
- un Terria sin `ckanSession` en su `config.json` (produccion hoy) no hace ninguna de estas llamadas;
- las respuestas privadas no deben terminar en caches compartidas: `private, no-store`, `Vary` y `__no_cache__` (ver [[API y Endpoints]]).

## Pendiente por confirmar

- si el warmup corre de forma fiable bajo todos los servidores WSGI usados por CKAN;
- comportamiento del `came_from` de `/user/login` en CKAN 2.10 con `ckan.root_path` no vacio (la ruta la construye Terria a partir de `window.location.pathname`).

Confirmado: el botón `Save Configuration` sí requiere que la instancia Terria embebida implemente el handler `requestShareData` → `shareDataResponse` (`updateApplicationOnMessageFromParentWindow.js`); la imagen `pabrojast/terriamap` lo trae.
