# API y Endpoints

## Resumen

La extensión registra un Blueprint Flask con endpoints bajo `/api/terria/*` y un endpoint de compatibilidad en `/ihp-wins.json`.

Los responses JSON publicos (`_create_json_response`) agregan cabeceras CORS amplias:

- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

Los endpoints autenticados por cookie (`user/session`, `user/private-*`) usan `_create_private_json_response`, que no declara CORS propio y desactiva el cacheo compartido; ver "Cabeceras efectivas en el cable" al final.

## Endpoints principales

### Dataset

- `GET /api/terria/dataset/<dataset_id>`
- `GET /api/terria/file/dataset/<dataset_id>`

Parámetros:

- `view_index` opcional para elegir una vista específica.

Uso:

- obtener el catálogo Terria de un dataset;
- expandir múltiples vistas `terria_view` de un recurso.

### Organización

- `GET /api/terria/organization/<org_name>`
- `GET /api/terria/file/organization/<org_name>`

Uso:

- agrupar datasets públicos/activos por organización.

### Tag

- `GET /api/terria/tag/<tag_name>`

### Catálogo completo

- `GET /api/terria/full`
- `GET /api/terria/file/full`
- `GET /ihp-wins.json`

Comportamiento relevante:

- usa stale-while-revalidate para no bloquear regeneraciones pesadas;
- puede devolver `202` si aún no existe caché inicial.

### Catálogo modular

- `GET /api/terria/modular`

Uso:

- devuelve una estructura más liviana basada en referencias Terria.

### Vistas de recurso

- `GET /api/terria/resource/<resource_id>/views`

Uso:

- listar vistas Terria de un recurso;
- descubrir `view_index`, `style`, `custom_config` y `json_url`.

### Caché

- `GET /api/terria/cache/stats`
- `POST /api/terria/cache/invalidate`
- `POST /api/terria/cache/cleanup`

Parámetros opcionales en invalidate:

- `type`
- `id`

### Guardado de configuración de vista

- `POST /api/terria/view/<view_id>/save-config`

Body esperado:

- JSON con `custom_config_url`.

Validación observada:

- la URL debe ser `http://` o `https://`;
- `prepare_saved_custom_config_url`: en modo lazy colapsa las capas privadas mostradas dentro de `Saved private layers` y elimina el navegador; en modo inline conserva la poda legacy. En ambos casos quita el `?token=` firmado y se renueva por visor en render;
- se rechaza con 413 si tras la limpieza supera `max_custom_config_bytes` (4 MB por defecto, configurable).

### Sesion y datasets no publicos del usuario

- `GET /api/terria/user/session`
- `GET /api/terria/user/private-catalog?catalog_id=<nonce>`
- `GET /api/terria/user/private-catalog/dataset/<dataset_id>?catalog_id=<nonce>`
- `GET /api/terria/user/private-datasets`

#### `user/session` (whoami same-origin)

Pensado para el Terria standalone que comparte origen con CKAN y arranca con `configParameters.ckanSession` (lado TerriaJS). Responde **siempre `200`**, tambien a anonimos; cualquier excepcion interna se registra con `log.exception` y degrada al payload anonimo.

Anonimo:

```json
{"authenticated": false, "user": null, "private_catalog_url": null,
 "login_url": "/user/login", "logout_url": null, "profile_url": null}
```

Autenticado:

```json
{"authenticated": true,
 "user": {"name": "alice", "display_name": "Alice Example", "sysadmin": false},
 "private_catalog_url": "/api/terria/user/private-catalog?catalog_id=<nonce>",
 "login_url": "/user/login", "logout_url": "/user/_logout", "profile_url": "/user/alice"}
```

- todas las URLs son **relativas**: `_ckan_path(endpoint, fallback)` usa `toolkit.url_for` solo si devuelve una ruta que empieza por `/` y no por `//` (respeta `ckan.root_path`); si no, el fallback fijo. Terria descarta cualquier URL absoluta o `//`;
- cada llamada acuna un `catalog_id` nuevo (`new_catalog_id()`); Terria conserva el primero por usuario;
- `_get_user_context()` trata el `AnonymousUser` truthy de CKAN 2.10 (`is_anonymous=True`, `name=''`) como anonimo;
- cabeceras: las de `_create_private_json_response` (abajo) mas `X-Content-Type-Options: nosniff`.

#### Indice y expansion lazy

- `private-catalog` devuelve Organizacion → `terria-reference` de dataset. El indice sale de **una sola** `package_search` paginada con `include_private=True`, `fq = NON_PUBLIC_FQ` = `+(capacity:private OR (access_level:* AND NOT access_level:public))` y `fl = INDEX_FL` (`id, name, title, organization, capacity, extras_access_level`; CKAN pliega `extras_access_level` en `row['access_level']`). Es decir: confidenciales (`private=True` en CKAN core) ∪ cualquier nivel `ckanext-datashare` distinto de `public` (`findable`, `viewable`, `restricted`).
- Cada candidato pasa por la accion `datashare_access_check` y solo se incluye si `can_download` es verdadero: Terria descarga el archivo crudo, asi que `can_view_resources` no basta y un `viewable` sin autorizacion queda fuera. Si la accion no esta registrada (`ckanext-datashare` ausente) se conserva el comportamiento historico private-only (`capacity == 'private'` / `private is True`); cualquier otra excepcion excluye el dataset (fail closed).
- Los grupos de organizacion se emiten con `isOpen: true` y `shareable: false`; cada referencia lleva `description: "Access level: <nivel>"` (`confidential` para `private=True` sin nivel datashare).
- `private-catalog/dataset/<id>` hace `package_show`, exige `state=active`, dataset no publico (`is_non_public_dataset`) y `can_download` (mismo fallback sin datashare: `private=True`); si algo falla responde `404` sin revelar si el id existe. Formatea solo los recursos de ese dataset con `format_dataset_item(..., relative_urls=True)`.
- En modo lazy todas las URLs (referencias de dataset y proxy de recursos) son **relativas** (`/api/terria/...`) para que un Terria same-origin las pida con la cookie y sin pasar por el proxy de terriajs-server. `build_private_catalog_reference(..., absolute=...)` solo emite absoluta cuando `is_same_origin(site_url, terria_instance_url)` es falso.
- `private-datasets` conserva el catalogo completo legacy (private-only, URLs absolutas) para compatibilidad.

`private-catalog`, `private-catalog/dataset/<id>` y `private-datasets` exigen sesion (`401` si no); `session` no. Los cuatro responden con `_create_private_json_response`: `Cache-Control: private, no-store, max-age=0`, `CDN-Cache-Control: no-store`, `Surrogate-Control: no-store`, `Expires: 0`, `Vary: Cookie, Authorization`, sin CORS propio, y marcan `request.environ['__no_cache__'] = True` (ya no envian `Pragma`; ver "Cabeceras efectivas en el cable").

### Proxy de recursos no publicos

- `GET /api/terria/resource/<resource_id>/content?token=<token>`
- `GET /api/terria/resource/<resource_id>/content/<filename>?token=<token>`
- `HEAD` en ambas variantes.

Uso:

- iframe Terria cross-origin (sin sesion CKAN): descarga recursos no publicos con el token firmado, sin depender de la configuracion CORS del Storage Account Azure;
- Terria standalone same-origin: puede autorizar con la **sesion CKAN** (cookie), lo que ademas cubre tokens caducados de capas ya cargadas mientras la sesion viva.

Autorizacion (orden fijo en `resource_content`):

1. `token` presente y valido (`verify_resource_token`: HMAC atado al `resource_id`, TTL 1 h por defecto, no falsificable sin el secret de CKAN) → servir (`authorized_by = 'token'`);
2. si no, sesion autenticada y `ResourceUtils.user_may_download(context, resource_id)` → servir (`'session'`);
3. anonimo sin token valido → `401` (`Authentication required (token or CKAN session)`); autenticado sin permiso → `403`.

`user_may_download` prueba `datashare_resource_download` (exige `can_download`) y solo cae a `resource_show` si esa auth no esta registrada (`check_access` lanza `ValueError`); `NotAuthorized` o cualquier otra excepcion deniegan. El mismo helper se usa al renovar tokens en `plugin._refresh_proxy_tokens_in_encoded_config`. `resource_show` a secas no sirve como gate: la version encadenada de datashare permite `viewable` y el proxy entrega el archivo crudo.

`ResourceUtils.get_resource_url` aplica el mismo gate **antes** de acunar un token (render de la vista, expansion lazy, catalogo inline): un usuario logueado sin `can_download` sobre un dataset no publico (p. ej. `viewable` sin autorizacion, cuya pagina de vista si puede abrir porque el `resource_show` de datashare solo exige `can_view_resources`) recibe la URL de descarga normal de CKAN, que `datashare_resource_download` responde con `403`; tampoco se le resuelve la SAS. Datasets publicos y anonimos no ejecutan la comprobacion. Ademas, `setup_template_variables` no persiste `cached_config` para datasets no publicos ni cuando la URL lleva token (`_may_persist_cached_config`), porque `cached_config` es un campo del schema que `resource_view_show` devuelve a cualquiera que pueda ver la vista.

Upstream:

- `resolve_private_resource_source` obtiene la URL SAS con el uploader (`ignore_auth=True`, solo despues de autorizar);
- se reenvian `Range`, `If-Range`, `If-None-Match`, `If-Modified-Since` y se fuerza `Accept-Encoding: identity` (evita que el backend comprima y rompa `Content-Length`/206); nunca se reenvian `Cookie` ni `Authorization`; `timeout=(10, 60)`;
- `200`/`206` se pasan con el mismo status (`direct_passthrough`, `raw.stream(8192, decode_content=False)`); `304` y `416` se pasan sin cuerpo; otros `>= 400` y errores de red responden `502` con mensaje **generico** (la URL SAS y el cuerpo upstream solo van al log del servidor);
- `HEAD` cierra la conexion upstream de inmediato y responde sin cuerpo.
- el segmento `<filename>` es **cosmetico**: TerriaJS valida la extension de la URL antes de hacer fetch (shapefiles requieren `.zip`, GeoJSON espera `.geojson`). No interviene en la autorizacion.

Cabeceras de respuesta (`_apply_proxy_headers`):

- se copian `Content-Length`, `Content-Range`, `Content-Encoding`, `ETag`, `Last-Modified`, `Accept-Ranges` cuando el upstream los expone (un `200` sin `Accept-Ranges` recibe `bytes`);
- `Access-Control-Allow-Origin: *`, `Access-Control-Allow-Methods: GET, HEAD, OPTIONS`, `Access-Control-Expose-Headers: Content-Length, Content-Range, Content-Encoding, ETag, Last-Modified, Accept-Ranges, Content-Disposition`;
- `Content-Disposition: inline` con filename saneado (sin `"`, `\`, CR/LF, `;` ni caracteres de control) y `filename*=UTF-8''...` para nombres no ASCII;
- `Cache-Control`: por token `private, max-age=300` (la URL ya es unica por token); por sesion `private, no-store` + `Vary: Cookie`;
- `X-Content-Type-Options: nosniff`, `X-Accel-Buffering: no` y `__no_cache__` activado. Los errores (`_create_cors_error_response`) llevan `Cache-Control: no-store` y tambien el flag.

### Preflight CORS

- `OPTIONS /api/terria/<path:path>` → `Access-Control-Allow-Methods: GET, HEAD, POST, OPTIONS`, `Access-Control-Allow-Headers: Content-Type, Range, If-Range, If-None-Match, If-Modified-Since`, `Access-Control-Max-Age: 600`.

## Contratos funcionales importantes

- Los endpoints públicos intentan excluir datasets privados e inactivos.
- Los endpoints de archivo dependen de que la caché de archivos esté habilitada.
- Si falla el envío de archivo, algunos endpoints hacen fallback a respuesta JSON estándar.

## Seguridad y autorización

Observaciones:

- `save-config` intenta operar con el usuario actual y respeta autorización CKAN.
- `user/private-catalog`, `user/private-catalog/dataset/<id>` y `user/private-datasets` exigen usuario autenticado (`401`); `user/session` **no**: responde `200` a cualquiera y solo describe al propio solicitante.
- el gate de datos no publicos es `can_download` (`datashare_access_check`) en indice y expansion, y `datashare_resource_download` en el proxy por sesion; el fallback a private-only / `resource_show` solo se activa si `ckanext-datashare` no esta instalado (ver [[Variables de Entorno]]).
- el proxy por token sigue siendo legible por cualquiera que tenga el token (TTL 1 h); el proxy por sesion, el whoami y el indice solo por el navegador con la cookie.
- `resource_views` y otros endpoints públicos dependen de permisos CKAN y de cómo respondan las acciones base.

### Cabeceras efectivas en el cable

CKAN 2.10 aplica dos middlewares a **toda** respuesta, incluidas las de este Blueprint:

- `set_cache_control_headers_for_response` borra `Pragma` y anade `public, must-revalidate` a `Cache-Control`, salvo que `request.environ['__no_cache__']` sea `True`; con el flag solo anade `private`. Por eso `_create_private_json_response`, el proxy y los errores CORS llaman a `_disable_ckan_response_cache()` y ya no envian `Pragma`. Sin el flag, el `401` del indice llegaba al cliente con `private, no-store, max-age=0, public, must-revalidate` (verificado en vivo).
- con `ckan.cors.origin_allow_all = true`, `set_cors_headers_for_response` anade `Access-Control-Allow-Origin: *` a cualquier respuesta que traiga cabecera `Origin`, aunque el endpoint no la declare.

Consecuencia: la proteccion real de las respuestas autenticadas por cookie no es la ausencia de ACAO sino la regla del navegador de no combinar credenciales con `*` (una peticion con `credentials: include` hacia `*` se rechaza). Un origen ajeno no puede leer `session`, el indice ni el proxy por sesion; ademas, ninguna de estas URLs debe pasar por el proxy de terriajs-server, que descarta `Cookie`.

## Inferencia

La API parece pensada tanto para consumo interno desde la propia vista CKAN como para un consumidor externo que necesite catálogos Terria ya construidos.

## Pendiente por confirmar

- consumidores reales de cada endpoint;
- expectativas de versionado de API;
- si existe un proxy o CDN delante de `/api/terria/file/*`;
- valor de `ckan.cors.origin_allow_all` en cada despliegue (decide si el middleware anade ACAO `*` a las respuestas privadas).
