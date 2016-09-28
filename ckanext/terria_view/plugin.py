import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib
import re
import functools
import os


SUPPORTED_FORMATS = ['wms', 'wfs', 'kml', 'esri rest', 'geojson', 'czml', 'csv-geo-*']
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
    ret = resource_view_list(context, data_dict)
    has_plugin = len([r for r in ret if r['view_type'] == PLUGIN_NAME]) > 0
    if not has_plugin:
        if can_view_resource(context['resource'].__dict__):
            ret.append({
                "description": "", 
                "title": plugin.default_title, 
                "resource_id": data_dict['id'], 
                "view_type": "terria_view", 
                "id": "00000000-0000-0000-0000-000000000000", 
                "package_id": "00000000-0000-0000-0000-000000000000"
            });
    return ret


class Terria_ViewPlugin(plugins.SingletonPlugin):

    site_url = ''
    
    default_title = 'National Map'
    default_instance_url = '//nationalmap.gov.au'
    
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
        organisation = package['organization']
        organization_id = organisation['id']
        view = data_dict['resource_view']
        view_title = view.get('title', self.default_title)
        view_terria_instance_url = view.get('terria_instance_url', self.default_instance_url)

        config = {  
            "version":"0.0.05",
            "initSources":[  
                {  
                    "catalog":[  
                        {  
                            "name":"User-Added Data",
                            "description":"The group for data that was added by the user via the Add Data panel.",
                            "isUserSupplied":True,
                            "id":"Root Group/User-Added Data",
                            "isOpen":True,
                            "type":"group"
                        },
                        {  
                            "name":"" + self.site_url + "",
                            "isUserSupplied":True,
                            "id":"Root Group/" + self.site_url + "",
                            "isOpen":True,
                            "url":"" + self.site_url + "",
                            "filterQuery":[  
                                SUPPORTED_FILTER_EXPR
                            ],
                            "groupBy":"organization",
                            "includeWms":True,
                            "includeWfs":True,
                            "includeKml":True,
                            "includeCsv":True,
                            "includeEsriMapServer":True,
                            "includeGeoJson":True,
                            "includeCzml":True,
                            "type":"ckan"
                        }
                    ]
                },
                {  
                    "sharedCatalogMembers":{  
                        "Root Group/User-Added Data":{  
                            "isOpen":True,
                            "type":"group",
                            "parents":[  

                            ]
                        },
                        "Root Group/" + self.site_url + "":{  
                            "isOpen":True,
                            "type":"ckan",
                            "parents":[  

                            ]
                        },
                        "Root Group/" + self.site_url + "/" + organization_id + "":{  
                            "isOpen":True,
                            "type":"group",
                            "parents":[  
                                "Root Group/" + self.site_url + ""
                            ]
                        },
                        "Root Group/" + self.site_url + "/" + organization_id + "/" + resource_id + "":{  
                            "nowViewingIndex":0,
                            "isEnabled":True,
                            "isShown":True,
                            "isLegendVisible":True,
                            "opacity":0.6,
                            "keepOnTop":False,
                            "disableUserChanges":False,
                            "tableStyle":{  
                                "scale":1,
                                "colorBinMethod":"auto",
                                "legendTicks":3,
                                "dataVariable":"id"
                            },
                            "type":"csv",
                            "parents":[  
                                "Root Group/" + self.site_url + "",
                                "Root Group/" + self.site_url + "/" + organization_id + ""
                            ]
                        }
                    }
                }
            ]
        }
        
        encoded_config = urllib.quote(json.dumps(config))
        
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
