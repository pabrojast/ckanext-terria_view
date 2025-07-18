#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import json

# Add the current directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def main():
    print("=== Debug para problema de columna ===")
    
    sld_url = "https://data.dev-wins.com/dataset/b3a0b81e-9cec-448c-9639-5d430441b059/resource/6f419955-90dd-4466-b7ab-4b94b5b50df2/download/landslide-susceptibility-school-road-health-style-file.sld"
    
    processor = SLDProcessor()
    result = processor.process_shp_sld(sld_url)
    
    if result:
        styles = result.get('styles', [])
        if styles:
            style = styles[0]
            color_config = style.get('color', {})
            column_name = color_config.get('colorColumn')
            
            print(f"\n🔍 ANÁLISIS DEL PROBLEMA:")
            print(f"   - Columna configurada: '{column_name}'")
            print(f"   - Tipo de mapeo: {color_config.get('mapType')}")
            
            print(f"\n🧪 POSIBLES VARIACIONES DE NOMBRE DE COLUMNA A PROBAR:")
            variations = [
                column_name,  # Original
                column_name.lower(),  # lsscombine
                column_name.upper(),  # LSSCOMBINE
                column_name.replace('SS', '_'),  # LS_Combine
                column_name.replace('Combine', '_COMBINE'),  # LSS_COMBINE
                'lss_combine',  # Common snake_case
                'LSSCombine',  # Original again
                'lsscombine',  # All lowercase
                'LSSCOMBINE',  # All uppercase
            ]
            
            for i, var in enumerate(set(variations), 1):
                print(f"   {i}. '{var}'")
            
            print(f"\n📊 POSIBLES FORMATOS DE DATOS A VERIFICAR:")
            print(f"   - Decimales: 0.15, 0.35, 0.6, 0.7, 0.9")
            print(f"   - Enteros: 1, 2, 3, 4, 5")
            print(f"   - Porcentajes: 15, 35, 60, 70, 90")
            print(f"   - Strings: '0.2', '0.5', '0.68'")
            
            print(f"\n🔧 CONFIGURACIÓN ACTUAL QUE SE ENVÍA A TERRIAJS:")
            print(f"   mapType: '{color_config.get('mapType')}'")
            print(f"   colorColumn: '{color_config.get('colorColumn')}'")
            
            bin_maximums = color_config.get('binMaximums', [])
            print(f"   binMaximums: {bin_maximums}")
            
            print(f"\n💡 CÓMO VERIFICAR:")
            print(f"   1. Abrir el shapefile en QGIS u otro visor")
            print(f"   2. Ver tabla de atributos")
            print(f"   3. Verificar nombre exacto de columna")
            print(f"   4. Ver algunos valores de ejemplo")
            print(f"   5. Ajustar si es necesario")
            
            print(f"\n⚠️  DIAGNÓSTICO:")
            print(f"   Si ves 'solo colores naranjos', probablemente:")
            print(f"   - La columna se llama diferente en el shapefile")
            print(f"   - Los valores están en un formato/rango diferente")
            print(f"   - Hay un problema de cache en TerriaJS")
            
    else:
        print("❌ Error: No se pudo procesar el SLD")

if __name__ == "__main__":
    main()
