# Estructura del Repo

## Vista general

```text
ckanext-terria_view/
├── ckanext/
│   └── terria_view/
│       ├── plugin.py
│       ├── api_endpoints.py
│       ├── terria_json_generator.py
│       ├── terria_config_builder.py
│       ├── sld_processor.py
│       ├── resource_utils.py
│       ├── config_manager.py
│       ├── cache_manager.py
│       ├── file_cache_manager.py
│       ├── cache_preloader.py
│       ├── action_filters.py
│       ├── templates/
│       ├── public/
│       └── tests/
├── bin/
├── docs/
│   └── obsidian-vault/
├── test_*.py
├── README.rst
├── TERRIA_API_GUIDE.md
├── setup.py
├── setup.cfg
├── test.ini
├── .travis.yml
└── .coveragerc
```

## Directorios y archivos relevantes

### `ckanext/terria_view/`

Código de la extensión.

Ver también:

- [[Modulos]]
- [[Arquitectura]]

### `ckanext/terria_view/templates/`

Templates Jinja para render y configuración de la vista.

### `ckanext/terria_view/public/`

Assets estáticos usados por la UI de configuración.

### `ckanext/terria_view/tests/`

Tests del paquete CKAN.

Estado observado:

- solo existe `test_plugin.py` y es un placeholder mínimo;
- para colectarlo hace falta tener CKAN instalado.

### `test_*.py` en la raíz

Conjunto heterogéneo de scripts y tests.

Patrones observados:

- validaciones del procesador SLD;
- pruebas manuales contra endpoints remotos;
- tests de importación/compatibilidad;
- debugging específico de estilos y columnas de shapefile.

No todos estos archivos representan una suite automatizada estable de CI.

### `bin/`

Scripts de Travis CI para levantar CKAN de prueba, Postgres y Solr.

### `README.rst`

Documentación histórica de instalación, pruebas y publicación en PyPI.

### `TERRIA_API_GUIDE.md`

Guía complementaria sobre la API Terria on-demand y caché.

Importante:

- referencia un DAG externo que no existe en este repositorio.

### `setup.py` y `setup.cfg`

Packaging del plugin e instrucciones de i18n/Babel.

### `requirements.txt` y `dev-requirements.txt`

Están presentes, pero vacíos.

Implicación:

- la dependencia fuerte en CKAN se resuelve desde el entorno donde se instala la extensión.

## Configuración e infraestructura encontradas

- CI legacy: `.travis.yml`
- tests CKAN: `test.ini`
- cobertura: `.coveragerc`

No se encontraron en el árbol actual:

- `Dockerfile`
- `docker-compose`
- Helm charts
- GitHub Actions
- `pyproject.toml`
- `tox.ini`

## Inferencia

El repositorio mezcla código de producto con artefactos de investigación y debugging en la raíz. Para onboarding conviene tratar `ckanext/terria_view/` como la fuente principal y los `test_*.py` de raíz como soporte auxiliar.

## Pendiente por confirmar

- si existe otro repositorio para infraestructura o DAGs;
- si parte de los tests raíz deberían migrarse a una suite formal bajo `ckanext/terria_view/tests/`.
