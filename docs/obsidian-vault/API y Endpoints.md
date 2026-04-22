# API y Endpoints

## Resumen

La extensión registra un Blueprint Flask con endpoints bajo `/api/terria/*` y un endpoint de compatibilidad en `/ihp-wins.json`.

Todos los responses JSON agregan cabeceras CORS amplias:

- `Access-Control-Allow-Origin: *`
- `Access-Control-Allow-Methods: GET, POST, OPTIONS`
- `Access-Control-Allow-Headers: Content-Type`

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

- la URL debe ser `http://` o `https://`.

### Datasets privados del usuario

- `GET /api/terria/user/private-datasets`

Uso:

- construir un catálogo Terria con datasets privados accesibles al usuario autenticado.

### Proxy de recursos privados

- `GET /api/terria/resource/<resource_id>/content?token=<token>`
- `GET /api/terria/resource/<resource_id>/content/<filename>?token=<token>`
- `HEAD` en ambas variantes.

Uso:

- permite que el iframe de Terria (que vive en otro dominio y no tiene sesión CKAN) descargue recursos privados sin depender de la configuración CORS del Storage Account Azure.

Comportamiento:

- exige un `token` HMAC firmado por `ResourceUtils.generate_resource_token`.
- el token está atado al `resource_id` y a una expiración (default 1 hora); no es transferible entre recursos y no puede falsificarse sin el secret de CKAN.
- el segmento `<filename>` es **cosmético**: TerriaJS valida la extensión de la URL antes de hacer fetch (p. ej. shapefiles requieren `.zip`, GeoJSON espera `.geojson`). Se preserva en el path para no romper esas validaciones; la autorización sigue siendo solo el token.
- CKAN resuelve la URL SAS server-side usando el uploader, descarga el blob con `ignore_auth=True`, y devuelve el contenido con `Access-Control-Allow-Origin: *`.
- se conservan `Content-Length`, `ETag`, `Last-Modified`, `Accept-Ranges`, `Content-Disposition` cuando el upstream los expone.
- si el upstream responde `>= 400`, el endpoint devuelve `502` con el cuerpo recortado del error para facilitar debugging.

### Preflight CORS

- `OPTIONS /api/terria/<path:path>`

## Contratos funcionales importantes

- Los endpoints públicos intentan excluir datasets privados e inactivos.
- Los endpoints de archivo dependen de que la caché de archivos esté habilitada.
- Si falla el envío de archivo, algunos endpoints hacen fallback a respuesta JSON estándar.

## Seguridad y autorización

Observaciones:

- `save-config` intenta operar con el usuario actual y respeta autorización CKAN.
- `user/private-datasets` exige usuario autenticado.
- `resource_views` y otros endpoints públicos dependen de permisos CKAN y de cómo respondan las acciones base.

## Inferencia

La API parece pensada tanto para consumo interno desde la propia vista CKAN como para un consumidor externo que necesite catálogos Terria ya construidos.

## Pendiente por confirmar

- consumidores reales de cada endpoint;
- expectativas de versionado de API;
- si existe un proxy o CDN delante de `/api/terria/file/*`.
