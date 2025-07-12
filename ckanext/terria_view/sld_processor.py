# encoding: utf-8
"""
Módulo para procesar archivos SLD (Styled Layer Descriptor).
"""
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any


class SLDProcessor:
    """Procesador de archivos SLD para extraer información de estilos."""
    
    # Namespaces XML estándar para SLD
    NAMESPACES = {
        'sld': 'http://www.opengis.net/sld',
        'se': 'http://www.opengis.net/se',
        'ogc': 'http://www.opengis.net/ogc'
    }
    
    def __init__(self):
        """Inicializa el procesador SLD."""
        pass
    
    def fetch_sld_content(self, sld_url: str) -> Optional[bytes]:
        """
        Descarga el contenido de un archivo SLD desde una URL.
        
        Args:
            sld_url: URL del archivo SLD
            
        Returns:
            Contenido del archivo SLD como bytes, None en caso de error
        """
        try:
            with urllib.request.urlopen(sld_url) as response:
                return response.read()
        except Exception as e:
            print(f"Error fetching SLD file from {sld_url}: {e}")
            return None
    
    def parse_sld_xml(self, sld_content: bytes) -> Optional[ET.Element]:
        """
        Parsea el contenido XML de un archivo SLD.
        
        Args:
            sld_content: Contenido del archivo SLD como bytes
            
        Returns:
            Elemento raíz del XML parseado, None en caso de error
        """
        try:
            return ET.fromstring(sld_content)
        except Exception as e:
            print(f"Error parsing SLD XML: {e}")
            return None
    
    def process_cog_sld(self, sld_url: str) -> Dict[str, Any]:
        """
        Procesa un archivo SLD para recursos COG (Cloud Optimized GeoTIFF).
        
        Args:
            sld_url: URL del archivo SLD
            
        Returns:
            Diccionario con información de estilos para COG
        """
        sld_content = self.fetch_sld_content(sld_url)
        if not sld_content:
            return {}
        
        root = self.parse_sld_xml(sld_content)
        if root is None:
            return {}
        
        colors = []
        legend_items = []
        
        try:
            color_map_entries = root.findall('.//sld:ColorMapEntry', self.NAMESPACES)
            
            for entry in color_map_entries:
                quantity = entry.get('quantity')
                color = entry.get('color')
                label = entry.get('label', '')
                
                if quantity and color:
                    # Convertir color hex a RGB
                    if color.startswith('#'):
                        hex_color = color.lstrip('#')
                        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                        rgb_string = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
                    else:
                        rgb_string = color
                    
                    colors.append([float(quantity), rgb_string])
                    legend_items.append({
                        "title": label,
                        "color": color
                    })
        
        except Exception as e:
            print(f"Error processing COG SLD: {e}")
            return {}
        
        result = {}
        if legend_items:
            result["legends"] = [{
                "title": "Legend",
                "items": legend_items
            }]
        
        if colors:
            result["renderOptions"] = {
                "single": {
                    "colors": colors,
                    "useRealValue": True
                }
            }
        
        return result
    
    def process_shp_sld(self, sld_url: str) -> Dict[str, Any]:
        """
        Procesa un archivo SLD para recursos Shapefile.
        
        Args:
            sld_url: URL del archivo SLD
            
        Returns:
            Diccionario con información de estilos para Shapefile
        """
        sld_content = self.fetch_sld_content(sld_url)
        if not sld_content:
            return {}
        
        root = self.parse_sld_xml(sld_content)
        if root is None:
            return {}
        
        legend_items = []
        enum_colors = []
        valid_property_name = None
        
        try:
            rules = root.findall('.//se:Rule', self.NAMESPACES)
            
            for rule in rules:
                name = rule.find('se:Name', self.NAMESPACES)
                title = rule.find('.//se:Title', self.NAMESPACES)
                fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
                property_name = rule.find('.//ogc:PropertyName', self.NAMESPACES)
                property_value = rule.find('.//ogc:Literal', self.NAMESPACES)
                
                if fill is not None and (name is not None or title is not None):
                    color = fill.text
                    label = (title.text if title is not None else name.text) if name is not None else "Sin etiqueta"
                    
                    # Agregar a la leyenda
                    legend_items.append({
                        "title": label,
                        "color": color
                    })
                    
                    # Solo procesar si property_name tiene un valor no vacío
                    if (property_name is not None and property_name.text and 
                        property_name.text.strip() and property_value is not None):
                        valid_property_name = property_name.text.strip()
                        
                        # Convertir color hex a rgba
                        if color.startswith('#'):
                            hex_color = color.lstrip('#')
                            rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                            rgba_string = f"rgba({rgb[0]},{rgb[1]},{rgb[2]},1)"
                        else:
                            rgba_string = color
                        
                        enum_colors.append({
                            "value": property_value.text,
                            "color": rgba_string
                        })
        
        except Exception as e:
            print(f"Error processing SHP SLD: {e}")
            return {}
        
        result = {}
        if legend_items:
            result["legends"] = [{
                "title": "Legend",
                "items": legend_items
            }]
        
        # Solo agregar estilos si tenemos un property_name válido y enum_colors
        if enum_colors and valid_property_name:
            result["styles"] = [{
                "id": valid_property_name,
                "color": {
                    "enumColors": enum_colors
                }
            }]
            result["activeStyle"] = valid_property_name
        
        return result
    
    def process_sld_for_resource(self, sld_url: str, resource_format: str) -> Dict[str, Any]:
        """
        Procesa un archivo SLD según el tipo de recurso.
        
        Args:
            sld_url: URL del archivo SLD
            resource_format: Formato del recurso (shp, tif, etc.)
            
        Returns:
            Diccionario con información de estilos apropiada para el tipo de recurso
        """
        if not sld_url or sld_url == 'NA':
            return {}
        
        resource_format = resource_format.lower()
        
        if resource_format == 'shp':
            return self.process_shp_sld(sld_url)
        elif resource_format in ['tif', 'tiff', 'geotiff']:
            return self.process_cog_sld(sld_url)
        else:
            # Para otros formatos, intentar procesamiento genérico
            return self.process_generic_sld(sld_url)
    
    def process_generic_sld(self, sld_url: str) -> Dict[str, Any]:
        """
        Procesa un archivo SLD de forma genérica.
        
        Args:
            sld_url: URL del archivo SLD
            
        Returns:
            Diccionario con información de estilos genérica
        """
        sld_content = self.fetch_sld_content(sld_url)
        if not sld_content:
            return {}
        
        root = self.parse_sld_xml(sld_content)
        if root is None:
            return {}
        
        # Intentar extraer información básica de leyenda
        legend_items = []
        
        try:
            # Buscar reglas con nombres y colores
            rules = root.findall('.//se:Rule', self.NAMESPACES)
            
            for rule in rules:
                name = rule.find('se:Name', self.NAMESPACES)
                title = rule.find('.//se:Title', self.NAMESPACES)
                fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
                
                if fill is not None and (name is not None or title is not None):
                    color = fill.text
                    label = (title.text if title is not None else name.text) if name is not None else "Sin etiqueta"
                    
                    legend_items.append({
                        "title": label,
                        "color": color
                    })
        
        except Exception as e:
            print(f"Error processing generic SLD: {e}")
            return {}
        
        result = {}
        if legend_items:
            result["legends"] = [{
                "title": "Legend",
                "items": legend_items
            }]
        
        return result 