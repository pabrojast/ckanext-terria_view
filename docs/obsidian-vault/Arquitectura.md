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

## Decisiones observables en código

- La vista Terria se autogenera desde `resource_view_list`, no solo manualmente.
- El catálogo completo y los archivos JSON grandes se sirven con patrón stale-while-revalidate.
- La extensión filtra datasets privados o inactivos en varios generadores públicos.
- Para payloads CKAN grandes, `action_filters.py` elimina extras pesados de recursos.

## Integraciones externas

- CKAN
- TerriaJS
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
