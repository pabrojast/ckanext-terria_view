# encoding: utf-8
"""
Main plugin for Terria View - Refactored for better maintainability.
"""
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib.parse
import functools
from flask import request
import ckan.logic.action.get as get

# Import refactored modules
from .config_manager import ConfigManager
from .sld_processor import SLDProcessor
from .resource_utils import ResourceUtils
from .terria_config_builder import TerriaConfigBuilder

# Get the original callback
resource_view_list = get.resource_view_list

PLUGIN_NAME = 'terria_view'


def new_resource_view_list(plugin_instance, context, data_dict):
    """
    Function to automatically create TerriaJS resource views.
    
    Args:
        plugin_instance: Plugin instance
        context: Action context
        data_dict: Dictionary with action data
        
    Returns:
        List of resource views
    """
    try:
        resource_id = data_dict.get('id')
        
        # Check if there's an activity_id in the URL, so it doesn't try to create anything
        if 'activity_id' in request.args:
            print("Activity ID detected, skipping resource view creation.")
            return []
        
        resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        if not resource:
            print("Debug: Resource not found")
            return []
            
        ret = resource_view_list(context, data_dict)
        
    except Exception as e:
        print(f"Error retrieving resource view list: {e}")
        ret = []
    
    # Check if a plugin view already exists
    has_plugin = len([r for r in ret if r['view_type'] == PLUGIN_NAME]) > 0
    
    if not has_plugin:
        if 'resource' in context and plugin_instance.config_manager.can_view_resource(context['resource'].__dict__):
            data_dict2 = {
                'resource_id': data_dict['id'],
                'title': plugin_instance.config_manager.default_title,
                'view_type': PLUGIN_NAME,
                'description': '',
                'custom_config': 'NA',
                'terria_instance_url': plugin_instance.config_manager.default_instance_url,
                'style': 'NA'
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
    """Main plugin for Terria View - Refactored version."""
    
    def __init__(self, name=None):
        """Initialize the plugin with refactored modules."""
        super().__init__()
        
        # Initialize modules
        self.config_manager = ConfigManager()
        self.sld_processor = SLDProcessor()
        self.resource_utils = ResourceUtils(self.config_manager)
        self.terria_config_builder = TerriaConfigBuilder(self.config_manager, self.sld_processor)
        
        # Callback for resource_view_list
        self.resource_view_list_callback = None
    
    plugins.implements(plugins.IConfigurer)
    def update_config(self, config_):
        """Update plugin configuration."""
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
    
    plugins.implements(plugins.ITemplateHelpers)
    def get_helpers(self):
        """Register template helpers."""
        return {
            'terria_get_sld_files': self.terria_get_sld_files
        }
    
    def terria_get_sld_files(self, package_id):
        """
        Helper to get SLD files from template.
        
        Args:
            package_id: Package ID
            
        Returns:
            List of SLD files
        """
        try:
            return self.resource_utils.get_sld_files_from_dataset(
                self.config_manager.site_url, package_id
            )
        except Exception as e:
            print(f"Error in terria_get_sld_files helper: {e}")
            return []
    
    plugins.implements(plugins.IConfigurable, inherit=True)
    def configure(self, config):
        """
        Configure the plugin with values from configuration file.
        
        Args:
            config: Configuration dictionary
        """
        # Update configuration in config_manager
        self.config_manager.site_url = config.get('ckan.site_url', '')
        self.config_manager.default_title = config.get(
            f'ckanext.{PLUGIN_NAME}.default_title', 'Terria Viewer'
        )
        self.config_manager.default_instance_url = config.get(
            f'ckanext.{PLUGIN_NAME}.default_instance_url', 
            'https://ihp-wins.unesco.org/terria/'
        )
        
        # Configure callback
        self.resource_view_list_callback = functools.partial(new_resource_view_list, self)
    
    plugins.implements(plugins.IResourceView, inherit=True)
    def info(self):
        """
        Provide information about the plugin.
        
        Returns:
            Dictionary with plugin information
        """
        return {
            'name': PLUGIN_NAME,
            'title': toolkit._('TerriaJS Preview'),
            'default_title': toolkit._(self.config_manager.default_title),
            'icon': 'globe',
            'always_available': True,
            'filterable': True,
            'iframed': False,
            "schema": self.config_manager.get_schema_info()
        }
    
    def can_view(self, data_dict):
        """
        Determine if a resource can be visualized.
        
        Args:
            data_dict: Dictionary with resource data
            
        Returns:
            True if it can be visualized, False otherwise
        """
        return self.config_manager.can_view_resource(data_dict['resource'])
    
    def before_create(self, context, data_dict):
        """
        Process data before creating resource view.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
            
        Returns:
            Dictionary with processed data
        """
        return self._process_form_data(data_dict)
    
    def before_update(self, context, data_dict):
        """
        Process data before updating resource view.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
            
        Returns:
            Dictionary with processed data
        """
        return self._process_form_data(data_dict)
    
    def _process_form_data(self, data_dict):
        """
        Process form data to convert temporary fields to final fields.
        
        Args:
            data_dict: Dictionary with form data
            
        Returns:
            Dictionary with processed data
        """
        # Process custom configuration
        custom_config_option = data_dict.get('custom_config_option', 'automatic')
        custom_config_url = data_dict.get('custom_config_url', '')
        
        if custom_config_option == 'custom' and custom_config_url:
            data_dict['custom_config'] = custom_config_url
        else:
            data_dict['custom_config'] = 'NA'
        
        # Process style
        style_option = data_dict.get('style_option', 'none')
        style_custom_input = data_dict.get('style_custom_input', '')
        
        if style_option == 'custom_url' and style_custom_input:
            data_dict['style'] = style_custom_input
        elif style_option == 'sld_file':
            # JavaScript in the form should have already put the SLD URL in style_custom_input
            # but we can also look for radio buttons
            sld_radios = [k for k in data_dict.keys() if k.startswith('style_option') and 'data-sld-url' in str(data_dict.get(k, ''))]
            if style_custom_input:
                data_dict['style'] = style_custom_input
            else:
                data_dict['style'] = 'NA'
        else:
            data_dict['style'] = 'NA'
        
        # Clean temporary form fields
        fields_to_remove = [
            'custom_config_option', 'custom_config_url', 
            'style_option', 'style_custom_input',
            'available_sld_files', 'package_id'
        ]
        
        for field in fields_to_remove:
            data_dict.pop(field, None)
        
        return data_dict
    
    def setup_template_variables(self, context, data_dict):
        """
        Configure template variables for the view.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
            
        Returns:
            Dictionary with variables for the template
        """
        package = data_dict['package']
        resource = data_dict['resource']
        view = data_dict['resource_view']
        
        view_title = view.get('title', self.config_manager.default_title)
        view_terria_instance_url = view.get('terria_instance_url', self.config_manager.default_instance_url)
        
        # If terria_instance_url contains a complete TerriaJS URL, use it directly
        if view_terria_instance_url and '#' in view_terria_instance_url:
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'direct_url': True
            }
        
        # If format is JSON, we only need to pass the TerriaJS URL
        if resource.get('format', '').lower() == 'json':
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'resource': resource
            }
        
        # Get safe resource name
        safe_resource_name = self.config_manager.get_safe_resource_name(resource)
        
        # Get view configurations
        view_custom_config = view.get('custom_config', 'NA')
        view_style = view.get('style', 'NA')
        
        # User context
        user_context = {
            'user': toolkit.g.user,
            'auth_user_obj': toolkit.g.userobj
        }
        
        # Get resource URL
        resource_url = self.resource_utils.get_resource_url(resource, package, user_context)
        
        # Get package bounds
        bounds = self.resource_utils.get_resource_bounds(package)
        
        # Generate configuration
        if view_custom_config == 'NA' or view_custom_config == '':
            # Standard configuration
            config = self.terria_config_builder.create_config_for_resource(
                resource, safe_resource_name, resource_url, bounds, view_style
            )
            encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))
        else:
            # Custom configuration
            custom_config = self.terria_config_builder.process_custom_config(
                view_custom_config, resource_url, resource.get('format', ''), view_style
            )
            if custom_config:
                encoded_config = urllib.parse.quote(custom_config)
            else:
                # Fallback to standard configuration
                config = self.terria_config_builder.create_config_for_resource(
                    resource, safe_resource_name, resource_url, bounds, view_style
                )
                encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))
        
        return {
            'title': view_title,
            'terria_instance_url': view_terria_instance_url,
            'encoded_config': encoded_config,
            'origin': self.config_manager.site_url,
            'custom_config': view_custom_config
        }
    
    def view_template(self, context, data_dict):
        """
        Specify the template for the view.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
            
        Returns:
            Template name
        """
        return 'terria.html'
    
    def form_template(self, context, data_dict):
        """
        Specify the template for the configuration form.
        
        Args:
            context: Form context
            data_dict: Dictionary with form data
            
        Returns:
            Template name
        """
        # Pass resource format to template
        if 'resource' in data_dict and 'format' in data_dict['resource']:
            data_dict['resource_format'] = data_dict['resource']['format']
        
        # Get SLD files from dataset if package exists
        if 'package' in data_dict:
            package_id = data_dict['package']['id']
            sld_files = self.resource_utils.get_sld_files_from_dataset(
                self.config_manager.site_url, package_id
            )
            
            # Pass SLD files to template
            data_dict['available_sld_files'] = sld_files
            context['available_sld_files'] = sld_files
            
            # Add to global template variables
            if 'c' in context:
                context['c'].available_sld_files = sld_files
        else:
            data_dict['available_sld_files'] = []
        
        return 'terria_instance_url.html'
    
    plugins.implements(plugins.IActions, inherit=True)
    def get_actions(self):
        """
        Register additional plugin actions.
        
        Returns:
            Dictionary with plugin actions
        """
        return {
            'resource_view_list': self.resource_view_list_callback
        }
