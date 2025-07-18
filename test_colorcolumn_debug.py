#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def main():
    print("=== Debug específico del colorColumn ===")
    
    sld_url = "https://data.dev-wins.com/dataset/b3a0b81e-9cec-448c-9639-5d430441b059/resource/6f419955-90dd-4466-b7ab-4b94b5b50df2/download/landslide-susceptibility-school-road-health-style-file.sld"
    
    processor = SLDProcessor()
    result = processor.process_shp_sld(sld_url)
    
    if result:
        print("\n" + "="*60)
        print("CONFIGURACIÓN COMPLETA PARA TERRIAJS")
        print("="*60)
        
        # Mostrar la configuración exacta que se envía a TerriaJS
        styles = result.get('styles', [])
        default_style = result.get('defaultStyle', {})
        
        if styles:
            style = styles[0]
            print(f"\n🔧 ESTILO PRINCIPAL:")
            print(f"   - ID: {style.get('id')}")
            print(f"   - Título: {style.get('title')}")
            
            color_config = style.get('color', {})
            print(f"\n🎨 CONFIGURACIÓN DE COLOR:")
            print(f"   - mapType: {color_config.get('mapType')}")
            print(f"   - colorColumn: '{color_config.get('colorColumn')}'")
            print(f"   - nullColor: {color_config.get('nullColor')}")
            
            bin_maximums = color_config.get('binMaximums', [])
            bin_colors = color_config.get('binColors', [])
            
            print(f"\n📊 BINS CONFIGURADOS:")
            for i, (max_val, color) in enumerate(zip(bin_maximums, bin_colors)):
                prev_val = bin_maximums[i-1] if i > 0 else 0.0
                print(f"   Bin {i+1}: {prev_val:.2f} < valor ≤ {max_val} → {color}")
        
        print(f"\n✅ VERIFICACIONES IMPORTANTES:")
        print(f"   1. El shapefile debe tener una columna llamada exactamente: 'LSSCombine'")
        print(f"   2. Los valores en esa columna deben ser numéricos (decimales entre 0.0 y 1.0)")
        print(f"   3. TerriaJS asignará automáticamente los colores según el bin correspondiente")
        
        print(f"\n📋 JSON COMPLETO PARA DEBUGGEAR EN TERRIAJS:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    else:
        print("❌ Error: No se pudo procesar el SLD")

if __name__ == "__main__":
    main()
