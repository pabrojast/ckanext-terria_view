# Arquitectura del Plugin Terria View

## Descripción General

El plugin Terria View ha sido refactorizado para mejorar su mantenibilidad y escalabilidad. La nueva estructura separa las responsabilidades en módulos especializados, siguiendo principios de diseño limpio y separación de responsabilidades.

## Estructura Modular

### 1. `config_manager.py`
**Responsabilidad:** Gestión de configuraciones y validaciones.

**Funciones principales:**
- Validación de formatos de recursos soportados
- Gestión de URLs y dominios válidos
- Limpieza y validación de coordenadas
- Configuración del esquema del plugin

**Métodos clave:**
- `can_view_resource()`: Valida si un recurso puede ser visualizado
- `is_shp_resource()`, `is_tiff_resource()`, `is_csv_resource()`: Identifican tipos de recursos
- `get_safe_resource_name()`: Genera nombres seguros para recursos
- `clean_coordinate()`: Limpia y valida coordenadas

### 2. `sld_processor.py`
**Responsabilidad:** Procesamiento de archivos SLD (Styled Layer Descriptor).

**Funciones principales:**
- Descarga y parseo de archivos SLD
- Extracción de información de estilos para diferentes tipos de recursos
- Conversión de estilos a formato compatible con TerriaJS

**Métodos clave:**
- `process_cog_sld()`: Procesa SLD para recursos COG (GeoTIFF)
- `process_shp_sld()`: Procesa SLD para recursos Shapefile
- `process_sld_for_resource()`: Procesamiento genérico según tipo de recurso

### 3. `resource_utils.py`
**Responsabilidad:** Utilidades para manejo de recursos.

**Funciones principales:**
- Obtención de archivos SLD desde datasets
- Procesamiento de información espacial
- Gestión de URLs de recursos considerando permisos
- Decodificación de nombres con caracteres especiales

**Métodos clave:**
- `get_sld_files_from_dataset()`: Obtiene archivos SLD de un dataset
- `extract_bounds_from_spatial()`: Extrae coordenadas de datos espaciales
- `get_resource_url()`: Obtiene URL apropiada considerando permisos
- `process_custom_config_url()`: Procesa URLs de configuración personalizada

### 4. `terria_config_builder.py`
**Responsabilidad:** Construcción de configuraciones TerriaJS.

**Funciones principales:**
- Creación de configuraciones específicas por tipo de recurso
- Procesamiento de configuraciones personalizadas
- Aplicación de estilos SLD a configuraciones

**Métodos clave:**
- `create_csv_config()`: Configuración para recursos CSV
- `create_cog_config()`: Configuración para recursos COG
- `create_shp_config()`: Configuración para recursos Shapefile
- `create_config_for_resource()`: Creación automática según tipo
- `process_custom_config()`: Procesamiento de configuraciones personalizadas

### 5. `plugin.py` (Refactorizado)
**Responsabilidad:** Orquestación y interface con CKAN.

**Funciones principales:**
- Implementación de interfaces de CKAN
- Coordinación entre módulos
- Gestión de templates y helpers
- Configuración del plugin

## Beneficios de la Nueva Estructura

### 1. **Separación de Responsabilidades**
- Cada módulo tiene una responsabilidad específica y bien definida
- Facilita el mantenimiento y testing individual de componentes
- Reduce el acoplamiento entre funcionalidades

### 2. **Mantenibilidad Mejorada**
- Código más legible y comprensible
- Funciones más pequeñas y enfocadas
- Documentación clara con type hints
- Manejo consistente de errores

### 3. **Escalabilidad**
- Fácil agregar nuevos tipos de recursos
- Extensión simple de procesadores SLD
- Configuraciones modulares para diferentes casos de uso

### 4. **Testing**
- Cada módulo puede ser testeado independientemente
- Mocking más simple para pruebas unitarias
- Separación clara entre lógica de negocio y framework

## Flujo de Procesamiento

1. **Inicialización**: `plugin.py` inicializa todos los módulos
2. **Validación**: `config_manager` valida si el recurso puede ser visualizado
3. **Procesamiento de Recursos**: `resource_utils` obtiene información del recurso
4. **Procesamiento SLD**: `sld_processor` extrae estilos si están disponibles
5. **Construcción de Configuración**: `terria_config_builder` genera la configuración TerriaJS
6. **Renderizado**: `plugin.py` pasa la configuración al template

## Compatibilidad

La refactorización mantiene **100% de compatibilidad** con:
- Todas las funcionalidades existentes
- APIs y interfaces de CKAN
- Templates y configuraciones actuales
- Formatos de recursos soportados

## Extensibilidad

### Agregar Nuevo Formato de Recurso

1. Actualizar `SUPPORTED_FORMATS` en `config_manager.py`
2. Agregar método de validación `is_nuevo_formato_resource()`
3. Crear método de configuración en `terria_config_builder.py`
4. Opcional: Agregar procesamiento SLD específico

### Agregar Nuevo Procesador SLD

1. Agregar método `process_nuevo_formato_sld()` en `sld_processor.py`
2. Actualizar `process_sld_for_resource()` para incluir el nuevo formato
3. Opcional: Agregar namespace XML si es necesario

### Personalizar Configuraciones

1. Extender `terria_config_builder.py` con nuevos métodos
2. Agregar configuración en `config_manager.py` si es necesaria
3. Actualizar schema en `get_schema_info()` si se agregan nuevos campos

## Mejores Prácticas para Mantenimiento con IA

1. **Documentación Clara**: Cada función incluye docstrings descriptivos
2. **Type Hints**: Uso consistente de type hints para mejor comprensión
3. **Separación de Concerns**: Cada módulo tiene una responsabilidad específica
4. **Manejo de Errores**: Logging consistente y manejo de excepciones
5. **Naming Conventions**: Nombres descriptivos y consistentes
6. **Modularidad**: Funciones pequeñas y enfocadas en una tarea específica

## Migración y Deployment

La refactorización no requiere cambios en:
- Configuración de CKAN
- Templates existentes
- Base de datos
- Archivos de configuración del plugin

El deployment es directo: reemplazar los archivos y reiniciar CKAN. 