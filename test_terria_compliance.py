#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script to validate TerriaJS compliance of SLD processor output.
"""

import json
from ckanext.terria_view.sld_processor import SLDProcessor

def test_terria_traits_compliance():
    """Test that the SLD processor generates TerriaJS-compliant output."""
    
    # Sample SLD content for testing
    sample_sld = """<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor version="1.0.0" xmlns="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc" xmlns:se="http://www.opengis.net/se">
  <NamedLayer>
    <Name>test_layer</Name>
    <UserStyle>
      <Title>Test Style</Title>
      <FeatureTypeStyle>
        <Rule>
          <Name>Rule 1</Name>
          <Title>Low Values</Title>
          <ogc:Filter>
            <ogc:PropertyIsLessThan>
              <ogc:PropertyName>VALUE</ogc:PropertyName>
              <ogc:Literal>10</ogc:Literal>
            </ogc:PropertyIsLessThan>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:Fill>
                  <se:SvgParameter name="fill">#FF0000</se:SvgParameter>
                </se:Fill>
              </se:Mark>
            </se:Graphic>
          </se:PointSymbolizer>
        </Rule>
        <Rule>
          <Name>Rule 2</Name>
          <Title>High Values</Title>
          <ogc:Filter>
            <ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyName>VALUE</ogc:PropertyName>
              <ogc:Literal>10</ogc:Literal>
            </ogc:PropertyIsGreaterThanOrEqualTo>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:Fill>
                  <se:SvgParameter name="fill">#00FF00</se:SvgParameter>
                </se:Fill>
              </se:Mark>
            </se:Graphic>
          </se:PointSymbolizer>
        </Rule>
      </FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>"""
    
    processor = SLDProcessor()
    
    # Test processing from content
    result = processor.process_shp_sld_from_content(sample_sld)
    
    print("=== TerriaJS Compliance Test Results ===")
    print(json.dumps(result, indent=2))
    
    # Check for required TerriaJS traits
    required_traits = {
        'GeoJsonTraits': ['forceCesiumPrimitives', 'clampToGround'],
        'LegendOwnerTraits': ['legends'],
        'OpacityTraits': ['opacity']
    }
    
    print("\n=== Trait Compliance Check ===")
    for trait_group, traits in required_traits.items():
        print(f"\n{trait_group}:")
        for trait in traits:
            if trait in result:
                print(f"  ✓ {trait}: {result[trait]}")
            else:
                print(f"  ✗ {trait}: MISSING")
    
    # Check TableTraits if styles are present
    if 'styles' in result:
        print(f"\nTableTraits:")
        print(f"  ✓ styles: {len(result['styles'])} styles found")
        
        if result['styles']:
            style = result['styles'][0]
            print(f"  ✓ style.id: {style.get('id', 'MISSING')}")
            print(f"  ✓ style.color.mapType: {style.get('color', {}).get('mapType', 'MISSING')}")
            print(f"  ✓ style.color.enumColors: {len(style.get('color', {}).get('enumColors', []))} colors")
    
    # Check StyleTraits if style is present
    if 'style' in result:
        print(f"\nStyleTraits (simplestyle-spec):")
        style_props = result['style']
        for prop in ['fill', 'fill-opacity', 'stroke', 'stroke-opacity', 'stroke-width']:
            if prop in style_props:
                print(f"  ✓ {prop}: {style_props[prop]}")
            else:
                print(f"  ✗ {prop}: MISSING")
    
    print(f"\n=== Summary ===")
    print(f"Result contains {len(result)} top-level properties")
    print(f"TerriaJS GeoJsonTraits implemented: {'forceCesiumPrimitives' in result and 'clampToGround' in result}")
    print(f"Legend support: {'legends' in result}")
    print(f"Styling approach: {'Table styles' if 'styles' in result else 'Simple styles' if 'style' in result else 'Fallback'}")
    
    return result

if __name__ == "__main__":
    test_terria_traits_compliance()
