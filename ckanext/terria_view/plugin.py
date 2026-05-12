# encoding: utf-8
"""
Main plugin for Terria View - Refactored for better maintainability.
"""
import ckan.plugins as plugins
import ckan.plugins.toolkit as toolkit
import json
import urllib.parse
import functools
import hashlib
from flask import request
import ckan.logic.action.get as get

# Import refactored modules
from .config_manager import ConfigManager
from .sld_processor import SLDProcessor
from .resource_utils import ResourceUtils
from .terria_config_builder import (
    TerriaConfigBuilder,
    prepare_saved_custom_config_url,
    refresh_proxy_tokens,
    payload_has_private_catalog,
)
from .cache_manager import CacheManager
from .file_cache_manager import FileCacheManager
from .api_endpoints import terria_api
from .cache_preloader import CachePreloader
from .terria_json_generator import TerriaJSONGenerator
from . import action_filters

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
    resource = None
    ret = []
    try:
        resource_id = data_dict.get('id')
        
        # Ensure 'model' is in context (required by CKAN actions outside request context)
        if 'model' not in context:
            import ckan.model as _model
            context['model'] = _model
        if 'session' not in context:
            import ckan.model as _model
            context['session'] = _model.Session
        
        # Check if there's an activity_id in the URL, so it doesn't try to create anything
        # Guard against missing request context (e.g. background threads, CLI)
        try:
            has_activity_id = 'activity_id' in request.args
        except RuntimeError:
            has_activity_id = False
        
        if has_activity_id:
            import os
            if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
                print("Activity ID detected, skipping resource view creation.")
            return []
        
        resource = toolkit.get_action('resource_show')(context, {'id': resource_id})
        if not resource:
            import os
            if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
                print("Debug: Resource not found")
            return []
            
        ret = resource_view_list(context, data_dict)
        
    except Exception as e:
        import os
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(f"Error retrieving resource view list: {e}")
    
    # Check if a plugin view already exists
    has_plugin = any(
        isinstance(r, dict) and r.get('view_type') == PLUGIN_NAME
        for r in ret
    )
    
    if not has_plugin:
        if resource and plugin_instance.config_manager.can_view_resource(resource):
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
        self.cache_manager = CacheManager()
        self.file_cache_manager = FileCacheManager()
        
        # Initialize cache preloader (will be started after configuration)
        self.cache_preloader = None
        
        # Callback for resource_view_list
        self.resource_view_list_callback = None
        self.package_show_callback = None
        self.resource_show_callback = None
    
    def _debug_print(self, message: str):
        """
        Print debug messages only when TERRIA_DEBUG environment variable is set to 'true'.
        
        Args:
            message: Debug message to print
        """
        import os
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(message)
    
    plugins.implements(plugins.IConfigurer)
    def update_config(self, config_):
        """Update plugin configuration."""
        toolkit.add_template_directory(config_, 'templates')
        toolkit.add_public_directory(config_, 'public')
    
    plugins.implements(plugins.IBlueprint)
    def get_blueprint(self):
        """Register API blueprint."""
        return terria_api
    
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
            return self.resource_utils.get_sld_files_from_dataset(package_id)
        except Exception as e:
            self._debug_print(f"Error in terria_get_sld_files helper: {e}")
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
        self.package_show_callback = action_filters.package_show
        self.resource_show_callback = action_filters.resource_show
        
        # Initialize and start cache preloader
        self._initialize_cache_preloader()
    
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
    
    def after_create(self, context, data_dict):
        """
        Process data after creating resource view.
        Invalidate cache for the affected resource.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
        """
        self._invalidate_resource_related_cache(
            data_dict.get('resource_id'),
            'after view creation'
        )
    
    def after_update(self, context, data_dict):
        """
        Process data after updating resource view.
        Invalidate cache for the affected resource.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
        """
        self._invalidate_resource_related_cache(
            data_dict.get('resource_id'),
            'after view update'
        )
    
    def after_delete(self, context, data_dict):
        """
        Process data after deleting resource view.
        Invalidate cache for the affected resource.
        
        Args:
            context: View context
            data_dict: Dictionary with view data
        """
        self._invalidate_resource_related_cache(
            data_dict.get('resource_id'),
            'after view deletion'
        )

    def _invalidate_resource_related_cache(self, resource_id, reason=''):
        """Invalidate memory/file caches related to a resource."""
        if not resource_id:
            return
        try:
            self.cache_manager.invalidate_by_resource_id(resource_id)
            self.file_cache_manager.invalidate_by_resource_id(resource_id)
            self._clear_sld_result_caches()
            if reason:
                self._debug_print(
                    f"Cache invalidated for resource {resource_id} {reason}"
                )
            else:
                self._debug_print(
                    f"Cache invalidated for resource {resource_id}"
                )
        except Exception as e:
            self._debug_print(
                f"Failed to invalidate cache for resource {resource_id}: {e}"
            )

    def _clear_sld_result_caches(self):
        """
        Clear SLD in-memory caches used by view rendering and catalog generation.

        SLD processors cache by URL; when a style file is updated in-place
        (same URL, different content), stale style results can persist.
        """
        processors = [getattr(self, 'sld_processor', None)]
        try:
            processors.append(TerriaJSONGenerator().sld_processor)
        except Exception:
            pass

        seen = set()
        for processor in processors:
            if not processor:
                continue
            processor_id = id(processor)
            if processor_id in seen:
                continue
            seen.add(processor_id)
            try:
                if hasattr(processor, '_sld_content_cache'):
                    processor._sld_content_cache.clear()
                if hasattr(processor, '_sld_result_cache'):
                    processor._sld_result_cache.clear()
            except Exception as e:
                self._debug_print(f"Could not clear SLD cache: {e}")

    def _resolve_resource_id_from_view(self, view_id):
        """
        Resolve resource_id from a resource view id.

        Useful for update/delete action payloads that only include the view id.
        """
        if not view_id:
            return None
        try:
            view_data = toolkit.get_action('resource_view_show')(
                {'ignore_auth': True}, {'id': view_id}
            )
            return view_data.get('resource_id')
        except Exception:
            return None

    @toolkit.chained_action
    def resource_view_create(self, next_action, context, data_dict):
        """
        Chain resource_view_create to invalidate Terria caches after success.
        """
        result = next_action(context, data_dict)
        resource_id = result.get('resource_id') or data_dict.get('resource_id')
        self._invalidate_resource_related_cache(resource_id, 'after action create')
        return result

    @toolkit.chained_action
    def resource_view_update(self, next_action, context, data_dict):
        """
        Chain resource_view_update to invalidate Terria caches after success.
        """
        result = next_action(context, data_dict)
        resource_id = (
            result.get('resource_id')
            or data_dict.get('resource_id')
            or self._resolve_resource_id_from_view(result.get('id') or data_dict.get('id'))
        )
        self._invalidate_resource_related_cache(resource_id, 'after action update')
        return result

    @toolkit.chained_action
    def resource_view_delete(self, next_action, context, data_dict):
        """
        Chain resource_view_delete to invalidate Terria caches after success.
        """
        resource_id = data_dict.get('resource_id') or self._resolve_resource_id_from_view(
            data_dict.get('id')
        )
        result = next_action(context, data_dict)
        self._invalidate_resource_related_cache(resource_id, 'after action deletion')
        return result
    
    def _process_form_data(self, data_dict):
        """
        Process form data to convert temporary fields to final fields.
        
        Args:
            data_dict: Dictionary with form data
            
        Returns:
            Dictionary with processed data
        """
        # Process custom configuration
        custom_config_option = data_dict.get('custom_config_option')
        custom_config_url = data_dict.get('custom_config_url', '')
        if custom_config_option is None:
            # Preserve existing custom_config when provided (e.g. API updates)
            if not data_dict.get('custom_config'):
                data_dict['custom_config'] = 'NA'
        elif custom_config_option == 'custom' and custom_config_url:
            data_dict['custom_config'] = custom_config_url
        else:
            data_dict['custom_config'] = 'NA'
        
        # Process style
        style_option = data_dict.get('style_option')
        style_custom_input = data_dict.get('style_custom_input', '')
        if style_option is None:
            # Preserve existing style when provided (e.g. API updates)
            if not data_dict.get('style'):
                data_dict['style'] = 'NA'
        elif style_option == 'custom_url' and style_custom_input:
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
        
        # Prune any injected private-dataset catalog down to the items actually
        # displayed and strip the expired-once proxy ``?token=`` before
        # persisting. The kept private branch lets a saved view be shared with
        # other users who still have access; a fresh per-viewer token is
        # re-minted at render time (see setup_template_variables ->
        # _refresh_proxy_tokens_in_encoded_config).
        if data_dict.get('custom_config') and data_dict['custom_config'] != 'NA':
            data_dict['custom_config'] = prepare_saved_custom_config_url(
                data_dict['custom_config']
            )

        # Clean temporary form fields
        fields_to_remove = [
            'custom_config_option', 'custom_config_url',
            'style_option', 'style_custom_input',
            'available_sld_files', 'package_id'
        ]

        for field in fields_to_remove:
            data_dict.pop(field, None)

        return data_dict

    # Bump this version whenever the config generation/processing logic changes
    # to invalidate stale cached configs.
    _CONFIG_PROCESSING_VERSION = 4

    def _build_cached_config_signature(self, resource, package, resource_url, bounds,
                                       view_custom_config, view_style, resource_name):
        """
        Build a deterministic signature for cached Terria config.

        This avoids rebuilding (and re-fetching SLDs) when inputs haven't changed.
        """
        signature_payload = {
            "config_version": self._CONFIG_PROCESSING_VERSION,
            "resource": {
                "id": resource.get('id'),
                "name": resource.get('name', ''),
                "safe_name": resource_name,
                "format": resource.get('format', ''),
                "url": resource.get('url', ''),
                "computed_url": resource_url,
                "last_modified": resource.get('last_modified', '')
            },
            "package": {
                "id": package.get('id'),
                "metadata_modified": package.get('metadata_modified', '')
            },
            "bounds": list(bounds),
            "view": {
                "custom_config": view_custom_config or '',
                "style": view_style or ''
            }
        }
        signature_raw = json.dumps(signature_payload, sort_keys=True, default=str)
        return hashlib.md5(signature_raw.encode('utf-8')).hexdigest()

    def _update_view_cached_config(self, context, view, encoded_config, signature):
        """Persist cached config and signature in the resource view."""
        try:
            view_id = view.get('id')
            if not view_id or not encoded_config or not signature:
                return

            update_data = {
                'id': view_id,
                'resource_id': view.get('resource_id'),
                'view_type': view.get('view_type'),
                'title': view.get('title'),
                'description': view.get('description', ''),
                'terria_instance_url': view.get('terria_instance_url', ''),
                'custom_config': view.get('custom_config', 'NA'),
                'style': view.get('style', 'NA'),
                'cached_config': encoded_config,
                'cached_config_signature': signature
            }

            # Preserve optional fields if present
            for key in ('filterable', 'show_fields'):
                if key in view:
                    update_data[key] = view.get(key)

            sysadmin_context = {
                'model': context.get('model'),
                'session': context.get('session'),
                'user': 'ckan.system',
                'ignore_auth': True
            }

            toolkit.get_action('resource_view_update')(sysadmin_context, update_data)
            self._debug_print(f"Cached Terria config saved for view {view_id}")
        except Exception as e:
            self._debug_print(f"Failed to persist cached Terria config: {e}")
    
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
                'direct_url': True,
                'view_id': view.get('id'),
                'resource_id': resource.get('id')
            }
        
        # If format is JSON, we only need to pass the TerriaJS URL
        if resource.get('format', '').lower() == 'json':
            return {
                'title': view_title,
                'terria_instance_url': view_terria_instance_url,
                'resource': resource,
                'view_id': view.get('id'),
                'resource_id': resource.get('id')
            }
        
        # Get safe resource name
        safe_resource_name = self.config_manager.get_safe_resource_name(resource)
        
        # Get view configurations
        view_custom_config = view.get('custom_config', 'NA')
        view_style = view.get('style', 'NA')
        
        self._debug_print(f"TerriaView: Processing view for resource {resource.get('name', 'unknown')}")
        self._debug_print(f"TerriaView: Resource format: {resource.get('format', 'unknown')}")
        self._debug_print(f"TerriaView: Style URL: {view_style}")
        
        # User context (CKAN 2.10+ compatible)
        try:
            current_user = toolkit.current_user
            user_context = {
                'user': current_user.name if hasattr(current_user, 'name') else str(current_user),
                'auth_user_obj': current_user
            }
        except (AttributeError, RuntimeError):
            user_context = {
                'user': getattr(toolkit.g, 'user', ''),
                'auth_user_obj': getattr(toolkit.g, 'userobj', None)
            }
        
        # Get resource URL
        resource_url = self.resource_utils.get_resource_url(resource, package, user_context)
        
        # Get package bounds
        bounds = self.resource_utils.get_resource_bounds(package)

        # Try to reuse cached configuration when inputs haven't changed
        cached_config = view.get('cached_config')
        cached_signature = view.get('cached_config_signature')
        current_signature = self._build_cached_config_signature(
            resource, package, resource_url, bounds, view_custom_config, view_style, safe_resource_name
        )

        if cached_config and cached_signature == current_signature:
            encoded_config = cached_config
        else:
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
                    view_custom_config, resource_url, resource.get('format', ''), view_style,
                    resource_id=resource.get('id')
                )
                if custom_config:
                    encoded_config = urllib.parse.quote(custom_config)
                else:
                    # Fallback to standard configuration
                    config = self.terria_config_builder.create_config_for_resource(
                        resource, safe_resource_name, resource_url, bounds, view_style
                    )
                    encoded_config = urllib.parse.quote(json.dumps(json.loads(config)))

            # Persist cached configuration so we avoid future external calls
            # Skip caching for private packages — their resolved URLs may be
            # user-specific or temporary and must not leak across requests.
            if not package.get('private'):
                self._update_view_cached_config(context, view, encoded_config, current_signature)

        # A *saved* config may carry injected private-dataset catalog branches
        # (with their proxy ``?token=`` stripped on save). Re-mint a fresh
        # per-viewer token for each referenced private resource the current user
        # may read; users without access get a token-less URL (the proxy then
        # answers 401 for that item). When the saved config already carries a
        # private catalog we skip re-injecting the current user's full one below
        # (avoids duplicates and unbounded growth across re-saves).
        saved_config_has_private_catalog = False
        private_resources_blocked = False
        if encoded_config:
            encoded_config, saved_config_has_private_catalog, private_resources_blocked = (
                self._refresh_proxy_tokens_in_encoded_config(encoded_config, user_context)
            )

        # Inject the logged-in user's private-dataset catalog into the Terria
        # ``#start=`` payload so the catalog tree shows their accessible private
        # datasets. By default this only happens on views of *private* datasets:
        # baking that catalog into a *public* view's payload bloats it for every
        # logged-in viewer and — if someone clicks "Save Configuration" — would
        # persist private dataset names + short-lived signed proxy tokens into a
        # view config any visitor can read. Operators who want the private
        # catalog visible from public-dataset maps too can opt in with
        # ``ckanext.terria_view.inject_private_catalog_on_public_views = true``.
        inject_on_public_views = toolkit.asbool(
            toolkit.config.get(
                'ckanext.terria_view.inject_private_catalog_on_public_views',
                False,
            )
        )
        include_private_catalog = bool(user_context.get('user')) and (
            bool(package.get('private')) or inject_on_public_views
        )
        private_catalog_data = (
            self._get_private_datasets_catalog(user_context)
            if include_private_catalog else None
        )

        # Merge private catalog as an extra init source into the same encoded_config
        # so TerriaJS sees everything in the original ``#start=`` payload. This keeps
        # the cross-origin iframe flow identical to public views (workbench and
        # timeline populate reliably) while still making the user's private datasets
        # available in the catalog tree.
        if encoded_config and private_catalog_data and not saved_config_has_private_catalog:
            encoded_config = self._merge_private_catalog_into_encoded_config(
                encoded_config, private_catalog_data
            )

        return {
            'title': view_title,
            'terria_instance_url': view_terria_instance_url,
            'encoded_config': encoded_config,
            'origin': self.config_manager.site_url,
            'custom_config': view_custom_config,
            'view_id': view.get('id'),
            'resource_id': resource.get('id'),
            'user_logged_in': bool(user_context.get('user')),
            'private_catalog_data': private_catalog_data,
            # True when the saved config references private resources the current
            # viewer can't access — the template shows a "log in / no access"
            # notice above the map.
            'private_resources_blocked': private_resources_blocked,
        }

    def _refresh_proxy_tokens_in_encoded_config(self, encoded_config, user_context):
        """Re-mint per-viewer private-resource proxy tokens in an encoded Terria config.

        Returns ``(encoded_config, has_private_catalog, blocked)``:

        * ``encoded_config`` is re-encoded only when it actually references the
          resource proxy; viewers without access to a referenced resource get a
          token-less URL (the proxy then answers ``401`` for that item).
        * ``blocked`` is True when at least one referenced private resource was
          denied for the current viewer (so the template can show a "log in /
          no access" notice).
        """
        if not encoded_config:
            return encoded_config, False, False
        try:
            decoded = urllib.parse.unquote(encoded_config)
        except Exception:
            return encoded_config, False, False

        references_proxy = '/api/terria/resource/' in decoded
        # Cheap pre-check before paying for a full JSON parse.
        if not references_proxy and 'Private Datasets (' not in decoded:
            return encoded_config, False, False

        try:
            data = json.loads(decoded)
        except (ValueError, TypeError):
            return encoded_config, False, False

        has_private_catalog = payload_has_private_catalog(data)
        blocked_ids = []

        if references_proxy:
            auth_context = {
                'user': user_context.get('user'),
                'auth_user_obj': user_context.get('auth_user_obj'),
            }
            decisions = {}

            def mint(resource_id):
                if resource_id not in decisions:
                    allowed = False
                    try:
                        toolkit.check_access('resource_show', auth_context, {'id': resource_id})
                        allowed = True
                    except toolkit.NotAuthorized:
                        allowed = False
                    except Exception:
                        allowed = False
                    if allowed:
                        try:
                            decisions[resource_id] = self.resource_utils.generate_resource_token(
                                resource_id
                            )
                        except Exception:
                            decisions[resource_id] = None
                    else:
                        decisions[resource_id] = None
                        blocked_ids.append(resource_id)
                return decisions[resource_id]

            try:
                refresh_proxy_tokens(data, mint)
                encoded_config = urllib.parse.quote(
                    json.dumps(data, separators=(',', ':'), ensure_ascii=False)
                )
            except Exception as e:
                self._debug_print(f"Could not refresh proxy tokens in encoded_config: {e}")

        return encoded_config, has_private_catalog, bool(blocked_ids)

    def _merge_private_catalog_into_encoded_config(self, encoded_config, private_catalog_data):
        """
        Merge the private catalog groups into the resource's existing initSource.

        We extend ``initSources[0].catalog`` with the private catalog entries
        instead of appending a new initSource. Adding a standalone initSource
        that doesn't declare ``workbench`` can cause TerriaJS to reset the
        resource's workbench entries while processing init sources in order;
        merging inside the same initSource keeps the main resource's workbench
        untouched while still exposing the user's private datasets in the
        catalog tree.

        Returns the re-encoded (URL-quoted) config string. On any error, returns
        the original ``encoded_config`` so the main resource view still loads.
        """
        try:
            decoded = urllib.parse.unquote(encoded_config)
            config_dict = json.loads(decoded)
            if not isinstance(config_dict, dict):
                return encoded_config

            private_entries = []
            if isinstance(private_catalog_data, dict):
                private_entries = private_catalog_data.get('catalog') or []
            if not private_entries:
                return encoded_config

            init_sources = config_dict.get('initSources')
            if not isinstance(init_sources, list) or not init_sources:
                # Fallback: preserve previous behaviour by appending a full init source.
                config_dict['initSources'] = [private_catalog_data]
                return urllib.parse.quote(json.dumps(config_dict))

            primary = init_sources[0]
            if not isinstance(primary, dict):
                return encoded_config

            catalog = primary.get('catalog')
            if not isinstance(catalog, list):
                catalog = []
                primary['catalog'] = catalog
            catalog.extend(private_entries)

            return urllib.parse.quote(json.dumps(config_dict))
        except Exception as e:
            self._debug_print(f"Could not merge private catalog into encoded_config: {e}")
            return encoded_config
    
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
            sld_files = self.resource_utils.get_sld_files_from_dataset(package_id)
            
            # Pass SLD files to template
            data_dict['available_sld_files'] = sld_files
            context['available_sld_files'] = sld_files
            
            # Add to global template variables
            if 'c' in context:
                context['c'].available_sld_files = sld_files
        else:
            data_dict['available_sld_files'] = []
        
        return 'terria_instance_url.html'
    
    def _get_private_datasets_catalog(self, user_context):
        """
        Get private datasets accessible to the current user as inline Terria catalog data.
        
        Loaded server-side to avoid cross-origin authentication issues when
        TerriaJS tries to fetch data from a different domain.
        
        Args:
            user_context: Dictionary with user and auth_user_obj
            
        Returns:
            Dictionary with Terria catalog configuration or None if no private datasets
        """
        try:
            user = user_context.get('user')
            if not user:
                return None
            
            context = {
                'user': user,
                'auth_user_obj': user_context.get('auth_user_obj')
            }
            
            search_result = toolkit.get_action('package_search')(context, {
                'include_private': True,
                'rows': 1000,
                'q': '*:*'
            })
            
            generator = TerriaJSONGenerator()

            # Group dataset entries by organization so the catalog tree
            # mirrors the public catalog layout (Org → Dataset → Resources).
            # ``orgs`` is keyed by org name (slug) so we keep stable order;
            # if the dataset has no organization we bucket it under a
            # synthetic ``"__no_org__"`` group with a friendlier label.
            from collections import OrderedDict
            orgs = OrderedDict()

            for dataset in search_result.get('results', []):
                if not dataset.get('private', False):
                    continue

                dataset_id = dataset.get('id')
                dataset_title = dataset.get('title', dataset.get('name', 'Unknown'))
                notes = dataset.get('notes', '')
                resources = dataset.get('resources', [])

                org = dataset.get('organization') or {}
                org_key = org.get('name') or '__no_org__'
                org_info = {
                    'display_name': org.get('title') or org.get('name') or 'Unknown Organization',
                    'description': org.get('description', '') or '',
                    'image_display_url': org.get('image_display_url', '') or ''
                }

                dataset_members = []

                for resource in resources:
                    resource_format = resource.get('format', '').lower()
                    if resource_format not in [f.lower() for f in generator.formatos_permitidos]:
                        continue

                    try:
                        formatted_item, total_views = generator.format_dataset_item(
                            resource, dataset_id, notes, org_info, 0,
                            package=dataset, user_context=user_context
                        )
                        dataset_members.append(formatted_item)

                        if total_views > 1:
                            for vi in range(1, total_views):
                                additional_item, _ = generator.format_dataset_item(
                                    resource, dataset_id, notes, org_info, vi,
                                    package=dataset, user_context=user_context
                                )
                                dataset_members.append(additional_item)
                    except Exception:
                        continue

                if not dataset_members:
                    continue

                dataset_group = {
                    "name": dataset_title,
                    "type": "group",
                    "members": dataset_members,
                    "description": notes[:500] if notes else '',
                    "info": [{
                        "name": "About Dataset",
                        "content": notes or ''
                    }, {
                        "name": "Organization",
                        "content": org_info.get('display_name', '')
                    }, {
                        "name": "Access",
                        "content": "Private Dataset"
                    }],
                    "infoSectionOrder": ["About Dataset", "Organization", "Access"]
                }

                bucket = orgs.setdefault(org_key, {
                    'info': org_info,
                    'datasets': [],
                })
                bucket['datasets'].append(dataset_group)

            if not orgs:
                return None

            catalog_members = []
            for org_key, bucket in orgs.items():
                org_info = bucket['info']
                catalog_members.append({
                    "name": org_info['display_name'],
                    "type": "group",
                    "members": bucket['datasets'],
                    "description": org_info.get('description', '') or '',
                    "info": [{
                        "name": f"Organization: {org_info['display_name']}",
                        "content": (
                            f"<img style=\"max-width:300px;width:100%\" "
                            f"alt=\"{org_info['display_name']}\" "
                            f"src=\"{org_info.get('image_display_url', '')}\" /><br/>"
                            f"{org_info.get('description', '') or ''}"
                        ) if org_info.get('image_display_url') else (org_info.get('description', '') or '')
                    }],
                    "infoSectionOrder": [f"Organization: {org_info['display_name']}"]
                })

            config = {
                "catalog": [{
                    "name": f"Private Datasets ({user})",
                    "type": "group",
                    "members": catalog_members,
                    "description": f"Private datasets accessible to {user}",
                    "isOpen": True
                }]
            }

            config = generator.convert_sets_to_lists(config)

            return config
            
        except Exception as e:
            self._debug_print(f"Error getting private datasets catalog: {e}")
            return None
    
    def _initialize_cache_preloader(self):
        """Initialize and start the cache preloader."""
        try:
            # Create Terria JSON generator instance
            generator = TerriaJSONGenerator()
            
            # Initialize cache preloader
            self.cache_preloader = CachePreloader(generator)
            
            # Start preloading in background
            self.cache_preloader.start_preload()
            
            self._debug_print("Cache preloader initialized and started")
            
        except Exception as e:
            self._debug_print(f"Error initializing cache preloader: {e}")
            # Don't fail plugin initialization if preloader fails
    
    plugins.implements(plugins.IActions, inherit=True)
    def get_actions(self):
        """
        Register additional plugin actions.
        
        Returns:
            Dictionary with plugin actions (only those initialized)
        """
        actions = {}
        if self.resource_view_list_callback is not None:
            actions['resource_view_list'] = self.resource_view_list_callback
        actions['resource_view_create'] = self.resource_view_create
        actions['resource_view_update'] = self.resource_view_update
        actions['resource_view_delete'] = self.resource_view_delete
        if self.package_show_callback is not None:
            actions['package_show'] = self.package_show_callback
        if self.resource_show_callback is not None:
            actions['resource_show'] = self.resource_show_callback
        return actions
