# Claude Instructions

## Rol

Este archivo define reglas persistentes de documentación y mantenimiento para Claude.

## Fuente de verdad documental

- La documentación principal para humanos vive en `docs/obsidian-vault/`.
- Empezar por `docs/obsidian-vault/Index.md`.
- Si una explicación detallada ya existe en la vault, referenciarla en lugar de duplicarla.

## Política documental

- No inventar comportamiento, configuración ni flujos.
- Si algo no es seguro, marcarlo como `Pendiente por confirmar`.
- Si algo es una deducción razonable, marcarlo como `Inferencia`.
- Mantener el onboarding simple, útil y rápido de recorrer.

## Convenciones mínimas

- Mantener los nombres de notas en `Title Case`.
- Usar wikilinks `[[...]]` entre notas relacionadas.

## Cuándo actualizar la vault

- Cuando cambien arquitectura, módulos, flujos, comandos, setup, testing, variables de entorno, configuración o deployment.
- Cuando una explicación nueva sea útil para onboarding o mantenimiento.

## Alcance

Este archivo debe permanecer breve. Los detalles del repositorio viven en `docs/obsidian-vault/`, y las reglas de ejecución para Codex viven en `AGENTS.md`.
