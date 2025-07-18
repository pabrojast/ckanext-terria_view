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
    
    # Extended XML namespaces for SLD (based on QGIS implementation)
    NAMESPACES = {
        'sld': 'http://www.opengis.net/sld',
        'se': 'http://www.opengis.net/se', 
        'ogc': 'http://www.opengis.net/ogc',
        'xlink': 'http://www.w3.org/1999/xlink',
        'gml': 'http://www.opengis.net/gml',
        'ows': 'http://www.opengis.net/ows'
    }
    
    # Well-known SLD attribute names for color properties (based on QGIS)
    COLOR_PROPERTIES = ['fill', 'stroke', 'fill-color', 'stroke-color']
    
    # Default values for missing properties (following QGIS defaults)
    DEFAULTS = {
        'fill_color': '#808080',  # Gray
        'stroke_color': '#000000',  # Black
        'stroke_width': 1.0,
        'opacity': 1.0
    }
    
    def __init__(self):
        """Initialize the SLD processor."""
        pass
    
    def _normalize_color(self, color: str) -> str:
        """
        Normalize color values to ensure TerriaJS compatibility.
        Enhanced color parsing based on QGIS implementation.
        
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
            elif len(hex_color) == 6:
                return f"#{hex_color.upper()}"
            elif len(hex_color) == 8:
                # 8-digit hex with alpha, take first 6 digits
                return f"#{hex_color[:6].upper()}"
            else:
                return "#000000"  # Invalid hex, return black
            return f"#{hex_color.upper()}"
        
        # Handle RGB format: rgb(r,g,b) or rgba(r,g,b,a)
        rgb_match = re.match(r'rgba?\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)', color.lower())
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            # Clamp values to 0-255 range
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # Handle percentage RGB format: rgb(r%,g%,b%)
        rgb_percent_match = re.match(r'rgba?\s*\(\s*([\d.]+)%\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%(?:\s*,\s*[\d.]+)?\s*\)', color.lower())
        if rgb_percent_match:
            r_pct, g_pct, b_pct = map(float, rgb_percent_match.groups())
            r = int(max(0, min(100, r_pct)) * 2.55)
            g = int(max(0, min(100, g_pct)) * 2.55)
            b = int(max(0, min(100, b_pct)) * 2.55)
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # Handle HSL format: hsl(h,s%,l%)
        hsl_match = re.match(r'hsla?\s*\(\s*([\d.]+)\s*,\s*([\d.]+)%\s*,\s*([\d.]+)%(?:\s*,\s*[\d.]+)?\s*\)', color.lower())
        if hsl_match:
            h, s, l = map(float, hsl_match.groups())
            # Convert HSL to RGB (simplified conversion)
            h = h / 360.0
            s = s / 100.0
            l = l / 100.0
            
            def hue_to_rgb(p, q, t):
                if t < 0: t += 1
                if t > 1: t -= 1
                if t < 1/6: return p + (q - p) * 6 * t
                if t < 1/2: return q
                if t < 2/3: return p + (q - p) * (2/3 - t) * 6
                return p
            
            if s == 0:
                r = g = b = l  # achromatic
            else:
                q = l * (1 + s) if l < 0.5 else l + s - l * s
                p = 2 * l - q
                r = hue_to_rgb(p, q, h + 1/3)
                g = hue_to_rgb(p, q, h)
                b = hue_to_rgb(p, q, h - 1/3)
            
            r = int(r * 255)
            g = int(g * 255)
            b = int(b * 255)
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # Handle named colors (basic set based on QGIS)
        named_colors = {
            'black': '#000000',
            'white': '#FFFFFF',
            'red': '#FF0000',
            'green': '#008000',
            'blue': '#0000FF',
            'yellow': '#FFFF00',
            'cyan': '#00FFFF',
            'magenta': '#FF00FF',
            'gray': '#808080',
            'grey': '#808080',
            'transparent': '#000000'  # Handle transparent as black
        }
        
        lower_color = color.lower()
        if lower_color in named_colors:
            return named_colors[lower_color]
        
        # If nothing matches, return black as default
        return "#000000"
        
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
        
        # Handle rgb() and rgba() formats with regex
        rgb_match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*[\d.]+)?\)', color)
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            return f"#{r:02X}{g:02X}{b:02X}"
        
        # If all else fails, return black
        return "#000000"
    
    def _convert_color_to_rgba(self, color: str, opacity: float = 1.0) -> str:
        """
        Convert any color format to rgba format for TerriaJS.
        Simplified version that works like the original code.
        
        Args:
            color: Color string in any format (hex, rgb, rgba, named)
            opacity: Default opacity value if not specified in the color
            
        Returns:
            RGBA color string formatted specifically for TerriaJS
        """
        try:
            # Normalize color first
            normalized_color = self._normalize_color(color)
            
            # If it's already in rgba format, return as-is
            if normalized_color.startswith('rgba('):
                return normalized_color
            
            # If it's in rgb format, convert to rgba
            if normalized_color.startswith('rgb('):
                # Extract RGB values and add opacity
                rgb_match = re.match(r'rgb\((\d+),\s*(\d+),\s*(\d+)\)', normalized_color)
                if rgb_match:
                    r, g, b = map(int, rgb_match.groups())
                    return f"rgba({r},{g},{b},{opacity})"
            
            # For hex colors, convert directly like the original code
            if normalized_color.startswith('#'):
                hex_color = normalized_color.lstrip('#')
                if len(hex_color) == 6:
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    return f"rgba({r},{g},{b},{opacity})"
                elif len(hex_color) == 3:
                    r = int(hex_color[0] + hex_color[0], 16)
                    g = int(hex_color[1] + hex_color[1], 16)
                    b = int(hex_color[2] + hex_color[2], 16)
                    return f"rgba({r},{g},{b},{opacity})"
            
            # For named colors, try to convert to hex first
            if not normalized_color.startswith('#') and not normalized_color.startswith('rgb'):
                # Try to convert named color to hex
                named_colors = {
                    'black': '#000000', 'white': '#FFFFFF', 'red': '#FF0000',
                    'green': '#00FF00', 'blue': '#0000FF', 'yellow': '#FFFF00',
                    'cyan': '#00FFFF', 'magenta': '#FF00FF', 'gray': '#808080',
                    'grey': '#808080', 'orange': '#FFA500', 'purple': '#800080',
                    'brown': '#A52A2A', 'pink': '#FFC0CB', 'lime': '#00FF00',
                    'navy': '#000080', 'teal': '#008080', 'silver': '#C0C0C0',
                    'maroon': '#800000', 'olive': '#808000'
                }
                
                color_lower = normalized_color.lower()
                if color_lower in named_colors:
                    hex_color = named_colors[color_lower].lstrip('#')
                    r = int(hex_color[0:2], 16)
                    g = int(hex_color[2:4], 16)
                    b = int(hex_color[4:6], 16)
                    return f"rgba({r},{g},{b},{opacity})"
            
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
        Download the content of an SLD file from a URL with robust error handling.
        
        Args:
            sld_url: URL of the SLD file
            
        Returns:
            SLD file content as bytes, None in case of error
        """
        if not sld_url or not isinstance(sld_url, str):
            print(f"Invalid SLD URL provided: {sld_url}")
            return None
        
        # Clean and validate URL
        sld_url = sld_url.strip()
        if not sld_url:
            print("Empty SLD URL provided")
            return None
        
        # Handle different URL schemes
        if sld_url.startswith(('http://', 'https://')):
            return self._fetch_http_content(sld_url)
        elif sld_url.startswith('file://'):
            return self._fetch_file_content(sld_url)
        elif sld_url.startswith('/') or (':\\' in sld_url and len(sld_url) > 3):
            # Local file path
            return self._fetch_local_file_content(sld_url)
        else:
            print(f"Unsupported URL scheme in: {sld_url}")
            return None
    
    def _fetch_http_content(self, url: str) -> Optional[bytes]:
        """Fetch content from HTTP/HTTPS URL."""
        try:
            request = urllib.request.Request(url)
            request.add_header('User-Agent', 'CKAN-TerriaView/1.0')
            request.add_header('Accept', 'application/xml, text/xml, */*')
            
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
                
                # Validate content size (prevent extremely large files)
                if len(content) > 10 * 1024 * 1024:  # 10MB limit
                    print(f"SLD file too large: {len(content)} bytes")
                    return None
                
                return content
                
        except urllib.error.HTTPError as e:
            print(f"HTTP error fetching SLD from {url}: {e.code} {e.reason}")
            return None
        except urllib.error.URLError as e:
            print(f"URL error fetching SLD from {url}: {e.reason}")
            return None
        except Exception as e:
            print(f"Unexpected error fetching SLD from {url}: {e}")
            return None
    
    def _fetch_file_content(self, file_url: str) -> Optional[bytes]:
        """Fetch content from file:// URL."""
        try:
            import os
            # Remove file:// prefix and decode path
            file_path = urllib.parse.unquote(file_url[7:])
            return self._fetch_local_file_content(file_path)
        except Exception as e:
            print(f"Error fetching file from {file_url}: {e}")
            return None
    
    def _fetch_local_file_content(self, file_path: str) -> Optional[bytes]:
        """Fetch content from local file path."""
        try:
            import os
            
            if not os.path.exists(file_path):
                print(f"SLD file not found: {file_path}")
                return None
            
            if not os.path.isfile(file_path):
                print(f"SLD path is not a file: {file_path}")
                return None
            
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > 10 * 1024 * 1024:  # 10MB limit
                print(f"SLD file too large: {file_size} bytes")
                return None
            
            with open(file_path, 'rb') as f:
                return f.read()
                
        except Exception as e:
            print(f"Error reading local SLD file {file_path}: {e}")
            return None
    
    def parse_sld_xml(self, sld_content: bytes) -> Optional[ET.Element]:
        """
        Parse the XML content of an SLD file with robust error handling.
        
        Args:
            sld_content: SLD file content as bytes
            
        Returns:
            Root element of the parsed XML, None in case of error
        """
        if not sld_content:
            print("No SLD content provided for parsing")
            return None
        
        try:
            # Validate content is not empty
            if len(sld_content.strip()) == 0:
                print("SLD content is empty")
                return None
            
            # Try different decoding approaches
            content_str = None
            
            # Try UTF-8 first
            try:
                content_str = sld_content.decode('utf-8', errors='ignore')
            except UnicodeDecodeError:
                # Try other common encodings
                for encoding in ['latin-1', 'iso-8859-1', 'cp1252']:
                    try:
                        content_str = sld_content.decode(encoding, errors='ignore')
                        print(f"Successfully decoded SLD using {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
            
            if not content_str:
                print("Failed to decode SLD content")
                return None
            
            # Remove BOM if present
            if content_str.startswith('\ufeff'):
                content_str = content_str[1:]
            
            # Basic XML validation
            if not content_str.strip().startswith('<?xml') and not content_str.strip().startswith('<'):
                print("Content does not appear to be XML")
                return None
            
            # Check for SLD-specific elements
            if 'StyledLayerDescriptor' not in content_str:
                print("Content does not appear to be an SLD file (missing StyledLayerDescriptor)")
                return None
            
            # Parse XML with error recovery
            try:
                return ET.fromstring(content_str.encode('utf-8'))
            except ET.ParseError as e:
                print(f"XML parsing error: {e}")
                # Try to clean common XML issues and retry
                cleaned_content = self._clean_xml_content(content_str)
                if cleaned_content != content_str:
                    try:
                        print("Retrying with cleaned XML content")
                        return ET.fromstring(cleaned_content.encode('utf-8'))
                    except ET.ParseError as e2:
                        print(f"XML parsing failed even after cleaning: {e2}")
                return None
                
        except Exception as e:
            print(f"Unexpected error parsing SLD XML: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _clean_xml_content(self, content: str) -> str:
        """
        Clean common XML issues that might prevent parsing.
        
        Args:
            content: XML content string
            
        Returns:
            Cleaned XML content
        """
        try:
            # Remove null bytes
            content = content.replace('\x00', '')
            
            # Fix common namespace issues
            content = re.sub(r'xmlns:(\w+)="([^"]*)"', lambda m: f'xmlns:{m.group(1)}="{m.group(2).strip()}"', content)
            
            # Remove control characters except whitespace
            content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
            
            # Fix unclosed tags (basic attempt)
            # This is a simplified fix, might need enhancement for complex cases
            
            return content
            
        except Exception as e:
            print(f"Error cleaning XML content: {e}")
            return content
    
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
        Process an SLD file for Shapefile resources following QGIS approach with enhanced TerriaJS compatibility.
        
        Args:
            sld_url: URL of the SLD file
            
        Returns:
            Dictionary with style information for Shapefile
        """
        # Input validation
        if not sld_url or not isinstance(sld_url, str):
            print(f"Invalid SLD URL provided: {sld_url}")
            return {}
        
        sld_url = sld_url.strip()
        if not sld_url or sld_url.lower() in ['na', 'none', 'null']:
            print("No valid SLD URL provided")
            return {}
        
        # Fetch and parse SLD content
        sld_content = self.fetch_sld_content(sld_url)
        if not sld_content:
            print(f"Failed to fetch SLD content from: {sld_url}")
            return {}
        
        root = self.parse_sld_xml(sld_content)
        if root is None:
            print(f"Failed to parse SLD XML from: {sld_url}")
            return {}
        
        try:
            # Follow QGIS approach: find UserStyle elements first
            user_styles = self._find_user_styles(root)
            if not user_styles:
                print("No UserStyle elements found in SLD")
                return {}
            
            # Process all UserStyle elements and merge rules
            all_rules = []
            for user_style in user_styles:
                feature_type_styles = self._find_feature_type_styles(user_style)
                for feat_style in feature_type_styles:
                    rules = self._find_rules_in_feature_style(feat_style)
                    all_rules.extend(rules)
            
            if not all_rules:
                print("No valid rules found in any FeatureTypeStyle")
                return {}
            
            print(f"Found {len(all_rules)} total rules from all UserStyle/FeatureTypeStyle elements")
            
            # Process rules and determine renderer type
            renderer_type, processed_data = self._process_rules_qgis_style(all_rules)
            
            if not processed_data:
                print("No valid styling data extracted from rules")
                return {}
            
            # Build TerriaJS result based on renderer type
            return self._build_terria_result(renderer_type, processed_data)
            
        except Exception as e:
            print(f"Error processing SHP SLD: {e}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_result([])
    
    def _find_user_styles(self, root) -> List:
        """
        Find UserStyle elements in SLD following QGIS approach with enhanced detection.
        
        Args:
            root: XML root element
            
        Returns:
            List of UserStyle elements
        """
        user_styles = []
        
        try:
            # Primary search patterns following QGIS approach
            search_patterns = [
                './/sld:UserStyle',
                './/se:UserStyle', 
                './/UserStyle',
                './/sld:NamedLayer/sld:UserStyle',
                './/NamedLayer/UserStyle'
            ]
            
            for pattern in search_patterns:
                if pattern.startswith('.//sld:') or pattern.startswith('.//se:'):
                    user_styles = root.findall(pattern, self.NAMESPACES)
                else:
                    user_styles = root.findall(pattern)
                    
                if user_styles:
                    print(f"Found {len(user_styles)} UserStyle elements using pattern: {pattern}")
                    break
            
            # Additional validation: check if UserStyle elements have valid content
            if user_styles:
                valid_styles = []
                for style in user_styles:
                    if self._has_valid_symbolizers(style):
                        valid_styles.append(style)
                    else:
                        print(f"UserStyle element found but lacks valid symbolizers")
                
                user_styles = valid_styles
                print(f"After validation: {len(user_styles)} valid UserStyle elements")
            
        except Exception as e:
            print(f"Error finding UserStyle elements: {e}")
        
        return user_styles
    
    def _has_valid_symbolizers(self, style_element) -> bool:
        """
        Check if a style element contains valid symbolizers (based on QGIS hasSldSymbolizer).
        
        Args:
            style_element: Style XML element to check
            
        Returns:
            True if element contains valid symbolizers
        """
        try:
            symbolizer_types = [
                'PointSymbolizer', 'LineSymbolizer', 'PolygonSymbolizer',
                'TextSymbolizer', 'RasterSymbolizer'
            ]
            
            for symbolizer in symbolizer_types:
                # Check with namespace
                if style_element.findall(f'.//sld:{symbolizer}', self.NAMESPACES):
                    return True
                if style_element.findall(f'.//se:{symbolizer}', self.NAMESPACES):
                    return True
                    
                # Check without namespace
                if style_element.findall(f'.//{symbolizer}'):
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking for valid symbolizers: {e}")
            return False
    
    def _find_feature_type_styles(self, user_style) -> List:
        """
        Find FeatureTypeStyle elements within a UserStyle with enhanced detection.
        
        Args:
            user_style: UserStyle XML element
            
        Returns:
            List of FeatureTypeStyle elements
        """
        feature_styles = []
        
        try:
            # Enhanced search patterns based on QGIS approach
            search_patterns = [
                'sld:FeatureTypeStyle',
                'se:FeatureTypeStyle',
                'FeatureTypeStyle',
                './sld:FeatureTypeStyle',
                './se:FeatureTypeStyle',
                './FeatureTypeStyle'
            ]
            
            for pattern in search_patterns:
                if pattern.startswith('sld:') or pattern.startswith('se:') or pattern.startswith('./sld:') or pattern.startswith('./se:'):
                    feature_styles = user_style.findall(pattern, self.NAMESPACES)
                else:
                    feature_styles = user_style.findall(pattern)
                    
                if feature_styles:
                    print(f"Found {len(feature_styles)} FeatureTypeStyle elements using pattern: {pattern}")
                    break
            
            # Validate that FeatureTypeStyles contain rules
            if feature_styles:
                valid_styles = []
                for style in feature_styles:
                    rules = self._find_rules_in_feature_style(style)
                    if rules:
                        valid_styles.append(style)
                        print(f"FeatureTypeStyle contains {len(rules)} rules")
                    else:
                        print("FeatureTypeStyle found but contains no valid rules")
                
                feature_styles = valid_styles
            
        except Exception as e:
            print(f"Error finding FeatureTypeStyle elements: {e}")
        
        return feature_styles
    
    def _find_rules_in_feature_style(self, feature_style) -> List:
        """
        Find Rule elements within a FeatureTypeStyle following QGIS validation.
        
        Args:
            feature_style: FeatureTypeStyle XML element
            
        Returns:
            List of valid Rule elements
        """
        rules = []
        
        try:
            # Try with namespace first
            rule_elements = feature_style.findall('se:Rule', self.NAMESPACES)
            
            # Fallback: try without namespace
            if not rule_elements:
                rule_elements = feature_style.findall('Rule')
            
            # Validate rules like QGIS does
            for rule in rule_elements:
                if self._is_valid_renderer_rule(rule):
                    rules.append(rule)
                else:
                    print(f"Skipping rule without valid renderer symbolizer")
            
            print(f"Found {len(rules)} valid rules in FeatureTypeStyle")
            
        except Exception as e:
            print(f"Error finding rules in FeatureTypeStyle: {e}")
        
        return rules
    
    def _is_valid_renderer_rule(self, rule) -> bool:
        """
        Check if a rule has valid renderer symbolizers (following QGIS approach).
        
        Args:
            rule: Rule XML element
            
        Returns:
            True if rule has valid renderer symbolizers
        """
        try:
            # Get all child elements of the rule
            rule_children = list(rule)
            
            for child in rule_children:
                local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                # Check if it's a symbolizer but not a TextSymbolizer (like QGIS)
                if (local_name.endswith('Symbolizer') and 
                    local_name != 'TextSymbolizer'):
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error validating rule: {e}")
            return False
    
    def _process_rules_qgis_style(self, rules: List) -> Tuple[str, Dict]:
        """
        Process rules following QGIS approach to determine renderer type and extract data.
        
        Args:
            rules: List of rule elements
            
        Returns:
            Tuple of (renderer_type, processed_data)
        """
        legend_items = []
        enum_colors = []
        valid_property_name = None
        need_rule_renderer = False
        rule_count = 0
        
        try:
            for i, rule in enumerate(rules):
                # Check if rule needs RuleRenderer (has filters or scale denominators)
                has_rule_renderer_features = self._rule_needs_rule_renderer(rule)
                if has_rule_renderer_features:
                    need_rule_renderer = True
                    print(f"Rule {i+1}: Found Filter/Scale elements - needs RuleRenderer")
                
                # Extract rule information
                rule_info = self._extract_rule_info(rule, i+1)
                if not rule_info:
                    continue
                
                name, title, color, property_name, property_values = rule_info
                
                # Validate color
                if not color:
                    print(f"Rule {i+1}: No color found, skipping")
                    continue
                
                normalized_color = self._normalize_color(color)
                if not normalized_color or normalized_color == "#000000":
                    print(f"Rule {i+1}: Invalid color '{color}', using default")
                    normalized_color = "#808080"
                
                # Count valid rules
                rule_count += 1
                
                # Generate label
                label = self._generate_rule_label(name, title, i+1)
                
                # Add to legend
                legend_items.append({
                    "title": label,
                    "color": normalized_color
                })
                
                # Process for styling
                if property_name and property_values:
                    if not valid_property_name:
                        valid_property_name = property_name
                    elif valid_property_name != property_name:
                        print(f"Warning: Multiple property names: {valid_property_name} vs {property_name}")
                    
                    for prop_value in property_values:
                        if self._is_valid_numeric_value(prop_value):
                            enum_colors.append({
                                "value": str(prop_value),
                                "color": normalized_color
                            })
                        else:
                            print(f"Warning: Invalid numeric value: '{prop_value}'")
            
            # Determine renderer type (like QGIS)
            if rule_count > 1:
                need_rule_renderer = True
                print(f"Multiple rules found ({rule_count}) - needs RuleRenderer")
            
            renderer_type = "RuleRenderer" if need_rule_renderer else "singleSymbol"
            print(f"Determined renderer type: {renderer_type}")
            
            processed_data = {
                "legend_items": legend_items,
                "enum_colors": enum_colors,
                "property_name": valid_property_name,
                "rule_count": rule_count
            }
            
            return renderer_type, processed_data
            
        except Exception as e:
            print(f"Error processing rules QGIS style: {e}")
            return "singleSymbol", {}
    
    def _rule_needs_rule_renderer(self, rule) -> bool:
        """
        Check if a rule needs RuleRenderer based on QGIS criteria.
        
        Args:
            rule: Rule XML element
            
        Returns:
            True if rule needs RuleRenderer
        """
        try:
            rule_children = list(rule)
            
            for child in rule_children:
                local_name = child.tag.split('}')[-1] if '}' in child.tag else child.tag
                
                # Check for elements that require RuleRenderer (like QGIS)
                if local_name in ['Filter', 'ElseFilter', 'MinScaleDenominator', 'MaxScaleDenominator']:
                    return True
            
            return False
            
        except Exception as e:
            print(f"Error checking rule renderer requirements: {e}")
            return False
    
    def _build_terria_result(self, renderer_type: str, processed_data: Dict) -> Dict[str, Any]:
        """
        Build TerriaJS result based on renderer type and processed data.
        
        Args:
            renderer_type: Type of renderer ("RuleRenderer" or "singleSymbol")
            processed_data: Processed styling data
            
        Returns:
            TerriaJS-compatible result dictionary
        """
        result = {}
        
        try:
            legend_items = processed_data.get("legend_items", [])
            enum_colors = processed_data.get("enum_colors", [])
            property_name = processed_data.get("property_name")
            rule_count = processed_data.get("rule_count", 0)
            
            # Always include legends if available
            if legend_items:
                result["legends"] = [{
                    "title": "Legend",
                    "items": legend_items
                }]
            
            # Create styles based on renderer type
            if renderer_type == "RuleRenderer" and enum_colors and property_name:
                # Multi-rule styling
                style_result = self._create_terria_styles(enum_colors, property_name)
                result.update(style_result)
                print(f"Created RuleRenderer styles for {len(enum_colors)} rules")
                
            elif renderer_type == "singleSymbol" and legend_items:
                # Single symbol styling
                result.update(self._create_single_symbol_styling(legend_items[0]))
                print("Created singleSymbol styling")
                
            else:
                # Fallback styling
                print(f"Using fallback styling for renderer_type: {renderer_type}")
                result.update(self._create_fallback_styling())
            
            # Always ensure we have basic TerriaJS settings
            if "forceCesiumPrimitives" not in result:
                result["forceCesiumPrimitives"] = True
            
            print(f"Built TerriaJS result with renderer type: {renderer_type}")
            
        except Exception as e:
            print(f"Error building TerriaJS result: {e}")
            result = self._create_fallback_result(processed_data.get("legend_items", []))
        
        return result
    
    def _create_single_symbol_styling(self, first_legend_item: Dict) -> Dict[str, Any]:
        """
        Create single symbol styling for simple cases.
        
        Args:
            first_legend_item: First legend item to use for styling
            
        Returns:
            Single symbol styling configuration
        """
        try:
            color = first_legend_item.get("color", "#808080")
            
            return {
                "forceCesiumPrimitives": True,
                "opacity": 0.8,
                "clampToGround": False,
                "fill": {
                    "color": color
                },
                "stroke": {
                    "color": color,
                    "width": 1
                }
            }
            
        except Exception as e:
            print(f"Error creating single symbol styling: {e}")
            return self._create_fallback_styling()
    
    def _extract_rule_info(self, rule, rule_number: int) -> Optional[Tuple[Any, Any, str, str, List[str]]]:
        """
        Extract information from a single SLD rule with robust error handling.
        
        Args:
            rule: XML rule element
            rule_number: Rule number for logging
            
        Returns:
            Tuple of (name, title, color, property_name, property_values) or None if extraction fails
        """
        try:
            # Extract basic rule elements
            name = rule.find('se:Name', self.NAMESPACES)
            title = rule.find('.//se:Title', self.NAMESPACES)
            
            # Try multiple ways to find fill color
            fill = None
            color = None
            
            # Primary: PointSymbolizer fill
            fill = rule.find('.//se:PointSymbolizer/se:Graphic/se:Mark/se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
            if fill is None:
                # Secondary: Any Fill element
                fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
            if fill is None:
                # Tertiary: PolygonSymbolizer fill
                fill = rule.find('.//se:PolygonSymbolizer/se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
            if fill is None:
                # Fallback: stroke color
                fill = rule.find('.//se:Stroke/se:SvgParameter[@name="stroke"]', self.NAMESPACES)
            
            if fill is not None and fill.text:
                color = fill.text.strip()
            
            # Extract property information
            property_name, property_values = self._extract_property_info(rule)
            
            return (name, title, color, property_name, property_values)
            
        except Exception as e:
            print(f"Error extracting rule {rule_number} info: {e}")
            return None
        """
        Extract information from a single SLD rule with robust error handling.
        
        Args:
            rule: XML rule element
            rule_number: Rule number for logging
            
        Returns:
            Tuple of (name, title, color, property_name, property_values) or None if extraction fails
        """
        try:
            # Extract basic rule elements
            name = rule.find('se:Name', self.NAMESPACES)
            title = rule.find('.//se:Title', self.NAMESPACES)
            
            # Try multiple ways to find fill color
            fill = None
            color = None
            
            # Primary: PointSymbolizer fill
            fill = rule.find('.//se:PointSymbolizer/se:Graphic/se:Mark/se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
            if fill is None:
                # Secondary: Any Fill element
                fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
            if fill is None:
                # Tertiary: PolygonSymbolizer fill
                fill = rule.find('.//se:PolygonSymbolizer/se:Fill/se:SvgParameter[@name="fill"]', self.NAMESPACES)
            if fill is None:
                # Fallback: stroke color
                fill = rule.find('.//se:Stroke/se:SvgParameter[@name="stroke"]', self.NAMESPACES)
            
            if fill is not None and fill.text:
                color = fill.text.strip()
            
            # Extract property information
            property_name, property_values = self._extract_property_info(rule)
            
            return (name, title, color, property_name, property_values)
            
        except Exception as e:
            print(f"Error extracting rule {rule_number} info: {e}")
            return None
    
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
    
    def _extract_property_info(self, rule) -> Tuple[Optional[str], List[str]]:
        """
        Extract property name and values from rule filters.
        
        Args:
            rule: XML rule element
            
        Returns:
            Tuple of (property_name, property_values)
        """
        property_name = None
        property_values = []
        
        try:
            # Look for complex AND filters first
            and_filter = rule.find('.//ogc:And', self.NAMESPACES)
            
            if and_filter is not None:
                property_name, property_values = self._extract_range_filter_info(and_filter)
            
            # Fallback to simple property conditions
            if not property_name:
                property_name_elem = rule.find('.//ogc:PropertyName', self.NAMESPACES)
                property_value_elem = rule.find('.//ogc:Literal', self.NAMESPACES)
                
                if property_name_elem is not None and property_name_elem.text:
                    property_name = property_name_elem.text.strip()
                    
                if property_value_elem is not None and property_value_elem.text:
                    property_values.append(property_value_elem.text.strip())
            
            # Try without namespaces as fallback
            if not property_name:
                property_name_elem = rule.find('.//PropertyName')
                if property_name_elem is not None and property_name_elem.text:
                    property_name = property_name_elem.text.strip()
                    
                    property_value_elem = rule.find('.//Literal')
                    if property_value_elem is not None and property_value_elem.text:
                        property_values.append(property_value_elem.text.strip())
            
        except Exception as e:
            print(f"Error extracting property info: {e}")
        
        return property_name, property_values
    
    def _extract_range_filter_info(self, and_filter) -> Tuple[Optional[str], List[str]]:
        """
        Extract property information from range-based AND filters with enhanced error handling.
        Based on QGIS approach with support for various filter patterns.
        
        Args:
            and_filter: XML AND filter element
            
        Returns:
            Tuple of (property_name, property_values)
        """
        property_name = None
        property_values = []
        
        try:
            print(f"Processing AND filter with {len(list(and_filter))} children")
            
            # Enhanced property name extraction with multiple fallbacks
            property_name = self._extract_property_name_from_filter(and_filter)
            
            if not property_name:
                print("No property name found in AND filter")
                return None, []
            
            print(f"Found property name: {property_name}")
            
            # Extract range bounds with better error handling
            range_info = self._extract_range_bounds(and_filter)
            
            if range_info:
                min_val, max_val = range_info
                
                # Format the range appropriately
                if min_val is not None and max_val is not None:
                    # Create range representation
                    if min_val == max_val:
                        property_values = [str(min_val)]
                    else:
                        # Use max value as the primary value for TerriaJS bins
                        property_values = [str(max_val)]
                    
                    print(f"Extracted range: {min_val} to {max_val}")
                    print(f"Property values: {property_values}")
                elif min_val is not None:
                    property_values = [str(min_val)]
                    print(f"Extracted minimum value: {min_val}")
                elif max_val is not None:
                    property_values = [str(max_val)]
                    print(f"Extracted maximum value: {max_val}")
            
            # Additional pattern matching for edge cases
            if not property_values:
                property_values = self._extract_fallback_values(and_filter, property_name)
            
        except Exception as e:
            print(f"Error extracting range filter info: {e}")
            import traceback
            traceback.print_exc()
        
        return property_name, property_values
    
    def _extract_property_name_from_filter(self, filter_element) -> Optional[str]:
        """
        Extract property name from filter element with multiple search strategies.
        
        Args:
            filter_element: Filter XML element
            
        Returns:
            Property name or None
        """
        try:
            # Strategy 1: Direct PropertyName search with namespaces
            for ns_prefix in ['ogc', 'se', 'sld']:
                property_names = filter_element.findall(f'.//{ns_prefix}:PropertyName', self.NAMESPACES)
                for prop in property_names:
                    if prop.text and prop.text.strip():
                        return prop.text.strip()
            
            # Strategy 2: Search without namespaces
            property_names = filter_element.findall('.//PropertyName')
            for prop in property_names:
                if prop.text and prop.text.strip():
                    return prop.text.strip()
            
            # Strategy 3: Search in comparison operators
            comparison_ops = [
                'PropertyIsEqualTo', 'PropertyIsGreaterThan', 'PropertyIsLessThan',
                'PropertyIsGreaterThanOrEqualTo', 'PropertyIsLessThanOrEqualTo',
                'PropertyIsBetween'
            ]
            
            for op in comparison_ops:
                # With namespaces
                elements = filter_element.findall(f'.//ogc:{op}', self.NAMESPACES)
                for elem in elements:
                    prop_elem = elem.find('ogc:PropertyName', self.NAMESPACES)
                    if prop_elem is not None and prop_elem.text:
                        return prop_elem.text.strip()
                
                # Without namespaces
                elements = filter_element.findall(f'.//{op}')
                for elem in elements:
                    prop_elem = elem.find('PropertyName')
                    if prop_elem is not None and prop_elem.text:
                        return prop_elem.text.strip()
            
        except Exception as e:
            print(f"Error extracting property name: {e}")
        
        return None
    
    def _extract_range_bounds(self, and_filter) -> Optional[Tuple[Optional[float], Optional[float]]]:
        """
        Extract minimum and maximum bounds from AND filter.
        
        Args:
            and_filter: AND filter element
            
        Returns:
            Tuple of (min_val, max_val) or None
        """
        try:
            min_val = None
            max_val = None
            
            # Search patterns for different comparison operators
            patterns = [
                ('PropertyIsGreaterThan', 'min'),
                ('PropertyIsGreaterThanOrEqualTo', 'min'),
                ('PropertyIsLessThan', 'max'),
                ('PropertyIsLessThanOrEqualTo', 'max')
            ]
            
            for pattern, bound_type in patterns:
                # Try with namespaces
                elements = and_filter.findall(f'.//ogc:{pattern}', self.NAMESPACES)
                for elem in elements:
                    literal = elem.find('ogc:Literal', self.NAMESPACES)
                    if literal is not None and literal.text:
                        value = self._safe_float_conversion(literal.text)
                        if value is not None:
                            if bound_type == 'min':
                                min_val = value
                            else:
                                max_val = value
                
                # Try without namespaces if not found
                if (bound_type == 'min' and min_val is None) or (bound_type == 'max' and max_val is None):
                    elements = and_filter.findall(f'.//{pattern}')
                    for elem in elements:
                        literal = elem.find('Literal')
                        if literal is not None and literal.text:
                            value = self._safe_float_conversion(literal.text)
                            if value is not None:
                                if bound_type == 'min':
                                    min_val = value
                                else:
                                    max_val = value
            
            # Special case: PropertyIsBetween
            between_elem = and_filter.find('.//ogc:PropertyIsBetween', self.NAMESPACES)
            if between_elem is None:
                between_elem = and_filter.find('.//PropertyIsBetween')
            
            if between_elem is not None:
                lower = between_elem.find('.//ogc:LowerBoundary/ogc:Literal', self.NAMESPACES)
                upper = between_elem.find('.//ogc:UpperBoundary/ogc:Literal', self.NAMESPACES)
                
                if lower is None:
                    lower = between_elem.find('.//LowerBoundary/Literal')
                if upper is None:
                    upper = between_elem.find('.//UpperBoundary/Literal')
                
                if lower is not None and lower.text:
                    min_val = self._safe_float_conversion(lower.text)
                if upper is not None and upper.text:
                    max_val = self._safe_float_conversion(upper.text)
            
            if min_val is not None or max_val is not None:
                return (min_val, max_val)
            
        except Exception as e:
            print(f"Error extracting range bounds: {e}")
        
        return None
    
    def _extract_fallback_values(self, filter_element, property_name: str) -> List[str]:
        """
        Extract values using fallback methods when standard range extraction fails.
        
        Args:
            filter_element: Filter XML element
            property_name: Property name to look for
            
        Returns:
            List of extracted values
        """
        values = []
        
        try:
            # Look for any Literal values in the filter
            literals = filter_element.findall('.//ogc:Literal', self.NAMESPACES)
            if not literals:
                literals = filter_element.findall('.//Literal')
            
            for literal in literals:
                if literal.text and literal.text.strip():
                    # Try to convert to float for validation
                    value = self._safe_float_conversion(literal.text.strip())
                    if value is not None:
                        values.append(str(value))
                    else:
                        # Keep non-numeric values too
                        values.append(literal.text.strip())
            
            # Remove duplicates while preserving order
            seen = set()
            unique_values = []
            for value in values:
                if value not in seen:
                    seen.add(value)
                    unique_values.append(value)
            
            if unique_values:
                print(f"Fallback extraction found values: {unique_values}")
            
            return unique_values
            
        except Exception as e:
            print(f"Error in fallback value extraction: {e}")
            return []
    
    def _safe_float_conversion(self, value: str) -> Optional[float]:
        """
        Safely convert string to float with error handling.
        
        Args:
            value: String value to convert
            
        Returns:
            Float value or None if conversion fails
        """
        if not value:
            return None
        
        try:
            # Clean the value
            cleaned_value = value.strip()
            if not cleaned_value:
                return None
            
            # Handle scientific notation and very long decimals
            return float(cleaned_value)
            
        except (ValueError, OverflowError) as e:
            print(f"Warning: Could not convert '{value}' to float: {e}")
            return None
    
    def _is_valid_numeric_value(self, value: str) -> bool:
        """
        Check if a string represents a valid numeric value.
        
        Args:
            value: String to check
            
        Returns:
            True if value is numeric, False otherwise
        """
        if not value or not isinstance(value, str):
            return False
        
        return self._safe_float_conversion(value) is not None
    
    def _generate_rule_label(self, name, title, rule_number: int) -> str:
        """
        Generate a meaningful label for a rule.
        
        Args:
            name: Rule name element
            title: Rule title element
            rule_number: Rule number for fallback
            
        Returns:
            Generated label string
        """
        label = ""
        
        if title is not None and title.text and title.text.strip():
            label = title.text.strip()
        elif name is not None and name.text and name.text.strip():
            label = name.text.strip()
        else:
            label = f"Style {rule_number}"
        
        # Ensure label is not empty and reasonable length
        if not label or len(label.strip()) == 0:
            label = f"Style {rule_number}"
        elif len(label) > 100:
            label = label[:97] + "..."
        
        return label
    
    def _create_terria_styles(self, enum_colors: List[Dict], property_name: str) -> Dict[str, Any]:
        """
        Create TerriaJS-compatible style configuration with enhanced validation.
        Based on QGIS best practices for reliable styling.
        
        Args:
            enum_colors: List of color/value mappings
            property_name: Property name for styling
            
        Returns:
            TerriaJS style configuration
        """
        if not enum_colors or not property_name:
            print("Cannot create TerriaJS styles: missing colors or property name")
            return {}
        
        try:
            # Validate and sort enum colors
            valid_colors = self._validate_enum_colors(enum_colors)
            if not valid_colors:
                print("No valid colors found after validation")
                return {}
            
            # Sort by numeric value for proper gradient
            sorted_colors = self._sort_enum_colors(valid_colors)
            
            # Extract bin maximums and colors for TerriaJS
            bin_maximums = []
            colors = []
            
            for item in sorted_colors:
                try:
                    # Convert value to float for binMaximums
                    value = self._safe_float_conversion(str(item['value']))
                    if value is not None:
                        bin_maximums.append(value)
                        colors.append(item['color'])
                    else:
                        print(f"Skipping invalid numeric value: {item['value']}")
                except Exception as e:
                    print(f"Error processing color item {item}: {e}")
                    continue
            
            if not bin_maximums or not colors:
                print("No valid bin maximums or colors after processing")
                return {}
            
            # Ensure we have matching arrays
            if len(bin_maximums) != len(colors):
                print(f"Mismatch between bin_maximums ({len(bin_maximums)}) and colors ({len(colors)})")
                min_length = min(len(bin_maximums), len(colors))
                bin_maximums = bin_maximums[:min_length]
                colors = colors[:min_length]
            
            # Create TerriaJS configuration
            config = {
                "scale": {
                    "type": "enum",
                    "binMaximums": bin_maximums,
                    "binColors": colors,
                    "nullColor": self.DEFAULTS['fill_color']
                },
                "column": property_name,
                "colorProperty": property_name,
                "useRealValue": True
            }
            
            print(f"Created TerriaJS config with {len(bin_maximums)} bins")
            print(f"Bin maximums: {bin_maximums}")
            print(f"Colors: {colors}")
            
            return config
            
        except Exception as e:
            print(f"Error creating TerriaJS styles: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _validate_enum_colors(self, enum_colors: List[Dict]) -> List[Dict]:
        """
        Validate enum colors for TerriaJS compatibility.
        
        Args:
            enum_colors: List of color dictionaries
            
        Returns:
            List of validated color dictionaries
        """
        valid_colors = []
        
        for i, item in enumerate(enum_colors):
            try:
                # Validate required fields
                if not isinstance(item, dict):
                    print(f"Item {i}: Not a dictionary, skipping")
                    continue
                
                if 'value' not in item or 'color' not in item:
                    print(f"Item {i}: Missing required fields (value/color), skipping")
                    continue
                
                # Validate value
                value = item['value']
                if value is None or str(value).strip() == '':
                    print(f"Item {i}: Empty value, skipping")
                    continue
                
                # Validate color
                color = item['color']
                if not color or not isinstance(color, str):
                    print(f"Item {i}: Invalid color '{color}', skipping")
                    continue
                
                # Normalize color
                normalized_color = self._normalize_color(color)
                if normalized_color == "#000000" and color.lower() not in ['black', '#000000', '#000']:
                    print(f"Item {i}: Color '{color}' normalized to black, might be invalid")
                
                # Create validated item
                validated_item = {
                    'value': value,
                    'color': normalized_color,
                    'originalColor': color
                }
                
                valid_colors.append(validated_item)
                
            except Exception as e:
                print(f"Error validating item {i}: {e}")
                continue
        
        print(f"Validated {len(valid_colors)} out of {len(enum_colors)} color items")
        return valid_colors
    
    def _detect_sld_version(self, root) -> str:
        """
        Detect SLD version from XML root element.
        
        Args:
            root: XML root element
            
        Returns:
            SLD version string
        """
        try:
            # Check version attribute
            version = root.get('version')
            if version:
                return version
            
            # Check schema location for version hints
            schema_location = root.get('{http://www.w3.org/2001/XMLSchema-instance}schemaLocation')
            if schema_location:
                if '1.0.0' in schema_location:
                    return '1.0.0'
                elif '1.1.0' in schema_location:
                    return '1.1.0'
            
            # Check namespace URIs
            for prefix, uri in self.NAMESPACES.items():
                if uri in str(ET.tostring(root, encoding='unicode')[:1000]):
                    if 'se' in uri:
                        return '1.1.0'  # SE namespace indicates SLD 1.1
                    elif 'sld' in uri:
                        return '1.0.0'  # Traditional SLD namespace
            
            # Default fallback
            return 'unknown'
            
        except Exception as e:
            print(f"Error detecting SLD version: {e}")
            return 'unknown'
    
    def _enhance_error_resilience(self, root) -> bool:
        """
        Apply error resilience enhancements based on SLD content analysis.
        
        Args:
            root: XML root element
            
        Returns:
            True if enhancements were applied successfully
        """
        try:
            sld_version = self._detect_sld_version(root)
            print(f"Detected SLD version: {sld_version}")
            
            # Count different symbolizer types
            symbolizer_counts = self._count_symbolizers(root)
            print(f"Symbolizers found: {symbolizer_counts}")
            
            # Check for complex filters
            has_complex_filters = self._has_complex_filters(root)
            if has_complex_filters:
                print("Complex filters detected - using enhanced processing")
            
            # Validate structure integrity
            structure_valid = self._validate_sld_structure(root)
            if not structure_valid:
                print("Warning: SLD structure validation issues detected")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error in error resilience enhancement: {e}")
            return False
    
    def _count_symbolizers(self, root) -> Dict[str, int]:
        """Count different types of symbolizers in the SLD."""
        symbolizer_types = [
            'PointSymbolizer', 'LineSymbolizer', 'PolygonSymbolizer',
            'TextSymbolizer', 'RasterSymbolizer'
        ]
        
        counts = {}
        for symbolizer in symbolizer_types:
            count = 0
            count += len(root.findall(f'.//sld:{symbolizer}', self.NAMESPACES))
            count += len(root.findall(f'.//se:{symbolizer}', self.NAMESPACES))
            count += len(root.findall(f'.//{symbolizer}'))
            counts[symbolizer] = count
        
        return counts
    
    def _has_complex_filters(self, root) -> bool:
        """Check if SLD contains complex filters that need special handling."""
        try:
            # Look for AND/OR filters
            complex_filters = (
                len(root.findall('.//ogc:And', self.NAMESPACES)) +
                len(root.findall('.//ogc:Or', self.NAMESPACES)) +
                len(root.findall('.//And')) +
                len(root.findall('.//Or'))
            )
            
            return complex_filters > 0
            
        except Exception:
            return False
    
    def _validate_sld_structure(self, root) -> bool:
        """Validate basic SLD structure integrity."""
        try:
            # Check for required root element
            if root.tag not in ['StyledLayerDescriptor', '{http://www.opengis.net/sld}StyledLayerDescriptor']:
                print("Invalid root element")
                return False
            
            # Check for at least one layer
            layers = (
                root.findall('.//sld:NamedLayer', self.NAMESPACES) +
                root.findall('.//sld:UserLayer', self.NAMESPACES) +
                root.findall('.//NamedLayer') +
                root.findall('.//UserLayer')
            )
            
            if not layers:
                print("No layers found in SLD")
                return False
            
            return True
            
        except Exception as e:
            print(f"Error validating SLD structure: {e}")
            return False
    
    def _safe_sort_enum_colors(self, enum_colors: List[Dict]) -> List[Dict]:
        """
        Safely sort enum colors by numeric value.
        
        Args:
            enum_colors: List of color mappings
            
        Returns:
            Sorted list of color mappings
        """
        def sort_key(item):
            # Extraer valor numérico para ordenamiento, pero preservar el valor original
            value = self._extract_numeric_value(item.get('value', ''))
            return value if value is not None else float('inf')
        
        # Crear una copia para no modificar los valores originales
        sorted_colors = sorted(enum_colors, key=sort_key)
        return sorted_colors
    
    def _is_reasonable_numeric_value(self, value: float) -> bool:
        """
        Check if a numeric value is reasonable for styling.
        
        Args:
            value: Numeric value to check
            
        Returns:
            True if value is reasonable, False otherwise
        """
        if not isinstance(value, (int, float)):
            return False
        
        # Check for infinity and NaN
        if not isinstance(value, bool) and (value != value or abs(value) == float('inf')):
            return False
        
        # Check for extremely large or small values
        if abs(value) > 1e10 or (value != 0 and abs(value) < 1e-10):
            return False
        
        return True
    
    def _sanitize_style_id(self, style_id: str) -> str:
        """
        Sanitize style ID to ensure it's valid for TerriaJS.
        
        Args:
            style_id: Original style ID
            
        Returns:
            Sanitized style ID
        """
        if not style_id:
            return "default_style"
        
        # Remove invalid characters and limit length
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', str(style_id))
        sanitized = sanitized[:50]  # Limit length
        
        # Ensure it doesn't start with a number
        if sanitized and sanitized[0].isdigit():
            sanitized = f"style_{sanitized}"
        
        return sanitized if sanitized else "default_style"
    
    def _create_fallback_result(self, legend_items: List[Dict]) -> Dict[str, Any]:
        """
        Create a fallback result when main processing fails.
        
        Args:
            legend_items: List of legend items
            
        Returns:
            Fallback result dictionary
        """
        result = {}
        
        if legend_items:
            result["legends"] = [{
                "title": "Legend",
                "items": legend_items
            }]
        
        # Add basic styling to ensure something is displayed
        result.update(self._create_fallback_styling())
        
        return result
    
    def _create_fallback_styling(self) -> Dict[str, Any]:
        """
        Create fallback styling when specific styling fails.
        
        Returns:
            Basic styling configuration
        """
        return {
            "forceCesiumPrimitives": True,
            "opacity": 0.8,
            "clampToGround": False
        }
    
    def process_shp_sld_from_content(self, sld_content: str) -> Dict[str, Any]:
        """
        Process SLD content directly from string with enhanced error handling.
        
        Args:
            sld_content: SLD XML content as string
            
        Returns:
            Dictionary with style information for Shapefile
        """
        if not sld_content or not isinstance(sld_content, str):
            print("Invalid SLD content provided")
            return {}
        
        try:
            # Parse XML with enhanced error handling
            root = self.parse_sld_xml(sld_content.encode('utf-8'))
            if root is None:
                print("Failed to parse SLD XML content")
                return {}
            
            # Apply error resilience enhancements
            if not self._enhance_error_resilience(root):
                print("Warning: Error resilience enhancements failed")
            
            # Process using existing method workflow
            user_styles = self._find_user_styles(root)
            if not user_styles:
                print("No UserStyle elements found in SLD content")
                return self._create_fallback_result([])
            
            # Get the first user style and extract rules
            user_style = user_styles[0]
            feature_styles = self._find_feature_type_styles(user_style)
            
            if not feature_styles:
                print("No FeatureTypeStyle found in UserStyle")
                return self._create_fallback_result([])
            
            # Extract rules from the first feature style
            rules = self._extract_rules_from_feature_style(feature_styles[0])
            
            if not rules:
                print("No rules found in FeatureTypeStyle")
                return self._create_fallback_result([])
            
            # Process rules using existing logic
            property_name, table_style = self._process_rules_qgis_style(rules)
            legends = self._create_legend_from_rules(rules, property_name)
            
            # Create result following the existing pattern
            result = {
                'tableStyle': table_style,
                'legends': legends
            }
            
            # Add basic styling
            result.update(self._create_fallback_styling())
            
            return result
            
        except Exception as e:
            print(f"Error processing SLD content: {e}")
            import traceback
            traceback.print_exc()
            return self._create_fallback_result([])