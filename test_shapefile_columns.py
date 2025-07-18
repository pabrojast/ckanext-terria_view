#!/usr/bin/env python3
"""
Script para diagnosticar las columnas del shapefile y verificar el mapeo correcto.
"""

import requests
import zipfile
import io
import tempfile
import os
from pathlib import Path

def download_and_analyze_shapefile():
    """Descargar y analizar el shapefile para encontrar las columnas exactas."""
    
    shapefile_url = "https://data.dev-wins.com/dataset/b3a0b81e-9cec-448c-9639-5d430441b059/resource/ab224078-be08-4e83-a3ca-f224600d57ea/download/landslide-susceptibility-of-health-facilities-in-chimanimani-and-chipinge.zip"
    
    print("Descargando shapefile...")
    
    try:
        response = requests.get(shapefile_url, timeout=30)
        response.raise_for_status()
        
        print(f"Shapefile descargado: {len(response.content)} bytes")
        
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as temp_dir:
            # Extraer el zip
            with zipfile.ZipFile(io.BytesIO(response.content)) as zip_file:
                zip_file.extractall(temp_dir)
                
                print(f"Archivos extraídos en: {temp_dir}")
                
                # Listar archivos
                extracted_files = list(Path(temp_dir).rglob("*"))
                print("\nArchivos encontrados:")
                for file_path in extracted_files:
                    if file_path.is_file():
                        print(f"  {file_path.name} ({file_path.stat().st_size} bytes)")
                
                # Buscar archivo .shp
                shp_files = list(Path(temp_dir).rglob("*.shp"))
                if not shp_files:
                    print("ERROR: No se encontró archivo .shp")
                    return
                
                shp_file = shp_files[0]
                print(f"\nArchivo shapefile encontrado: {shp_file.name}")
                
                # Intentar leer con diferentes métodos
                analyze_with_fiona(shp_file)
                analyze_with_geopandas(shp_file)
                analyze_dbf_directly(temp_dir)
                
    except Exception as e:
        print(f"Error descargando/analizando shapefile: {e}")
        import traceback
        traceback.print_exc()

def analyze_with_fiona(shp_file):
    """Analizar usando fiona si está disponible."""
    try:
        import fiona
        print("\n=== Análisis con Fiona ===")
        
        with fiona.open(shp_file) as src:
            print(f"Driver: {src.driver}")
            print(f"CRS: {src.crs}")
            print(f"Número de features: {len(src)}")
            
            # Schema y propiedades
            print(f"\nSchema:")
            print(f"  Geometry: {src.schema['geometry']}")
            print(f"  Properties:")
            for prop_name, prop_type in src.schema['properties'].items():
                print(f"    {prop_name}: {prop_type}")
            
            # Leer algunas features para ver los datos
            print(f"\nPrimeras 3 features:")
            for i, feature in enumerate(src):
                if i >= 3:
                    break
                print(f"  Feature {i+1}:")
                print(f"    Geometry type: {feature['geometry']['type']}")
                print(f"    Properties:")
                for prop_name, prop_value in feature['properties'].items():
                    print(f"      {prop_name}: {prop_value} (type: {type(prop_value).__name__})")
                print()
                
            # Buscar columnas que podrían ser LSSCombine
            print("\n=== Búsqueda de columnas relacionadas con LSS ===")
            schema_props = src.schema['properties']
            for prop_name in schema_props.keys():
                prop_lower = prop_name.lower()
                if any(term in prop_lower for term in ['lss', 'combine', 'landslide', 'susceptibility']):
                    print(f"CANDIDATO ENCONTRADO: '{prop_name}' (tipo: {schema_props[prop_name]})")
                
    except ImportError:
        print("Fiona no disponible")
    except Exception as e:
        print(f"Error con Fiona: {e}")

def analyze_with_geopandas(shp_file):
    """Analizar usando geopandas si está disponible."""
    try:
        import geopandas as gpd
        print("\n=== Análisis con GeoPandas ===")
        
        gdf = gpd.read_file(shp_file)
        print(f"Shape: {gdf.shape}")
        print(f"CRS: {gdf.crs}")
        
        print(f"\nColumnas:")
        for col in gdf.columns:
            if col != 'geometry':
                dtype = gdf[col].dtype
                non_null_count = gdf[col].notna().sum()
                print(f"  {col}: {dtype} ({non_null_count}/{len(gdf)} no nulos)")
                
                # Mostrar algunos valores únicos
                unique_vals = gdf[col].dropna().unique()
                if len(unique_vals) <= 10:
                    print(f"    Valores únicos: {list(unique_vals)}")
                else:
                    print(f"    Primeros valores: {list(unique_vals[:10])}")
                    print(f"    Min: {gdf[col].min()}, Max: {gdf[col].max()}")
        
        # Buscar columnas candidatas
        print("\n=== Búsqueda de columnas LSS ===")
        for col in gdf.columns:
            if col != 'geometry':
                col_lower = col.lower()
                if any(term in col_lower for term in ['lss', 'combine', 'landslide', 'susceptibility']):
                    print(f"CANDIDATO: '{col}'")
                    print(f"  Tipo: {gdf[col].dtype}")
                    print(f"  Valores únicos: {gdf[col].dropna().unique()}")
                    print(f"  Estadísticas:")
                    try:
                        print(f"    Min: {gdf[col].min()}")
                        print(f"    Max: {gdf[col].max()}")
                        print(f"    Media: {gdf[col].mean():.4f}")
                    except:
                        pass
                
    except ImportError:
        print("GeoPandas no disponible")
    except Exception as e:
        print(f"Error con GeoPandas: {e}")

def analyze_dbf_directly(temp_dir):
    """Analizar el archivo DBF directamente."""
    try:
        import struct
        
        print("\n=== Análisis directo del DBF ===")
        
        # Buscar archivo .dbf
        dbf_files = list(Path(temp_dir).rglob("*.dbf"))
        if not dbf_files:
            print("No se encontró archivo .dbf")
            return
            
        dbf_file = dbf_files[0]
        print(f"Archivo DBF: {dbf_file.name}")
        
        with open(dbf_file, 'rb') as f:
            # Leer cabecera DBF
            header = f.read(32)
            
            # Extraer información básica
            version = header[0]
            record_count = struct.unpack('<I', header[4:8])[0]
            header_length = struct.unpack('<H', header[8:10])[0]
            record_length = struct.unpack('<H', header[10:12])[0]
            
            print(f"Versión DBF: {version}")
            print(f"Número de registros: {record_count}")
            print(f"Longitud de cabecera: {header_length}")
            print(f"Longitud de registro: {record_length}")
            
            # Leer campos
            field_count = (header_length - 33) // 32
            print(f"Número de campos: {field_count}")
            
            fields = []
            for i in range(field_count):
                field_data = f.read(32)
                field_name = field_data[:11].rstrip(b'\x00').decode('latin-1', errors='ignore')
                field_type = chr(field_data[11])
                field_length = field_data[16]
                field_decimal = field_data[17]
                
                fields.append({
                    'name': field_name,
                    'type': field_type,
                    'length': field_length,
                    'decimal': field_decimal
                })
                
                print(f"  Campo: '{field_name}' Tipo: {field_type} Longitud: {field_length}")
            
            # Buscar campos candidatos
            print(f"\n=== Campos candidatos para LSSCombine ===")
            for field in fields:
                field_lower = field['name'].lower()
                if any(term in field_lower for term in ['lss', 'combine', 'landslide', 'susceptibility']):
                    print(f"CANDIDATO DBF: '{field['name']}' (tipo: {field['type']}, longitud: {field['length']})")
                
    except Exception as e:
        print(f"Error analizando DBF: {e}")

def test_possible_column_names():
    """Probar posibles nombres de columna basados en patrones comunes."""
    
    print("\n=== Posibles nombres de columna a probar ===")
    
    base_names = [
        "LSSCombine",
        "lsscombine", 
        "LSSCOMBINE",
        "LSS_Combine",
        "lss_combine",
        "LSS_COMBINE",
        "Lss_Combine",
        "LandslideS",
        "landslides",
        "LANDSLIDES",
        "Susceptibi",
        "susceptibi",
        "SUSCEPTIBI",
        "LSS",
        "lss",
        "Combine",
        "combine",
        "COMBINE"
    ]
    
    print("Nombres a verificar en el shapefile:")
    for name in base_names:
        print(f"  - '{name}'")
    
    return base_names

if __name__ == "__main__":
    print("=== Diagnóstico de columnas del shapefile ===")
    download_and_analyze_shapefile()
    test_possible_column_names()
    
    print("\n=== Instrucciones ===")
    print("1. Verificar los nombres exactos de las columnas mostrados arriba")
    print("2. Buscar columnas que contengan valores numéricos de susceptibilidad")
    print("3. El nombre exacto debe usarse en 'colorColumn' en lugar de 'LSSCombine'")
    print("4. Si hay múltiples candidatos, probar con cada uno hasta encontrar el correcto")
