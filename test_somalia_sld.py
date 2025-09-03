#!/usr/bin/env python3
# encoding: utf-8
"""
Script de prueba para verificar el procesamiento del SLD de Somalia
"""
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ckanext', 'terria_view'))

from sld_processor import SLDProcessor

def main():
    # Configurar debug
    os.environ['TERRIA_DEBUG'] = 'true'
    
    # Ruta al archivo SLD de Somalia
    sld_path = r"C:\Users\pablo\Downloads\soamlia_geology_1.5m\somalia.sld"
    
    print("=== Iniciando prueba de procesamiento SLD Somalia ===")
    print(f"Archivo SLD: {sld_path}")
    
    # Crear procesador
    processor = SLDProcessor()
    
    # Procesar el SLD como shapefile
    print("\n1. Procesando SLD como shapefile...")
    try:
        result = processor.process_shp_sld(f"file://{sld_path}")
        try:
            print(f"Resultado obtenido: {result}")
        except UnicodeEncodeError:
            print("Resultado obtenido: [result contains special characters]")
        
        # Verificar elementos clave
        if 'legends' in result:
            print(f"\n2. Leyenda generada con {len(result['legends'][0]['items'])} elementos")
            for i, item in enumerate(result['legends'][0]['items'][:5]):  # Mostrar solo los primeros 5
                print(f"   - {item['title']}: {item['color']}")
            if len(result['legends'][0]['items']) > 5:
                print(f"   ... y {len(result['legends'][0]['items']) - 5} más")
        
        if 'styles' in result:
            print(f"\n3. Estilos generados:")
            for style in result['styles']:
                print(f"   - ID: {style.get('id')}")
                print(f"   - Título: {style.get('title')}")
                if 'color' in style:
                    color_config = style['color']
                    print(f"   - Tipo de mapa: {color_config.get('mapType')}")
                    print(f"   - Columna de color: {color_config.get('colorColumn')}")
                    
                    if 'enumColors' in color_config:
                        print(f"   - Enum colors: {len(color_config['enumColors'])} elementos")
                        for j, enum_color in enumerate(color_config['enumColors'][:3]):
                            print(f"     * {enum_color.get('value')}: {enum_color.get('color')}")
                        if len(color_config['enumColors']) > 3:
                            print(f"     ... y {len(color_config['enumColors']) - 3} más")
                    
                    if 'binMaximums' in color_config:
                        print(f"   - Bin maximums: {color_config['binMaximums'][:5]}")
                        print(f"   - Bin colors: {color_config['binColors'][:5]}")
        
        if 'style' in result:
            print(f"\n4. Estilo básico:")
            basic_style = result['style']
            print(f"   - Fill: {basic_style.get('fill')}")
            print(f"   - Stroke: {basic_style.get('stroke')}")
            
        print(f"\n5. Configuración completa:")
        import json
        try:
            print(json.dumps(result, indent=2))
        except UnicodeEncodeError:
            print("[Configuration contains special characters - cannot display]")
        
    except Exception as e:
        print(f"Error procesando SLD: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()