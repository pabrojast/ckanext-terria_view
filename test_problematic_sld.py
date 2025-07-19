# -*- coding: utf-8 -*-
"""
Test del SLD proporcionado que está causando el error.
"""

import sys
import os
sys.path.insert(0, '.')

from ckanext.terria_view.sld_processor import SLDProcessor

# SLD content from the error
sld_content = '''<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:se="http://www.opengis.net/se" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" version="1.1.0" xsi:schemaLocation="http://www.opengis.net/sld http://schemas.opengis.net/sld/1.1.0/StyledLayerDescriptor.xsd" xmlns:ogc="http://www.opengis.net/ogc" xmlns:xlink="http://www.w3.org/1999/xlink">
  <NamedLayer>
    <se:Name>HealthFacilities_LSS_ChimaniChipinge</se:Name>
    <UserStyle>
      <se:Name>HealthFacilities_LSS_ChimaniChipinge</se:Name>
      <se:FeatureTypeStyle>
        <se:Rule>
          <se:Name>very low [lower  40%]</se:Name>
          <se:Description>
            <se:Title>very low [lower  40%]</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.20000000000000001</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:WellKnownName>circle</se:WellKnownName>
                <se:Fill>
                  <se:SvgParameter name="fill">#ffffbf</se:SvgParameter>
                </se:Fill>
                <se:Stroke>
                  <se:SvgParameter name="stroke">#4d4d4d</se:SvgParameter>
                  <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
                </se:Stroke>
              </se:Mark>
              <se:Size>6</se:Size>
            </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>low [top 60%]</se:Name>
          <se:Description>
            <se:Title>low [top 60%]</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.20000000000000001</ogc:Literal>
              </ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.5</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:WellKnownName>circle</se:WellKnownName>
                <se:Fill>
                  <se:SvgParameter name="fill">#fee787</se:SvgParameter>
                </se:Fill>
                <se:Stroke>
                  <se:SvgParameter name="stroke">#4d4d4d</se:SvgParameter>
                  <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
                </se:Stroke>
              </se:Mark>
              <se:Size>6</se:Size>
            </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>moderate [top 30%]</se:Name>
          <se:Description>
            <se:Title>moderate [top 30%]</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.5</ogc:Literal>
              </ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.68000000000000005</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:WellKnownName>circle</se:WellKnownName>
                <se:Fill>
                  <se:SvgParameter name="fill">#fd8d3c</se:SvgParameter>
                </se:Fill>
                <se:Stroke>
                  <se:SvgParameter name="stroke">#4d4d4d</se:SvgParameter>
                  <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
                </se:Stroke>
              </se:Mark>
              <se:Size>6</se:Size>
            </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>high [top 10%]</se:Name>
          <se:Description>
            <se:Title>high [top 10%]</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.68000000000000005</ogc:Literal>
              </ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.71999999999999997</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:WellKnownName>circle</se:WellKnownName>
                <se:Fill>
                  <se:SvgParameter name="fill">#f03b20</se:SvgParameter>
                </se:Fill>
                <se:Stroke>
                  <se:SvgParameter name="stroke">#4d4d4d</se:SvgParameter>
                  <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
                </se:Stroke>
              </se:Mark>
              <se:Size>6</se:Size>
            </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <se:Name>very high [top 5%]</se:Name>
          <se:Description>
            <se:Title>very high [top 5%]</se:Title>
          </se:Description>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:And>
              <ogc:PropertyIsGreaterThan>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>0.71999999999999997</ogc:Literal>
              </ogc:PropertyIsGreaterThan>
              <ogc:PropertyIsLessThanOrEqualTo>
                <ogc:PropertyName>LSSCombine</ogc:PropertyName>
                <ogc:Literal>1</ogc:Literal>
              </ogc:PropertyIsLessThanOrEqualTo>
            </ogc:And>
          </ogc:Filter>
          <se:PointSymbolizer>
            <se:Graphic>
              <se:Mark>
                <se:WellKnownName>circle</se:WellKnownName>
                <se:Fill>
                  <se:SvgParameter name="fill">#bd0026</se:SvgParameter>
                </se:Fill>
                <se:Stroke>
                  <se:SvgParameter name="stroke">#4d4d4d</se:SvgParameter>
                  <se:SvgParameter name="stroke-width">0.5</se:SvgParameter>
                </se:Stroke>
              </se:Mark>
              <se:Size>6</se:Size>
            </se:Graphic>
          </se:PointSymbolizer>
        </se:Rule>
        <se:Rule>
          <ogc:Filter xmlns:ogc="http://www.opengis.net/ogc">
            <ogc:PropertyIsGreaterThan>
              <ogc:PropertyName>LSSCombine</ogc:PropertyName>
              <ogc:Literal>0.68000000000000005</ogc:Literal>
            </ogc:PropertyIsGreaterThan>
          </ogc:Filter>
          <se:TextSymbolizer>
            <se:Label>
              <!--SE Export for NAME not implemented yet-->Placeholder</se:Label>
            <se:Font>
              <se:SvgParameter name="font-family">Arial</se:SvgParameter>
              <se:SvgParameter name="font-size">6</se:SvgParameter>
              <se:SvgParameter name="font-style">italic</se:SvgParameter>
              <se:SvgParameter name="font-weight">bold</se:SvgParameter>
            </se:Font>
            <se:LabelPlacement>
              <se:PointPlacement>
                <se:AnchorPoint>
                  <se:AnchorPointX>0</se:AnchorPointX>
                  <se:AnchorPointY>0.5</se:AnchorPointY>
                </se:AnchorPoint>
                <se:Displacement>
                  <se:DisplacementX>2.83</se:DisplacementX>
                  <se:DisplacementY>2.83</se:DisplacementY>
                </se:Displacement>
              </se:PointPlacement>
            </se:LabelPlacement>
            <se:Fill>
              <se:SvgParameter name="fill">#000000</se:SvgParameter>
            </se:Fill>
            <se:VendorOption name="underlineText">true</se:VendorOption>
            <se:VendorOption name="maxDisplacement">5</se:VendorOption>
          </se:TextSymbolizer>
        </se:Rule>
      </se:FeatureTypeStyle>
    </UserStyle>
  </NamedLayer>
</StyledLayerDescriptor>'''

def test_sld_processing():
    """Test del procesamiento del SLD que está causando problemas."""
    
    processor = SLDProcessor()
    
    print("=== Test del SLD problemático ===")
    
    try:
        # Test processing from content
        result = processor.process_shp_sld_from_content(sld_content)
        
        print("✅ Procesamiento exitoso!")
        print(f"Resultado contiene {len(result)} propiedades:")
        for key, value in result.items():
            if key == 'legends':
                print(f"  - {key}: {len(value)} leyendas")
                if value:
                    print(f"    Primera leyenda tiene {len(value[0].get('items', []))} items")
            elif key == 'styles':
                print(f"  - {key}: {len(value)} estilos")
            else:
                print(f"  - {key}: {type(value).__name__}")
        
        # Verificar estructura esperada (sin claves problemáticas)
        expected_keys = ['legends']
        missing_keys = [key for key in expected_keys if key not in result]
        if missing_keys:
            print(f"⚠️  Claves faltantes: {missing_keys}")
        else:
            print("✅ Todas las claves esperadas están presentes")
        
        # Verificar que las claves problemáticas NO están presentes
        problematic_keys = ['forceCesiumPrimitives', 'clampToGround']
        present_problematic = [key for key in problematic_keys if key in result]
        if present_problematic:
            print(f"⚠️  Claves problemáticas presentes (deberían eliminarse): {present_problematic}")
        else:
            print("✅ Claves problemáticas correctamente ausentes")
            
        return result
        
    except Exception as e:
        print(f"❌ Error durante el procesamiento: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_sld_processing()
