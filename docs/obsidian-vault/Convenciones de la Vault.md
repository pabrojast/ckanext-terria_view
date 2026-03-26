# Convenciones de la Vault

## Objetivo

Mantener la documentación simple, navegable y alineada con el código real.

## Convención de nombres de notas

- usar `Title Case`;
- usar nombres descriptivos y estables;
- preferir español para títulos de notas;
- usar singular cuando el tema es un concepto estable;
- evitar prefijos numéricos salvo que la navegación realmente lo requiera.

Ejemplos correctos:

- `Arquitectura`
- `Flujos Importantes`
- `Variables de Entorno`
- `Backlog Documentacion`

## Convención de tags

Propuesta mínima:

- `#hub` para notas índice
- `#arquitectura` para diseño y módulos
- `#operacion` para setup, deployment y troubleshooting
- `#testing` para calidad y validación
- `#ckan` para integración CKAN
- `#terria` para integración TerriaJS
- `#pendiente` para vacíos o decisiones abiertas

Uso recomendado:

- no saturar notas con tags;
- usar entre 1 y 3 tags por nota si se decide adoptarlos;
- no usar tags como sustituto de wikilinks.

## Convención de estructura

- vault mayormente plana;
- `Index.md` como punto de entrada;
- cada nota debe enlazar a otras notas relacionadas;
- usar secciones explícitas para `Inferencia` y `Pendiente por confirmar` cuando aplique.

## Convención de contenido

- explicar antes de listar detalles;
- resumir, no copiar archivos completos;
- evitar dumps de código;
- referenciar módulos y rutas reales del repo;
- marcar incertidumbre explícitamente.

## Relación con archivos para asistentes

- la vault contiene el contexto humano mantenible;
- `CLAUDE.md` y `AGENTS.md` deben quedarse como capas operativas cortas;
- evitar copiar secciones completas de la vault en esos archivos.

## Cuándo crear una nota nueva

Crear una nota nueva solo si:

- el tema tiene entidad propia;
- mejora la navegación;
- evita sobrecargar otra nota principal.

Si no, expandir una nota existente.

## Ver también

- [[Guia de Mantenimiento]]
- [[Backlog Documentacion]]
