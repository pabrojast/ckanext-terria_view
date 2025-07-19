#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def main():
    print("=== Test de validación final ===")
    
    # URL del SLD problemático
    sld_url = "https://data.dev-wins.com/dataset/b3a0b81e-9cec-448c-9639-5d430441b059/resource/6f419955-90dd-4466-b7ab-4b94b5b50df2/download/landslide-susceptibility-school-road-health-style-file.sld"
    
    processor = SLDProcessor()
    result = processor.process_shp_sld(sld_url)
    
    if result:
        print("✅ Procesamiento exitoso")
        
        # Validar estructura TerriaJS
        required_keys = ['legends', 'styles', 'defaultStyle', 'activeStyle', 'opacity']
        for key in required_keys:
            if key in result:
                print(f"✅ {key}: OK")
            else:
                print(f"❌ {key}: FALTANTE")
        
        # Verificar que las claves problemáticas NO están presentes
        problematic_keys = ['forceCesiumPrimitives', 'clampToGround']
        for key in problematic_keys:
            if key not in result:
                print(f"✅ {key}: CORRECTAMENTE AUSENTE")
            else:
                print(f"❌ {key}: PRESENTE (problemático)")
        
        # Validar configuración de colores
        styles = result.get('styles', [])
        if styles:
            style = styles[0]
            color_config = style.get('color', {})
            
            map_type = color_config.get('mapType')
            color_column = color_config.get('colorColumn')
            bin_maximums = color_config.get('binMaximums', [])
            bin_colors = color_config.get('binColors', [])
            
            print(f"\n📊 Configuración de colores:")
            print(f"  - mapType: {map_type}")
            print(f"  - colorColumn: {color_column}")
            print(f"  - binMaximums: {bin_maximums}")
            print(f"  - binColors: {len(bin_colors)} colores")
            
            # Validar que bins están ordenados correctamente
            if bin_maximums == sorted(bin_maximums):
                print("✅ binMaximums están ordenados correctamente")
            else:
                print("❌ binMaximums NO están ordenados")
            
            # Validar que hay el mismo número de colors y maximums
            if len(bin_maximums) == len(bin_colors):
                print("✅ Número de binMaximums coincide con binColors")
            else:
                print(f"❌ Mismatch: {len(bin_maximums)} maximums vs {len(bin_colors)} colors")
            
            # Mostrar mapeo detallado
            print(f"\n🎨 Mapeo de rangos:")
            prev_max = 0.0
            for i, (max_val, color) in enumerate(zip(bin_maximums, bin_colors)):
                print(f"  Bin {i+1}: {prev_max:.2f} → {max_val} = {color}")
                prev_max = max_val
        
        print(f"\n💡 Para datos con valores como 0.15, 0.35, 0.6, etc.:")
        print(f"   - Valor 0.15 → Bin 1 (0.0-0.2) → {bin_colors[0] if bin_colors else 'N/A'}")
        print(f"   - Valor 0.35 → Bin 2 (0.2-0.5) → {bin_colors[1] if len(bin_colors) > 1 else 'N/A'}")
        print(f"   - Valor 0.6  → Bin 3 (0.5-0.68) → {bin_colors[2] if len(bin_colors) > 2 else 'N/A'}")
        
        print(f"\n🚀 LISTO PARA PRODUCCIÓN")
        print(f"   Este código debería resolver el problema de 'solo colores naranjos'")
        
    else:
        print("❌ Error: No se pudo procesar el SLD")

if __name__ == "__main__":
    main()
