import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib
import re

class Terria_ViewPlugin(plugins.SingletonPlugin):

    Site_Url = ''
    Supported_Formats_Regex = '^(wms|wfs|kml|kmz|gjson|geojson|czml|csv-geo-.*)'
    Default_Title = 'National Map'
    Default_Instance_Url = 'http://nationalmap.gov.au'
  
    # IConfigurer

    plugins.implements(plugins.IConfigurer)

    def update_config(self, config_):
        toolkit.add_template_directory(config_, 'templates')

    # IConfigurable
    
    plugins.implements(plugins.IConfigurable, inherit=True)

    def configure(self, config):
        self.Site_Url = config.get('ckan.site_url', self.Site_Url)
        self.Default_Title = config.get('ckan.terria_view.instance_title', self.Default_Title)
        self.Default_Instance_Url = config.get('ckan.terria_view.instance_url', self.Default_Instance_Url)
    
    # IResourceView
    
    plugins.implements(plugins.IResourceView, inherit=True)
  
    def info(self):
        return {
            'name': 'terria_view',
            'title': toolkit._('View In A TerriaJS Instance'),
            'default_title': self.Default_Title,
            'icon': 'globe',
            'always_available': True,
            'iframed': False
        }

    def can_view(self, data_dict):
        resource = data_dict['resource']
        format_lower = resource['format'].lower()
        if (format_lower == ''):
            format_lower = os.path.splitext(resource['url'])[1][1:].lower()
        return re.match(self.Supported_Formats_Regex, format_lower) != None

    def setup_template_variables(self, context, data_dict):
        resource = data_dict['resource']
        item = {
            "type": "ckan-resource",
            "name": resource['name'],
            "isUserSupplied": True,
            "isOpen": True,
            "isEnabled": True,
            "resourceId": resource['id'],
            "datasetId": resource['package_id'],
            "url": self.Site_Url,
            "zoomOnEnable": True
        }
        config = {
            "version": "0.0.03",
            "initSources": [{
                "catalog": [{
                    "type": "group",
                    "name": "User-Added Data",
                    "description": "The group for data that was added by the user via the Add Data panel.",
                    "isUserSupplied": True,
                    "isOpen": True,
                    "items": [item]
                }],
                "catalogIsUserSupplied": True
            }]
        }
        encoded_config = urllib.quote(json.dumps(config))

        view = {}
        
        if 'resource_view' in data_dict:
            view = data_dict['resource_view']
        
        if 'title' not in view:
            view['title'] = self.Default_Title
        
        if 'terria_instance_url' not in view:
            view['terria_instance_url'] = self.Default_Instance_Url
        
        terria_instance_url = view['terria_instance_url']
        
        preview_url = terria_instance_url + '#start=' + encoded_config
        
        plugins.toolkit.c.preview_url = preview_url
        
        return {
            'preview_url': preview_url
        }

    def view_template(self, context, data_dict):
        return 'terria.html'

    def form_template(self, context, data_dict):
        # The template used to generate the custom form elements. See below.
        return 'terria_instance_url.html'

    # IResourcePreview - deprecated but still needed
    
    plugins.implements(plugins.IResourcePreview, inherit=True)
    
    def can_preview(self, data_dict):
        return {
            'can_preview': True,
            'quality': 2
        }

    def preview_template(self, context, data_dict):
        return 'terria.html'
