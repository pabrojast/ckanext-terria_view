# Guía de la API de Terria JSON - Implementación On-Demand

## Resumen

Esta implementación reemplaza el sistema anterior de generación de JSON de Terria cada hora por un sistema on-demand con caché inteligente. Los usuarios ahora tienen acceso automático a la versión más actualizada sin duplicar código SLD entre el DAG y el plugin CKAN.

## Arquitectura

### Componentes Principales

1. **Cache Manager** (`cache_manager.py`) - Gestión de caché con invalidación automática
2. **Terria JSON Generator** (`terria_json_generator.py`) - Generación de configuraciones JSON
3. **API Endpoints** (`api_endpoints.py`) - Endpoints REST para acceso on-demand
4. **Plugin actualizado** (`plugin.py`) - Integración con hooks de invalidación de caché
5. **DAG refactorizado** (`terria_catalog_updater_v2.py`) - Usa endpoints en lugar de duplicar código

### Sistema de Caché Inteligente

- **Basado en contenido**: El caché se invalida automáticamente cuando cambian los datos
- **Multi-nivel**: Caché por dataset, organización, tag y catálogo completo
- **Consideración de vistas múltiples**: Incluye cambios en `custom_config`, `style`, y otras propiedades de vista
- **Invalidación automática**: Se activa cuando se crean, actualizan o eliminan vistas de Terria

## Endpoints de la API

### Base URL
```
https://ihp-wins.unesco.org/api/terria/
```

### Endpoints Disponibles

#### 1. Dataset Específico
```
GET /api/terria/dataset/{dataset_id}
```

**Parámetros:**
- `view_index` (opcional): Índice de vista específica (0, 1, 2...)

**Ejemplos:**
```bash
# Todas las vistas del dataset
curl "https://ihp-wins.unesco.org/api/terria/dataset/my-dataset-id"

# Vista específica (índice 1)
curl "https://ihp-wins.unesco.org/api/terria/dataset/my-dataset-id?view_index=1"
```

#### 2. Organización
```
GET /api/terria/organization/{org_name}
```

**Ejemplo:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/organization/unesco"
```

#### 3. Tag
```
GET /api/terria/tag/{tag_name}
```

**Ejemplo:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/tag/groundwater"
```

#### 4. Catálogo Completo
```
GET /api/terria/full
```

**Ejemplo:**
```bash
curl "https://ihp-wins.unesco.org/api/terria/full"
```

#### 5. Estadísticas de Caché
```
GET /api/terria/cache/stats
```

**Respuesta ejemplo:**
```json
{
  "total_entries": 25,
  "valid_entries": 23,
  "expired_entries": 2,
  "cache_timeout": 3600
}
```

#### 6. Invalidación de Caché
```
POST /api/terria/cache/invalidate
```

**Parámetros opcionales:**
- `type`: Tipo de caché (dataset, organization, tag, full)
- `id`: Identificador específico

**Ejemplos:**
```bash
# Invalidar todo el caché
curl -X POST "https://ihp-wins.unesco.org/api/terria/cache/invalidate"

# Invalidar caché de organización específica
curl -X POST "https://ihp-wins.unesco.org/api/terria/cache/invalidate?type=organization&id=unesco"
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

### Problema: Caché no se invalida automáticamente
**Solución:** Verificar que los hooks `after_create`, `after_update`, `after_delete` estén funcionando en el plugin.

### Problema: Múltiples vistas no aparecen
**Solución:** Verificar que `resource_view_list` retorne todas las vistas `terria_view` para el recurso.

### Problema: Performance lenta en endpoints
**Solución:** Verificar estadísticas de caché y considerar aumentar `cache_timeout`.

### Problema: DAG falla con timeouts
**Solución:** Incrementar `TIMEOUT_SECONDS` y verificar conectividad de red.

### Problema: JSON malformado
**Solución:** Verificar que `convert_sets_to_lists` se esté aplicando antes de serializar.

## Configuración de Producción

### Variables de Airflow Requeridas
- `APIDEV`: Token de API de CKAN con permisos de escritura

### Variables de Entorno CKAN
- `TERRIA_DEBUG`: `false` (en producción)

### Configuración de Cache
- Timeout por defecto: 1 hora (3600 segundos)
- Ajustable en `CacheManager.__init__()` si es necesario

### Monitoring Recomendado
- Alertas si el DAG tarda > 20 minutos
- Alertas si el cache hit rate < 70%
- Alertas si los endpoints retornan errores 5XX