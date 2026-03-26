# Setup Local

## Objetivo

Levantar un entorno útil para trabajar con la extensión, distinguiendo entre:

- trabajo rápido sobre lógica Python y SLD;
- integración real con CKAN.

## Requisitos previos

- Python disponible en el entorno local
- acceso a un entorno CKAN si se quiere probar la integración completa
- opcionalmente Postgres y Solr para tests integrados CKAN

## Opción A: trabajo rápido sobre código y tests no acoplados a CKAN

Útil para:

- iterar sobre `sld_processor.py`;
- revisar scripts de prueba de la raíz;
- editar documentación;
- validar imports parciales.

Pasos sugeridos:

1. Crear y activar un virtualenv.
2. Instalar el paquete en editable:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

3. Ejecutar tests o scripts que no dependan de CKAN completo.

Notas:

- `requirements.txt` y `dev-requirements.txt` están vacíos.
- Sin CKAN instalado, el test del plugin bajo `ckanext/terria_view/tests/` no colecta.

## Opción B: integración completa con CKAN

La documentación histórica del repo y la guía del repositorio apuntan a instalar la extensión dentro del virtualenv de CKAN.

Pasos base:

1. Activar el virtualenv de CKAN.
2. Instalar la extensión en editable:

```bash
python setup.py develop
```

Alternativa moderna:

```bash
pip install -e .
```

3. Agregar `terria_view` a `ckan.plugins`.
4. Configurar `ckan.site_url`.
5. Configurar opcionalmente:

- `ckanext.terria_view.default_title`
- `ckanext.terria_view.default_instance_url`
- `ckanext.terria_view.preload_cache`
- `ckanext.terria_view.preload_delay`

6. Reiniciar CKAN.

## Configuración mínima recomendada

```ini
ckan.plugins = ... terria_view
ckan.site_url = https://mi-ckan.example.org
ckanext.terria_view.default_title = Terria Viewer
ckanext.terria_view.default_instance_url = https://mi-terria.example.org/
```

Opcional:

```ini
ckan.views.default_views = ... terria_view
```

## Verificación manual rápida

1. Abrir un dataset con un recurso compatible.
2. Confirmar que CKAN crea o muestra una vista `TerriaJS Preview`.
3. Abrir la vista y verificar carga del iframe Terria.
4. Probar `GET /api/terria/cache/stats`.
5. Probar `GET /api/terria/dataset/<dataset_id>`.

## Observación local realizada durante esta documentación

`pytest --collect-only -q` en este entorno:

- colectó 22 tests raíz;
- falló al importar `ckanext/terria_view/tests/test_plugin.py` porque no hay módulo `ckan` instalado.

Esto confirma que el setup mínimo sin CKAN solo sirve para parte del repositorio.

## Pendiente por confirmar

- procedimiento exacto de setup para el entorno de producción actual;
- versión oficial de CKAN objetivo;
- si sigue siendo necesario `python setup.py develop` o ya se usa solo `pip install -e .`.
