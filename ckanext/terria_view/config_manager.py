# encoding: utf-8
"""
Module for managing Terria View plugin configurations.
"""
import os
import re
from typing import Dict, List, Optional, Union


class ConfigManager:
    """Manages Terria View plugin configurations."""
    
    # Formats supported by the plugin
    SUPPORTED_FORMATS = [
        'shp', 'wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 
        'csv-geo-*', 'wmts', 'tif', 'tiff', 'geotiff', 'csv', 'json'
    ]
    
    # Filter expression for searches
    SUPPORTED_FILTER_EXPR = 'fq=(' + ' OR '.join(['res_format:' + s for s in SUPPORTED_FORMATS]) + ')'
    
    # Regex to validate formats
    SUPPORTED_FORMATS_REGEX = '^(' + '|'.join([s.replace('*', '.*') for s in SUPPORTED_FORMATS]) + ')$'
    
    # Valid URLs and domains
    VALID_DOMAINS = [
        'https://data.dev-wins.com',
        'https://ihp-wins.unesco.org/'
    ]
    
    def __init__(self, site_url: str = '', default_title: str = 'Terria Viewer', 
                 default_instance_url: str = 'https://ihp-wins.unesco.org/terria/'):
        """
        Initialize the configuration manager.
        
        Args:
            site_url: Base URL of the CKAN site
            default_title: Default title for views
            default_instance_url: Default URL of the Terria instance
        """
        self.site_url = site_url
        self.default_title = default_title
        self.default_instance_url = default_instance_url
    
    def can_view_resource(self, resource: Dict) -> bool:
        """
        Determine if a resource can be visualized by the plugin.
        
        Args:
            resource: Dictionary with resource data
            
        Returns:
            True si el recurso puede ser visualizado, False en caso contrario
        """
        format_ = resource.get('format', '')
        if format_ == '':
            format_ = os.path.splitext(resource['url'])[1][1:]
        return re.match(self.SUPPORTED_FORMATS_REGEX, format_.lower()) is not None
    
    def is_valid_domain(self, url: str) -> bool:
        """
        Verifica si una URL pertenece a un dominio válido.
        
        Args:
            url: URL a verificar
            
        Returns:
            True si la URL es de un dominio válido, False en caso contrario
        """
        return any(url.startswith(domain) for domain in self.VALID_DOMAINS)
    
    def is_shp_resource(self, resource: Dict) -> bool:
        """
        Verifica si un recurso es de tipo Shapefile.
        
        Args:
            resource: Diccionario con datos del recurso
            
        Returns:
            True si es un Shapefile, False en caso contrario
        """
        return resource.get("format", "").lower() == 'shp'
    
    def is_tiff_resource(self, resource: Dict) -> bool:
        """
        Verifica si un recurso es de tipo TIFF/GeoTIFF.
        
        Args:
            resource: Diccionario con datos del recurso
            
        Returns:
            True si es un TIFF, False en caso contrario
        """
        accepted_formats = ['tif', 'tiff', 'geotiff']
        resource_format = resource.get("format", "").lower()
        return resource_format in accepted_formats
    
    def is_csv_resource(self, resource: Dict) -> bool:
        """
        Verifica si un recurso es de tipo CSV.
        
        Args:
            resource: Diccionario con datos del recurso
            
        Returns:
            True si es un CSV, False en caso contrario
        """
        accepted_formats = ['csv', 'csv-geo-*']
        resource_format = resource.get("format", "").lower()
        return any(resource_format == format for format in accepted_formats)
    
    def is_accepted_format(self, resource: Dict) -> bool:
        """
        Verifica si un recurso tiene un formato aceptado.
        
        Args:
            resource: Diccionario con datos del recurso
            
        Returns:
            True si el formato es aceptado, False en caso contrario
        """
        accepted_formats = [
            'shp', 'kml', 'geojson', 'czml', 'csv-geo-au', 
            'csv-geo-nz', 'csv-geo-us', 'WMTS', 'tif', 'tiff', 'geotiff'
        ]
        resource_format = resource.get("format", "").lower()
        return resource_format in accepted_formats
    
    def get_safe_resource_name(self, resource: Dict) -> str:
        """
        Obtiene un nombre seguro para el recurso.
        
        Args:
            resource: Diccionario con datos del recurso
            
        Returns:
            Nombre seguro del recurso
        """
        name = resource.get('name', '').strip()
        if not name or name.lower() in ['', 'none', 'null', 'undefined', 'Unnamed resource']:
            # Usar el ID del recurso o un nombre genérico
            fallback_name = resource.get('id', f"Recurso_{hash(resource.get('url', 'sin_url')) % 10000}")
            return fallback_name
        return name
    
    def clean_coordinate(self, value: Union[str, float, None], default: str) -> str:
        """
        Limpia y valida coordenadas.
        
        Args:
            value: Valor de coordenada a limpiar
            default: Valor por defecto si la coordenada no es válida
            
        Returns:
            Coordenada limpia como string
        """
        if value is None:
            return default
        cleaned_value = re.sub(r'\s+', '', str(value))
        if re.match(r'^-?\d+(\.\d+)?$', cleaned_value):
            return cleaned_value
        else:
            return default
    
    def get_schema_info(self) -> Dict:
        """
        Get plugin schema information.
        
        Returns:
            Dictionary with schema information
        """
        from ckan.plugins import toolkit
        
        ignore_missing = toolkit.get_validator('ignore_missing')
        boolean_validator = toolkit.get_validator('boolean_validator')
        default = toolkit.get_validator('default')
        
        return {
            "terria_instance_url": [ignore_missing],
            "custom_config": [ignore_missing],
            "style": [ignore_missing],
            'show_fields': [ignore_missing],
            'filterable': [default(True), boolean_validator],
            '__extras': [ignore_missing],
        } 