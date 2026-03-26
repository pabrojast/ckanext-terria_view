# Backlog Documentacion

## Objetivo

Registrar los vacíos de información detectados durante el análisis del repositorio para que la documentación pueda madurar sin inventar.

## Vacíos principales

### Compatibilidad real de versiones

Situación:

- `README.rst` y Travis apuntan a CKAN/Python antiguos;
- el código actual muestra compatibilidad más reciente.

Impacto:

- afecta onboarding, setup y despliegue.

Estado:

- `Pendiente por confirmar`

### Infraestructura real de despliegue

Situación:

- no hay Docker, Helm ni CI moderna en el repo;
- solo hay Travis legacy.

Impacto:

- la nota [[Deployment]] solo puede documentar despliegue lógico, no operativo real.

Estado:

- `Pendiente por confirmar`

### DAG o consumidor externo de la API

Situación:

- `TERRIA_API_GUIDE.md` menciona un DAG externo;
- ese archivo no está en este repositorio.

Impacto:

- no se puede documentar el flujo end-to-end fuera de CKAN.

Estado:

- `Pendiente por confirmar`

### Suite de tests oficial

Situación:

- hay muchos `test_*.py` raíz, pero mezclan validación automática, scripts manuales y debugging.

Impacto:

- onboarding puede confundir qué tests son confiables para CI.

Estado:

- `Pendiente por confirmar`

### Contrato exacto con la instancia Terria

Situación:

- la UI asume un protocolo `postMessage` para obtener `shareData`;
- no hay documentación en el repo sobre la contraparte Terria.

Impacto:

- debugging difícil si falla `Save Configuration`.

Estado:

- `Pendiente por confirmar`

### Formatos realmente soportados en producción

Situación:

- `ConfigManager` declara muchos formatos;
- la lógica más robusta está claramente enfocada en CSV, SHP y TIFF/COG.

Impacto:

- conviene distinguir soporte nominal de soporte probado.

Estado:

- `Inferencia` y `Pendiente por confirmar`

## Mejoras documentales sugeridas

- agregar una matriz oficial CKAN/Python/Terria soportada;
- documentar el entorno de producción y el proceso de release;
- convertir scripts raíz importantes en tests formales o moverlos a `scripts/`;
- agregar ejemplos reales de configuración CKAN;
- documentar el contrato `postMessage` con Terria.

## Ver también

- [[Deployment]]
- [[Testing]]
- [[Variables de Entorno]]
