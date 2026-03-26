# Deployment

## Qué se puede afirmar desde el repositorio

La extensión está pensada para desplegarse dentro de una instancia CKAN ya existente. No hay evidencia en el repositorio de un empaquetado container-first o de infraestructura Kubernetes/Helm.

## Pasos de despliegue conocidos

1. Instalar la extensión dentro del entorno Python de CKAN.
2. Agregar `terria_view` a `ckan.plugins`.
3. Configurar `ckan.site_url`.
4. Configurar una instancia Terria accesible desde CKAN con `ckanext.terria_view.default_instance_url`.
5. Reiniciar CKAN.

Opcional:

- agregar `terria_view` a `ckan.views.default_views`;
- habilitar preload de caché;
- ajustar filtros de extras pesados.

## Dependencias operativas

- CKAN
- acceso de red a la instancia Terria
- acceso de red a archivos SLD si vienen por URL
- directorio escribible para caché de archivos

## Compatibilidad encontrada

Señales mixtas:

- `README.rst` dice "Built with CKAN 2.7".
- scripts de Travis usan Python `2.7`.
- código actual incluye type hints y comentarios de compatibilidad con CKAN `2.10+`.

Conclusión:

- la compatibilidad real necesita validación explícita antes de cualquier despliegue nuevo.

## CI/CD e infraestructura detectada

Encontrado:

- `.travis.yml`
- `bin/travis-build.bash`
- `bin/travis-run.sh`

No encontrado:

- Dockerfile
- docker-compose
- Helm charts
- GitHub Actions
- Terraform

## Qué hacen los scripts de Travis

`bin/travis-build.bash`:

- instala Postgres y Solr;
- clona CKAN;
- inicializa base de datos de test;
- instala la extensión;
- mueve `test.ini` a `subdir/`.

`bin/travis-run.sh`:

- prepara Jetty/Solr;
- ejecuta `nosetests` con `subdir/test.ini`.

## Catálogos y operación

Endpoints importantes en despliegue:

- `/api/terria/full`
- `/api/terria/file/full`
- `/ihp-wins.json`
- `/api/terria/modular`

Operativamente, el catálogo completo depende de caché de archivo para evitar regeneraciones costosas en cada request.

## Inferencia

La extensión probablemente convivió con procesos externos que consumían estos endpoints para publicar catálogos Terria. La guía `TERRIA_API_GUIDE.md` menciona un DAG de Airflow, pero ese DAG no está en este repositorio.

## Pendiente por confirmar

- topología real de despliegue actual;
- proceso actual de release y rollback;
- si Travis sigue siendo relevante o es solo legado;
- si existe un repo separado con manifests de infraestructura.
