# Testing

## Resumen

El repositorio tiene una estrategia de pruebas mixta.

Hay tres capas distintas:

1. tests formales CKAN bajo `ckanext/terria_view/tests/`;
2. tests y scripts raíz orientados a SLD y compatibilidad;
3. scripts manuales contra endpoints remotos.

## Estado observado

Para el catálogo privado lazy se ejecuta:

```bash
pytest -q test_private_datasets.py test_strip_private_catalog.py
```

Cobertura: selección de modo, referencia inicial, índice modular, expansión por dataset, namespace de modelos, guardado idempotente y eliminación de tokens.

Durante esta documentación se ejecutó:

```bash
pytest --collect-only -q
```

Resultado:

- 22 tests raíz fueron colectados;
- la colección falló en `ckanext/terria_view/tests/test_plugin.py` por ausencia del módulo `ckan` en el entorno local.

Esto confirma que la suite no está completamente desacoplada del runtime CKAN.

## Qué tests existen

### Tests del plugin CKAN

Ruta:

- `ckanext/terria_view/tests/test_plugin.py`

Observación:

- actualmente es un placeholder con `pass`.

### Tests raíz orientados a SLD

Ejemplos:

- `test_sld_robust.py`
- `test_sld_final.py`
- `test_sld_corrections.py`
- `test_problematic_sld.py`
- `test_terria_compliance.py`

Cobertura funcional:

- parseo SLD;
- robustez ante XML defectuoso;
- normalización de colores;
- compliance de salida para TerriaJS;
- casos específicos de columnas y reglas.

### Tests raíz orientados a endpoints y compatibilidad

Ejemplos:

- `test_cache_preload.py`
- `test_fixes.py`
- `test_import_fix.py`

Observación:

- algunos llaman endpoints remotos hardcodeados;
- no todos son adecuados para CI determinista.

## Comandos relevantes

Tests rápidos:

```bash
pytest -q
pytest -k sld -q
```

Tests integrados CKAN:

```bash
nosetests --with-pylons=test.ini --with-coverage --cover-package=ckanext.terria_view
```

## Limitaciones actuales de la suite

- falta una suite formal más robusta para `plugin.py`, `api_endpoints.py` y `terria_json_generator.py`;
- varios tests son más scripts de exploración que unit tests aislados;
- hay dependencia en servicios externos y URLs concretas;
- el test del plugin no aporta cobertura real todavía.

## Recomendación práctica

Para iterar por áreas:

- cambios en SLD: ejecutar primero tests raíz `test_sld_*`;
- cambios en endpoints o caché: validar manualmente con `curl` y, si es posible, CKAN real;
- cambios en integración CKAN: ejecutar `nosetests` con entorno completo.

## Pendiente por confirmar

- qué subconjunto de tests se considera oficialmente soportado;
- si hay una suite CI moderna fuera de Travis;
- si los scripts raíz deben seguir siendo tests o migrarse a `scripts/` o `examples/`.
