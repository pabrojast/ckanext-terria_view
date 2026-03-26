# Glosario

## CKAN

Plataforma de catálogo de datos sobre la que se instala esta extensión.

## Extensión CKAN

Paquete Python que registra plugins, actions, templates y configuración dentro de CKAN.

## Dataset

Entidad principal de CKAN. En código también aparece como `package`.

## Resource

Archivo o endpoint asociado a un dataset.

## Resource View

Representación visual de un recurso dentro de CKAN. Esta extensión crea vistas `terria_view`.

## TerriaJS

Framework de visualización geoespacial que consume configuraciones JSON para mostrar capas, catálogos y mapas.

## SLD

Styled Layer Descriptor. Formato XML usado para describir estilos de capas geoespaciales.

## COG

Cloud Optimized GeoTIFF. Raster geoespacial optimizado para acceso HTTP eficiente.

## SHP / Shapefile

Formato vectorial geoespacial tradicional.

## Custom Config

URL de Terria con estado guardado, normalmente usando fragmento `#start=` o `#share=`.

## Cache warmup / preload

Proceso que genera anticipadamente catálogos para reducir latencia en primeras requests.

## Stale-while-revalidate

Patrón en el que se sirve una versión cacheada aunque esté vencida mientras se regenera una nueva en segundo plano.

## `ihp-wins.json`

Endpoint de compatibilidad que sirve el catálogo completo en la raíz del portal.

## Wikilink

Enlace interno estilo Obsidian usando doble corchete y el nombre de una nota existente.
