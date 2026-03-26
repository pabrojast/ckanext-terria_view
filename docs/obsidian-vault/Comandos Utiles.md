# Comandos Utiles

## Instalación y entorno

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Instalación en entorno CKAN

```bash
python setup.py develop
```

## Tests rápidos

```bash
pytest -q
pytest -k sld -q
pytest --collect-only -q
```

## Tests integrados con CKAN

```bash
nosetests --with-pylons=test.ini --with-coverage --cover-package=ckanext.terria_view
```

Comando histórico de README:

```bash
nosetests --nologcapture --with-pylons=test.ini
```

## Internacionalización

```bash
python setup.py extract_messages
python setup.py init_catalog
python setup.py update_catalog
python setup.py compile_catalog
```

## Endpoints útiles para operación

```bash
curl "http://localhost:5000/api/terria/cache/stats"
curl "http://localhost:5000/api/terria/modular"
curl "http://localhost:5000/api/terria/full"
curl "http://localhost:5000/api/terria/file/full"
```

## Invalidación y limpieza de caché

```bash
curl -X POST "http://localhost:5000/api/terria/cache/invalidate"
curl -X POST "http://localhost:5000/api/terria/cache/cleanup"
```

## Debug

```bash
export TERRIA_DEBUG=true
export TERRIA_PRELOAD_CACHE=true
export TERRIA_PRELOAD_DELAY=10
```

## Travis legacy

```bash
bash bin/travis-build.bash
sh bin/travis-run.sh
```

## Ver también

- [[Setup Local]]
- [[Variables de Entorno]]
- [[Testing]]
