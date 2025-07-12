# encoding: utf-8
"""
Plugin principal para Terria View - Refactorizado para mejor mantenimiento.
"""
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib.parse
import functools
from flask import request
import ckan.logic.action.get as get

# Importar módulos refactorizados
from .config_manager import ConfigManager
from .sld_processor import SLDProcessor
from .resource_utils import ResourceUtils
from .terria_config_builder import TerriaConfigBuilder

# Obtener el callback original
resource_view_list = get.resource_view_list

PLUGIN_NAME = 'terria_view'


def new_resource_view_list(plugin_instance, context, data_dict):
    """
    Función para crear automáticamente vistas de recursos TerriaJS.
    
    Args:
        plugin_instance: Instancia del plugin
        context: Contexto de la acción
        data_dict: Diccionario con datos de la acción
        
    Returns:
        Lista de vistas de recursos
    """
    try:
        resource_id = data_dict.get('id')
        
        # Verificar si hay un activity_id en la URL, así no intenta crear nada
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
    
    # Verificar si ya existe una vista del plugin
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
    """Plugin principal para Terria View - Versión refactorizada."""
    
    def __init__(self, name=None):
        """Inicializa el plugin con los módulos refactorizados."""
        super().__init__()
        
        # Inicializar módulos
        self.config_manager = ConfigManager()
        self.sld_processor = SLDProcessor()
        self.resource_utils = ResourceUtils(self.config_manager)
        self.terria_config_builder = TerriaConfigBuilder(self.config_manager, self.sld_processor)
        
        # Callback para resource_view_list
        self.resource_view_list_callback = None
    
    plugins.implements(plugins.IConfigurer)
    def update_config(self, config_):
        """Actualiza la configuración del plugin."""
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
    
    plugins.implements(plugins.ITemplateHelpers)
    def get_helpers(self):
        """Registra helpers del template."""
        return {
            'terria_get_sld_files': self.terria_get_sld_files
        }
    
    def terria_get_sld_files(self, package_id):
        """
        Helper para obtener archivos SLD desde el template.
        
        Args:
            package_id: ID del paquete
            
        Returns:
            Lista de archivos SLD
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
        Configura el plugin con los valores del archivo de configuración.
        
        Args:
            config: Diccionario de configuración
        """
        # Actualizar configuración en el config_manager
        self.config_manager.site_url = config.get('ckan.site_url', '')
        self.config_manager.default_title = config.get(
            f'ckanext.{PLUGIN_NAME}.default_title', 'Terria Viewer'
        )
        self.config_manager.default_instance_url = config.get(
            f'ckanext.{PLUGIN_NAME}.default_instance_url', 
            'https://ihp-wins.unesco.org/terria/'
        )
        
        # Configurar callback
        self.resource_view_list_callback = functools.partial(new_resource_view_list, self)
    
    plugins.implements(plugins.IResourceView, inherit=True)
    def info(self):
        """
        Proporciona información sobre el plugin.
        
        Returns:
            Diccionario con información del plugin
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
        Determina si un recurso puede ser visualizado.
        
        Args:
            data_dict: Diccionario con datos del recurso
            
        Returns:
            True si puede ser visualizado, False en caso contrario
        """
        return self.config_manager.can_view_resource(data_dict['resource'])
    
    def before_create(self, context, data_dict):
        """
        Procesa los datos antes de crear la vista de recurso.
        
        Args:
            context: Contexto de la vista
            data_dict: Diccionario con datos de la vista
            
        Returns:
            Diccionario con datos procesados
        """
        return self._process_form_data(data_dict)
    
    def before_update(self, context, data_dict):
        """
        Procesa los datos antes de actualizar la vista de recurso.
        
        Args:
            context: Contexto de la vista
            data_dict: Diccionario con datos de la vista
            
        Returns:
            Diccionario con datos procesados
        """
        return self._process_form_data(data_dict)
    
    def _process_form_data(self, data_dict):
        """
        Procesa los datos del formulario para convertir campos temporales a campos finales.
        
        Args:
            data_dict: Diccionario con datos del formulario
            
        Returns:
            Diccionario con datos procesados
        """
        # Procesar configuración personalizada
        custom_config_option = data_dict.get('custom_config_option', 'automatic')
        custom_config_url = data_dict.get('custom_config_url', '')
        
        if custom_config_option == 'custom' and custom_config_url:
            data_dict['custom_config'] = custom_config_url
        else:
            data_dict['custom_config'] = 'NA'
        
        # Procesar estilo
        style_option = data_dict.get('style_option', 'none')
        style_custom_input = data_dict.get('style_custom_input', '')
        
        if style_option == 'custom_url' and style_custom_input:
            data_dict['style'] = style_custom_input
        elif style_option == 'sld_file':
            # El JavaScript del formulario ya debería haber puesto la URL del SLD en style_custom_input
            # pero también podemos buscar en los radio buttons
            sld_radios = [k for k in data_dict.keys() if k.startswith('style_option') and 'data-sld-url' in str(data_dict.get(k, ''))]
            if style_custom_input:
                data_dict['style'] = style_custom_input
            else:
                data_dict['style'] = 'NA'
        else:
            data_dict['style'] = 'NA'
        
        # Limpiar campos temporales del formulario
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
        Configura las variables del template para la vista.
        
        Args:
            context: Contexto de la vista
            data_dict: Diccionario con datos de la vista
            
        Returns:
            Diccionario con variables para el template
        """
        package = data_dict['package']
        resource = data_dict['resource']
        view = data_dict['resource_view']
        
        view_title = view.get('title', self.config_manager.default_title)
        view_terria_instance_url = view.get('terria_instance_url', self.config_manager.default_instance_url)
        
        # Si terria_instance_url contiene una URL completa de TerriaJS, usarla directamente
        if view_terria_instance_url and '#' in view_terria_instance_url:
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'direct_url': True
            }
        
        # Si el formato es JSON, solo necesitamos pasar la URL de TerriaJS
        if resource.get('format', '').lower() == 'json':
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'resource': resource
            }
        
        # Obtener nombre seguro del recurso
        safe_resource_name = self.config_manager.get_safe_resource_name(resource)
        
        # Obtener configuraciones de la vista
        view_custom_config = view.get('custom_config', 'NA')
        view_style = view.get('style', 'NA')
        
        # Contexto del usuario
        user_context = {
            'user': toolkit.g.user,
            'auth_user_obj': toolkit.g.userobj
        }
        
        # Obtener URL del recurso
        resource_url = self.resource_utils.get_resource_url(resource, package, user_context)
        
        # Obtener bounds del package
        bounds = self.resource_utils.get_resource_bounds(package)
        
        # Generar configuración
        if view_custom_config == 'NA' or view_custom_config == '':
            # Configuración estándar
            config = self.terria_config_builder.create_config_for_resource(
                resource, safe_resource_name, resource_url, bounds, view_style
            )
            encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))
        else:
            # Configuración personalizada
            custom_config = self.terria_config_builder.process_custom_config(
                view_custom_config, resource_url, resource.get('format', ''), view_style
            )
            if custom_config:
                encoded_config = urllib.parse.quote(custom_config)
            else:
                # Fallback a configuración estándar
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
        Especifica el template para la vista.
        
        Args:
            context: Contexto de la vista
            data_dict: Diccionario con datos de la vista
            
        Returns:
            Nombre del template
        """
        return 'terria.html'
    
    def form_template(self, context, data_dict):
        """
        Especifica el template para el formulario de configuración.
        
        Args:
            context: Contexto del formulario
            data_dict: Diccionario con datos del formulario
            
        Returns:
            Nombre del template
        """
        # Pasar formato del recurso al template
        if 'resource' in data_dict and 'format' in data_dict['resource']:
            data_dict['resource_format'] = data_dict['resource']['format']
        
        # Obtener archivos SLD del dataset si existe el package
        if 'package' in data_dict:
            package_id = data_dict['package']['id']
            sld_files = self.resource_utils.get_sld_files_from_dataset(
                self.config_manager.site_url, package_id
            )
            
            # Pasar archivos SLD al template
            data_dict['available_sld_files'] = sld_files
            context['available_sld_files'] = sld_files
            
            # Agregar a las variables globales del template
            if 'c' in context:
                context['c'].available_sld_files = sld_files
        else:
            data_dict['available_sld_files'] = []
        
        return 'terria_instance_url.html'
    
    plugins.implements(plugins.IActions, inherit=True)
    def get_actions(self):
        """
        Registra acciones adicionales del plugin.
        
        Returns:
            Diccionario con acciones del plugin
        """
        return {
            'resource_view_list': self.resource_view_list_callback
        }
