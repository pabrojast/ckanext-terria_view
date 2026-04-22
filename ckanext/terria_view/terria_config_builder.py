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
    
    def _debug_print(self, message: str):
        """
        Print debug messages only when TERRIA_DEBUG environment variable is set to 'true'.
        
        Args:
            message: Debug message to print
        """
        import os
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(message)
    
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
            # "forceCesiumPrimitives": True,  # Removed - causes issues with GeoJSON conversion to Cesium primitives
            "enableManualRegionMapping": False  # Ensure we use point/feature rendering
        }
        
        # Apply SLD styles if available
        if sld_url:
            self._debug_print(f"Processing SLD for shapefile: {sld_url}")
            sld_styles = self.sld_processor.process_shp_sld(sld_url)
            self._debug_print(f"SLD processing result: {sld_styles}")
            
            if sld_styles:
                # Apply all SLD style properties
                for key, value in sld_styles.items():
                    catalog_item[key] = value
                    self._debug_print(f"Applied SLD property {key}: {value}")
        
        config_dict = self.create_base_config(resource_name, bounds)
        config_dict["initSources"][0]["catalog"] = [catalog_item]
        
        return json.dumps(config_dict)
    
    def create_geojson_config(self, resource_name: str, resource_url: str, bounds: tuple,
                              sld_url: Optional[str] = None) -> str:
        """
        Crea configuración para recursos GeoJSON.
        
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
            "type": "geojson",
            "id": resource_name,
            "url": resource_url,
            "cacheDuration": "5m",
            "isOpenInWorkbench": True,
            "opacity": 0.8,
            "clampToGround": False,
            "enableManualRegionMapping": False
        }
        
        # Apply SLD styles if available (same vector styling as SHP)
        if sld_url:
            self._debug_print(f"Processing SLD for geojson: {sld_url}")
            sld_styles = self.sld_processor.process_shp_sld(sld_url)
            self._debug_print(f"SLD processing result: {sld_styles}")
            
            if sld_styles:
                for key, value in sld_styles.items():
                    catalog_item[key] = value
                    self._debug_print(f"Applied SLD property {key}: {value}")
        
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
        elif self.config_manager.is_geojson_resource(resource):
            return self.create_geojson_config(resource_name, resource_url, bounds, sld_url)
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
            # Parse custom configuration
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
                    self._debug_print(f"Error fetching gist config: {e}")
                    return None
            else:
                # Caso original con #start
                start_param = fragment.split('=', 1)[1]
                decoded_param = urllib.parse.unquote(start_param)
            
            # Parsear el JSON
            start_data = json.loads(decoded_param)
            
            # Decode names
            start_data = self._decode_names_in_object(start_data)
            
            # Get SLD styles if available
            sld_styles = None
            if sld_url and resource_format in ['shp', 'geojson', 'tif', 'tiff', 'geotiff', 'cog']:
                self._debug_print(f"Processing SLD for resource format: {resource_format}")
                sld_styles = self.sld_processor.process_sld_for_resource(sld_url, resource_format)
                self._debug_print(f"SLD styles result: {sld_styles}")
            
            # Strip orphaned group models (e.g. built-in catalog groups like
            # "//IHP-WINS") that were captured in the saved Terria state but
            # already exist in the Terria instance, causing duplicates.
            for init_source in start_data.get('initSources', []):
                if 'models' in init_source:
                    original_keys = set(init_source['models'].keys())
                    init_source['models'] = self._strip_orphaned_group_models(
                        init_source['models']
                    )
                    stripped_keys = original_keys - set(init_source['models'].keys())

                    # Remove previewedItemId when it references a stripped model
                    if stripped_keys and init_source.get('previewedItemId') in stripped_keys:
                        self._debug_print(
                            f"Removing previewedItemId '{init_source['previewedItemId']}' "
                            f"(references stripped model)"
                        )
                        del init_source['previewedItemId']
            
            # Update URLs and apply styles
            for init_source in start_data.get('initSources', []):
                if 'models' in init_source:
                    updated_model_ids = []
                    for model_key, model_value in init_source['models'].items():
                        if isinstance(model_value, dict) and 'url' in model_value:
                            # Actualizar la URL
                            model_value['url'] = resource_url
                            model_value.setdefault('isOpenInWorkbench', True)
                            model_value.setdefault('show', True)
                            self._debug_print(f"Updated URL for model {model_key}: {resource_url}")
                            updated_model_ids.append(model_key)
                            
                            # Apply SLD styles if available
                            if sld_styles and resource_format.lower() in ['shp', 'geojson', 'tif', 'tiff', 'geotiff', 'cog']:
                                self._debug_print(f"Applying SLD styles to model {model_key}")
                                # Always apply legends if available
                                if 'legends' in sld_styles:
                                    model_value['legends'] = sld_styles['legends']
                                    self._debug_print(f"Applied legends to model {model_key}")
                                
                                # Apply styles for SHP/GeoJSON resources
                                if resource_format.lower() in ['shp', 'geojson'] and 'styles' in sld_styles:
                                    model_value['styles'] = sld_styles['styles']
                                    if 'activeStyle' in sld_styles:
                                        model_value['activeStyle'] = sld_styles['activeStyle']
                                    # if 'forceCesiumPrimitives' in sld_styles:
                                    #     model_value['forceCesiumPrimitives'] = sld_styles['forceCesiumPrimitives']
                                    self._debug_print(f"Applied styles to model {model_key}: {sld_styles['styles']}")
                                    self._debug_print(f"Applied activeStyle: {sld_styles.get('activeStyle')}")
                                    # print(f"Applied forceCesiumPrimitives: {sld_styles.get('forceCesiumPrimitives')}")
                                    
                                # Apply renderOptions for COG resources
                                elif resource_format.lower() in ['tif', 'tiff', 'geotiff', 'cog'] and 'renderOptions' in sld_styles:
                                    model_value['renderOptions'] = sld_styles['renderOptions']
                                    self._debug_print(f"Applied renderOptions to model {model_key}")
                            self._sanitize_model_styles(model_value)

                    # Ensure data items are visible on map by default
                    # (saved share links may sometimes have an empty workbench list)
                    if updated_model_ids:
                        workbench = init_source.get('workbench')
                        if not isinstance(workbench, list):
                            workbench = []
                        for model_id in updated_model_ids:
                            if model_id not in workbench:
                                workbench.append(model_id)
                        init_source['workbench'] = workbench
            
            return json.dumps(start_data)
            
        except Exception as e:
            self._debug_print(f"Error processing custom config: {e}")
            return None

    def _sanitize_model_styles(self, model_value: Dict) -> None:
        """
        Normalize table style blocks to avoid Terria parse/runtime errors.

        Some saved custom configs contain partial style definitions
        (for example enumColors without mapType/colorColumn). This method
        fills safe defaults when they can be inferred.
        """
        styles = model_value.get('styles')
        if not isinstance(styles, list):
            return

        style_ids = []
        for style in styles:
            if not isinstance(style, dict):
                continue
            style_id = style.get('id')
            if isinstance(style_id, str):
                style_ids.append(style_id)

            color = style.get('color')
            if not isinstance(color, dict):
                continue

            enum_colors = color.get('enumColors')
            bin_colors = color.get('binColors')
            has_enum = isinstance(enum_colors, list) and len(enum_colors) > 0
            has_bin = isinstance(bin_colors, list) and len(bin_colors) > 0
            has_palette = bool(color.get('colorPalette'))

            if not color.get('mapType'):
                if has_enum:
                    color['mapType'] = 'enum'
                elif has_bin:
                    color['mapType'] = 'bin'
                elif has_palette:
                    # Terria table styles commonly use palette-only color blocks
                    # with a numeric column and no explicit mapType.
                    color['mapType'] = 'continuous'

            # Infer colorColumn from style id when missing (common in legacy share links)
            if isinstance(color, dict) and not color.get('colorColumn'):
                inferred_column = style_id or model_value.get('activeStyle')
                if inferred_column:
                    color['colorColumn'] = inferred_column

        active_style = model_value.get('activeStyle')
        if style_ids and (not active_style or active_style not in style_ids):
            model_value['activeStyle'] = style_ids[0]
    
    def _strip_orphaned_group_models(self, models: Dict) -> Dict:
        """
        Remove group models not in the ancestry chain of any data item.
        
        Saved Terria states include model entries for built-in catalog groups
        (e.g. "//IHP-WINS") that were merely opened/browsed.  When loaded via
        #start=, these create duplicates of groups already in the instance.
        This method keeps only models reachable from data items (those with a
        ``url``) plus the root ``/``.
        """
        if not models:
            return models

        needed = {"/"}
        # Seed with data-item models (have a url) and trace their ancestry
        for key, model in models.items():
            if isinstance(model, dict) and 'url' in model:
                needed.add(key)
                to_visit = [key]
                while to_visit:
                    current = to_visit.pop()
                    current_model = models.get(current, {})
                    if isinstance(current_model, dict):
                        for cid in current_model.get('knownContainerUniqueIds', []):
                            if cid not in needed and cid in models:
                                needed.add(cid)
                                to_visit.append(cid)

        # Also follow members from already-needed groups
        changed = True
        while changed:
            changed = False
            for key in list(needed):
                model = models.get(key, {})
                if isinstance(model, dict):
                    for member in model.get('members', []):
                        if member in models and member not in needed:
                            needed.add(member)
                            changed = True

        stripped = {k: v for k, v in models.items() if k in needed}
        removed = set(models.keys()) - needed
        if removed:
            self._debug_print(
                f"Stripped orphaned group models from config: {removed}"
            )
        return stripped

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
                # Decode the key if it contains '+'
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
