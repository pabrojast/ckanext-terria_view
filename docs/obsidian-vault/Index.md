# Index

## Propósito

`ckanext-terria_view` es una extensión de CKAN que agrega vistas de recursos basadas en TerriaJS y expone endpoints JSON para construir catálogos consumibles por Terria.

En términos prácticos, el proyecto hace tres cosas:

- agrega automáticamente vistas `terria_view` a recursos compatibles;
- construye configuraciones TerriaJS para recursos individuales;
- genera catálogos JSON on-demand para datasets, organizaciones, tags y catálogo completo.

## Ruta recomendada de onboarding

1. [[Arquitectura]]
2. [[Modulos]]
3. [[Flujos Importantes]]
4. [[Estructura del Repo]]
5. [[Setup Local]]
6. [[Testing]]
7. [[Troubleshooting]]

## Mapa de navegación

- Entendimiento del sistema: [[Arquitectura]], [[Modulos]], [[Flujos Importantes]]
- Ubicación de código: [[Estructura del Repo]]
- Trabajo local: [[Setup Local]], [[Comandos Utiles]], [[Variables de Entorno]]
- Operación y despliegue: [[Deployment]], [[API y Endpoints]]
- Calidad: [[Testing]], [[Troubleshooting]]
- Gobernanza documental: [[Convenciones de la Vault]], [[Guia de Mantenimiento]], [[Backlog Documentacion]]
- Términos del dominio: [[Glosario]]

## Hechos rápidos

- Stack principal: Python + CKAN plugin API + Flask Blueprint + Jinja templates.
- Entrada principal del plugin: `terria_view=ckanext.terria_view.plugin:Terria_ViewPlugin`.
- Módulos más importantes: `plugin.py`, `terria_json_generator.py`, `api_endpoints.py`, `sld_processor.py`.
- Caché: memoria y archivos temporales.
- Configuración crítica: `ckan.site_url` y `ckanext.terria_view.default_instance_url`.
- La extensión intenta crear vistas Terria automáticamente en `resource_view_list`.

## Qué leer según tarea

- Quiero entender cómo se renderiza una vista: [[Flujos Importantes]].
- Quiero cambiar soporte de formatos o defaults: [[Modulos]] y [[Variables de Entorno]].
- Quiero tocar endpoints o catálogos: [[API y Endpoints]] y [[Arquitectura]].
- Quiero trabajar con estilos SLD: [[Modulos]], [[Testing]] y [[Troubleshooting]].
- Quiero desplegar o revisar operación: [[Deployment]].

## Pendiente por confirmar

- Compatibilidad objetivo exacta entre versiones de CKAN y Python.
- Infraestructura de despliegue actual fuera del repositorio.
- Si el catálogo modular y el endpoint `ihp-wins.json` siguen siendo el contrato principal en producción.
