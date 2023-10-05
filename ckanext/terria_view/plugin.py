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

        # config = {  
            # "version":"0.0.05",
            # "initSources":[  
                # {  
                    # "catalog":[  
                        # {  
                            # "name":"User-Added Data",
                            # "description":"The group for data that was added by the user via the Add Data panel.",
                            # "isUserSupplied":True,
                            # "id":"Root Group/User-Added Data",
                            # "isOpen":True,
                            # "type":"group"
                        # },
                        # {  
                            # "name":"" + self.site_url + "",
                            # "isUserSupplied":True,
                            # "id":"Root Group/" + self.site_url + "",
                            # "isOpen":True,
                            # "url":"" + self.site_url + "",
                            # "filterQuery":[  
                                # SUPPORTED_FILTER_EXPR
                            # ],
                            # "groupBy":"organization",
                            # "includeWms":True,
                            # "includeWfs":True,
                            # "includeKml":True,
                            # "includeCsv":True,
                            # "includeEsriMapServer":True,
                            # "includeGeoJson":True,
                            # "includeCzml":True,
                            # "type":"ckan"
                        # }
                    # ]
                # },
                # {  
                    # "sharedCatalogMembers":{  
                        # "Root Group/User-Added Data":{  
                            # "isOpen":True,
                            # "type":"group",
                            # "parents":[  

                            # ]
                        # },
                        # "Root Group/" + self.site_url + "":{  
                            # "isOpen":True,
                            # "type":"ckan",
                            # "parents":[  

                            # ]
                        # },
                        # "Root Group/" + self.site_url + "/" + organization_id + "":{  
                            # "isOpen":True,
                            # "type":"group",
                            # "parents":[  
                                # "Root Group/" + self.site_url + ""
                            # ]
                        # },
                        # "Root Group/" + self.site_url + "/" + organization_id + "/" + resource_id + "":{  
                            # "nowViewingIndex":0,
                            # "isEnabled":True,
                            # "isShown":True,
                            # "isLegendVisible":True,
                            # "opacity":0.6,
                            # "keepOnTop":False,
                            # "disableUserChanges":False,
                            # "tableStyle":{  
                                # "scale":1,
                                # "colorBinMethod":"auto",
                                # "legendTicks":3,
                                # "dataVariable":"id"
                            # },
                            # "type":"csv",
                            # "parents":[  
                                # "Root Group/" + self.site_url + "",
                                # "Root Group/" + self.site_url + "/" + organization_id + ""
                            # ]
                        # }
                    # }
                # }
            # ]
        # }
            config = {  
            "version":"0.0.05",
            "initSources":[  
                {  
                
                "catalog": [
                        {
                          "name": "data.dev-wins.com",
                          "shareKeys": [
                            "Root Group"
                          ],
                          "url": "https://pabrojast.github.io/prod.json",
                          "type": "terria-reference",
                          "isGroup": true
                        },
                                {
                              "name": "Power Stations (with template)",
                              "type": "kml",
                              "url": "https://data.dev-wins.com/dataset/9897691a-c6d4-416c-8d16-02e0e7db1a2f/resource/64abc581-d97b-45ae-bd2d-6bc6b2e5953d/download/bwa.kml",
                              "cacheDuration": "5m",
                              "featureInfoTemplate": {"template": "<h3>{{Station Name}} ({{DUID}})</h3><p><strong>{{Participant}}</strong><div><strong>{{Current Output (MW)}}MW</strong> at {{Most Recent Output Time (AEST)}}</div><div><strong>{{Current % of Reg Cap}}%</strong> of {{Reg Cap (MW)}}MW registered capacity</div><div><strong>{{Current % of Max Cap}}%</strong> of {{Max Cap (MW)}}MW maximum capacity</div></p><table><tbody><tr><td>Category</td><td class='strong'>{{Category}}</td></tr><tr><td>Classification</td><td class='strong'>{{Classification}}</td></tr><tr><td>Fuel Source</td><td class='strong'>{{Fuel Source - Primary}} ({{Fuel Source - Descriptor}})</td></tr><tr><td>Technology Type</td><td class='strong'>{{Technology Type - Primary}} ({{Technology Type - Descriptor}})</td></tr><tr><td>Physical Unit No.</td><td class='strong'>{{Physical Unit No_}}</td></tr><tr><td>Aggregation</td><td class='strong'>{{Aggregation}}</td></tr><tr><td>Unit Size (MW)</td><td class='strong'>{{Unit Size (MW)}}</td></tr><tr><td>Power generation</td><td><chart sources='http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=1D,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=5D,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=30D,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=3M' source-names='1d,5d,30d,3m' downloads='http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=1D,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=5D,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=30D,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=3M,http://services.aremi.nicta.com.au/aemo/v4/duidcsv/{{DUID}}?offset=1Y' download-names='1d,5d,30d,3m,1y' preview-x-label='Last 24 hours' column-names='Time,Power Generation' column-units='Date,MW'></chart></td></tr></tbody></table>"}
                            }
                          
                      ]
                    
                },
                "homeCamera": {
                            "north": 0,
                            "east": 50,
                            "south": -75,
                            "west": 98
                          },
              "viewerMode": "3dSmooth",
              "baseMaps": {
                            "defaultBaseMapId": "basemap-positron",
                            "previewBaseMapId": "basemap-positron"
              }
                
            ]
        }
        
        encoded_config = urllib.parse.quote(json.dumps(config))
        
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
