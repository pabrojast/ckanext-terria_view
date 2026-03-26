# Codex Instructions

## Alcance

Este archivo define reglas de ejecución para Codex en este repositorio.

## Documentación principal

- La fuente de verdad para humanos es `docs/obsidian-vault/`.
- Empezar por `docs/obsidian-vault/Index.md`.
- No duplicar en este archivo contenido que ya vive mejor en la vault.
- Para detalles documentales persistentes, respetar `CLAUDE.md`.

## Orden de trabajo

1. Explorar el código y la documentación existente.
2. Planificar cambios mínimos y focalizados.
3. Implementar.
4. Verificar con tests o validaciones razonables.
5. Documentar y actualizar la vault si cambió algo relevante.

## Reglas operativas

- Preferir cambios pequeños, locales y reversibles.
- No expandir alcance sin necesidad.
- Basar cambios en el código y en la vault; si falta información, documentar el vacío siguiendo la convención de la vault.

## Obligación de documentación

Actualizar `docs/obsidian-vault/` cuando cambien:

- arquitectura o flujos;
- comandos o setup;
- variables de entorno o configuración;
- testing;
- deployment u operación.

## Checklist antes de cerrar una tarea

- el cambio cumple el objetivo pedido;
- se verificó lo que era razonable verificar;
- la documentación quedó actualizada si correspondía;
- `CLAUDE.md`, `AGENTS.md` y la vault siguen siendo coherentes;
- los supuestos y vacíos quedaron marcados según la convención documental vigente.
