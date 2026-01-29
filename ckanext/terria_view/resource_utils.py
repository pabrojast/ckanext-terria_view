# encoding: utf-8
"""
Módulo con utilidades para manejo de recursos.
"""
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
import time
from ckan.lib import uploader
from ckan.plugins import toolkit
from .private_download import generate_token


class ResourceUtils:
    """Utilidades para manejo de recursos."""
    
    def __init__(self, config_manager):
        """
        Inicializa las utilidades de recursos.
        
        Args:
            config_manager: Instancia del gestor de configuraciones
        """
        # Cache for SLD files to avoid repeated HTTP calls
        self._sld_cache = {}
        self._sld_cache_max_age = 300  # 5 minutes cache
        self._cache_timestamps = {}
    
    def get_sld_files_from_dataset(self, site_url: str, package_id: str) -> List[Dict]:
        """
        Obtiene archivos SLD de un dataset usando la API de CKAN.
        Usa cache para evitar llamadas repetidas (5 minutos).
        Limita a máximo 5 recursos si hay más de 11.
        
        Args:
            site_url: URL base del sitio CKAN
            package_id: ID del paquete/dataset
            
        Returns:
            Lista de diccionarios con información de archivos SLD
        """
        # Check cache first
        cache_key = f"{site_url}:{package_id}"
        current_time = time.time()
        
        if cache_key in self._sld_cache:
            cache_age = current_time - self._cache_timestamps.get(cache_key, 0)
            if cache_age < self._sld_cache_max_age:
                return self._sld_cache[cache_key]
        
        try:
            # Construir la URL de la API
            api_url = f"{site_url.rstrip('/')}/api/3/action/package_show?id={package_id}"
            
            # Make the API request with timeout
            with urllib.request.urlopen(api_url, timeout=5) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            if data.get('success') and data.get('result'):
                package_data = data['result']
                sld_files = []
                resources = package_data.get('resources', [])
                
                # Limitar recursos si son más de 11 -> procesar solo 5
                if len(resources) > 11:
                    resources = resources[:5]
                
                # Buscar recursos con formato 'sld'
                for resource in resources:
                    resource_format = resource.get('format', '').lower()
                    
                    if resource_format == 'sld':
                        sld_file = {
                            'id': resource.get('id'),
                            'name': resource.get('name', 'Archivo SLD sin nombre'),
                            'url': resource.get('url'),
                            'description': resource.get('description', '')
                        }
                        sld_files.append(sld_file)
                
                # Cache the result
                self._sld_cache[cache_key] = sld_files
                self._cache_timestamps[cache_key] = current_time
                
                return sld_files
            else:
                return []
        except Exception as e:
            print(f"Error obteniendo archivos SLD desde la API: {e}")
            # Cache empty result to avoid repeated failures
            self._sld_cache[cache_key] = []
            self._cache_timestamps[cache_key] = current_time
            return []

    
    def extract_bounds_from_spatial(self, spatial: str) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Extrae coordenadas de un campo spatial en formato GeoJSON.
        
        Args:
            spatial: String con datos espaciales en formato GeoJSON
            
        Returns:
            Tupla con (ymax, xmax, ymin, xmin) como strings, None si no se pueden extraer
        """
        try:
            spatial_data = json.loads(spatial)
            if spatial_data.get("type") == "Polygon":
                coordinates = spatial_data["coordinates"][0]
                lats = [coord[1] for coord in coordinates]
                lons = [coord[0] for coord in coordinates]
                ymax = max(lats)
                ymin = min(lats)
                xmax = max(lons)
                xmin = min(lons)
                return str(ymax), str(xmax), str(ymin), str(xmin)
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
        return None, None, None, None
    
    def get_resource_bounds(self, package: Dict) -> Tuple[str, str, str, str]:
        """
        Obtiene las coordenadas de un paquete/dataset.
        
        Args:
            package: Diccionario con datos del paquete
            
        Returns:
            Tupla con (ymax, xmax, ymin, xmin) como strings
        """
        # Intentar extraer las coordenadas desde 'spatial'
        ymax_spatial, xmax_spatial, ymin_spatial, xmin_spatial = self.extract_bounds_from_spatial(
            package.get("spatial", "")
        )
        
        # Si no se pudo extraer desde 'spatial', usar valores por defecto
        ymax = self.config_manager.clean_coordinate(
            ymax_spatial if ymax_spatial else package.get("ymax"), "20"
        )
        xmax = self.config_manager.clean_coordinate(
            xmax_spatial if xmax_spatial else package.get("xmax"), "-13"
        )
        ymin = self.config_manager.clean_coordinate(
            ymin_spatial if ymin_spatial else package.get("ymin"), "-60"
        )
        xmin = self.config_manager.clean_coordinate(
            xmin_spatial if xmin_spatial else package.get("xmin"), "-108"
        )
        
        return ymax, xmax, ymin, xmin
    
    def get_resource_url(self, resource: Dict, package: Dict, user_context: Dict) -> str:
        """
        Obtiene la URL apropiada para un recurso considerando permisos y ubicación.
        
        Args:
            resource: Diccionario con datos del recurso
            package: Diccionario con datos del paquete
            user_context: Contexto del usuario
            
        Returns:
            URL del recurso
        """
        resource_url = resource.get("url", "")
        user = user_context.get("user") if user_context else None

        # Use a short-lived signed URL for private resources to avoid cross-site auth issues
        if user and package.get("private") is True:
            site_url = self.config_manager.site_url or toolkit.config.get("ckan.site_url", "")
            resource_id = resource.get("id")
            token = generate_token(resource_id, user) if resource_id else None
            if site_url and token:
                query = urllib.parse.urlencode({"token": token})
                signed_url = f"{site_url.rstrip('/')}/api/terria/resource/{resource_id}/download?{query}"
                return self.config_manager.ensure_https_url(signed_url)
        
        # Check if it's a valid domain and accepted format
        if self.config_manager.is_valid_domain(resource_url):
            if self.config_manager.is_accepted_format(resource):
                # Fix para datasets privados
                if user and package.get("private") == True:
                    upload = uploader.get_resource_uploader(resource)
                    uploaded_url = upload.get_url_from_filename(resource['id'], resource_url)
                else:
                    uploaded_url = resource_url
            else:
                uploaded_url = resource_url
        else:
            uploaded_url = resource_url
        
        return self.config_manager.ensure_https_url(uploaded_url)
    
    def decode_names_in_object(self, obj: Any) -> Any:
        """
        Decodifica nombres con caracteres especiales en objetos anidados.
        
        Args:
            obj: Objeto a procesar (dict, list, str, etc.)
            
        Returns:
            Objeto procesado con nombres decodificados
        """
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                # Decodificar el key si contiene '+'
                new_key = urllib.parse.unquote_plus(key) if '+' in key else key
                
                if isinstance(value, dict):
                    # If there are specific fields that contain names
                    if 'name' in value:
                        value['name'] = urllib.parse.unquote_plus(value['name'])
                    if 'title' in value:
                        value['title'] = urllib.parse.unquote_plus(value['title'])
                    if 'legend' in value and isinstance(value['legend'], dict):
                        if 'title' in value['legend']:
                            value['legend']['title'] = urllib.parse.unquote_plus(value['legend']['title'])
                    
                    value = self.decode_names_in_object(value)
                elif isinstance(value, list):
                    value = [
                        urllib.parse.unquote_plus(item) if isinstance(item, str) else self.decode_names_in_object(item) 
                        for item in value
                    ]
                elif isinstance(value, str) and '+' in value:
                    value = urllib.parse.unquote_plus(value)
                    
                new_dict[new_key] = value
            return new_dict
        elif isinstance(obj, list):
            return [self.decode_names_in_object(item) for item in obj]
        return obj
    
    def process_custom_config_url(self, custom_config_url: str) -> Optional[Dict]:
        """
        Procesa una URL de configuración personalizada para extraer datos.
        
        Args:
            custom_config_url: URL con configuración personalizada
            
        Returns:
            Diccionario con datos de configuración parseados, None en caso de error
        """
        try:
            # Extract the 'start' or 'share' parameter from the URL
            parsed_url = urllib.parse.urlparse(custom_config_url)
            fragment = parsed_url.fragment
            
            if fragment.startswith('share='):
                # Caso de URL con #share
                gist_id = fragment.split('=g-')[1]
                gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
                try:
                    with urllib.request.urlopen(gist_url, timeout=5) as response:
                        decoded_param = response.read().decode('utf-8')
                except Exception as e:
                    print(f"Error fetching gist config: {e}")
                    return None
            else:
                # Caso original con #start
                start_param = fragment.split('=', 1)[1]
                decoded_param = urllib.parse.unquote(start_param)
            
            # Parsear el JSON
            start_data = json.loads(decoded_param)
            
            # Decodificar nombres
            start_data = self.decode_names_in_object(start_data)
            
            return start_data
            
        except Exception as e:
            print(f"Error processing custom config: {e}")
            return None 
