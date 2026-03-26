# Vault de Documentación

Esta carpeta convierte el repositorio en una base de conocimiento compatible con Obsidian para onboarding técnico, operación y mantenimiento.

## Cómo usar esta vault

1. Abrir `docs/obsidian-vault/` como vault o como carpeta dentro de Obsidian.
2. Empezar por [[Index]].
3. Seguir la ruta sugerida de lectura:
   [[Index]] -> [[Arquitectura]] -> [[Modulos]] -> [[Flujos Importantes]] -> [[Setup Local]].
4. Usar los wikilinks para navegar entre notas relacionadas.

## Qué cubre

- Visión general del sistema en [[Arquitectura]]
- Mapa de código en [[Estructura del Repo]]
- Setup y operación local en [[Setup Local]]
- Comandos recurrentes en [[Comandos Utiles]]
- Variables y configuración en [[Variables de Entorno]]
- Despliegue y operación en [[Deployment]]
- Endpoints en [[API y Endpoints]]
- Pruebas en [[Testing]]
- Problemas frecuentes en [[Troubleshooting]]
- Vacíos documentales en [[Backlog Documentacion]]

## Capas de documentación del repositorio

- `docs/obsidian-vault/` es la documentación principal para humanos y la fuente de verdad documental.
- `CLAUDE.md` es una guía operativa breve para Claude Code.
- `AGENTS.md` es una guía operativa breve para Codex.

Los archivos de asistentes deben referenciar esta vault y no duplicar contenido que ya vive mejor aquí.

## Qué no asume

- No asume conocimiento previo de CKAN ni de TerriaJS.
- No inventa detalles de infraestructura no presentes en el repositorio.
- Marca explícitamente `Inferencia` y `Pendiente por confirmar` donde falta evidencia en código o configuración.

## Convención de mantenimiento

Antes de actualizar esta vault, revisar [[Guia de Mantenimiento]] y [[Convenciones de la Vault]].
