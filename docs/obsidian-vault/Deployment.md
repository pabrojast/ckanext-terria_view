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

### Regenerar catálogos después de cambiar su generación

La corrección de configuración guardada SWOT en `terria_json_generator.py` no requiere migrar datos ni volver a guardar vistas. Sí requiere retirar los JSON generados por la versión anterior:

1. Desplegar la extensión mediante el procedimiento del entorno.
2. Con una sesión/API de sysadmin, ejecutar `POST /api/terria/cache/invalidate` sin parámetros para limpiar todos los tipos de catálogo. La invalidación de archivos debe alcanzar cada instancia con un directorio de caché independiente.
3. Reiniciar todos los workers CKAN del entorno para retirar sus cachés en memoria; una petición de invalidación sólo limpia la memoria del worker que la atiende. Hacerlo según el procedimiento operativo del entorno.
4. Consultar de nuevo los catálogos de dataset y completo; si el completo responde `202 generating`, esperar a su regeneración. Comprobar que el item GeoJSON contiene `style`, `perPropertyStyles` y `featureInfoTemplate` cuando la vista los guarda, y abrirlo en una sesión nueva de Terria para comprobar colores y gráficos.

`_CONFIG_PROCESSING_VERSION` versiona la configuración del iframe CKAN, no los JSON de catálogo; aumentarla no sustituye esta invalidación. La corrección no cambia ese render. Ver [[Flujos Importantes]] y [[Testing]].

## Inferencia

La extensión probablemente convivió con procesos externos que consumían estos endpoints para publicar catálogos Terria. La guía `TERRIA_API_GUIDE.md` menciona un DAG de Airflow, pero ese DAG no está en este repositorio.

## Pendiente por confirmar

- topología real de despliegue actual;
- proceso actual de release y rollback;
- si Travis sigue siendo relevante o es solo legado;
- si existe un repo separado con manifests de infraestructura.
