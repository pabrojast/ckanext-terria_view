import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib
import re
import functools
import os
from ckan.lib import base, uploader
from flask import abort


SUPPORTED_FORMATS = ['shp','wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*','tif','tiff','geotiff']
SUPPORTED_FILTER_EXPR = 'fq=(' + ' OR '.join(['res_format:' + s for s in SUPPORTED_FORMATS]) + ')'
SUPPORTED_FORMATS_REGEX = '^(' + '|'.join([s.replace('*', '.*') for s in SUPPORTED_FORMATS]) +')$'


def can_view_resource(resource):
    '''
    Check if we support a resource
    '''
    
    format_ = resource.get('format', '')
    if format_ == '':
        format_ = os.path.splitext(resource['url'])[1][1:]

    return re.match(SUPPORTED_FORMATS_REGEX, format_.lower()) != None


import ckan.logic.action.get as get
resource_view_list = get.resource_view_list

PLUGIN_NAME = 'terria_view'

def new_resource_view_list(plugin, context, data_dict):
    '''
    Automatically add resource view to legacy resources which did add terria_view
    on creation. Unfortunately, action patching is necessary.
    '''
    try:
        # Verificar si el recurso existe
        resource_id = data_dict.get('id')
        resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        if not resource:
            #Esto arregla que no envié por defecto un correo cuando haya un 404.
            abort(404, description='Resource not found')   
        ret = resource_view_list(context, data_dict)
    except:
        ret=[]
    has_plugin = len([r for r in ret if r['view_type'] == PLUGIN_NAME]) > 0
    if not has_plugin:
        if can_view_resource(context['resource'].__dict__):
            data_dict2 = {
            'resource_id': data_dict['id'],
            'title': plugin.default_title,
            'view_type': 'terria_view',
            'description': '',
            'terria_instance_url': '//ihp-wins.unesco.org/terria/'
            }
            # Create a new sysadmin context
            sysadmin_context = {
                'model': context['model'],
                'session': context['session'],
                'user': 'ckan.system',
                'ignore_auth': True
            }

            toolkit.get_action('resource_view_create')(sysadmin_context, data_dict2)
            ret = resource_view_list(context, data_dict)
            
    return ret


class Terria_ViewPlugin(plugins.SingletonPlugin):

    site_url = ''
    
    default_title = 'Terria Viewer'
    default_instance_url = '//ihp-wins.unesco.org/terria/'
    
    resource_view_list_callback = None
  
    # IConfigurer

    plugins.implements(plugins.IConfigurer)

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')

    # IConfigurable
    
    plugins.implements(plugins.IConfigurable, inherit=True)

    def configure(self, config):
        self.site_url = config.get('ckan.site_url', self.site_url)
        self.default_title = config.get('ckanext.' + PLUGIN_NAME + '.default_title', self.default_title)
        self.default_instance_url = config.get('ckanext.' + PLUGIN_NAME + '.default_instance_url', self.default_instance_url)
        self.resource_view_list_callback = functools.partial(new_resource_view_list, self)
    
    # IResourceView
    
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
                "terria_instance_url": []
            }
        }

    def can_view(self, data_dict):
        return can_view_resource(data_dict['resource']);

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
        
        # Contexto con información del usuario
        context = {
            'user': toolkit.g.user, 
            'auth_user_obj': toolkit.g.userobj
        }
        #fix formato
        def is_accepted_format(resource):
            # Lista de formatos aceptados
            accepted_formats = ['shp', 'kml', 'geojson', 'czml', 'csv-geo-au', 'csv-geo-nz', 'csv-geo-us', 'tif','tiff','geotiff']
            # Obtener el formato del recurso y convertirlo a minúsculas
            resource_format = resource["format"].lower()
            # Verificar si el formato está en la lista de formatos aceptados
            return any(resource_format == format for format in accepted_formats)
        # Verificar si la URL comienza con los dominios permitidos

        def is_valid_domain(url):
            return url.startswith('https://data.dev-wins.com') or url.startswith('https://ihp-wins.unesco.org/')

        if is_valid_domain(resource["url"]):
            if is_accepted_format(resource):
                if context['user']:
                    upload = uploader.get_resource_uploader(resource)
                    uploaded_url = upload.get_url_from_filename(resource_id, resource['url'])
                else:
                    uploaded_url = resource["url"]
            else:
                uploaded_url = resource["url"]
        else:
            uploaded_url = resource["url"]
          
        #idk why in some case didn't detect the default value on some server, not in local
        #Verificar si alguno de los valores es None o vacío y asignar un valor predeterminado

        def clean_coordinate(value, default):
            """
            Asegura que el valor de la coordenada es un número válido.
            Elimina espacios en blanco y verifica si el valor es numérico.
            Retorna el valor limpio o un valor predeterminado si es necesario.
            """
            if value is None:
                return default
            # Remover cualquier espacio en blanco
            cleaned_value = re.sub(r'\s+', '', str(value))
            # Verificar si el valor es un número válido (incluyendo negativos)
            if re.match(r'^-?\d+(\.\d+)?$', cleaned_value):
                return cleaned_value
            else:
                return default

        # Limpieza y asignación de valores predeterminados
        ymax = clean_coordinate(package.get("ymax"), "20")
        xmax = clean_coordinate(package.get("xmax"), "-13")
        ymin = clean_coordinate(package.get("ymin"), "-60")
        xmin = clean_coordinate(package.get("xmin"), "-108")

        #en el caso de un tif necesitamos tener consideraciones especiales
        def is_tiff(resource):
            # Lista de formatos aceptados
            accepted_formats = ['tif','tiff','geotiff']
            # Obtener el formato del recurso y convertirlo a minúsculas
            resource_format = resource["format"].lower()
            # Verificar si el formato está en la lista de formatos aceptados
            return any(resource_format == format for format in accepted_formats)
        
        if is_tiff(resource):
            import httpx
            import matplotlib.pyplot as plt
            import numpy as np

            def get_statistics_and_color_scale(url: str):
                """
                Get statistics from a COG using Titiler and generate color scale URL.
                """
                titiler_statistics_endpoint = "https://titiler.dev-wins.com/cog/statistics"
                titiler_tiles_endpoint = "https://titiler.dev-wins.com/cog/tiles/WebMercatorQuad/{z}/{x}/{y}.png"

                # Fetch file metadata to get min/max rescaling values
                response = httpx.get(
                    titiler_statistics_endpoint,
                    params={"url": url}
                )
                
                if response.status_code != 200:
                    raise Exception(f"Error fetching statistics: {response.status_code} - {response.text}")

                stats = response.json()
                
                # Print the raw statistics for debugging
                print(json.dumps(stats, indent=4))
                
                # Extract min, max, mean, stddev and histogram for the first band
                first_band = next(iter(stats.keys()))
                band_stats = stats[first_band]
                
                histogram_counts = band_stats["histogram"][0]
                bins = band_stats["histogram"][1]

                num_bins = len(bins) - 1  # Number of bins

                colormap = []

                if num_bins < 2:
                    colormap.append(([band_stats["min"], band_stats["max"]], [0, 0, 255, 255]))
                else:
                    # Determine number of ranges based on data density
                    ranges_per_bin = np.maximum(np.ceil(np.array(histogram_counts) / np.max(histogram_counts) * 3).astype(int), 1)

                    # Generate colors using matplotlib's colormap
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
                """
                Generate a list of color mappings from the colormap.
                """
                color_list = []
                for color_range, color in colormap:
                    # Convert the color from RGBA to HEX
                    hex_color = '#{:02x}{:02x}{:02x}'.format(color[0], color[1], color[2])
                    title = f"{int(color_range[0])} - {int(color_range[1])}"
                    color_list.append({"title": title, "color": hex_color})

                return color_list

            def get_zoom_levels(url: str):
                """
                Get min and max zoom levels from COG metadata.
                """
                titiler_info_endpoint = "https://titiler.dev-wins.com/cog/info"

                # Fetch file metadata to get min/max zoom levels
                response = httpx.get(
                    titiler_info_endpoint,
                    params={"url": url}
                )
                
                if response.status_code != 200:
                    raise Exception(f"Error fetching file info: {response.status_code} - {response.text}")

                info = response.json()
                bounds = info.get("bounds", None)
                minzoom = info.get("minzoom", None)
                maxzoom = info.get("maxzoom", None)

                return bounds, minzoom, maxzoom


            # Example usage
            result_url, colormap = get_statistics_and_color_scale(uploaded_url)
            color_scale_list = generate_color_list(colormap)
            bounds, minzoom, maxzoom = get_zoom_levels(uploaded_url)

            print("Generated URL:")
            print(result_url)
            print("\nGenerated Color Scale List:")
            print(json.dumps(color_scale_list, indent=4))
            print("\nBounds, Min Zoom, Max Zoom:")
            print(bounds, minzoom, maxzoom)
            
            config ="""{ 
                        "version": "8.0.0",
                        "initSources": [
                    { 
                            "catalog": [
                            {
                                "name": """+'"'+resource["name"]+'"'+""",
                                "type": "url-template-imagery",
                                "id": """+'"'+resource["name"]+'"'+""",
                                "name": """+'"'+resource["name"]+'"'+""",
                                "type": "url-template-imagery",
                                "url": """+'"'+result_url+'"'+""",
                                "cacheDuration": "5m",
                                "isOpenInWorkbench": true,
                                "minimumLevel":  """+str(minzoom)+""",
	                            "maximumLevel": """+str(maxzoom)+""",
                                "opacity": 0.8,
                                "legends": [
                                    {
                                    "title": """+'"'+resource["name"]+'"'+""",
                                    "items": """+str(json.dumps(color_scale_list, indent=4))+"""
                                    }
                                         ]
                            }
                            ],
                            "homeCamera": {
                                "north": """+ymax+""",
                                "east": """+xmax+""",
                                "south": """+ymin+""",
                                "west": """+xmin+"""
                                          },
                                "initialCamera": {
                                "north": """+ymax+""",
                                "east": """+xmax+""",
                                "south": """+ymin+""",
                                "west": """+xmin+"""
                                         },
                            "stratum": "user",
                            "workbench": [
                                """+'"'+resource["name"]+'"'+"""
                                ],
                            "viewerMode": "3dSmooth",
                            "focusWorkbenchItems": true,
                            "baseMaps": {
                                "defaultBaseMapId": "basemap-positron",
                                "previewBaseMapId": "basemap-positron"
                                        }
                            }
                            ]
                        }"""


        else:
            config ="""{ 
                        "version": "8.0.0",
                        "initSources": [
                    {
                            "catalog": [
                            {
                                "name": """+'"'+resource["name"]+'"'+""",
                                "type": "group",
                                "isOpen": true,
                                "members": [
                                { "id": """+'"'+resource["name"]+'"'+""",
                                    "name": """+'"'+resource["name"]+'"'+""",
                                    "type": """+'"'+resource["format"].lower()+'"'+""",
                                    "url": """+'"'+uploaded_url+'"'+""",
                                    "cacheDuration": "5m",
                                    "isOpenInWorkbench": true
                                }
                                ]
                            }
                            ],
                        "homeCamera": {
                            "north": """+ymax+""",
                            "east": """+xmax+""",
                            "south": """+ymin+""",
                            "west": """+xmin+"""
                },
                            "initialCamera": {
                            "north": """+ymax+""",
                            "east": """+xmax+""",
                            "south": """+ymin+""",
                            "west": """+xmin+"""
                },
                        "stratum": "user",
                            "models": {
                            """+'"//'+resource["name"]+'"'+""": {
                                "isOpen": true,
                                "knownContainerUniqueIds": [
                                "/"
                                ],
                                "type": "group"
                            },
                            """+'"'+resource["name"]+'"'+""": {
                                "show": true,
                                "isOpenInWorkbench": true,
                                "knownContainerUniqueIds": [
                                """+'"//'+resource["name"]+'"'+"""
                                ],
                                "type": """+'"'+resource["format"].lower()+'"'+"""
                            },
                            "/": {
                                "type": "group"
                            }
                            },
                            "workbench": [
                            """+'"'+resource["name"]+'"'+"""
                            ],
                            "viewerMode": "3dSmooth",
                        "focusWorkbenchItems": true,
                            "baseMaps": {
                            "defaultBaseMapId": "basemap-positron",
                            "previewBaseMapId": "basemap-positron"
                            }
                        }
                        ]
                    }"""


        encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))
        
        return {
            'title': view_title,
            'terria_instance_url': view_terria_instance_url,
            'encoded_config': encoded_config,
            'origin': self.site_url
        }

    def view_template(self, context, data_dict):
        return 'terria.html'

    def form_template(self, context, data_dict):
        # The template used to generate the custom form elements. See below.
        return 'terria_instance_url.html'


    # IActions - Make it so that this plugin behaves like the
    # deprecated IResourcePreview interface and better

    plugins.implements(plugins.IActions, inherit=True)

    def get_actions(self):
        return {
            'resource_view_list': self.resource_view_list_callback
        }

    '''
    # IResourcePreview - deprecated implementation
    
    plugins.implements(plugins.IResourcePreview, inherit=True)
    
    def can_preview(self, data_dict):
        return {
            'can_preview': True,
            'quality': 2
        }

    def preview_template(self, context, data_dict):
        return 'terria.html'
    '''