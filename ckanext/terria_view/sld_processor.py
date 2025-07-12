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
        
        # Handle rgb() and rgba() formats
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # For other formats, return as-is (named colors, etc.)
        return color
    
    def _convert_hex_to_rgba(self, color: str, opacity: float = 1.0) -> str:
        """
        Convert hex color to rgba format for TerriaJS.
        
        Args:
            color: Hex color string
            opacity: Opacity value (0.0 to 1.0)
            
        Returns:
            RGBA color string
        """
        normalized_color = self._normalize_color(color)
        if normalized_color.startswith('#'):
            hex_color = normalized_color.lstrip('#')
            rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
            return f"rgba({rgb[0]},{rgb[1]},{rgb[2]},{opacity})"
        return color
    
    def _extract_numeric_value(self, value_str: str) -> Optional[float]:
        """
        Extract numeric value from property value, handling different formats.
        
        Args:
            value_str: String containing numeric value
            
        Returns:
            Numeric value or None if extraction fails
        """
        if not value_str:
            return None
        
        try:
            # Try direct conversion
            return float(value_str)
        except ValueError:
            # Try to extract numeric part from string
            numeric_match = re.search(r'[\d.]+', value_str)
            if numeric_match:
                try:
                    return float(numeric_match.group())
                except ValueError:
                    pass
        
        return None
    
    def _sort_enum_colors_by_value(self, enum_colors: List[Dict]) -> List[Dict]:
        """
        Sort enum colors by numeric value for better TerriaJS rendering.
        
        Args:
            enum_colors: List of enum color dictionaries
            
        Returns:
            Sorted list of enum colors
        """
        def sort_key(item):
            value = self._extract_numeric_value(item.get('value', ''))
            return value if value is not None else float('inf')
        
        return sorted(enum_colors, key=sort_key)
    
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
        Process an SLD file for COG (Cloud Optimized GeoTIFF) resources.
        
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
            color_map_entries = root.findall('.//sld:ColorMapEntry', self.NAMESPACES)
            
            for entry in color_map_entries:
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
                        legend_items.append({
                            "title": label or f"Value {quantity}",
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
                    })
                    
                    # Only process if property_name has a non-empty value
                    if (property_name is not None and property_name.text and 
                        property_name.text.strip() and property_value is not None):
                        valid_property_name = property_name.text.strip()
                        
                        # Convert to RGBA for TerriaJS
                        rgba_color = self._convert_hex_to_rgba(normalized_color)
                        
                        enum_colors.append({
                            "value": property_value.text,
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
            
            result["styles"] = [{
                "id": valid_property_name,
                "color": {
                    "enumColors": sorted_enum_colors
                }
            }]
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