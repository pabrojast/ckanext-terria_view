# encoding: utf-8
"""
Módulo con utilidades para manejo de recursos.
"""
import json
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Tuple, Any
from ckan.lib import uploader
from ckan.plugins import toolkit


class ResourceUtils:
    """Utilidades para manejo de recursos."""
    
    def __init__(self, config_manager):
        """
        Inicializa las utilidades de recursos.
        
        Args:
            config_manager: Instancia del gestor de configuraciones
        """
        self.config_manager = config_manager
    
    def get_sld_files_from_dataset(self, site_url: str, package_id: str) -> List[Dict]:
        """
        Obtiene archivos SLD de un dataset usando la API de CKAN.
        
        Args:
            site_url: URL base del sitio CKAN
            package_id: ID del paquete/dataset
            
        Returns:
            Lista de diccionarios con información de archivos SLD
        """
        try:
            # Construir la URL de la API
            api_url = f"{site_url.rstrip('/')}/api/3/action/package_show?id={package_id}"
            
            # Make the API request
            with urllib.request.urlopen(api_url) as response:
                data = json.loads(response.read().decode('utf-8'))
            
            if data.get('success') and data.get('result'):
                package_data = data['result']
                sld_files = []
                resources = package_data.get('resources', [])
                
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
                
                return sld_files
            else:
                return []
        except Exception as e:
            print(f"Error obteniendo archivos SLD desde la API: {e}")
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
        
        # Check if it's a valid domain and accepted format
        if self.config_manager.is_valid_domain(resource_url):
            if self.config_manager.is_accepted_format(resource):
                # Fix para datasets privados
                if user_context['user'] and package.get("private") == True:
                    upload = uploader.get_resource_uploader(resource)
                    uploaded_url = upload.get_url_from_filename(resource['id'], resource_url)
                else:
                    uploaded_url = resource_url
            else:
                uploaded_url = resource_url
        else:
            uploaded_url = resource_url
        
        return uploaded_url
    
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
                    with urllib.request.urlopen(gist_url) as response:
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