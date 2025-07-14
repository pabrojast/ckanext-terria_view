# encoding: utf-8
"""
Module for processing SLD (Styled Layer Descriptor) files.
Enhanced for better TerriaJS compatibility.
"""
import urllib.request
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple, Any
import re


class SLDProcessor:
    """SLD file processor for extracting style information with TerriaJS compatibility."""
    
    # Standard XML namespaces for SLD
    NAMESPACES = {
        'sld': 'http://www.opengis.net/sld',
        'se': 'http://www.opengis.net/se',
        'ogc': 'http://www.opengis.net/ogc'
    }
    
    def __init__(self):
        """Initialize the SLD processor."""
        pass
    
    def _normalize_color(self, color: str) -> str:
        """
        Normalize color values to ensure TerriaJS compatibility.
        
        Args:
            color: Color string (hex, rgb, rgba, or named color)
            
        Returns:
            Normalized color string
        """
        if not color:
            return "#000000"
        
        color = color.strip()
        
        # If it's already a hex color, ensure it's properly formatted
        if color.startswith('#'):
            # Remove # and ensure 6 characters
            hex_color = color.lstrip('#')
            if len(hex_color) == 3:
                # Convert 3-digit hex to 6-digit
                hex_color = ''.join([c*2 for c in hex_color])
            elif len(hex_color) != 6:
                return "#000000"  # Invalid hex, return black
            return f"#{hex_color.upper()}"
        
        # Handle RGB/RGBA format
        if color.startswith(('rgb(', 'rgba(')):
            return color  # Already in correct format
        
        # Handle named colors (basic set)
        named_colors = {
            'black': '#000000', 'white': '#FFFFFF', 'red': '#FF0000',
            'green': '#00FF00', 'blue': '#0000FF', 'yellow': '#FFFF00',
            'cyan': '#00FFFF', 'magenta': '#FF00FF', 'gray': '#808080',
            'grey': '#808080', 'orange': '#FFA500', 'purple': '#800080',
            'brown': '#A52A2A', 'pink': '#FFC0CB', 'lime': '#00FF00',
            'navy': '#000080', 'teal': '#008080', 'silver': '#C0C0C0',
            'maroon': '#800000', 'olive': '#808000'
        }
        
        color_lower = color.lower()
        if color_lower in named_colors:
            return named_colors[color_lower]
        
        # Try to parse as decimal RGB values (e.g., "255,0,0")
        if ',' in color and not color.startswith(('rgb', 'rgba')):
            try:
                parts = [float(p.strip()) for p in color.split(',')]
                if len(parts) == 3:
                    r, g, b = [int(max(0, min(255, p))) for p in parts]
                    return f"#{r:02X}{g:02X}{b:02X}"
            except ValueError:
                pass
        
        # If all else fails, return black
        return "#000000"
        
        # Handle rgb() and rgba() formats
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # For other formats, return as-is (named colors, etc.)
        return color
    
    def _convert_color_to_rgba(self, color: str, opacity: float = 1.0) -> str:
        """
        Convert any color format to rgba format for TerriaJS.
        This is a more comprehensive version of _convert_hex_to_rgba
        that handles more input formats.
        
        Args:
            color: Color string in any format (hex, rgb, rgba, named)
            opacity: Default opacity value if not specified in the color
            
        Returns:
            RGBA color string formatted specifically for TerriaJS
        """
        try:
            # Extract RGB/A values using our enhanced function
            rgb_values = self._extract_rgb_values(color)
            
            if rgb_values:
                if len(rgb_values) >= 4:  # RGBA
                    return f"rgba({int(rgb_values[0])},{int(rgb_values[1])},{int(rgb_values[2])},{rgb_values[3]})"
                else:  # RGB
                    return f"rgba({int(rgb_values[0])},{int(rgb_values[1])},{int(rgb_values[2])},{opacity})"
            
            # If extraction failed, try with normalized color
            normalized_color = self._normalize_color(color)
            rgb_values = self._extract_rgb_values(normalized_color)
            
            if rgb_values:
                if len(rgb_values) >= 4:  # RGBA
                    return f"rgba({int(rgb_values[0])},{int(rgb_values[1])},{int(rgb_values[2])},{rgb_values[3]})"
                else:  # RGB
                    return f"rgba({int(rgb_values[0])},{int(rgb_values[1])},{int(rgb_values[2])},{opacity})"
            
            # Last resort fallback
            return f"rgba(0,0,0,{opacity})"
        except Exception as e:
            print(f"Error converting color to RGBA: {e}")
            return f"rgba(0,0,0,{opacity})"
    
    def _convert_hex_to_rgba(self, color: str, opacity: float = 1.0) -> str:
        """
        Convert hex color to rgba format for TerriaJS.
        Ensures proper format for TerriaJS compatibility.
        
        Args:
            color: Hex color string
            opacity: Opacity value (0.0 to 1.0)
            
        Returns:
            RGBA color string
        """
        # For backward compatibility, delegate to the more comprehensive function
        return self._convert_color_to_rgba(color, opacity)
    
    def _extract_numeric_value(self, value_str: str) -> Optional[float]:
        """
        Extract numeric value from property value, handling different formats.
        Handles scientific notation and long decimal numbers properly.
        
        Args:
            value_str: String containing numeric value
            
        Returns:
            Numeric value or None if extraction fails
        """
        if not value_str:
            return None
        
        try:
            # Try direct conversion with high precision
            # Esto manejará correctamente valores como "0.20000000000000001"
            return float(value_str)
        except ValueError:
            # Try to extract numeric part from string
            # Mejorado para manejar notación científica y decimales largos
            numeric_match = re.search(r'-?\d*\.?\d+(?:[eE][-+]?\d+)?', value_str)
            if numeric_match:
                try:
                    return float(numeric_match.group())
                except ValueError:
                    pass
        
        return None
    
    def _sort_enum_colors_by_value(self, enum_colors: List[Dict]) -> List[Dict]:
        """
        Sort enum colors by numeric value for better TerriaJS rendering.
        Preserves the exact string representation of values.
        
        Args:
            enum_colors: List of enum color dictionaries
            
        Returns:
            Sorted list of enum colors
        """
        def sort_key(item):
            # Extraer valor numérico para ordenamiento, pero preservar el valor original
            value = self._extract_numeric_value(item.get('value', ''))
            return value if value is not None else float('inf')
        
        # Crear una copia para no modificar los valores originales
        sorted_colors = sorted(enum_colors, key=sort_key)
        return sorted_colors
    
    def fetch_sld_content(self, sld_url: str) -> Optional[bytes]:
        """
        Download the content of an SLD file from a URL.
        
        Args:
            sld_url: URL of the SLD file
            
        Returns:
            SLD file content as bytes, None in case of error
        """
        try:
            # Add timeout and better error handling
            request = urllib.request.Request(sld_url)
            request.add_header('User-Agent', 'CKAN-TerriaView/1.0')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except Exception as e:
            print(f"Error fetching SLD file from {sld_url}: {e}")
            return None
    
    def parse_sld_xml(self, sld_content: bytes) -> Optional[ET.Element]:
        """
        Parse the XML content of an SLD file.
        
        Args:
            sld_content: SLD file content as bytes
            
        Returns:
            Root element of the parsed XML, None in case of error
        """
        try:
            # Remove XML declaration and encoding issues
            content_str = sld_content.decode('utf-8', errors='ignore')
            # Remove BOM if present
            if content_str.startswith('\ufeff'):
                content_str = content_str[1:]
            
            return ET.fromstring(content_str.encode('utf-8'))
        except Exception as e:
            print(f"Error parsing SLD XML: {e}")
            return None
    
    def process_cog_sld(self, sld_url: str) -> Dict[str, Any]:
        """
        Process an SLD file for COG (Cloud Optimized GeoTIFF) resources with enhanced gradient support.
        
        Args:
            sld_url: URL of the SLD file
            
        Returns:
            Dictionary with style information for COG
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
            # Look for ColorMap elements (can contain ColorMapEntry elements)
            color_maps = root.findall('.//sld:ColorMap', self.NAMESPACES)
            
            all_entries = []
            interpolation_type = "linear"  # default
            
            for color_map in color_maps:
                # Check for interpolation type
                color_map_type = color_map.get('type', 'ramp')
                if color_map_type in ['ramp', 'intervals']:
                    interpolation_type = "linear" if color_map_type == 'ramp' else "discrete"
                
                # Get ColorMapEntry elements
                color_map_entries = color_map.findall('sld:ColorMapEntry', self.NAMESPACES)
                all_entries.extend(color_map_entries)
            
            # If no ColorMap found, look for direct ColorMapEntry elements
            if not all_entries:
                all_entries = root.findall('.//sld:ColorMapEntry', self.NAMESPACES)
            
            # Process all entries
            for entry in all_entries:
                quantity = entry.get('quantity')
                color = entry.get('color')
                label = entry.get('label', '')
                opacity = entry.get('opacity', '1.0')
                
                if quantity and color:
                    try:
                        quantity_val = float(quantity)
                        opacity_val = float(opacity)
                        
                        # Normalize color
                        normalized_color = self._normalize_color(color)
                        
                        # Convert to RGB for TerriaJS renderOptions
                        if normalized_color.startswith('#'):
                            hex_color = normalized_color.lstrip('#')
                            rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                            if opacity_val < 1.0:
                                rgb_string = f"rgba({rgb[0]}, {rgb[1]}, {rgb[2]}, {opacity_val})"
                            else:
                                rgb_string = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
                        else:
                            rgb_string = normalized_color
                        
                        colors.append([quantity_val, rgb_string])
                        
                        # Create legend entry
                        legend_title = label if label else f"{quantity_val}"
                        legend_items.append({
                            "title": legend_title,
                            "color": normalized_color
                        })
                        
                    except ValueError as e:
                        print(f"Error processing color map entry: {e}")
                        continue
        
        except Exception as e:
            print(f"Error processing COG SLD: {e}")
            return {}
        
        # Sort colors by quantity for proper rendering
        colors.sort(key=lambda x: x[0])
        
        # If we have colors, check if we need to create intermediate gradients
        if len(colors) >= 2:
            colors = self._enhance_color_gradient(colors, interpolation_type)
        
        result = {}
        if legend_items:
            # Sort legend items by quantity value for logical display
            try:
                legend_items.sort(key=lambda x: float(x['title']) if x['title'].replace('-', '').replace('.', '').isdigit() else float('inf'))
            except:
                pass  # If sorting fails, keep original order
                
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
        Process an SLD file for Shapefile resources with enhanced TerriaJS compatibility.
        
        Args:
            sld_url: URL of the SLD file
            
        Returns:
            Dictionary with style information for Shapefile
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
                    label = (title.text if title is not None else name.text) if name is not None else "No label"
                    
                    # Normalize color
                    normalized_color = self._normalize_color(color)
                    
                    # Add to legend
                    legend_items.append({
                        "title": label,
                        "color": normalized_color
                    })                        # Only process if property_name has a non-empty value
                    if (property_name is not None and property_name.text and 
                        property_name.text.strip() and property_value is not None):
                        valid_property_name = property_name.text.strip()
                        
                        # Convert any color format to RGBA for TerriaJS compatibility
                        rgba_color = self._convert_color_to_rgba(normalized_color)
                        
                        # Mantener el formato exacto del valor numérico sin redondeo
                        prop_value = property_value.text
                        # Tratar de preservar formatos numéricos exactos (como "0.20000000000000001")
                        try:
                            # Solo convertir a float para ordenamiento posterior
                            float(prop_value)
                        except ValueError:
                            # Si no es un número, dejarlo como texto
                            pass
                            
                        enum_colors.append({
                            "value": prop_value,
                            "color": rgba_color
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
        
        # Only add styles if we have a valid property_name and enum_colors
        if enum_colors and valid_property_name:
            # Sort enum colors for better rendering
            sorted_enum_colors = self._sort_enum_colors_by_value(enum_colors)
            
            # Verificar si hay algún valor no numérico en los enum_colors
            has_non_numeric = any(
                not re.match(r'^-?\d*\.?\d+(?:[eE][-+]?\d+)?$', item.get('value', '')) 
                for item in sorted_enum_colors
            )
            
            style_config = {
                "id": valid_property_name,
                "color": {
                    "enumColors": sorted_enum_colors,
                    "colorPalette": "HighContrast"
                }
            }
            
            result["styles"] = [style_config]
            result["activeStyle"] = valid_property_name
        
        return result
    
    def process_sld_for_resource(self, sld_url: str, resource_format: str) -> Dict[str, Any]:
        """
        Process an SLD file according to the resource type.
        
        Args:
            sld_url: URL of the SLD file
            resource_format: Resource format (shp, tif, etc.)
            
        Returns:
            Dictionary with style information appropriate for the resource type
        """
        if not sld_url or sld_url == 'NA':
            return {}
        
        resource_format = resource_format.lower()
        
        if resource_format == 'shp':
            return self.process_shp_sld(sld_url)
        elif resource_format in ['tif', 'tiff', 'geotiff', 'cog']:
            return self.process_cog_sld(sld_url)
        else:
            # For other formats, try generic processing
            return self.process_generic_sld(sld_url)
    
    def process_generic_sld(self, sld_url: str) -> Dict[str, Any]:
        """
        Process an SLD file in a generic way with enhanced error handling.
        
        Args:
            sld_url: URL of the SLD file
            
        Returns:
            Dictionary with generic style information
        """
        sld_content = self.fetch_sld_content(sld_url)
        if not sld_content:
            return {}
        
        root = self.parse_sld_xml(sld_content)
        if root is None:
            return {}
        
        # Try to extract basic legend information
        legend_items = []
        
        try:
            # Look for rules with names and colors
            rules = root.findall('.//se:Rule', self.NAMESPACES)
            
            for rule in rules:
                name = rule.find('se:Name', self.NAMESPACES)
                title = rule.find('.//se:Title', self.NAMESPACES)
                fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
                stroke = rule.find('.//se:Stroke/se:SvgParameter[@name="stroke"]', self.NAMESPACES)
                
                if (name is not None or title is not None):
                    label = (title.text if title is not None else name.text) if name is not None else "No label"
                    
                    # Get color (prefer fill, fallback to stroke)
                    color = None
                    if fill is not None:
                        color = fill.text
                    elif stroke is not None:
                        color = stroke.text
                    
                    if color:
                        normalized_color = self._normalize_color(color)
                        legend_items.append({
                            "title": label,
                            "color": normalized_color
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
    
    def _enhance_color_gradient(self, colors: List[Tuple[float, str]], interpolation_type: str = "linear") -> List[Tuple[float, str]]:
        """
        Enhance color gradient by adding intermediate points for smoother transitions.
        
        Args:
            colors: List of [quantity, color] tuples
            interpolation_type: Type of interpolation ("linear" or "discrete")
            
        Returns:
            Enhanced list of [quantity, color] tuples
        """
        if len(colors) < 2 or interpolation_type == "discrete":
            return colors
        
        enhanced_colors = []
        
        for i in range(len(colors)):
            enhanced_colors.append(colors[i])
            
            # Add intermediate colors between this and next point
            if i < len(colors) - 1:
                current_quantity, current_color = colors[i]
                next_quantity, next_color = colors[i + 1]
                
                # Calculate the gap between quantities
                quantity_gap = next_quantity - current_quantity
                
                # If gap is large, add intermediate points for smoother gradient
                if quantity_gap > 0:
                    # Add 1-3 intermediate points depending on the gap size
                    num_intermediate = min(3, max(1, int(quantity_gap / 10)))
                    
                    for j in range(1, num_intermediate + 1):
                        fraction = j / (num_intermediate + 1)
                        intermediate_quantity = current_quantity + (quantity_gap * fraction)
                        intermediate_color = self._interpolate_colors(current_color, next_color, fraction)
                        enhanced_colors.append([intermediate_quantity, intermediate_color])
        
        return enhanced_colors
    
    def _interpolate_colors(self, color1: str, color2: str, fraction: float) -> str:
        """
        Interpolate between two RGB/RGBA colors.
        
        Args:
            color1: First color (rgb/rgba string)
            color2: Second color (rgb/rgba string)  
            fraction: Interpolation fraction (0.0 to 1.0)
            
        Returns:
            Interpolated color string
        """
        try:
            # Extract RGB values from color strings
            rgb1 = self._extract_rgb_values(color1)
            rgb2 = self._extract_rgb_values(color2)
            
            if not rgb1 or not rgb2:
                return color1  # Fallback if parsing fails
            
            # Interpolate each component
            r = int(rgb1[0] + (rgb2[0] - rgb1[0]) * fraction)
            g = int(rgb1[1] + (rgb2[1] - rgb1[1]) * fraction)
            b = int(rgb1[2] + (rgb2[2] - rgb1[2]) * fraction)
            
            # Handle alpha if present
            if len(rgb1) > 3 and len(rgb2) > 3:
                a = rgb1[3] + (rgb2[3] - rgb1[3]) * fraction
                return f"rgba({r}, {g}, {b}, {a:.2f})"
            else:
                return f"rgb({r}, {g}, {b})"
                
        except Exception as e:
            print(f"Error interpolating colors: {e}")
            return color1  # Fallback to first color
    
    def _extract_rgb_values(self, color: str) -> Optional[List[float]]:
        """
        Extract RGB/RGBA values from color string.
        
        Args:
            color: Color string (rgb, rgba, or hex)
            
        Returns:
            List of RGB(A) values or None if parsing fails
        """
        try:
            if color.startswith('rgb('):
                # Extract from rgb(r, g, b)
                values_str = color[4:-1]  # Remove 'rgb(' and ')'
                values = [float(v.strip()) for v in values_str.split(',')]
                return values if len(values) == 3 else None
                
            elif color.startswith('rgba('):
                # Extract from rgba(r, g, b, a)
                values_str = color[5:-1]  # Remove 'rgba(' and ')'
                values = [float(v.strip()) for v in values_str.split(',')]
                return values if len(values) == 4 else None
                
            elif color.startswith('#'):
                # Convert hex to RGB
                hex_color = color.lstrip('#')
                
                # Handle different hex formats
                if len(hex_color) == 6:  # #RRGGBB format
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    return [r, g, b]
                elif len(hex_color) == 8:  # #RRGGBBAA format
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    a = int(hex_color[6:8], 16) / 255.0
                    return [r, g, b, a]
                elif len(hex_color) == 3:  # #RGB format
                    r = int(hex_color[0] + hex_color[0], 16)
                    g = int(hex_color[1] + hex_color[1], 16)
                    b = int(hex_color[2] + hex_color[2], 16)
                    return [r, g, b]
                elif len(hex_color) == 4:  # #RGBA format
                    r = int(hex_color[0] + hex_color[0], 16)
                    g = int(hex_color[1] + hex_color[1], 16)
                    b = int(hex_color[2] + hex_color[2], 16)
                    a = int(hex_color[3] + hex_color[3], 16) / 255.0
                    return [r, g, b, a]
                    
        except Exception as e:
            print(f"Error extracting RGB values: {e}")
            pass
            
        return None