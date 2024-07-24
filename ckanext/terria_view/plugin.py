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

SUPPORTED_FORMATS = ['shp','wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*','tif','tiff','geotiff']
#SUPPORTED_FORMATS = ['shp','wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*']
SUPPORTED_FILTER_EXPR = 'fq=(' + ' OR '.join(['res_format:' + s for s in SUPPORTED_FORMATS]) + ')'
SUPPORTED_FORMATS_REGEX = '^(' + '|'.join([s.replace('*', '.*') for s in SUPPORTED_FORMATS]) +')$'

def can_view_resource(resource):
    print('can view')
    format_ = resource.get('format', '')
    if format_ == '':
        format_ = os.path.splitext(resource['url'])[1][1:]
    return re.match(SUPPORTED_FORMATS_REGEX, format_.lower()) != None

import ckan.logic.action.get as get
resource_view_list = get.resource_view_list

PLUGIN_NAME = 'terria_view'

def new_resource_view_list(plugin, context, data_dict):

    try:
        ret = resource_view_list(context, data_dict)
        resource_id = data_dict.get('id')

        # Verificar si hay un activity_id en la URL, así no intenta crear nada.
        if 'activity_id' in request.args:
            print("Activity ID detected, skipping resource view creation.")
            return ret
        
        resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        if not resource:
            print("Debug: Resource not found")
            abort(404, description='Resource not found')

    except Exception as e:
        print(f"Error retrieving resource view list: {e}")

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
            accepted_formats = ['shp', 'kml', 'geojson', 'czml', 'csv-geo-au', 'csv-geo-nz', 'csv-geo-us', 'tif','tiff','geotiff']
            resource_format = resource["format"].lower()
            return any(resource_format == format for format in accepted_formats)

        def is_valid_domain(url):
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

        ymax = clean_coordinate(package.get("ymax"), "20")
        xmax = clean_coordinate(package.get("xmax"), "-13")
        ymin = clean_coordinate(package.get("ymin"), "-60")
        xmin = clean_coordinate(package.get("xmin"), "-108")

        def is_tiff(resource):
            accepted_formats = ['tif','tiff','geotiff']
            resource_format = resource["format"].lower()
            return any(resource_format == format for format in accepted_formats)

        if is_tiff(resource):
            import httpx
            import matplotlib.pyplot as plt
            import numpy as np

            def fetch_with_retries(endpoint, params, retries=3, delay=5, timeout=30.0):
                for attempt in range(retries):
                    try:
                        response = httpx.get(endpoint, params=params, timeout=timeout)
                        response.raise_for_status()
                        return response
                    except httpx.ReadTimeout:
                        print(f"Timeout al intentar acceder a {endpoint} (intento {attempt + 1} de {retries})")
                        if attempt < retries - 1:
                            sleep(delay)
                        else:
                            raise
                    except httpx.RequestError as exc:
                        print(f"Error en la solicitud: {exc} (intento {attempt + 1} de {retries})")
                        if attempt < retries - 1:
                            sleep(delay)
                        else:
                            raise

            def get_statistics_and_color_scale(url: str):
                titiler_statistics_endpoint = "https://titiler.dev-wins.com/cog/statistics"
                titiler_tiles_endpoint = "https://titiler.dev-wins.com/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png"

                response = fetch_with_retries(titiler_statistics_endpoint, {"url": url})

                stats = response.json()
                print(json.dumps(stats, indent=4))

                first_band = next(iter(stats.keys()))
                band_stats = stats[first_band]
                
                histogram_counts = band_stats["histogram"][0]
                bins = band_stats["histogram"][1]

                num_bins = len(bins) - 1

                colormap = []

                if num_bins < 2:
                    colormap.append(([band_stats["min"], band_stats["max"]], [0, 0, 255, 255]))
                else:
                    ranges_per_bin = np.maximum(np.ceil(np.array(histogram_counts) / np.max(histogram_counts) * 3).astype(int), 1)

                    total_ranges = np.sum(ranges_per_bin)
                    cmap = plt.get_cmap('viridis', total_ranges)
                    color_index = 0

                    for i in range(num_bins):
                        bin_start = bins[i]
                        bin_end = bins[i+1]
                        bin_ranges = ranges_per_bin[i]

                        if bin_ranges > 0:
                            range_step = (bin_end - bin_start) / bin_ranges
                            for j in range(bin_ranges):
                                range_start = bin_start + j * range_step
                                range_end = bin_start + (j + 1) * range_step
                                color = [int(cmap(color_index)[k] * 255) for k in range(4)]
                                colormap.append(([range_start, range_end], color))
                                color_index += 1

                cmap_param = json.dumps(colormap)
                request_url = f"{titiler_tiles_endpoint}?url={url}&bidx=1&colormap={cmap_param}"
                return request_url, colormap

            def generate_color_list(colormap):
                color_list = []
                for color_range, color in colormap:
                    hex_color = '#{:02x}{:02x}{:02x}'.format(color[0], color[1], color[2])
                    title = f"{int(color_range[0])} - {int(color_range[1])}"
                    color_list.append({"title": title, "color": hex_color})
                return color_list

            def get_zoom_levels(url: str):
                titiler_info_endpoint = "https://titiler.dev-wins.com/cog/info"
                response = fetch_with_retries(titiler_info_endpoint, {"url": url})
                info = response.json()
                bounds = info.get("bounds", None)
                minzoom = info.get("minzoom", None)
                maxzoom = info.get("maxzoom", None)
                return bounds, minzoom, maxzoom

            result_url, colormap = get_statistics_and_color_scale(uploaded_url)
            color_scale_list = generate_color_list(colormap)
            bounds, minzoom, maxzoom = get_zoom_levels(uploaded_url)

            print("Generated URL:")
            print(result_url)
            print("\nGenerated Color Scale List:")
            print(json.dumps(color_scale_list, indent=4))
            print("\nBounds, Min Zoom, Max Zoom:")
            print(bounds, minzoom, maxzoom)
            
            config = f"""{{
                "version": "8.0.0",
                "initSources": [
                    {{
                        "catalog": [
                            {{
                                "name": "{resource["name"]}",
                                "type": "url-template-imagery",
                                "id": "{resource["name"]}",
                                "name": "{resource["name"]}",
                                "type": "url-template-imagery",
                                "url": "{result_url}",
                                "cacheDuration": "5m",
                                "isOpenInWorkbench": true,
                                "minimumLevel": {minzoom},
                                "maximumLevel": {maxzoom},
                                "opacity": 0.8,
                                "legends": [
                                    {{
                                        "title": "{resource["name"]}",
                                        "items": {json.dumps(color_scale_list, indent=4)}
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
                        "workbench": [
                            "{resource["name"]}"
                        ],
                        "viewerMode": "2D",
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

        if(view_custom_config == 'NA'):
            encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))
        else:
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
                        if 'url' in model_value:
                            model_value['url'] = uploaded_url

            # Codificar nuevamente el JSON
            updated_start_param = json.dumps(start_data)
            encoded_config = urllib.parse.quote(updated_start_param)

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
