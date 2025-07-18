#!/usr/bin/env python3
"""
Test específico para verificar que LSSCombine se procesa correctamente usando SLD local
"""

import sys
import os

# Agregar el directorio padre al path para importar el módulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def test_lsscombine_from_local_sld():
    """Test específico para LSSCombine usando SLD local"""
    
    # Usar el SLD local
    sld_file = os.path.join(os.path.dirname(__file__), 'test_lsscombine.sld')
    
    processor = SLDProcessor()
    
    print("=" * 60)
    print("TEST ESPECÍFICO PARA LSSCombine (SLD LOCAL)")
    print("=" * 60)
    
    print(f"Procesando SLD local: {sld_file}")
    print()
    
    try:
        # Leer el contenido del SLD
        with open(sld_file, 'r', encoding='utf-8') as f:
            sld_content = f.read()
        
        print("SLD Content Preview:")
        print(sld_content[:500] + "..." if len(sld_content) > 500 else sld_content)
        print()
        
        # Procesar usando el método que procesa contenido directamente
        result = processor.process_shp_sld_from_content(sld_content)
        
        print("=" * 40)
        print("RESULTADO COMPLETO:")
        print("=" * 40)
        import json
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        print()
        print("=" * 40)
        print("ANÁLISIS DEL RESULTADO:")
        print("=" * 40)
        
        # Verificar styles
        if 'styles' in result:
            print(f"✓ Encontrados {len(result['styles'])} estilos")
            for i, style in enumerate(result['styles']):
                print(f"  Estilo {i+1}:")
                print(f"    ID: {style.get('id', 'N/A')}")
                print(f"    Title: {style.get('title', 'N/A')}")
                
                if 'color' in style:
                    color_config = style['color']
                    print(f"    Color config:")
                    print(f"      mapType: {color_config.get('mapType', 'N/A')}")
                    print(f"      colorColumn: '{color_config.get('colorColumn', 'N/A')}'")
                    
                    if color_config.get('colorColumn'):
                        column_name = color_config['colorColumn']
                        print(f"      ✓ Column name: '{column_name}'")
                        print(f"      ✓ Column name type: {type(column_name)}")
                        print(f"      ✓ Column name length: {len(column_name)}")
                        print(f"      ✓ Column name repr: {repr(column_name)}")
                        
                        # Verificar si es exactamente LSSCombine
                        if column_name == "LSSCombine":
                            print(f"      ✅ CORRECTO: Nombre exacto 'LSSCombine'")
                        else:
                            print(f"      ❌ ERROR: Esperado 'LSSCombine', obtenido '{column_name}'")
                    
                    if 'binMaximums' in color_config:
                        print(f"      binMaximums: {color_config['binMaximums']}")
                    if 'binColors' in color_config:
                        print(f"      binColors: {color_config['binColors']}")
                        
        else:
            print("❌ No se encontraron estilos en el resultado")
            
        # Verificar legends
        if 'legends' in result:
            print(f"✓ Encontradas {len(result['legends'])} leyendas")
            for legend in result['legends']:
                items = legend.get('items', [])
                print(f"  Leyenda con {len(items)} elementos")
                for item in items:
                    print(f"    - {item.get('title', 'N/A')}: {item.get('color', 'N/A')}")
        else:
            print("❌ No se encontraron leyendas")
            
        print()
        print("=" * 40)
        print("VERIFICACIÓN FINAL:")
        print("=" * 40)
        
        # Verificar que tenemos lo esperado
        success = True
        
        if not result.get('styles'):
            print("❌ Falta configuración de estilos")
            success = False
        elif not result['styles'][0].get('color', {}).get('colorColumn'):
            print("❌ Falta colorColumn en la configuración")
            success = False
        elif result['styles'][0]['color']['colorColumn'] != "LSSCombine":
            print(f"❌ colorColumn incorrecto: '{result['styles'][0]['color']['colorColumn']}'")
            success = False
        else:
            print("✅ colorColumn correcto: 'LSSCombine'")
            
        if result.get('styles', [{}])[0].get('color', {}).get('mapType') != "bin":
            print("❌ mapType debería ser 'bin'")
            success = False
        else:
            print("✅ mapType correcto: 'bin'")
            
        if not result.get('styles', [{}])[0].get('color', {}).get('binMaximums'):
            print("❌ Faltan binMaximums")
            success = False
        else:
            bin_maxs = result['styles'][0]['color']['binMaximums']
            expected_bins = [0.2, 0.5, 0.68, 0.72, 1.0]
            print(f"✅ binMaximums presente: {bin_maxs}")
            if bin_maxs == expected_bins:
                print("✅ binMaximums correcto")
            else:
                print(f"⚠️  binMaximums diferente del esperado: {expected_bins}")
            
        if not result.get('styles', [{}])[0].get('color', {}).get('binColors'):
            print("❌ Faltan binColors") 
            success = False
        else:
            bin_colors = result['styles'][0]['color']['binColors']
            expected_colors = ["#FFFFBF", "#FEE787", "#FD8D3C", "#F03B20", "#BD0026"]
            print(f"✅ binColors presente: {len(bin_colors)} colores")
            print(f"   Colores: {bin_colors}")
            if bin_colors == expected_colors:
                print("✅ binColors correcto")
            else:
                print(f"⚠️  binColors diferente del esperado: {expected_colors}")
            
        if success:
            print()
            print("🎉 TODOS LOS TESTS PASARON")
            print("La configuración está correcta para TerriaJS")
            print()
            print("CONFIGURACIÓN FINAL PARA TERRIAJS:")
            print("="*50)
            if result.get('styles'):
                style = result['styles'][0]
                color_config = style.get('color', {})
                print(f"mapType: '{color_config.get('mapType')}'")
                print(f"colorColumn: '{color_config.get('colorColumn')}'")
                print(f"binMaximums: {color_config.get('binMaximums')}")
                print(f"binColors: {color_config.get('binColors')}")
                print()
                print("Esta configuración debe funcionar correctamente en TerriaJS")
                print("siempre que la columna 'LSSCombine' exista en el shapefile.")
        else:
            print()
            print("💥 ALGUNOS TESTS FALLARON")
            print("Revisar la configuración")
            
    except Exception as e:
        print(f"❌ ERROR en el procesamiento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_lsscombine_from_local_sld()
