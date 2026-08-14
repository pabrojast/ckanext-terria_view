# Modulos

## Módulos principales

### `ckanext/terria_view/plugin.py`

Punto de entrada principal del plugin.

Responsabilidades:

- inicializar managers y utilidades;
- registrar interfaces CKAN;
- crear automáticamente vistas `terria_view`;
- transformar datos del formulario antes de persistir;
- calcular y persistir `cached_config` en la vista;
- invalidar cachés después de crear, actualizar o borrar vistas.

Tocar aquí cuando:

- cambie el comportamiento de auto-creación de vistas;
- cambie el formulario de configuración;
- cambie el render de la vista principal;
- cambie la integración de acciones CKAN.

### `ckanext/terria_view/config_manager.py`

Centraliza defaults y validaciones básicas.

Responsabilidades:

- formatos soportados;
- validación de dominios;
- defaults de título e instancia Terria;
- helpers para nombres de recurso y coordenadas;
- schema de campos extra para la vista CKAN.

Tocar aquí cuando:

- haya que soportar nuevos formatos;
- cambien defaults o campos del schema;
- cambien reglas de aceptación de recursos.

### `ckanext/terria_view/resource_utils.py`

Utilidades para datasets y recursos.

Responsabilidades:

- descubrir SLDs dentro de un dataset;
- extraer bounds desde `spatial` GeoJSON;
- resolver URL efectiva del recurso (público directo vs proxy CKAN firmado para privados);
- firmar y verificar tokens HMAC del proxy de recursos privados;
- resolver la URL upstream (SAS) que el proxy debe stremear;
- decodificar nombres y parsear URLs de configuración custom.

Tocar aquí cuando:

- cambie la procedencia de bounds;
- cambie la lógica para recursos privados o subidos a CKAN;
- cambie el formato/TTL del token del proxy o el secret utilizado para firmarlo;
- cambie el tratamiento de URLs `#start` o `#share`.

### `ckanext/terria_view/terria_config_builder.py`

Construye la configuración Terria por recurso.

Responsabilidades:

- generar configs para CSV, COG, SHP y formatos genéricos;
- adaptar una config custom a una URL de recurso concreta;
- aplicar estilos SLD a modelos Terria;
- eliminar grupos huérfanos en configs guardadas.

Tocar aquí cuando:

- cambie la estructura JSON enviada a Terria;
- cambie la forma de aplicar estilos;
- se quiera soportar otro tipo de item Terria.

### `ckanext/terria_view/sld_processor.py`

Procesador SLD con mucho peso funcional.

Responsabilidades:

- descargar y parsear SLD;
- convertir reglas SLD a estilos TerriaJS;
- construir leyendas;
- adaptar estilos para SHP y COG;
- normalizar colores y valores numéricos.

Tocar aquí cuando:

- haya problemas de estilos;
- haya que soportar otro patrón SLD;
- Terria cambie su contrato de estilos.

### `ckanext/terria_view/terria_json_generator.py`

Generador de catálogos JSON on-demand.

Responsabilidades:

- construir catálogo por dataset, organización, tag y completo;
- expandir múltiples vistas Terria por recurso;
- aplicar estilos y configuraciones custom existentes;
- servir como base funcional de los endpoints `/api/terria/*`.

Tocar aquí cuando:

- cambie la estructura de salida de catálogos;
- se necesiten nuevas agrupaciones;
- cambie la estrategia de cacheado o serialización.

### `ckanext/terria_view/private_catalog.py`

Responsabilidades:

- resolver `auto|lazy|inline` según los orígenes CKAN/Terria;
- crear la referencia privada mínima con namespace por sesión;
- construir el índice privado de campos mínimos;
- expandir y autorizar un solo dataset bajo demanda.

### `ckanext/terria_view/api_endpoints.py`

Blueprint Flask que expone la API.

Responsabilidades:

- endpoints JSON y endpoints de archivo;
- respuestas CORS (incluye preflight con `Range`);
- regeneración asíncrona del catálogo completo;
- guardado de `custom_config` desde la UI;
- endpoints lazy y legacy de datasets privados del usuario;
- proxy streaming de recursos privados (`/api/terria/resource/<id>/content`) validado por token firmado.

Tocar aquí cuando:

- cambien rutas o contratos HTTP;
- haya que reforzar seguridad o autorización;
- cambie la forma de servir archivos cacheados;
- se quiera soportar `Range` requests o caching avanzado en el proxy.

### `ckanext/terria_view/cache_manager.py`

Caché en memoria con invalidación por contenido.

### `ckanext/terria_view/file_cache_manager.py`

Caché en archivos JSON sobre un directorio escribible.

### `ckanext/terria_view/cache_preloader.py`

Warmup de caché en background durante arranque.

### `ckanext/terria_view/action_filters.py`

Wrappers sobre `package_show` y `resource_show` para recortar extras pesados de recursos.

## Templates y assets

### `ckanext/terria_view/templates/terria.html`

Template de render.

Incluye:

- iframe hacia Terria;
- botón para abrir en ventana separada;
- botón para toggle de ancho completo;
- botón para guardar configuración desde el estado actual del mapa.

### `ckanext/terria_view/templates/terria_instance_url.html`

Template del formulario de configuración.

Incluye:

- URL de la instancia Terria;
- selección entre configuración automática y custom;
- selección de SLD desde archivos del dataset o URL custom;
- ayuda visual `custom_config.gif`.

### `ckanext/terria_view/public/help/custom_config.gif`

Asset de ayuda usado en el formulario.

## Dónde tocar según objetivo

- Quiero cambiar soporte de formatos: [[Variables de Entorno]] y `config_manager.py`.
- Quiero corregir estilos SLD: `sld_processor.py` y [[Testing]].
- Quiero cambiar la UI de la vista: templates y `plugin.py`.
- Quiero cambiar la API de catálogos: `api_endpoints.py` y `terria_json_generator.py`.
- Quiero cambiar caché o performance: `cache_manager.py`, `file_cache_manager.py`, `cache_preloader.py`.

## Pendiente por confirmar

- si `terria_json_generator.py` reemplaza completamente un DAG externo o solo convive con él;
- si `action_filters.py` está habilitado en todos los despliegues.
