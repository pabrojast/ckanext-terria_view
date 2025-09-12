# Cache Preload Configuration

El sistema de pre-carga de caché se ejecuta automáticamente cuando el pod arranca, pero puede ser configurado mediante variables de entorno y configuración de CKAN.

## Variables de Entorno

### TERRIA_PRELOAD_CACHE
Controla si la pre-carga está habilitada.

```bash
# Habilitar pre-carga (por defecto: true)
export TERRIA_PRELOAD_CACHE=true

# Deshabilitar pre-carga
export TERRIA_PRELOAD_CACHE=false
```

### TERRIA_PRELOAD_DELAY
Tiempo de espera en segundos antes de iniciar la pre-carga después del arranque.

```bash
# Esperar 10 segundos después del arranque (por defecto)
export TERRIA_PRELOAD_DELAY=10

# Esperar 30 segundos (útil para pods lentos en arrancar)
export TERRIA_PRELOAD_DELAY=30

# Empezar inmediatamente
export TERRIA_PRELOAD_DELAY=0
```

### TERRIA_DEBUG
Habilita logs detallados de la pre-carga.

```bash
# Ver logs de pre-carga
export TERRIA_DEBUG=true
```

## Configuración en CKAN

También puedes configurar la pre-carga en el archivo de configuración de CKAN:

```ini
# En ckan.ini o development.ini

# Habilitar/deshabilitar pre-carga
ckanext.terria_view.preload_cache = true

# Tiempo de espera en segundos
ckanext.terria_view.preload_delay = 10
```

## Comportamiento de la Pre-carga

La pre-carga sigue esta secuencia:

1. **Catálogo modular** (más ligero, respuesta rápida)
2. **Organizaciones** (top 5 con más datasets)
3. **Datasets populares** (10 más recientes/modificados)
4. **Tags populares** (top 5 con más datasets)
5. **Catálogo completo** (más pesado, al final)

## Logs de Pre-carga

Cuando `TERRIA_DEBUG=true`, verás logs como:

```
CachePreloader: Starting cache preloading in 10 seconds
CachePreloader: Starting cache preloading...
CachePreloader: Preloading modular_catalog...
CachePreloader: Completed modular_catalog (1/5)
CachePreloader: Preloading organizations...
CachePreloader: Preloaded organization: unesco
CachePreloader: Preloaded organization: example-org
CachePreloader: Preloaded 2 organization catalogs
CachePreloader: Completed organizations (2/5)
CachePreloader: Preloading popular_datasets...
CachePreloader: Preloaded dataset: example-dataset-1
CachePreloader: Preloaded 10 popular datasets
CachePreloader: Completed popular_datasets (3/5)
CachePreloader: Preloading tags...
CachePreloader: Preloaded tag: groundwater
CachePreloader: Preloaded 5 tag catalogs
CachePreloader: Completed tags (4/5)
CachePreloader: Preloading full_catalog...
CachePreloader: Starting full catalog preload (this may take a while)...
CachePreloader: Preloaded full catalog with 150 entries (with file cache)
CachePreloader: Completed full_catalog (5/5)
CachePreloader: Cache preloading completed in 45.32 seconds (5/5 tasks)
```

## Configuración Recomendada por Entorno

### Desarrollo
```bash
export TERRIA_PRELOAD_CACHE=true
export TERRIA_PRELOAD_DELAY=5
export TERRIA_DEBUG=true
```

### Staging
```bash
export TERRIA_PRELOAD_CACHE=true
export TERRIA_PRELOAD_DELAY=10
export TERRIA_DEBUG=false
```

### Producción
```bash
export TERRIA_PRELOAD_CACHE=true
export TERRIA_PRELOAD_DELAY=15
export TERRIA_DEBUG=false
```

## Verificación

Para verificar que la pre-carga funciona:

1. **Revisar estadísticas de caché**:
```bash
curl "https://your-site.com/api/terria/cache/stats"
```

2. **Verificar respuesta rápida** de endpoints:
```bash
# Debería responder en < 1 segundo si está pre-cargado
time curl "https://your-site.com/api/terria/modular"
```

3. **Revisar logs del pod** para mensajes de pre-carga.

## Troubleshooting

### Pre-carga no se ejecuta
- Verificar que `TERRIA_PRELOAD_CACHE=true`
- Revisar logs del pod para errores de inicialización
- Verificar que el plugin se carga correctamente

### Pre-carga muy lenta
- Aumentar `TERRIA_PRELOAD_DELAY` para dar más tiempo al sistema
- Verificar que no hay problemas de red o base de datos
- Considerar deshabilitar temporalmente si afecta el arranque

### Errores en pre-carga
- Los errores en pre-carga no afectan el funcionamiento normal
- La pre-carga continúa con otras tareas aunque una falle
- Revisar logs con `TERRIA_DEBUG=true` para detalles

### Pre-carga consume mucha memoria
- La pre-carga usa memoria adicional temporalmente
- El caché tiene límites automáticos y limpieza
- Considerar ajustar el retraso para momentos de menor carga