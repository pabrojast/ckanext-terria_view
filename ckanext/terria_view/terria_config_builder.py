# encoding: utf-8
"""
Módulo para construir configuraciones de TerriaJS.
"""
import json
import urllib.parse
from typing import Dict, List, Optional, Any


class TerriaConfigBuilder:
    """Constructor de configuraciones para TerriaJS."""
    
    def __init__(self, config_manager, sld_processor):
        """
        Inicializa el constructor de configuraciones.
        
        Args:
            config_manager: Instancia del gestor de configuraciones
            sld_processor: Instancia del procesador SLD
        """
        self.config_manager = config_manager
        self.sld_processor = sld_processor
    
    def create_base_config(self, resource_name: str, bounds: tuple) -> Dict:
        """
        Crea la configuración base para TerriaJS.
        
        Args:
            resource_name: Nombre del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            
        Returns:
            Diccionario con configuración base
        """
        ymax, xmax, ymin, xmin = bounds
        
        return {
            "version": "8.0.0",
            "initSources": [{
                "homeCamera": {
                    "north": float(ymax),
                    "east": float(xmax),
                    "south": float(ymin),
                    "west": float(xmin)
                },
                "initialCamera": {
                    "north": float(ymax),
                    "east": float(xmax),
                    "south": float(ymin),
                    "west": float(xmin)
                },
                "stratum": "user",
                "workbench": [resource_name],
                "viewerMode": "3D",
                "focusWorkbenchItems": True,
                "baseMaps": {
                    "defaultBaseMapId": "basemap-positron",
                    "previewBaseMapId": "basemap-positron"
                }
            }]
        }
    
    def create_csv_config(self, resource_name: str, resource_url: str, bounds: tuple) -> str:
        """
        Crea configuración para recursos CSV.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "csv",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "styles": [{
                "id": "default",
                "time": {
                    "spreadStartTime": True,
                    "spreadFinishTime": True
                }
            }],
            "activeStyle": "default"
        }
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_cog_config(self, resource_name: str, resource_url: str, bounds: tuple, 
                         sld_url: Optional[str] = None) -> str:
        """
        Crea configuración para recursos COG (Cloud Optimized GeoTIFF).
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "cog",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "opacity": 0.8
        }
        
        # Apply SLD styles if available
        if sld_url:
            sld_styles = self.sld_processor.process_cog_sld(sld_url)
            catalog_item.update(sld_styles)
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_shp_config(self, resource_name: str, resource_url: str, bounds: tuple, 
                         sld_url: Optional[str] = None) -> str:
        """
        Crea configuración para recursos Shapefile.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        catalog_item = {
            "name": resource_name,
            "type": "shp",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "opacity": 0.8,
            "clampToGround": False,
            "forceCesiumPrimitives": True
        }
        
        # Aplicar estilos SLD si están disponibles
        if sld_url:
            sld_styles = self.sld_processor.process_shp_sld(sld_url)
            catalog_item.update(sld_styles)
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_generic_config(self, resource_name: str, resource_url: str, 
                            resource_format: str, bounds: tuple) -> str:
        """
        Crea configuración genérica para otros tipos de recursos.
        
        Args:
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            resource_format: Formato del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            
        Returns:
            Configuración JSON como string
        """
        ymax, xmax, ymin, xmin = bounds
        
        config = f"""{{
            "version": "8.0.0",
            "initSources": [
                {{
                    "catalog": [
                        {{
                            "name": "{resource_name}",
                            "type": "group",
                            "isOpen": true,
                            "members": [
                                {{
                                    "id": "{resource_name}",
                                    "name": "{resource_name}",
                                    "type": "{resource_format.lower()}",
                                    "url": "{resource_url}",
                                    "cacheDuration": "5m",
                                    "isOpenInWorkbench": true
                                }}
                            ]
                        }}
                    ],
                    "homeCamera": {{
                        "north": {ymax},
                        "east": {xmax},
                        "south": {ymin},
                        "west": {xmin}
                    }},
                    "initialCamera": {{
                        "north": {ymax},
                        "east": {xmax},
                        "south": {ymin},
                        "west": {xmin}
                    }},
                    "stratum": "user",
                    "models": {{
                        "//{resource_name}": {{
                            "isOpen": true,
                            "knownContainerUniqueIds": [
                                "/"
                            ],
                            "type": "group"
                        }},
                        "{resource_name}": {{
                            "show": true,
                            "isOpenInWorkbench": true,
                            "knownContainerUniqueIds": [
                                "//{resource_name}"
                            ],
                            "type": "{resource_format.lower()}"
                        }},
                        "/": {{
                            "type": "group"
                        }}
                    }},
                    "workbench": [
                        "{resource_name}"
                    ],
                    "viewerMode": "3dSmooth",
                    "focusWorkbenchItems": true,
                    "baseMaps": {{
                        "defaultBaseMapId": "basemap-positron",
                        "previewBaseMapId": "basemap-positron"
                    }}
                }}
            ]
        }}"""
        
        return config
    
    def create_config_for_resource(self, resource: Dict, resource_name: str, 
                                  resource_url: str, bounds: tuple, 
                                  sld_url: Optional[str] = None) -> str:
        """
        Crea la configuración apropiada según el tipo de recurso.
        
        Args:
            resource: Diccionario con datos del recurso
            resource_name: Nombre del recurso
            resource_url: URL del recurso
            bounds: Tupla con (ymax, xmax, ymin, xmin)
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración JSON como string
        """
        resource_format = resource.get('format', '').lower()
        
        if self.config_manager.is_csv_resource(resource):
            return self.create_csv_config(resource_name, resource_url, bounds)
        elif self.config_manager.is_tiff_resource(resource):
            return self.create_cog_config(resource_name, resource_url, bounds, sld_url)
        elif self.config_manager.is_shp_resource(resource):
            return self.create_shp_config(resource_name, resource_url, bounds, sld_url)
        else:
            return self.create_generic_config(resource_name, resource_url, resource_format, bounds)
    
    def process_custom_config(self, custom_config: str, resource_url: str, 
                            resource_format: str, sld_url: Optional[str] = None) -> Optional[str]:
        """
        Procesa una configuración personalizada y actualiza URLs y estilos.
        
        Args:
            custom_config: Configuración personalizada
            resource_url: URL del recurso
            resource_format: Formato del recurso
            sld_url: URL del archivo SLD (opcional)
            
        Returns:
            Configuración procesada como string JSON, None en caso de error
        """
        try:
            # Parsear la configuración personalizada
            parsed_url = urllib.parse.urlparse(custom_config)
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
            start_data = self._decode_names_in_object(start_data)
            
            # Obtener estilos SLD si están disponibles
            sld_styles = None
            if sld_url and resource_format in ['shp', 'tif', 'tiff', 'geotiff']:
                sld_styles = self.sld_processor.process_sld_for_resource(sld_url, resource_format)
            
            # Actualizar URLs y aplicar estilos
            for init_source in start_data.get('initSources', []):
                if 'models' in init_source:
                    for model_key, model_value in init_source['models'].items():
                        if isinstance(model_value, dict) and 'url' in model_value:
                            # Actualizar la URL
                            model_value['url'] = resource_url
                            
                            # Aplicar estilos SLD si están disponibles
                            if sld_styles:
                                model_value.update(sld_styles)
            
            return json.dumps(start_data)
            
        except Exception as e:
            print(f"Error processing custom config: {e}")
            return None
    
    def _decode_names_in_object(self, obj: Any) -> Any:
        """
        Método auxiliar para decodificar nombres en objetos anidados.
        
        Args:
            obj: Objeto a procesar
            
        Returns:
            Objeto procesado con nombres decodificados
        """
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                # Decodificar el key si contiene '+'
                new_key = urllib.parse.unquote_plus(key) if '+' in key else key
                
                if isinstance(value, dict):
                    # Si hay campos específicos que contienen nombres
                    if 'name' in value:
                        value['name'] = urllib.parse.unquote_plus(value['name'])
                    if 'title' in value:
                        value['title'] = urllib.parse.unquote_plus(value['title'])
                    if 'legend' in value and isinstance(value['legend'], dict):
                        if 'title' in value['legend']:
                            value['legend']['title'] = urllib.parse.unquote_plus(value['legend']['title'])
                    
                    value = self._decode_names_in_object(value)
                elif isinstance(value, list):
                    value = [
                        urllib.parse.unquote_plus(item) if isinstance(item, str) else self._decode_names_in_object(item) 
                        for item in value
                    ]
                elif isinstance(value, str) and '+' in value:
                    value = urllib.parse.unquote_plus(value)
                    
                new_dict[new_key] = value
            return new_dict
        elif isinstance(obj, list):
            return [self._decode_names_in_object(item) for item in obj]
        return obj 