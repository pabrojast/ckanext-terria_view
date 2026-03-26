# Guia de Mantenimiento

## Objetivo

Evitar que la documentación se desalineé del código tras cambios funcionales.

## Checklist general después de cambios

- revisar si cambió el flujo descrito en [[Flujos Importantes]];
- revisar si cambió la arquitectura o límites de responsabilidad en [[Arquitectura]] y [[Modulos]];
- revisar si se agregaron o quitaron archivos relevantes en [[Estructura del Repo]];
- revisar si cambiaron comandos de instalación o pruebas en [[Setup Local]], [[Comandos Utiles]] y [[Testing]];
- revisar si aparecieron nuevas variables o claves de configuración en [[Variables de Entorno]];
- revisar si cambió la forma de desplegar o cachear en [[Deployment]];
- agregar o actualizar vacíos en [[Backlog Documentacion]];
- revisar `CLAUDE.md` y `AGENTS.md` si cambió el modo recomendado de trabajar sobre este repo;
- asegurar que los wikilinks nuevos funcionen.

## Regla de coherencia entre capas

- la explicación humana detallada debe vivir en `docs/obsidian-vault/`;
- `CLAUDE.md` y `AGENTS.md` deben permanecer breves y referenciar la vault;
- si un detalle empieza a crecer, moverlo o resumirlo en la vault en vez de duplicarlo.

## Si cambia backend

Revisar:

- `plugin.py`
- `api_endpoints.py`
- `terria_json_generator.py`
- managers de caché

Actualizar:

- [[Arquitectura]]
- [[Modulos]]
- [[Flujos Importantes]]
- [[API y Endpoints]]
- [[Troubleshooting]]

## Si cambia frontend o templates

Revisar:

- `templates/terria.html`
- `templates/terria_instance_url.html`
- `public/`

Actualizar:

- [[Modulos]]
- [[Flujos Importantes]]
- [[Troubleshooting]]

## Si cambia infraestructura o despliegue

Revisar:

- archivos CI/CD nuevos o eliminados;
- cambios en variables de entorno;
- cambios en storage/cache;
- cambios en endpoints expuestos públicamente.

Actualizar:

- [[Deployment]]
- [[Variables de Entorno]]
- [[Comandos Utiles]]
- [[Backlog Documentacion]]

## Si cambia testing

Revisar:

- nuevos tests formales;
- scripts raíz movidos o eliminados;
- comandos de CI.

Actualizar:

- [[Testing]]
- [[Comandos Utiles]]
- [[Setup Local]]

## Buenas prácticas

- documentar cambios en el mismo PR o commit que modifica el comportamiento;
- no documentar hipótesis como hechos;
- citar el archivo o módulo real del que sale la información;
- preferir actualización incremental sobre reescrituras totales;
- si falta contexto, registrar el hueco en [[Backlog Documentacion]].
