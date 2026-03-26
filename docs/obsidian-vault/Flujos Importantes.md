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

## 4. Guardar configuración desde la UI

Entrada:

- un usuario autenticado pulsa `Save Configuration` en la vista.

Secuencia:

1. `terria.html` envía `postMessage` al iframe Terria pidiendo `shareData`.
2. Construye una URL `#start=...`.
3. Hace `POST /api/terria/view/<view_id>/save-config`.
4. El endpoint valida la URL HTTP(S).
5. La vista CKAN se actualiza con el nuevo `custom_config`.

Resultado:

- la próxima carga reutiliza el estado guardado del mapa.

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

1. `after_create`, `after_update` o `after_delete` invalidan caché por `resource_id`.
2. Se limpian entradas de dataset, organización, tags y catálogo completo.
3. Los endpoints regeneran a demanda en la siguiente solicitud.

## 8. Preload de caché al arranque

Secuencia:

1. `configure()` inicializa `CachePreloader`.
2. Se espera un delay configurable.
3. Se intentan precargar catálogo modular, organizaciones, datasets recientes, tags populares y catálogo completo.

## Pendiente por confirmar

- si el warmup corre de forma fiable bajo todos los servidores WSGI usados por CKAN;
- si el botón `Save Configuration` depende de una modificación específica en la instancia Terria embebida para responder `shareDataResponse`.
