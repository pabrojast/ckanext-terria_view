# encoding: utf-8
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib
import re
import functools
import os
from ckan.lib import base, uploader
from flask import abort, request
from time import sleep
import ckan.logic.action.get as get
import urllib.request  # Asegúrate de tener esta importación
import xml.etree.ElementTree as ET  # Asegúrate de tener esta importación
ignore_missing = toolkit.get_validator(u'ignore_missing')
boolean_validator = toolkit.get_validator(u'boolean_validator')
default = toolkit.get_validator(u'default')

SUPPORTED_FORMATS = ['shp', 'wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*', 'wmts', 'tif', 'tiff', 'geotiff', 'csv', 'json']
SUPPORTED_FILTER_EXPR = 'fq=(' + ' OR '.join(['res_format:' + s for s in SUPPORTED_FORMATS]) + ')'
SUPPORTED_FORMATS_REGEX = '^(' + '|'.join([s.replace('*', '.*') for s in SUPPORTED_FORMATS]) + ')$'

def can_view_resource(resource):
    format_ = resource.get('format', '')
    if format_ == '':
        format_ = os.path.splitext(resource['url'])[1][1:]
    return re.match(SUPPORTED_FORMATS_REGEX, format_.lower()) != None

resource_view_list = get.resource_view_list

PLUGIN_NAME = 'terria_view'

def get_sld_files_from_dataset(site_url, package_id):
    """
    Función para obtener archivos SLD de un dataset usando la API de CKAN
    """
    try:
        # Construir la URL de la API
        api_url = f"{site_url.rstrip('/')}/api/3/action/package_show?id={package_id}"
        
        # Hacer la petición a la API
        with urllib.request.urlopen(api_url) as response:
            data = json.loads(response.read().decode('utf-8'))
        
        if data.get('success') and data.get('result'):
            package_data = data['result']
            sld_files = []
            
            # Buscar recursos con formato 'sld'
            for resource in package_data.get('resources', []):
                if resource.get('format', '').lower() == 'sld':
                    sld_files.append({
                        'id': resource.get('id'),
                        'name': resource.get('name', 'Archivo SLD sin nombre'),
                        'url': resource.get('url'),
                        'description': resource.get('description', '')
                    })
            
            return sld_files
    except Exception as e:
        print(f"Error obteniendo archivos SLD desde la API: {e}")
        return []

def new_resource_view_list(plugin, context, data_dict):

    try:
        resource_id = data_dict.get('id')
        # Verificar si hay un activity_id en la URL, así no intenta crear nada.
        if 'activity_id' in request.args:
            print("Activity ID detected, skipping resource view creation.")
            ret = []
            return ret
        resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        if not resource:
            print("Debug: Resource not found")
            ret = []
            return ret
        ret = resource_view_list(context, data_dict)
    except Exception as e:
        print(f"Error retrieving resource view list: {e}")
    try:
        ret
    except NameError:
        ret = []
        
    has_plugin = len([r for r in ret if r['view_type'] == PLUGIN_NAME]) > 0

    if not has_plugin:
        if 'resource' in context and can_view_resource(context['resource'].__dict__):
            data_dict2 = {
                'resource_id': data_dict['id'],
                'title': plugin.default_title,
                'view_type': 'terria_view',
                'description': '',
                'custom_config': 'NA',
                'terria_instance_url': '//ihp-wins.unesco.org/terria/',
                'style':  'NA'
            }
            sysadmin_context = {
                'model': context['model'],
                'session': context['session'],
                'user': 'ckan.system',
                'ignore_auth': True
            }
            try:
                toolkit.get_action('resource_view_create')(sysadmin_context, data_dict2)
                ret = resource_view_list(context, data_dict)
            except Exception as e:
                print(f"Error creating resource view: {e}")

    return ret

class Terria_ViewPlugin(plugins.SingletonPlugin):
    site_url = ''
    default_title = 'Terria Viewer'
    default_instance_url = 'https://ihp-wins.unesco.org/terria/'
    resource_view_list_callback = None
  
    plugins.implements(plugins.IConfigurer)
    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_,'public')

    plugins.implements(plugins.IConfigurable, inherit=True)
    def configure(self, config):
        self.site_url = config.get('ckan.site_url', self.site_url)
        self.default_title = config.get('ckanext.' + PLUGIN_NAME + '.default_title', self.default_title)
        self.default_instance_url = config.get('ckanext.' + PLUGIN_NAME + '.default_instance_url', self.default_instance_url)
        self.resource_view_list_callback = functools.partial(new_resource_view_list, self)
    
    plugins.implements(plugins.IResourceView, inherit=True)
    def info(self):
        return {
            'name': PLUGIN_NAME,
            'title': toolkit._('TerriaJS Preview'),
            'default_title': toolkit._(self.default_title),
            'icon': 'globe',
            'always_available': True,
            'filterable': True,
            'iframed': False,
            "schema": {
                "terria_instance_url": [],
                "custom_config": [],
                "style": [],
                'show_fields': [ignore_missing],
                'filterable': [default(True), boolean_validator],
                'time_resample': [ignore_missing],
            }
        }

    def can_view(self, data_dict):
        return can_view_resource(data_dict['resource'])

    def is_shp(self, resource):
        return resource["format"].lower() == 'shp'

    def setup_template_variables(self, context, data_dict):
        package = data_dict['package']
        resource = data_dict['resource']
        view = data_dict['resource_view']
        view_title = view.get('title', self.default_title)
        view_terria_instance_url = view.get('terria_instance_url', self.default_instance_url)
        
        # Fix para recursos sin nombre - generar nombre por defecto
        def get_safe_resource_name(resource):
            name = resource.get('name', '').strip()
            if not name or name.lower() in ['', 'none', 'null', 'undefined', 'Unnamed resource']:
                # Usar el ID del recurso o un nombre genérico
                fallback_name = resource.get('id', f"Recurso_{hash(resource.get('url', 'sin_url')) % 10000}")
                return fallback_name
            return name
        
        # Obtener el nombre seguro del recurso
        safe_resource_name = get_safe_resource_name(resource)
        
        # Si terria_instance_url contiene una URL completa de TerriaJS, usarla directamente
        if view_terria_instance_url and '#' in view_terria_instance_url:
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'direct_url': True  # Nueva bandera para indicar URL directa
            }
        
        view_custom_config = view.get('custom_config', 'NA')
        view_style = view.get('style', 'NA')
        
        # Si el formato es JSON, solo necesitamos pasar la URL de TerriaJS
        if resource.get('format', '').lower() == 'json':
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'resource': resource
            }
        
        resource_id = resource['id']
        organization = package['organization']
        name = package['name']
        organization_id = organization['id']
        view = data_dict['resource_view']
        #print(view)
        view_title = view.get('title', self.default_title)
        view_terria_instance_url = view.get('terria_instance_url', self.default_instance_url)
        view_custom_config = view.get('custom_config', 'NA')
        view_style = view.get('style', 'NA')
        
        # Contexto con información del usuario
        user_context = {
            'user': toolkit.g.user, 
            'auth_user_obj': toolkit.g.userobj
        }

        def is_accepted_format(resource):
            accepted_formats = ['shp', 'kml', 'geojson', 'czml', 'csv-geo-au', 'csv-geo-nz', 'csv-geo-us', 'WMTS', 'tif', 'tiff', 'geotiff']
            resource_format = resource["format"].lower()
            return any(resource_format == format for format in accepted_formats)

        def is_valid_domain(url):
            #return False
            return url.startswith('https://data.dev-wins.com') or url.startswith('https://ihp-wins.unesco.org/')

        if is_valid_domain(resource["url"]):
            if is_accepted_format(resource):
                #fix for private datasets
                if user_context['user'] and package["private"] == True:
                    upload = uploader.get_resource_uploader(resource)
                    uploaded_url = upload.get_url_from_filename(resource_id, resource['url'])
                else:
                    uploaded_url = resource["url"]
            else:
                uploaded_url = resource["url"]
        else:
            uploaded_url = resource["url"]
          
        def clean_coordinate(value, default):
            if value is None:
                return default
            cleaned_value = re.sub(r'\s+', '', str(value))
            if re.match(r'^-?\d+(\.\d+)?$', cleaned_value):
                return cleaned_value
            else:
                return default
            
        def extract_bounds_from_spatial(spatial):
            try:
                spatial_data = json.loads(spatial)
                if spatial_data["type"] == "Polygon":
                    coordinates = spatial_data["coordinates"][0]
                    lats = [coord[1] for coord in coordinates]
                    lons = [coord[0] for coord in coordinates]
                    ymax = max(lats)
                    ymin = min(lats)
                    xmax = max(lons)
                    xmin = min(lons)
                    return str(ymax), str(xmax), str(ymin), str(xmin)
            except (json.JSONDecodeError, KeyError, TypeError):
                pass
            return None, None, None, None

        # Intentar extraer las coordenadas desde 'spatial'
        ymax_spatial, xmax_spatial, ymin_spatial, xmin_spatial = extract_bounds_from_spatial(package.get("spatial"))

        # Si no se pudo extraer desde 'spatial', usar el valor predeterminado
        ymax = clean_coordinate(ymax_spatial if ymax_spatial else package.get("ymax"), "20")
        xmax = clean_coordinate(xmax_spatial if xmax_spatial else package.get("xmax"), "-13")
        ymin = clean_coordinate(ymin_spatial if ymin_spatial else package.get("ymin"), "-60")
        xmin = clean_coordinate(xmin_spatial if xmin_spatial else package.get("xmin"), "-108")


        def is_tiff(resource):
            accepted_formats = ['tif', 'tiff', 'geotiff']
            resource_format = resource["format"].lower()
            return any(resource_format == format for format in accepted_formats)

        def is_csv(resource):
            accepted_formats = ['csv', 'csv-geo-*']
            resource_format = resource["format"].lower()
            return any(resource_format == format for format in accepted_formats)
        
        if is_csv(resource):
            # Construir la URL base del datastore
            base_url = self.site_url.rstrip('/')
            resource_id = resource['id']
            
            time_resample = view.get('time_resample', '')
            
            # Inicialmente, usar la URL normal del datastore
            datastore_url = f"{base_url}/datastore/dump/{resource_id}"
            
            filters = view.get('filters', {})
            filters_param = ""
            
            if filters:
                # Convertir los filtros a formato JSON
                filters_json = json.dumps(filters)
                # Codificar los filtros para la URL
                encoded_filters = urllib.parse.quote(filters_json)
                # Configurar parámetro de filtros
                filters_param = f"filters={encoded_filters}"
            
            # Si hay resampling configurado, usar SQL query
            if time_resample and time_resample in ['day', 'week', 'month', 'year']:
                # Construir SQL query para resampling
                sql_query = f"""
                SELECT 
                    "Latitude", 
                    "Longitude",
                    DATE_TRUNC('{time_resample}', "time") AS time,
                    "Parameter Code",
                    AVG("Value") AS "Value",
                    MAX("Unit") AS "Unit",
                    COUNT(*) AS "Count"
                FROM "{resource_id}"
                """
                
                # Agregar WHERE si hay filtros (simplificado para el ejemplo)
                if filters and 'Parameter Code' in filters:
                    param_values = filters['Parameter Code']
                    if isinstance(param_values, list) and len(param_values) > 0:
                        param_list = "', '".join(param_values)
                        sql_query += f" WHERE \"Parameter Code\" IN ('{param_list}')"
                
                # Agregar GROUP BY y ORDER BY
                sql_query += f"""
                GROUP BY "Latitude", "Longitude", DATE_TRUNC('{time_resample}', "time"), "Parameter Code"
                ORDER BY time ASC
                """
                
                # Usar directamente datastore_search_sql con formato CSV
                encoded_sql = urllib.parse.quote(sql_query)
                
                # Dos opciones para intentar obtener CSV:
                # 1. Usar el endpoint SQL con parámetro de formato CSV
                datastore_url = f"{base_url}/api/3/action/datastore_search_sql?sql={encoded_sql}&format=csv"
                
                try:
                    # Verificar si el endpoint con format=csv funciona
                    response = urllib.request.urlopen(datastore_url)
                    content_type = response.info().get_content_type()
                    
                    # Si la respuesta no es CSV, volver a la URL sin format=csv
                    if 'csv' not in content_type.lower():
                        print(f"Warning: Expected CSV response but got {content_type}")
                        # Intentar opción alternativa - guardar en variable de sesión y crear endpoint
                        # temporal para servir CSV
                        
                        # En producción: implementar solución más robusta aquí
                        datastore_url = f"{base_url}/api/3/action/datastore_search_sql?sql={encoded_sql}"
                        
                except Exception as e:
                    print(f"Error testing SQL endpoint: {e}")
                    # Fallback a la URL normal con filtros
                    if filters_param:
                        datastore_url = f"{base_url}/datastore/dump/{resource_id}?{filters_param}"
                    else:
                        datastore_url = f"{base_url}/datastore/dump/{resource_id}"
            elif filters_param:
                # Si no hay resampling pero sí hay filtros, añadir los filtros a la URL normal
                datastore_url += f"?{filters_param}"
            #fix temporal
            #uploaded_url = datastore_url
            print(f"CSV URL: {uploaded_url}")

            # Configurar CSV con time properties correctamente y estilo por defecto
            catalog_item = {
                "name": safe_resource_name,
                "type": "csv",
                "id": safe_resource_name,
                "url": uploaded_url,
                "cacheDuration": "5m",
                "isOpenInWorkbench": True,
                "styles": [
                    {
                        "id": "default",
                        "time": {
                            "spreadStartTime": True,
                            "spreadFinishTime": True
                        }
                    }
                ],
                "activeStyle": "default"
            }
            
            config_dict = {
                "version": "8.0.0",
                "initSources": [{
                    "catalog": [catalog_item],
                    "homeCamera": {
                        "north": float(ymax),
                        "east": float(xmax),
                        "south": float(ymin),
                        "west": float(xmin)
                    },
                    "initialCamera": {
                        "north": float(ymax),
                        "east": float(xmax),
                        "south": float(ymin),
                        "west": float(xmin)
                    },
                    "stratum": "user",
                    "workbench": [safe_resource_name],
                    "viewerMode": "3D",
                    "focusWorkbenchItems": True,
                    "baseMaps": {
                        "defaultBaseMapId": "basemap-positron",
                        "previewBaseMapId": "basemap-positron"
                    }
                }]
            }
            
            config = json.dumps(config_dict)
        elif is_tiff(resource):
            colors = []
            legend_items = []

            if view_style and view_style != 'NA':
                try:
                    with urllib.request.urlopen(view_style) as response:
                        sld_xml = response.read()
                except Exception as e:
                    print(f"Error fetching SLD file from {view_style}: {e}")
                    sld_xml = None

                if sld_xml:
                    try:
                        root = ET.fromstring(sld_xml)
                        namespaces = {'sld': 'http://www.opengis.net/sld'}
                        color_map_entries = root.findall('.//sld:ColorMapEntry', namespaces)

                        for entry in color_map_entries:
                            quantity = entry.get('quantity')
                            color = entry.get('color')
                            label = entry.get('label', '')

                            if color.startswith('#'):
                                hex_color = color.lstrip('#')
                                rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                                rgb_string = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
                            else:
                                rgb_string = color

                            colors.append([float(quantity), rgb_string])
                            legend_items.append({
                                "title": label,
                                "color": color
                            })

                    except Exception as e:
                        print(f"Error parsing SLD XML: {e}")
                        colors = []
                        legend_items = []

            catalog_item = {
                "name": safe_resource_name,
                "type": "cog",
                "id": safe_resource_name,
                "url": uploaded_url,
                "cacheDuration": "5m",
                "isOpenInWorkbench": True,
                "opacity": 0.8
            }

            if colors:
                catalog_item["renderOptions"] = {
                    "single": {
                        "colors": colors,
                        "useRealValue": True
                    }
                }

            if legend_items:
                catalog_item["legends"] = [
                    {
                        "title": "Legend",
                        "items": legend_items
                    }
                ]

            config_dict = {
                "version": "8.0.0",
                "initSources": [
                    {
                        "catalog": [catalog_item],
                        "homeCamera": {
                            "north": float(ymax),
                            "east": float(xmax),
                            "south": float(ymin),
                            "west": float(xmin)
                        },
                        "initialCamera": {
                            "north": float(ymax),
                            "east": float(xmax),
                            "south": float(ymin),
                            "west": float(xmin)
                        },
                        "stratum": "user",
                        "workbench": [safe_resource_name],
                        "viewerMode": "3D",
                        "focusWorkbenchItems": True,
                        "baseMaps": {
                            "defaultBaseMapId": "basemap-positron",
                            "previewBaseMapId": "basemap-positron"
                        }
                    }
                ]
            }

            config = json.dumps(config_dict)
        elif self.is_shp(resource):
            colors = []
            legend_items = []
            enum_colors = []  # Nueva lista para los estilos

            if view_style and view_style != 'NA':
                try:
                    with urllib.request.urlopen(view_style) as response:
                        sld_xml = response.read()
                except Exception as e:
                    print(f"Error fetching SLD file from {view_style}: {e}")
                    sld_xml = None

                if sld_xml:
                    try:
                        root = ET.fromstring(sld_xml)
                        namespaces = {
                            'sld': 'http://www.opengis.net/sld',
                            'se': 'http://www.opengis.net/se',
                            'ogc': 'http://www.opengis.net/ogc'
                        }
                        
                        rules = root.findall('.//se:Rule', namespaces)
                        valid_property_name = None  # Para almacenar un property_name válido
                        
                        for rule in rules:
                            name = rule.find('se:Name', namespaces)
                            title = rule.find('.//se:Title', namespaces)
                            fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', namespaces)
                            property_name = rule.find('.//ogc:PropertyName', namespaces)
                            property_value = rule.find('.//ogc:Literal', namespaces)
                            
                            if fill is not None and (name is not None or title is not None):
                                color = fill.text
                                label = (title.text if title is not None else name.text) if name is not None else "Sin etiqueta"
                                
                                # Agregar a la leyenda
                                legend_items.append({
                                    "title": label,
                                    "color": color
                                })

                                # Solo procesar si property_name tiene un valor no vacío
                                if (property_name is not None and property_name.text and 
                                    property_name.text.strip() and property_value is not None):
                                    valid_property_name = property_name.text.strip()
                                    enum_colors.append({
                                        "value": property_value.text,
                                        "color": f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},1)"
                                    })

                    except Exception as e:
                        print(f"Error parsing SLD XML: {e}")
                        legend_items = []
                        enum_colors = []

            catalog_item = {
                "name": safe_resource_name,
                "type": "shp",
                "id": safe_resource_name,
                "url": uploaded_url,
                "cacheDuration": "5m",
                "isOpenInWorkbench": True,
                "opacity": 0.8
            }

            if legend_items:
                catalog_item["legends"] = [{
                    "title": "Legend",
                    "items": legend_items
                }]

            # Solo agregar estilos si tenemos un property_name válido y enum_colors
            if enum_colors and valid_property_name:
                catalog_item["styles"] = [{
                    "id": valid_property_name,
                    "color": {
                        "enumColors": enum_colors,
                        "colorPalette": "HighContrast"
                    }
                }]
                catalog_item["activeStyle"] = valid_property_name

            config_dict = {
                "version": "8.0.0",
                "initSources": [{
                    "catalog": [catalog_item],
                    "homeCamera": {
                        "north": float(ymax),
                        "east": float(xmax),
                        "south": float(ymin),
                        "west": float(xmin)
                    },
                    "initialCamera": {
                        "north": float(ymax),
                        "east": float(xmax),
                        "south": float(ymin),
                        "west": float(xmin)
                    },
                    "stratum": "user",
                    "workbench": [safe_resource_name],
                    "viewerMode": "3D",
                    "focusWorkbenchItems": True,
                    "baseMaps": {
                        "defaultBaseMapId": "basemap-positron",
                        "previewBaseMapId": "basemap-positron"
                    }
                }]
            }

            config = json.dumps(config_dict)
        else:
            config = f"""{{
                "version": "8.0.0",
                "initSources": [
                    {{
                        "catalog": [
                            {{
                                "name": "{safe_resource_name}",
                                "type": "group",
                                "isOpen": true,
                                "members": [
                                    {{
                                        "id": "{safe_resource_name}",
                                        "name": "{safe_resource_name}",
                                        "type": "{resource["format"].lower()}",
                                        "url": "{uploaded_url}",
                                        "cacheDuration": "5m",
                                        "isOpenInWorkbench": true
                                    }}
                                ]
                            }}
                        ],
                        "homeCamera": {{
                            "north": {ymax},
                            "east": {xmax},
                            "south": {ymin},
                            "west": {xmin}
                        }},
                        "initialCamera": {{
                            "north": {ymax},
                            "east": {xmax},
                            "south": {ymin},
                            "west": {xmin}
                        }},
                        "stratum": "user",
                        "models": {{
                            "//{safe_resource_name}": {{
                                "isOpen": true,
                                "knownContainerUniqueIds": [
                                    "/"
                                ],
                                "type": "group"
                            }},
                            "{safe_resource_name}": {{
                                "show": true,
                                "isOpenInWorkbench": true,
                                "knownContainerUniqueIds": [
                                    "//{safe_resource_name}"
                                ],
                                "type": "{resource["format"].lower()}"
                            }},
                            "/": {{
                                "type": "group"
                            }}
                        }},
                        "workbench": [
                            "{safe_resource_name}"
                        ],
                        "viewerMode": "3dSmooth",
                        "focusWorkbenchItems": true,
                        "baseMaps": {{
                            "defaultBaseMapId": "basemap-positron",
                            "previewBaseMapId": "basemap-positron"
                        }}
                    }}
                ]
            }}"""

        if(view_custom_config == 'NA' or view_custom_config == ''):
            encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))
        else:
            try:
                # Extraer el parámetro 'start' o 'share' de la URL
                parsed_url = urllib.parse.urlparse(view_custom_config)
                fragment = parsed_url.fragment
                
                if fragment.startswith('share='):
                    # Caso de URL con #share
                    gist_id = fragment.split('=g-')[1]
                    gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
                    try:
                        with urllib.request.urlopen(gist_url) as response:
                            decoded_param = response.read().decode('utf-8')
                    except Exception as e:
                        print(f"Error fetching gist config: {e}")
                        decoded_param = urllib.parse.unquote(json.dumps(json.loads(config)))
                else:
                    # Caso original con #start
                    start_param = fragment.split('=', 1)[1]
                    decoded_param = urllib.parse.unquote(start_param)
                
                # Parsear el JSON
                start_data = json.loads(decoded_param)
                
                # Función auxiliar para decodificar nombres
                def decode_names(obj):
                    if isinstance(obj, dict):
                        new_dict = {}
                        for key, value in obj.items():
                            # Decodificar el key si contiene '+'
                            new_key = urllib.parse.unquote_plus(key) if '+' in key else key
                            
                            if isinstance(value, dict):
                                # Si hay campos específicos que contienen nombres
                                if 'name' in value:
                                    value['name'] = urllib.parse.unquote_plus(value['name'])
                                if 'title' in value:
                                    value['title'] = urllib.parse.unquote_plus(value['title'])
                                if 'legend' in value and isinstance(value['legend'], dict):
                                    if 'title' in value['legend']:
                                        value['legend']['title'] = urllib.parse.unquote_plus(value['legend']['title'])
                                
                                value = decode_names(value)
                            elif isinstance(value, list):
                                value = [urllib.parse.unquote_plus(item) if isinstance(item, str) else decode_names(item) for item in value]
                            elif isinstance(value, str) and '+' in value:
                                value = urllib.parse.unquote_plus(value)
                                
                            new_dict[new_key] = value
                        return new_dict
                    elif isinstance(obj, list):
                        return [decode_names(item) for item in obj]
                    return obj

                # Decodificar todos los nombres en el custom config
                start_data = decode_names(start_data)

                # Obtener los estilos del SLD si existe y el recurso es shp o cog
                sld_styles = None
                if view_style and view_style != 'NA' and (resource["format"].lower() in ['shp', 'tif', 'tiff', 'geotiff']):
                    try:
                        with urllib.request.urlopen(view_style) as response:
                            sld_xml = response.read()
                            root = ET.fromstring(sld_xml)
                            namespaces = {
                                'sld': 'http://www.opengis.net/sld',
                                'se': 'http://www.opengis.net/se',
                                'ogc': 'http://www.opengis.net/ogc'
                            }
                            
                            legend_items = []
                            if resource["format"].lower() == 'shp':
                                # Procesar estilos para SHP
                                enum_colors = []
                                rules = root.findall('.//se:Rule', namespaces)
                                valid_property_name = None  # Para almacenar un property_name válido
                                
                                for rule in rules:
                                    name = rule.find('se:Name', namespaces)
                                    title = rule.find('.//se:Title', namespaces)
                                    fill = rule.find('.//se:Fill/se:SvgParameter[@name="fill"]', namespaces)
                                    property_name = rule.find('.//ogc:PropertyName', namespaces)
                                    property_value = rule.find('.//ogc:Literal', namespaces)

                                    if fill is not None and (name is not None or title is not None):
                                        color = fill.text
                                        label = (title.text if title is not None else name.text) if name is not None else "Sin etiqueta"
                                        
                                        legend_items.append({
                                            "title": label,
                                            "color": color
                                        })

                                        # Solo procesar si property_name tiene un valor no vacío
                                        if (property_name is not None and property_name.text and 
                                            property_name.text.strip() and property_value is not None):
                                            valid_property_name = property_name.text.strip()
                                            enum_colors.append({
                                                "value": property_value.text,
                                                "color": f"rgba({int(color[1:3],16)},{int(color[3:5],16)},{int(color[5:7],16)},1)"
                                            })
                            
                                sld_styles = {
                                    "legends": [{
                                        "title": "Legend",
                                        "items": legend_items
                                    }]
                                }
                                
                                # Solo agregar styles si tenemos un property_name válido y enum_colors
                                if enum_colors and valid_property_name:
                                    sld_styles["styles"] = [{
                                        "id": valid_property_name,
                                        "color": {
                                            "enumColors": enum_colors,
                                            "colorPalette": "HighContrast"
                                        }
                                    }]
                                    sld_styles["activeStyle"] = valid_property_name
                            else:  # COG (tif, tiff, geotiff)
                                # Procesar estilos para COG
                                colors = []
                                color_map_entries = root.findall('.//sld:ColorMapEntry', namespaces)
                                
                                for entry in color_map_entries:
                                    quantity = entry.get('quantity')
                                    color = entry.get('color')
                                    label = entry.get('label', '')
                                    
                                    if color.startswith('#'):
                                        hex_color = color.lstrip('#')
                                        rgb = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
                                        rgb_string = f"rgb({rgb[0]}, {rgb[1]}, {rgb[2]})"
                                    else:
                                        rgb_string = color
                                        
                                    colors.append([float(quantity), rgb_string])
                                    legend_items.append({
                                        "title": label,
                                        "color": color
                                    })
                                
                                sld_styles = {
                                    "legends": [{
                                        "title": "Legend",
                                        "items": legend_items
                                    }]
                                }
                                
                                if colors:
                                    sld_styles["renderOptions"] = {
                                        "single": {
                                            "colors": colors,
                                            "useRealValue": True
                                        }
                                    }
                                    
                    except Exception as e:
                        print(f"Error processing SLD styles: {e}")
                        sld_styles = None
                
                # Actualizar la URL y aplicar estilos en el custom config
                for init_source in start_data['initSources']:
                    if 'models' in init_source:
                        for model_key, model_value in init_source['models'].items():
                            if isinstance(model_value, dict) and 'url' in model_value:
                                # Actualizar la URL
                                model_value['url'] = uploaded_url
                                
                                # Aplicar los nuevos estilos si existen y el tipo es SHP
                                if sld_styles:
                                    for key, value in sld_styles.items():
                                        model_value[key] = value
                encoded_config = urllib.parse.quote(json.dumps(start_data))

            except Exception as e:
                print(f"Error processing custom config: {e}")
                encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))

        return {
            'title': view_title,
            'terria_instance_url': view_terria_instance_url,
            'encoded_config': encoded_config,
            'origin': self.site_url,
            'custom_config': view_custom_config
        }

    def view_template(self, context, data_dict):
        return 'terria.html'

    def form_template(self, context, data_dict):
        # Pass resource format to template so we can show/hide resampling options
        if 'resource' in data_dict and 'format' in data_dict['resource']:
            data_dict['resource_format'] = data_dict['resource']['format']
        
        # Obtener archivos SLD del dataset si existe el package
        if 'package' in data_dict:
            package_id = data_dict['package']['id']
            sld_files = get_sld_files_from_dataset(self.site_url, package_id)
            data_dict['available_sld_files'] = sld_files
        else:
            data_dict['available_sld_files'] = []
            
        return 'terria_instance_url.html'

    plugins.implements(plugins.IActions, inherit=True)
    def get_actions(self):
        return {
            'resource_view_list': self.resource_view_list_callback
        }
