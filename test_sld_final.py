#!/usr/bin/env python
"""
Prueba final del procesador SLD mejorado con técnicas de QGIS
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def test_real_sld_example():
    """Prueba con un ejemplo SLD real más complejo"""
    processor = SLDProcessor()
    
    # SLD con múltiples reglas y simbolizadores
    sld_content = """<?xml version="1.0" encoding="UTF-8"?>
<sld:StyledLayerDescriptor version="1.0.0" 
    xmlns:sld="http://www.opengis.net/sld" 
    xmlns:ogc="http://www.opengis.net/ogc" 
    xmlns:xlink="http://www.w3.org/1999/xlink" 
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  <sld:NamedLayer>
    <sld:Name>test_layer</sld:Name>
    <sld:UserStyle>
      <sld:Name>style1</sld:Name>
      <sld:Title>Test Style</sld:Title>
      <sld:FeatureTypeStyle>
        <sld:Name>feature_style</sld:Name>
        <sld:Rule>
          <sld:Name>rule1</sld:Name>
          <sld:Title>Low Values</sld:Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>population</ogc:PropertyName>
                <ogc:Literal>0</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>population</ogc:PropertyName>
                <ogc:Literal>1000</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <sld:PolygonSymbolizer>
            <sld:Fill>
              <sld:CssParameter name="fill">#ffcccc</sld:CssParameter>
              <sld:CssParameter name="fill-opacity">0.8</sld:CssParameter>
            </sld:Fill>
            <sld:Stroke>
              <sld:CssParameter name="stroke">#ff0000</sld:CssParameter>
              <sld:CssParameter name="stroke-width">1</sld:CssParameter>
            </sld:Stroke>
          </sld:PolygonSymbolizer>
        </sld:Rule>
        <sld:Rule>
          <sld:Name>rule2</sld:Name>
          <sld:Title>Medium Values</sld:Title>
          <ogc:Filter>
            <ogc:And>
              <ogc:PropertyIsGreaterThanOrEqualTo>
                <ogc:PropertyName>population</ogc:PropertyName>
                <ogc:Literal>1000</ogc:Literal>
              </ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyIsLessThan>
                <ogc:PropertyName>population</ogc:PropertyName>
                <ogc:Literal>5000</ogc:Literal>
              </ogc:PropertyIsLessThan>
            </ogc:And>
          </ogc:Filter>
          <sld:PolygonSymbolizer>
            <sld:Fill>
              <sld:CssParameter name="fill">rgb(100%, 50%, 0%)</sld:CssParameter>
              <sld:CssParameter name="fill-opacity">0.8</sld:CssParameter>
            </sld:Fill>
            <sld:Stroke>
              <sld:CssParameter name="stroke">hsl(30, 100%, 40%)</sld:CssParameter>
              <sld:CssParameter name="stroke-width">2</sld:CssParameter>
            </sld:Stroke>
          </sld:PolygonSymbolizer>
        </sld:Rule>
        <sld:Rule>
          <sld:Name>rule3</sld:Name>
          <sld:Title>High Values</sld:Title>
          <ogc:Filter>
            <ogc:PropertyIsGreaterThanOrEqualTo>
              <ogc:PropertyName>population</ogc:PropertyName>
              <ogc:Literal>5000</ogc:Literal>
            </ogc:PropertyIsGreaterThanOrEqualTo>
          </ogc:Filter>
          <sld:PolygonSymbolizer>
            <sld:Fill>
              <sld:CssParameter name="fill">darkred</sld:CssParameter>
              <sld:CssParameter name="fill-opacity">0.9</sld:CssParameter>
            </sld:Fill>
            <sld:Stroke>
              <sld:CssParameter name="stroke">#800000</sld:CssParameter>
              <sld:CssParameter name="stroke-width">3</sld:CssParameter>
            </sld:Stroke>
          </sld:PolygonSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </sld:NamedLayer>
</sld:StyledLayerDescriptor>"""
    
    print("=== Prueba Final del Procesador SLD Mejorado ===")
    print("Procesando SLD complejo con múltiples reglas y formatos de color...")
    
    # Probar el método principal
    result = processor.process_shp_sld_from_content(sld_content)
    
    print(f"\n✓ Resultado obtenido: {bool(result)}")
    if result:
        print(f"✓ Claves en resultado: {list(result.keys())}")
        
        if 'styles' in result:
            print(f"✓ Número de estilos: {len(result['styles'])}")
            
        if 'tableStyle' in result:
            print(f"✓ tableStyle presente: {bool(result['tableStyle'])}")
            if result['tableStyle'] and 'columns' in result['tableStyle']:
                print(f"✓ Columnas de tabla: {result['tableStyle']['columns']}")
                
        if 'legends' in result:
            print(f"✓ Leyendas presente: {len(result['legends'])}")
            for i, legend in enumerate(result['legends']):
                if 'items' in legend:
                    print(f"  - Leyenda {i+1}: {len(legend['items'])} elementos")
                    for j, item in enumerate(legend['items'][:3]):  # Mostrar solo primeros 3
                        print(f"    * {item.get('title', 'Sin título')}: {item.get('color', 'Sin color')}")
    
    print("\n=== Prueba de Validación de Estructura ===")
    # Probar validación de estructura
    root = processor.parse_sld_xml(sld_content.encode('utf-8'))
    if root:
        is_valid = processor._validate_sld_structure(root)
        print(f"✓ Estructura SLD válida: {is_valid}")
        
        version = processor._detect_sld_version(root)
        print(f"✓ Versión detectada: {version}")
        
        symbolizers = processor._count_symbolizers(root)
        print(f"✓ Simbolizadores encontrados: {symbolizers}")
        
        user_styles = processor._find_user_styles(root)
        print(f"✓ UserStyles encontrados: {len(user_styles)}")
        
        if user_styles:
            has_valid = processor._has_valid_symbolizers(user_styles[0])
            print(f"✓ UserStyle tiene simbolizadores válidos: {has_valid}")
    
    print("\n=== Prueba de Extracción de Propiedades ===")
    # Probar extracción de propiedades de un Rule
    if root:
        rules = root.findall('.//sld:Rule', processor.NAMESPACES)
        if rules:
            prop_name = processor._extract_property_name_from_filter(rules[0])
            print(f"✓ Propiedad extraída: {prop_name}")
            print(f"✓ Total de reglas encontradas: {len(rules)}")
    
    print("\n🎉 ¡Prueba final completada exitosamente!")
    return result

if __name__ == '__main__':
    test_real_sld_example()
