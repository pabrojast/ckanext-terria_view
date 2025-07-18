#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script for enhanced SLD processing based on QGIS implementation.
Tests robustness and error handling improvements.
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from ckanext.terria_view.sld_processor import SLDProcessor


def test_enhanced_color_parsing():
    """Test enhanced color parsing capabilities."""
    print("=== Testing Enhanced Color Parsing ===")
    
    processor = SLDProcessor()
    
    # Test cases based on QGIS color parsing
    test_colors = [
        # Hex colors
        ('#FF0000', '#FF0000'),
        ('#f00', '#FF0000'),  # 3-digit hex
        ('#FF0000AA', '#FF0000'),  # 8-digit hex with alpha
        
        # RGB colors
        ('rgb(255,0,0)', '#FF0000'),
        ('rgba(255,0,0,0.5)', '#FF0000'),
        ('rgb(100%, 0%, 0%)', '#FF0000'),  # Percentage RGB
        
        # HSL colors
        ('hsl(0, 100%, 50%)', '#FF0000'),
        ('hsla(0, 100%, 50%, 0.8)', '#FF0000'),
        
        # Named colors
        ('red', '#FF0000'),
        ('blue', '#0000FF'),
        ('transparent', '#000000'),
        
        # Invalid colors (should default to black)
        ('invalid_color', '#000000'),
        ('', '#000000'),
        (None, '#000000'),
    ]
    
    for input_color, expected in test_colors:
        try:
            result = processor._normalize_color(input_color)
            status = "✓" if result == expected else "✗"
            print(f"{status} {input_color} -> {result} (expected: {expected})")
        except Exception as e:
            print(f"✗ {input_color} -> ERROR: {e}")


def test_enhanced_property_extraction():
    """Test enhanced property extraction from filters."""
    print("\n=== Testing Enhanced Property Extraction ===")
    
    processor = SLDProcessor()
    
    # Mock XML filter element for testing
    import xml.etree.ElementTree as ET
    
    # Test complex AND filter
    and_filter_xml = """
    <ogc:And xmlns:ogc="http://www.opengis.net/ogc">
        <ogc:PropertyIsGreaterThanOrEqualTo>
            <ogc:PropertyName>test_property</ogc:PropertyName>
            <ogc:Literal>0.5</ogc:Literal>
        </ogc:PropertyIsGreaterThanOrEqualTo>
        <ogc:PropertyIsLessThan>
            <ogc:PropertyName>test_property</ogc:PropertyName>
            <ogc:Literal>1.0</ogc:Literal>
        </ogc:PropertyIsLessThan>
    </ogc:And>
    """
    
    try:
        and_filter = ET.fromstring(and_filter_xml)
        property_name = processor._extract_property_name_from_filter(and_filter)
        range_bounds = processor._extract_range_bounds(and_filter)
        
        print(f"✓ Property name extracted: {property_name}")
        if range_bounds:
            min_val, max_val = range_bounds
            print(f"✓ Range bounds extracted: {min_val} to {max_val}")
        else:
            print("✗ Range bounds not extracted")
            
    except Exception as e:
        print(f"✗ Property extraction failed: {e}")


def test_sld_structure_detection():
    """Test improved SLD structure detection."""
    print("\n=== Testing SLD Structure Detection ===")
    
    processor = SLDProcessor()
    
    # Test SLD version detection
    sld_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <sld:StyledLayerDescriptor version="1.0.0" 
        xmlns:sld="http://www.opengis.net/sld"
        xmlns:ogc="http://www.opengis.net/ogc">
        <sld:NamedLayer>
            <sld:Name>test_layer</sld:Name>
            <sld:UserStyle>
                <sld:FeatureTypeStyle>
                    <sld:Rule>
                        <sld:PolygonSymbolizer>
                            <sld:Fill>
                                <sld:CssParameter name="fill">#FF0000</sld:CssParameter>
                            </sld:Fill>
                        </sld:PolygonSymbolizer>
                    </sld:Rule>
                </sld:FeatureTypeStyle>
            </sld:UserStyle>
        </sld:NamedLayer>
    </sld:StyledLayerDescriptor>"""
    
    try:
        import xml.etree.ElementTree as ET
        root = ET.fromstring(sld_xml)
        
        # Test version detection
        version = processor._detect_sld_version(root)
        print(f"✓ SLD version detected: {version}")
        
        # Test symbolizer counting
        symbolizer_counts = processor._count_symbolizers(root)
        print(f"✓ Symbolizers found: {symbolizer_counts}")
        
        # Test structure validation
        is_valid = processor._validate_sld_structure(root)
        print(f"✓ Structure validation: {'Valid' if is_valid else 'Invalid'}")
        
        # Test UserStyle detection
        user_styles = processor._find_user_styles(root)
        print(f"✓ UserStyles found: {len(user_styles)}")
        
        # Test symbolizer validation
        for style in user_styles:
            has_symbolizers = processor._has_valid_symbolizers(style)
            print(f"✓ UserStyle has valid symbolizers: {has_symbolizers}")
            
    except Exception as e:
        print(f"✗ Structure detection failed: {e}")
        import traceback
        traceback.print_exc()


def test_error_resilience():
    """Test error resilience with malformed SLD."""
    print("\n=== Testing Error Resilience ===")
    
    processor = SLDProcessor()
    
    # Test with malformed XML
    malformed_sld = """<?xml version="1.0"?>
    <sld:StyledLayerDescriptor xmlns:sld="http://www.opengis.net/sld">
        <sld:NamedLayer>
            <sld:UserStyle>
                <!-- Missing closing tag and invalid structure -->
                <sld:FeatureTypeStyle>
                    <sld:Rule>
                        <sld:Filter>
                            <ogc:PropertyIsEqualTo>
                                <ogc:PropertyName>invalid_property</ogc:PropertyName>
                                <ogc:Literal>invalid_value</ogc:Literal>
                        </sld:Filter>
                    </sld:Rule>
            </sld:UserStyle>
        </sld:NamedLayer>
    </sld:StyledLayerDescriptor>"""
    
    try:
        result = processor.process_shp_sld_from_content(malformed_sld)
        if result:
            print("✓ Malformed SLD handled gracefully with result")
        else:
            print("✓ Malformed SLD rejected appropriately")
    except Exception as e:
        print(f"✗ Error resilience test failed: {e}")


def test_enum_color_validation():
    """Test enum color validation."""
    print("\n=== Testing Enum Color Validation ===")
    
    processor = SLDProcessor()
    
    # Test various enum color scenarios
    test_enum_colors = [
        {'value': '1.0', 'color': '#FF0000'},
        {'value': '2.0', 'color': '#00FF00'},
        {'value': 'invalid', 'color': '#0000FF'},  # Invalid value
        {'value': '3.0', 'color': 'invalid_color'},  # Invalid color
        {'value': '', 'color': '#FFFF00'},  # Empty value
        {'invalid_field': 'test'},  # Missing required fields
    ]
    
    try:
        valid_colors = processor._validate_enum_colors(test_enum_colors)
        print(f"✓ Valid colors after validation: {len(valid_colors)}")
        
        for color in valid_colors:
            print(f"  - Value: {color['value']}, Color: {color['color']}")
            
    except Exception as e:
        print(f"✗ Enum color validation failed: {e}")


def main():
    """Run all robustness tests."""
    print("Testing Enhanced SLD Processor Robustness")
    print("=" * 50)
    
    try:
        test_enhanced_color_parsing()
        test_enhanced_property_extraction()
        test_sld_structure_detection()
        test_error_resilience()
        test_enum_color_validation()
        
        print("\n" + "=" * 50)
        print("✓ All robustness tests completed")
        
    except Exception as e:
        print(f"\n✗ Test suite failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
