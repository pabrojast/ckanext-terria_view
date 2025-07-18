#!/usr/bin/env python3
"""
Test específico para verificar que LSSCombine se procesa correctamente
"""

import sys
import os

# Agregar el directorio padre al path para importar el módulo
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def test_lsscombine_processing():
    """Test específico para LSSCombine"""
    
    # URL del SLD que sabemos contiene LSSCombine
    sld_url = "https://data.dev-wins.com/dataset/b3a0b81e-9cec-448c-9639-5d430441b059/resource/ab224078-be08-4e83-a3ca-f224600d57ea/download/landslide-susceptibility-of-health-facilities-in-chimanimani-and-chipinge.sld"
    
    processor = SLDProcessor()
    
    print("=" * 60)
    print("TESTE ESPECÍFICO PARA LSSCombine")
    print("=" * 60)
    
    print(f"Procesando SLD: {sld_url}")
    print()
    
    try:
        result = processor.process_shp_sld(sld_url)
        
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
            print(f"✅ binMaximums presente: {bin_maxs}")
            
        if not result.get('styles', [{}])[0].get('color', {}).get('binColors'):
            print("❌ Faltan binColors") 
            success = False
        else:
            bin_colors = result['styles'][0]['color']['binColors']
            print(f"✅ binColors presente: {len(bin_colors)} colores")
            
        if success:
            print()
            print("🎉 TODOS LOS TESTS PASARON")
            print("La configuración está correcta para TerriaJS")
        else:
            print()
            print("💥 ALGUNOS TESTS FALLARON")
            print("Revisar la configuración")
            
    except Exception as e:
        print(f"❌ ERROR en el procesamiento: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_lsscombine_processing()
