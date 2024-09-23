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

SUPPORTED_FORMATS = ['shp','wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*','WMTS', 'tif','tiff','geotiff']
#SUPPORTED_FORMATS = ['shp','wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*']
SUPPORTED_FILTER_EXPR = 'fq=(' + ' OR '.join(['res_format:' + s for s in SUPPORTED_FORMATS]) + ')'
SUPPORTED_FORMATS_REGEX = '^(' + '|'.join([s.replace('*', '.*') for s in SUPPORTED_FORMATS]) +')$'

def can_view_resource(resource):
    format_ = resource.get('format', '')
    if format_ == '':
        format_ = os.path.splitext(resource['url'])[1][1:]
    return re.match(SUPPORTED_FORMATS_REGEX, format_.lower()) != None

resource_view_list = get.resource_view_list

PLUGIN_NAME = 'terria_view'

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
                'terria_instance_url': '//ihp-wins.unesco.org/terria/'
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
    default_instance_url = '//ihp-wins.unesco.org/terria/'
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
            'iframed': False,
            "schema": {
                "terria_instance_url": [],
                "custom_config": []
            }
        }

    def can_view(self, data_dict):
        return can_view_resource(data_dict['resource'])

    def setup_template_variables(self, context, data_dict):
        package = data_dict['package']
        resource = data_dict['resource']
        resource_id = resource['id']
        organization = package['organization']
        name = package['name']
        organization_id = organization['id']
        view = data_dict['resource_view']
        view_title = view.get('title', self.default_title)
        view_terria_instance_url = view.get('terria_instance_url', self.default_instance_url)
        view_custom_config = view.get('custom_config', 'NA')
        
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
                if user_context['user']:
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
            #this depcretaed the use in old views
            accepted_formats = ['tif','tiff','geotiff']
            #accepted_formats = []
            resource_format = resource["format"].lower()
            return any(resource_format == format for format in accepted_formats)

        if is_tiff(resource):

            config = f"""{{
                "version": "8.0.0",
                "initSources": [
                    {{
                        "catalog": [
                            {{
                                "name": "{resource["name"]}",
                                "type": "cog",
                                "id": "{resource["name"]}",
                                "name": "{resource["name"]}",
                                "type": "cog",
                                "url": "{uploaded_url}",
                                "cacheDuration": "5m",
                                "isOpenInWorkbench": true,
                                "opacity": 0.8
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
                        "workbench": [
                            "{resource["name"]}"
                        ],
                        "viewerMode": "3D",
                        "focusWorkbenchItems": true,
                        "baseMaps": {{
                            "defaultBaseMapId": "basemap-positron",
                            "previewBaseMapId": "basemap-positron"
                        }}
                    }}
                ]
            }}"""
        else:
            config = f"""{{
                "version": "8.0.0",
                "initSources": [
                    {{
                        "catalog": [
                            {{
                                "name": "{resource["name"]}",
                                "type": "group",
                                "isOpen": true,
                                "members": [
                                    {{
                                        "id": "{resource["name"]}",
                                        "name": "{resource["name"]}",
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
                            "//{resource["name"]}": {{
                                "isOpen": true,
                                "knownContainerUniqueIds": [
                                    "/"
                                ],
                                "type": "group"
                            }},
                            "{resource["name"]}": {{
                                "show": true,
                                "isOpenInWorkbench": true,
                                "knownContainerUniqueIds": [
                                    "//{resource["name"]}"
                                ],
                                "type": "{resource["format"].lower()}"
                            }},
                            "/": {{
                                "type": "group"
                            }}
                        }},
                        "workbench": [
                            "{resource["name"]}"
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
                # Extraer el parámetro 'start' de la URL
                parsed_url = urllib.parse.urlparse(view_custom_config)
                fragment = parsed_url.fragment
                start_param = fragment.split('=', 1)[1]
                decoded_param = urllib.parse.unquote(start_param)
                
                # Parsear el JSON
                start_data = json.loads(decoded_param)
                
                # Modificar el valor del parámetro 'url' en el JSON
                for init_source in start_data['initSources']:
                    if 'models' in init_source:
                        for model_key, model_value in init_source['models'].items():
                            if 'name' in model_value:
                                model_value['name'] = model_value['name'].replace('+', ' ')
                            if 'url' in model_value:
                                model_value['url'] = uploaded_url
                            if 'styles' in model_value:
                                for style in model_value['styles']:                   
                                    if 'color' in style and 'legend' in style['color']:
                                        style['color']['legend']['title'] = style['color']['legend']['title'].replace('+', ' ')
                                
                
                # Codificar nuevamente el JSON
                updated_start_param = json.dumps(start_data)
                encoded_config = urllib.parse.quote(updated_start_param)

            except (IndexError, json.JSONDecodeError) as e:
                # Si ocurre un error, se usa el encoded_config básico
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
        return 'terria_instance_url.html'

    plugins.implements(plugins.IActions, inherit=True)
    def get_actions(self):
        return {
            'resource_view_list': self.resource_view_list_callback
        }
