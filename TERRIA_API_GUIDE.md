# Terria JSON API Guide - On-Demand Implementation

## Overview

This implementation replaces the previous hourly Terria JSON generation system with an on-demand system featuring intelligent caching. Users now have automatic access to the latest version without duplicating SLD code between the DAG and CKAN plugin.

## Architecture

### Main Components

1. **Cache Manager** (`cache_manager.py`) - Cache management with automatic invalidation
2. **File Cache Manager** (`file_cache_manager.py`) - File-based caching for pre-generated JSONs
3. **Terria JSON Generator** (`terria_json_generator.py`) - JSON configuration generation
4. **API Endpoints** (`api_endpoints.py`) - REST endpoints for on-demand access
5. **Updated Plugin** (`plugin.py`) - Integration with cache invalidation hooks
6. **Refactored DAG** (`terria_catalog_updater_v2.py`) - Uses endpoints instead of duplicating code

### Intelligent Caching System

- **Content-based**: Cache is automatically invalidated when data changes
- **Multi-level**: Cache by dataset, organization, tag, and full catalog
- **Multiple views consideration**: Includes changes in `custom_config`, `style`, and other view properties
- **Automatic invalidation**: Triggered when Terria views are created, updated, or deleted
- **File-based pre-generation**: Large JSONs are pre-generated and served as files for better performance
- **Private/Draft filtering**: Only public and active datasets are included in generated JSONs

## API Endpoints

### Base URL
```
https://ihp-wins.unesco.org/api/terria/
```

### Available Endpoints

#### 1. Specific Dataset
```
GET /api/terria/dataset/{dataset_id}
GET /api/terria/file/dataset/{dataset_id}  # Optimized version with file
```

**Parameters:**
- `view_index` (optional): Specific view index (0, 1, 2...)

**Examples:**
```bash
# All views of the dataset (JSON response)
curl "https://ihp-wins.unesco.org/api/terria/dataset/my-dataset-id"

# Specific view (index 1, JSON response)
curl "https://ihp-wins.unesco.org/api/terria/dataset/my-dataset-id?view_index=1"

# Optimized version with pre-generated file
curl "https://ihp-wins.unesco.org/api/terria/file/dataset/my-dataset-id"
```

#### 2. Organization
```
GET /api/terria/organization/{org_name}
GET /api/terria/file/organization/{org_name}  # Optimized version with file
```

**Example:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/organization/unesco"
curl "https://ihp-wins.unesco.org/api/terria/file/organization/unesco"
```

#### 3. Tag
```
GET /api/terria/tag/{tag_name}
```

**Example:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/tag/groundwater"
```

#### 4. Full Catalog
```
GET /api/terria/full
GET /api/terria/file/full  # Optimized version with file
GET /ihp-wins.json        # Compatibility endpoint
```

**Examples:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/full"
curl "https://ihp-wins.unesco.org/api/terria/file/full"
curl "https://ihp-wins.unesco.org/ihp-wins.json"
```

#### 5. Modular Catalog
```
GET /api/terria/modular
```

**Example:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/modular"
```

#### 6. Resource Views Information
```
GET /api/terria/resource/{resource_id}/views
```

**Example:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/resource/my-resource-id/views"
```

**Response example:**
```json
{
  "resource_id": "my-resource-id",
  "resource_name": "Sample Dataset",
  "resource_format": "shp",
  "total_views": 2,
  "views": [
    {
      "view_index": 0,
      "view_id": "view-123",
      "title": "Default View",
      "description": "",
      "custom_config": "",
      "style": "https://example.com/style.sld",
      "json_url": "/api/terria/dataset/dataset-id?view_index=0"
    },
    {
      "view_index": 1,
      "view_id": "view-124",
      "title": "Themed View",
      "custom_config": "https://example.com#start=config",
      "style": "NA",
      "json_url": "/api/terria/dataset/dataset-id?view_index=1"
    }
  ]
}
```

#### 7. Cache Statistics
```
GET /api/terria/cache/stats
```

**Response example:**
```json
{
  "cache_directory": "/path/to/cache",
  "total_files": 45,
  "valid_files": 40,
  "expired_files": 5,
  "total_size_mb": 12.5,
  "cache_timeout": 3600
}
```

#### 8. Cache Management
```
POST /api/terria/cache/invalidate
POST /api/terria/cache/cleanup
```

**Optional parameters for invalidate:**
- `type`: Cache type (dataset, organization, tag, full)
- `id`: Specific identifier

**Examples:**
```bash
# Invalidate all cache
curl -X POST "https://ihp-wins.unesco.org/api/terria/cache/invalidate"

# Invalidate specific organization cache
curl -X POST "https://ihp-wins.unesco.org/api/terria/cache/invalidate?type=organization&id=unesco"

# Clean up expired cache files
curl -X POST "https://ihp-wins.unesco.org/api/terria/cache/cleanup"
```

## Manejo de Múltiples Vistas

### Comportamiento por Defecto

Cuando un recurso tiene múltiples vistas de Terria:

1. **Sin `view_index`**: Retorna todas las vistas como elementos separados
2. **Con `view_index`**: Retorna solo la vista especificada
3. **Nombres diferenciados**: Las vistas múltiples incluyen el nombre de la vista: "Recurso - Nombre Vista"
4. **IDs únicos**: Cada vista tiene un ID único: `{resource_id}-{view_index}`

### Ejemplo de Respuesta con Múltiples Vistas

```json
{
  "catalog": [{
    "name": "Dataset Ejemplo",
    "type": "group",
    "members": [
      {
        "name": "Mapa Base - Vista Predeterminada",
        "id": "resource-123-0",
        "type": "shp",
        "url": "...",
        "styles": [...],
        "legends": [...]
      },
      {
        "name": "Mapa Base - Vista Temática",
        "id": "resource-123-1", 
        "type": "shp",
        "url": "...",
        "styles": [...],
        "legends": [...]
      }
    ]
  }]
}
```

## Invalidación Automática de Caché

### Eventos que Disparan Invalidación

1. **Creación de Vista de Terria**: Invalida caché del recurso y dependencias
2. **Actualización de Vista**: Invalida cuando cambia `custom_config`, `style`, `title`, etc.
3. **Eliminación de Vista**: Limpia caché relacionado
4. **Actualización de Dataset**: Detectado por `metadata_modified`
5. **Cambio de Recursos**: Detectado por `last_modified` del recurso

### Alcance de Invalidación

Cuando se actualiza un recurso, se invalida:
- ✅ Caché del dataset específico (todas las variantes de vista)
- ✅ Caché de la organización que contiene el dataset
- ✅ Caché del catálogo completo
- ✅ Caché de todos los tags asociados al dataset

## Migración del DAG Anterior

### Cambios Principales

1. **Eliminación de código SLD duplicado**
2. **Uso de endpoints de API en lugar de procesamiento directo**
3. **Invalidación de caché al inicio para forzar regeneración**
4. **Simplificación de lógica de upload**

### Comparación

| Aspecto | DAG Anterior | DAG Nuevo |
|---------|--------------|-----------|
| Procesamiento SLD | Duplicado en DAG | Reutiliza plugin CKAN |
| Tiempo de ejecución | ~45-60 min | ~10-15 min |
| Mantenimiento | Código duplicado | Código centralizado |
| Caché | No | Sí, inteligente |
| Múltiples vistas | Limitado | Completo |
| Detección de cambios | Por tiempo | Por contenido |

## Testing

### 1. Testing de Endpoints

#### Verificar que los endpoints respondan:
```bash
# Test básico de conectividad
curl -I "https://ihp-wins.unesco.org/api/terria/cache/stats"

# Test de dataset específico (reemplazar con ID real)
curl "https://ihp-wins.unesco.org/api/terria/dataset/DATASET_ID_AQUI" | jq '.catalog[0].members | length'

# Test de organización (reemplazar con nombre real)
curl "https://ihp-wins.unesco.org/api/terria/organization/ORG_NAME_AQUI" | jq '.catalog[0].name'
```

#### Verificar múltiples vistas:
```bash
# Buscar un recurso con múltiples vistas
curl "https://ihp-wins.unesco.org/api/terria/dataset/DATASET_ID?view_index=0" > vista0.json
curl "https://ihp-wins.unesco.org/api/terria/dataset/DATASET_ID?view_index=1" > vista1.json

# Comparar diferencias
diff vista0.json vista1.json
```

### 2. Testing de Caché

#### Verificar invalidación automática:
```bash
# 1. Obtener estadísticas iniciales
curl "https://ihp-wins.unesco.org/api/terria/cache/stats"

# 2. Hacer una request para crear caché
curl "https://ihp-wins.unesco.org/api/terria/full" > /dev/null

# 3. Verificar que aumentó el caché
curl "https://ihp-wins.unesco.org/api/terria/cache/stats"

# 4. Invalidar caché manualmente
curl -X POST "https://ihp-wins.unesco.org/api/terria/cache/invalidate"

# 5. Verificar que el caché se limpió
curl "https://ihp-wins.unesco.org/api/terria/cache/stats"
```

### 3. Testing de Integración con CKAN

#### Verificar que los cambios de vista invaliden caché:
1. Editar una vista de Terria desde la interfaz CKAN
2. Cambiar el `custom_config` o `style`
3. Guardar los cambios
4. Verificar que el endpoint del dataset retorne la nueva configuración inmediatamente

### 4. Testing del DAG

#### Ejecutar manualmente:
```python
# En Airflow UI o consola
from dags.terria_catalog_updater_v2 import *

# Test individual de funciones
generate_and_upload_organization_catalogs()
generate_and_upload_tag_catalogs()  
generate_and_upload_full_catalog()
```

## Monitoreo y Debugging

### Variables de Entorno

```bash
# Activar debug en CKAN
export TERRIA_DEBUG=true
```

### Logs Importantes

1. **CKAN logs**: Mostrarán debug de procesamiento SLD y caché
2. **Airflow logs**: Progreso del DAG y errores de API
3. **Network logs**: Requests HTTP entre DAG y endpoints

### Métricas a Monitorear

- **Hit rate de caché**: `valid_entries / total_requests`
- **Tiempo de respuesta de endpoints**
- **Tiempo de ejecución del DAG** (debería ser < 15 min)
- **Errores de invalidación de caché**

## Troubleshooting

### Issue: Import errors with urllib3/requests
**Solution:** The implementation includes compatibility fixes for different urllib3 versions. If you still see import errors:
1. Check urllib3 version: `pip show urllib3`
2. For very old versions (<1.15), consider upgrading: `pip install "urllib3>=1.15"`
3. The code automatically falls back to `method_whitelist` for older versions

### Issue: Cache not invalidating automatically
**Solution:** Verify that the `after_create`, `after_update`, `after_delete` hooks are working in the plugin.

### Issue: Multiple views not appearing
**Solution:** Verify that `resource_view_list` returns all `terria_view` views for the resource.

### Issue: Slow endpoint performance
**Solution:** Check cache statistics and consider increasing `cache_timeout`.

### Issue: DAG fails with timeouts
**Solution:** Increase `TIMEOUT_SECONDS` and verify network connectivity.

### Issue: Malformed JSON
**Solution:** Verify that `convert_sets_to_lists` is being applied before serialization.

### Issue: Private datasets appearing in results
**Solution:** The implementation filters for `state:active` and `private:false`. If private datasets still appear, check the CKAN search query filters.

### Issue: File cache growing too large
**Solution:** Use the cleanup endpoint regularly: `POST /api/terria/cache/cleanup` or adjust `cache_timeout` in `FileCacheManager.__init__()`.

## Production Configuration

### Required Airflow Variables
- `APIDEV`: CKAN API token with write permissions

### CKAN Environment Variables
- `TERRIA_DEBUG`: `false` (in production)

### Cache Configuration
- Default timeout: 1 hour (3600 seconds)
- Adjustable in `CacheManager.__init__()` and `FileCacheManager.__init__()` if needed
- File cache directory: Uses CKAN's `ckan.storage_path` or system temp directory

### Recommended Monitoring
- Alerts if DAG takes > 20 minutes
- Alerts if cache hit rate < 70%
- Alerts if endpoints return 5XX errors
- Monitor file cache size and cleanup regularly
- Track endpoint response times

### Performance Optimization
- Use file-based endpoints (`/api/terria/file/*`) for large responses
- Consider increasing cache timeout for stable datasets
- Pre-generate commonly requested catalogs during low-traffic periods
- Monitor and cleanup expired cache files regularly