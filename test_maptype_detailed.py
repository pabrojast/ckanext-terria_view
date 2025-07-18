#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def main():
    print("=== Test detallado del mapType ===")
    
    # URL del SLD problemático
    sld_url = "https://data.dev-wins.com/dataset/b3a0b81e-9cec-448c-9639-5d430441b059/resource/6f419955-90dd-4466-b7ab-4b94b5b50df2/download/landslide-susceptibility-school-road-health-style-file.sld"
    
    processor = SLDProcessor()
    result = processor.process_shp_sld(sld_url)
    
    if result:
        print("\n=== RESULTADO COMPLETO ===")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # Verificar específicamente el mapType
        styles = result.get('styles', [])
        if styles:
            first_style = styles[0]
            color_config = first_style.get('color', {})
            map_type = color_config.get('mapType')
            print(f"\n✅ mapType detectado: {map_type}")
            
            enum_colors = color_config.get('enumColors', [])
            print(f"✅ Valores de enumColors:")
            for i, item in enumerate(enum_colors):
                print(f"  {i+1}. value: {item.get('value')} -> color: {item.get('color')}")
        
        # Comparar con el ejemplo que funciona
        working_example_map_type = "enum"  # Del ejemplo JSON que proporcionaste
        print(f"\n📊 Comparación:")
        print(f"  - Código actual: mapType = '{map_type}'")
        print(f"  - Ejemplo funcionando: mapType = '{working_example_map_type}'")
        
        if map_type == "continuous":
            print("🚨 PROBLEMA IDENTIFICADO: Estamos usando 'continuous' pero el ejemplo funciona con 'enum'")
            print("💡 SOLUCIÓN: Necesitamos revisar cuándo usar cada tipo")
        
    else:
        print("❌ Error: No se pudo procesar el SLD")

if __name__ == "__main__":
    main()
