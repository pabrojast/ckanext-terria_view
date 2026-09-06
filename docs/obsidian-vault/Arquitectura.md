# Arquitectura

## Resumen

El repositorio implementa una extensión de CKAN orientada a integrar recursos del portal con una instancia externa de TerriaJS.

La arquitectura se divide en cuatro responsabilidades:

1. integración con CKAN y render de vistas;
2. construcción de configuración Terria por recurso;
3. generación de catálogos JSON por entidad;
4. aceleración operativa mediante caché e invalidación.

## Vista de alto nivel

```text
CKAN Resource / Dataset
    -> Terria_ViewPlugin
        -> ConfigManager
        -> ResourceUtils
        -> TerriaConfigBuilder
        -> SLDProcessor
        -> CacheManager / FileCacheManager
        -> Jinja template terria.html
        -> TerriaJS instance externa

CKAN HTTP API
    -> Flask Blueprint /api/terria/*
        -> TerriaJSONGenerator
        -> CacheManager / FileCacheManager
        -> JSON o archivo .json cacheado
```

## Componentes arquitectónicos

### 1. Capa CKAN plugin

`Terria_ViewPlugin` registra:

- `IConfigurer` para templates y assets públicos;
- `IBlueprint` para exponer endpoints Flask;
- `ITemplateHelpers` para descubrir archivos SLD;
- `IConfigurable` para leer configuración CKAN;
- `IResourceView` para renderizar y configurar la vista;
- `IActions` para interceptar acciones CKAN como `resource_view_list`, `package_show` y `resource_show`.

### 2. Capa de construcción de configuración Terria

Cuando CKAN necesita renderizar una vista, el plugin:

- determina si el recurso es compatible;
- resuelve URL real del recurso;
- obtiene bounds del dataset;
- aplica configuración automática o custom;
- aplica estilo SLD si existe;
- serializa la configuración y la entrega a la template `terria.html`.

### 3. Capa de generación de catálogos

El `TerriaJSONGenerator` construye JSONs para:

- dataset;
- organización;
- tag;
- catálogo completo;
- catálogo modular de referencias.

Esta capa reutiliza la lógica de estilos y configuración de la extensión para evitar duplicación con procesos externos.

### 4. Capa de caché

Hay dos niveles:

- `CacheManager`: caché en memoria con invalidación por hash de contenido;
- `FileCacheManager`: caché en disco bajo `ckan.storage_path` o un directorio temporal.

Además existe `CachePreloader`, que intenta calentar catálogos al inicio en un hilo de fondo.

### 5. Capa de datasets no publicos

Usuarios autenticados pueden visualizar en Terria los datasets no publicos a los que estan autorizados: `private=True` de CKAN core (`confidential` en `ckanext-datashare`) y los niveles datashare `findable`/`restricted`/`viewable` cuando `datashare_access_check` devuelve `can_download` (`is_non_public_dataset` + `PrivateCatalogBuilder._can_load`).

- Los catálogos públicos (`ihp-wins.json`, `/api/terria/*`) **nunca** incluyen datos privados. Las cachés (`CacheManager`, `FileCacheManager`) son estrictamente públicas y nunca reciben un `user_context` real.
- Hay dos consumidores: la vista embebida en CKAN (catalogo inyectado en `#start=`) y el Terria standalone same-origin, que descubre la sesion con `GET /api/terria/user/session` (whoami, siempre `200`, URLs relativas) y anade el catalogo privado por su cuenta. Ver [[Flujos Importantes]] (flujos 5 y 10).
- En modo `auto` (default), una instancia Terria del mismo origen usa catálogo **lazy**: `setup_template_variables()` sólo inyecta un `terria-reference` pequeño en `encoded_config`; no ejecuta búsquedas ni formatea recursos durante el render inicial.
- Al abrir esa referencia, `/api/terria/user/private-catalog` devuelve Organización → referencias de datasets con **una** `package_search` de campos mínimos (`NON_PUBLIC_FQ`: `capacity:private` ∪ `access_level != public`) filtrada por `datashare_access_check.can_download`; sin `ckanext-datashare` el fallback es private-only. Los recursos y estilos de un dataset se generan recién al abrir `/api/terria/user/private-catalog/dataset/<id>`, con el mismo gate.
- En lazy same-origin (`is_same_origin(site_url, terria_instance_url)`) todas las URLs son relativas (`/api/terria/...`) para que viajen con la cookie CKAN y nunca pasen por el proxy de terriajs-server; cross-origin e inline mantienen URLs absolutas. `auto` conserva el catálogo inline anterior para cross-origin; puede forzarse con `private_catalog_mode=lazy|inline`.
- Las URLs de recursos no publicos se emiten como endpoint proxy CKAN firmado (`/api/terria/resource/<id>/content/<file>?token=<token>`). El proxy autoriza por token **o** por sesion CKAN (`ResourceUtils.user_may_download`: `datashare_resource_download`, `resource_show` solo si no existe), resuelve la SAS server-side con el uploader, reenvia `Range`/`If-*` y pasa `206`/`304` (COG por rangos), nunca reenvia `Cookie`/`Authorization`, y stremea con `Access-Control-Allow-Origin: *`, de modo que el iframe Terria (en otro dominio) no depende de la configuración CORS del Storage Account Azure.
- Los tokens del proxy se firman HMAC-SHA256 con `beaker.session.secret`/`SECRET_KEY`, expiran por defecto en 1h y están atados a un `resource_id` específico. Por sesion la respuesta es `private, no-store` + `Vary: Cookie`; por token `private, max-age=300`.
- Toda respuesta autenticada por cookie marca `request.environ['__no_cache__']` para que el middleware de CKAN no anada `public, must-revalidate` (ver [[API y Endpoints]]).
- La configuracion cacheada en `resource_view` (`cached_config`) se omite para paquetes no publicos (`is_non_public_dataset`: `private=True` o `access_level` distinto de `public`) y siempre que la URL calculada apunte al proxy con token (`Terria_ViewPlugin._may_persist_cached_config`): `cached_config` es legible via `resource_view_show`, asi que nunca debe guardar un token por visor.
- `ResourceUtils.get_resource_url` solo acuna el token del proxy (y solo resuelve la SAS) si `user_may_download` lo permite; iniciar sesion no basta, porque la pagina de vista de un dataset `viewable` la puede abrir cualquiera.

## Decisiones observables en código

- La vista Terria se autogenera desde `resource_view_list`, no solo manualmente.
- El catálogo completo y los archivos JSON grandes se sirven con patrón stale-while-revalidate.
- La extensión filtra datasets privados o inactivos en varios generadores públicos.
- Para payloads CKAN grandes, `action_filters.py` elimina extras pesados de recursos.
- Los catálogos privados no usan caché compartida. Al guardar una vista sólo persisten las capas privadas mostradas, sin tokens; el navegador lazy y los datasets no usados se descartan.

## Integraciones externas

- CKAN
- TerriaJS
- `ckanext-datashare` (opcional): accion `datashare_access_check` y auth `datashare_resource_download`; sin ella la capa de datasets no publicos degrada a private-only (ver [[Variables de Entorno]])
- archivos SLD accesibles por URL
- opcionalmente Gists Terria compartidos usando fragmentos `#share=...`

## Inferencia

El proyecto parece operar o haber operado principalmente en el contexto IHP-WINS / UNESCO:

- el default de `default_instance_url` apunta a `https://ihp-wins.unesco.org/terria/`;
- existe un endpoint raíz `ihp-wins.json`;
- varios ejemplos y guías internas referencian ese entorno.

## Riesgos arquitectónicos a tener presentes

- acoplamiento fuerte a CKAN y a disponibilidad de la instancia Terria externa;
- dependencias de red durante procesamiento de SLD y configuración custom;
- parte del comportamiento depende de threads en background;
- coexistencia de señales de compatibilidad antigua y moderna del stack.

## Pendiente por confirmar

- matriz oficial de compatibilidad CKAN/Python;
- si el preloading en threads es aceptable en el runtime real usado por CKAN;
- si existe un proceso externo consumiendo `/api/terria/*` fuera del portal principal.
