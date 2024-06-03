import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib
import re
import functools
import os
from ckan.lib import base, uploader


SUPPORTED_FORMATS = ['shp','wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*']
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
        ret = resource_view_list(context, data_dict)
    except NotFound:
        ret=[]
    has_plugin = len([r for r in ret if r['view_type'] == PLUGIN_NAME]) > 0
    if not has_plugin:
        if can_view_resource(context['resource'].__dict__):
            data_dict2 = {
            'resource_id': data_dict['id'],
            'title': plugin.default_title,
            'view_type': 'terria_view',
            'description': '',
            'terria_instance_url': '//terria.dev-wins.com'
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
    default_instance_url = '//terria.dev-wins.com'
    
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
            accepted_formats = ['shp', 'kml', 'geojson', 'czml', 'csv-geo-au', 'csv-geo-nz', 'csv-geo-us']
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