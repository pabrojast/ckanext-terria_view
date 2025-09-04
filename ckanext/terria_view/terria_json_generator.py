# encoding: utf-8
"""
Terria JSON Generator - Extraído y refactorizado desde el DAG.
"""
import json
import urllib.parse
from collections import defaultdict
from typing import Dict, List, Optional, Any, Tuple
import ckan.plugins.toolkit as toolkit
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache_manager import CacheManager
from .sld_processor import SLDProcessor
from .config_manager import ConfigManager
from .resource_utils import ResourceUtils


class TerriaJSONGenerator:
    """Generates Terria JSON configurations for datasets, organizations, and tags."""
    
    def __init__(self):
        """Initialize the Terria JSON generator."""
        self.cache_manager = CacheManager()
        self.sld_processor = SLDProcessor()
        self.config_manager = ConfigManager()
        self.resource_utils = ResourceUtils(self.config_manager)
        
        # Setup HTTP session with retry strategy
        retry_strategy = Retry(
            total=2,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.http = requests.Session()
        self.http.mount("https://", adapter)
        self.http.mount("http://", adapter)
        
        # Configuration
        self.TIMEOUT_SECONDS = 120
        self.formatos_permitidos = ['KML', 'tif', 'tiff', 'geotiff', 'csv', 'wms', 'wmts', 'shape', 'shp']
    
    def _debug_print(self, message: str):
        """Print debug messages when TERRIA_DEBUG is enabled."""
        import os
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(message)
    
    def format_dataset_item(self, resource: Dict, package_id: str, notes: str, 
                           org_info: Dict, view_index: int = 0) -> Tuple[Dict, int]:
        """
        Format a dataset item with multiple view support.
        
        Args:
            resource: Resource data dictionary
            package_id: ID of the package
            notes: Additional notes
            org_info: Dictionary containing organization information
            view_index: Index of the Terria view to use (default 0)
            
        Returns:
            tuple: (formatted_element, total_views)
        """
        resource_id = resource['id']
        resource_format = resource['format'].lower()
        
        # Fix for resources without name - generate default name
        resource_name = resource.get('name', '').strip()
        if not resource_name or resource_name.lower() in ['', 'none', 'null', 'undefined', 'unnamed resource']:
            resource_name = resource.get('id', f"Resource_{hash(resource.get('url', 'sin_url')) % 10000}")
        
        resource_url = resource['url']
        resource_description = resource.get('description', '')
        
        # Adjust the type if necessary
        if resource_format in ["tif", "tiff", "geotiff"]:
            resource_format = "cog"
        
        # Get site URL from config
        site_url = self.config_manager.site_url or toolkit.config.get('ckan.site_url', '')
        
        # Create the base element
        elemento = {
            "name": resource_name,
            "type": resource_format,
            "id": resource_id,
            "url": resource_url,
            'description': (notes or '') + '<br/><br/><strong>Dataset URL: </strong> <a href="' + site_url + '/dataset/' + package_id + '">' + site_url + '/dataset/' + package_id + '</a>',
            "info": [
                {
                    "name": f"Organization: {org_info['display_name']}",
                    "content": f"<img style=\"max-width:300px;width:100%\" alt=\"{org_info['display_name']}\" src=\"{org_info['image_display_url']}\" /><br/>{org_info['description']}<br/>"
                },
                {"name": "File Description", "content": resource_description},
                {"name": "Availability", "content": resource.get("availability", "")},
                {"name": "Last Modified", "content": resource.get("last_modified", "")},
                {"name": "Created", "content": resource.get("created", "")}
            ],
            "infoSectionOrder": [
                f"Organization: {org_info['display_name']}",
                "About Dataset",
                "File Description",
                "Availability",
                "Last Modified",
                "Created"
            ]
        }
        
        # Get Terria views for this resource
        try:
            views_data = toolkit.get_action('resource_view_list')({}, {'id': resource_id})
            terria_views = [view for view in views_data if view.get('view_type') == 'terria_view']
            total_views = len(terria_views)
            
            self._debug_print(f"Resource {resource_id}: Found {total_views} Terria views")
            
            if total_views > 0:
                if view_index >= total_views:
                    view_index = 0  # Reset to first view if index is out of range
                
                selected_view = terria_views[view_index]
                
                custom_config = selected_view.get('custom_config')
                style_url = selected_view.get('style')
                view_name = selected_view.get('title', '')
                
                self._debug_print(f"Using view {view_index}: {view_name}")
                
                # Modify resource name if there are multiple views
                if total_views > 1:
                    resource_name = f"{resource_name} - {view_name}"
                    elemento['name'] = resource_name
                    elemento['id'] = f"{resource_id}-{view_index}"
                    self._debug_print(f"Multi-view resource name: {resource_name}")
                
                # Process styles if available
                if style_url and style_url != 'NA':
                    self._debug_print(f"Processing SLD styles from: {style_url}")
                    style_config = self._process_sld_styles(style_url, resource_format)
                    if style_config:
                        self._apply_style_config(elemento, style_config, resource_format)
                
                # Process custom config if available
                if custom_config and custom_config not in ['NA', '']:
                    self._debug_print(f"Processing custom config: {custom_config}")
                    try:
                        self._apply_custom_config(elemento, custom_config)
                    except Exception as e:
                        self._debug_print(f"Error processing custom config: {e}")
            
        except Exception as e:
            self._debug_print(f"Error getting views for resource {resource_id}: {e}")
            total_views = 0
        
        return elemento, total_views
    
    def _process_sld_styles(self, style_url: str, resource_format: str) -> Optional[Dict]:
        """Process SLD styles from URL using the existing SLD processor."""
        try:
            # Use the existing SLD processor
            if resource_format in ['cog', 'tif', 'tiff', 'geotiff']:
                return self.sld_processor.process_cog_sld(style_url)
            elif resource_format in ['shp', 'shape']:
                return self.sld_processor.process_shp_sld(style_url)
            else:
                return None
        except Exception as e:
            self._debug_print(f"Error processing SLD styles: {e}")
            return None
    
    def _apply_style_config(self, elemento: Dict, style_config: Dict, resource_format: str):
        """Apply style configuration to element."""
        if resource_format in ['cog', 'tif', 'tiff', 'geotiff']:
            # For raster data (COG files)
            if 'renderOptions' in style_config:
                elemento['renderOptions'] = style_config['renderOptions']
            if 'legends' in style_config:
                elemento['legends'] = style_config['legends']
            elemento['opacity'] = 0.8
            
        elif resource_format in ['shp', 'shape']:
            # For vector data (SHP files)
            if 'styles' in style_config:
                elemento['styles'] = style_config['styles']
            if 'activeStyle' in style_config:
                elemento['activeStyle'] = style_config['activeStyle']
            if 'legends' in style_config:
                elemento['legends'] = style_config['legends']
            
            # Common properties for shapefiles
            elemento['opacity'] = 0.8
            elemento['clampToGround'] = True
            elemento['forceCesiumPrimitives'] = False  # Always false for categorical styling
    
    def _apply_custom_config(self, elemento: Dict, custom_config: str):
        """Apply custom configuration to element."""
        try:
            # Extract the 'start' or 'share' parameter from the URL
            parsed_url = urllib.parse.urlparse(custom_config)
            fragment = parsed_url.fragment
            
            if fragment.startswith('share='):
                # Case of URL with #share (gist)
                gist_id = fragment.split('=g-')[1]
                gist_url = f'https://gist.githubusercontent.com/pabrojast/{gist_id}/raw/Terriajs-usercatalog.json'
                try:
                    response = self.http.get(gist_url, timeout=self.TIMEOUT_SECONDS)
                    if response.status_code == 200:
                        decoded_param = response.text
                    else:
                        decoded_param = '{}'
                except Exception as e:
                    self._debug_print(f"Error fetching gist config: {e}")
                    decoded_param = '{}'
            else:
                # Original case with #start
                start_param = fragment.split('=', 1)[1]
                decoded_param = urllib.parse.unquote(start_param)
            
            # Parse the JSON
            custom_data = json.loads(decoded_param)
            
            # Apply custom configuration properties
            for init_source in custom_data.get('initSources', []):
                if 'models' in init_source:
                    for model_key, model_value in init_source['models'].items():
                        # Apply existing legends and styles from custom config
                        if 'legends' in model_value:
                            elemento['legends'] = model_value['legends']
                        if 'styles' in model_value:
                            elemento['styles'] = model_value['styles']
                            if 'activeStyle' in model_value:
                                elemento['activeStyle'] = model_value['activeStyle']
                        if 'renderOptions' in model_value:
                            elemento['renderOptions'] = model_value['renderOptions']
                        if 'opacity' in model_value:
                            elemento['opacity'] = model_value['opacity']
                        
        except Exception as e:
            self._debug_print(f"Error processing custom config: {e}")
    
    def generate_dataset_json(self, dataset_id: str, view_index: Optional[int] = None) -> Dict:
        """
        Generate Terria JSON for a specific dataset.
        
        Args:
            dataset_id: Dataset ID
            view_index: Specific view index (None for all views)
            
        Returns:
            Terria JSON configuration
        """
        # Check cache first
        cache_key = f"{dataset_id}_{view_index if view_index is not None else 'all'}"
        cached_config = self.cache_manager.get_cached_config('dataset', cache_key)
        if cached_config:
            self._debug_print(f"Returning cached config for dataset {dataset_id}")
            return cached_config
        
        try:
            # Get dataset information
            dataset = toolkit.get_action('package_show')({}, {'id': dataset_id})
            
            # Get organization info
            org = dataset.get('organization', {})
            if org:
                try:
                    org_data = toolkit.get_action('organization_show')({}, {'id': org['name']})
                    org_info = {
                        'display_name': org_data.get('display_name', org['title']),
                        'description': org_data.get('description', ''),
                        'image_display_url': org_data.get('image_display_url', '')
                    }
                except:
                    org_info = {
                        'display_name': org.get('title', 'Unknown Organization'),
                        'description': '',
                        'image_display_url': ''
                    }
            else:
                org_info = {
                    'display_name': 'Unknown Organization',
                    'description': '',
                    'image_display_url': ''
                }
            
            dataset_title = dataset['title']
            notes = dataset.get('notes', '')
            resources = dataset.get('resources', [])
            
            # Build catalog structure
            catalog_members = []
            
            for resource in resources:
                resource_format = resource.get('format', '').lower()
                if resource_format in [f.lower() for f in self.formatos_permitidos]:
                    
                    # Get all views for this resource
                    formatted_item, total_views = self.format_dataset_item(
                        resource, dataset_id, notes, org_info, 0
                    )
                    
                    if view_index is not None:
                        # Return specific view only
                        if view_index < total_views:
                            formatted_item, _ = self.format_dataset_item(
                                resource, dataset_id, notes, org_info, view_index
                            )
                            catalog_members.append(formatted_item)
                    else:
                        # Return all views
                        catalog_members.append(formatted_item)
                        
                        # Add additional views if they exist
                        if total_views > 1:
                            for vi in range(1, total_views):
                                additional_item, _ = self.format_dataset_item(
                                    resource, dataset_id, notes, org_info, vi
                                )
                                catalog_members.append(additional_item)
            
            # Create final configuration
            config = {
                "catalog": [{
                    "name": dataset_title,
                    "type": "group",
                    "members": catalog_members,
                    "info": [{
                        "name": "About Dataset",
                        "content": notes or ''
                    }],
                    "infoSectionOrder": ["About Dataset"]
                }]
            }
            
            # Cache the result
            self.cache_manager.cache_config('dataset', cache_key, config)
            
            return config
            
        except Exception as e:
            self._debug_print(f"Error generating dataset JSON for {dataset_id}: {e}")
            raise
    
    def generate_organization_json(self, org_name: str) -> Dict:
        """
        Generate Terria JSON for an organization.
        
        Args:
            org_name: Organization name
            
        Returns:
            Terria JSON configuration
        """
        # Check cache first
        cached_config = self.cache_manager.get_cached_config('organization', org_name)
        if cached_config:
            self._debug_print(f"Returning cached config for organization {org_name}")
            return cached_config
        
        try:
            # Get organization datasets
            datasets_search = toolkit.get_action('package_search')({}, {
                'fq': f'organization:{org_name}',
                'rows': 1000,  # Adjust as needed
                'include_private': False
            })
            
            # Get organization info
            try:
                org_data = toolkit.get_action('organization_show')({}, {'id': org_name})
                org_info = {
                    'display_name': org_data.get('display_name', org_data.get('title', org_name)),
                    'description': org_data.get('description', ''),
                    'image_display_url': org_data.get('image_display_url', '')
                }
            except:
                org_info = {
                    'display_name': org_name,
                    'description': '',
                    'image_display_url': ''
                }
            
            # Process datasets
            datasets_by_title = defaultdict(list)
            
            for dataset in datasets_search.get('results', []):
                dataset_title = dataset['title']
                notes = dataset.get('notes', '')
                resources = dataset.get('resources', [])
                package_id = dataset['id']
                
                for resource in resources:
                    resource_format = resource.get('format', '').lower()
                    if resource_format in [f.lower() for f in self.formatos_permitidos]:
                        
                        # Get all views for this resource
                        formatted_item, total_views = self.format_dataset_item(
                            resource, package_id, notes, org_info, 0
                        )
                        datasets_by_title[dataset_title].append(formatted_item)
                        
                        # Add additional views if they exist
                        if total_views > 1:
                            for view_index in range(1, total_views):
                                additional_item, _ = self.format_dataset_item(
                                    resource, package_id, notes, org_info, view_index
                                )
                                datasets_by_title[dataset_title].append(additional_item)
            
            # Build catalog structure
            org_members = []
            for dataset_title, items in datasets_by_title.items():
                if len(items) == 1:
                    # Single item, add directly
                    org_members.extend(items)
                else:
                    # Multiple items, group them
                    dataset_group = {
                        "name": dataset_title,
                        "type": "group",
                        "members": items
                    }
                    org_members.append(dataset_group)
            
            # Create final configuration
            config = {
                "catalog": [{
                    "name": org_info['display_name'],
                    "type": "group",
                    "members": org_members,
                    "info": [{
                        "name": f"Organization: {org_info['display_name']}",
                        "content": f"<img style=\"max-width:300px;width:100%\" alt=\"{org_info['display_name']}\" src=\"{org_info['image_display_url']}\" /><br/>{org_info['description']}<br/>"
                    }],
                    "infoSectionOrder": [f"Organization: {org_info['display_name']}"]
                }]
            }
            
            # Cache the result
            self.cache_manager.cache_config('organization', org_name, config)
            
            return config
            
        except Exception as e:
            self._debug_print(f"Error generating organization JSON for {org_name}: {e}")
            raise
    
    def generate_tag_json(self, tag_name: str) -> Dict:
        """
        Generate Terria JSON for a tag.
        
        Args:
            tag_name: Tag name
            
        Returns:
            Terria JSON configuration
        """
        # Check cache first
        cached_config = self.cache_manager.get_cached_config('tag', tag_name)
        if cached_config:
            self._debug_print(f"Returning cached config for tag {tag_name}")
            return cached_config
        
        try:
            # Get tag datasets
            datasets_search = toolkit.get_action('package_search')({}, {
                'fq': f'tags:{tag_name}',
                'rows': 1000,  # Adjust as needed
                'include_private': False
            })
            
            # Process datasets
            datasets_by_title = defaultdict(list)
            
            for dataset in datasets_search.get('results', []):
                dataset_title = dataset['title']
                notes = dataset.get('notes', '')
                resources = dataset.get('resources', [])
                package_id = dataset['id']
                
                # Get organization info for this dataset
                org = dataset.get('organization', {})
                if org:
                    try:
                        org_data = toolkit.get_action('organization_show')({}, {'id': org['name']})
                        org_info = {
                            'display_name': org_data.get('display_name', org.get('title', 'Unknown')),
                            'description': org_data.get('description', ''),
                            'image_display_url': org_data.get('image_display_url', '')
                        }
                    except:
                        org_info = {
                            'display_name': org.get('title', 'Unknown Organization'),
                            'description': '',
                            'image_display_url': ''
                        }
                else:
                    org_info = {
                        'display_name': 'Unknown Organization',
                        'description': '',
                        'image_display_url': ''
                    }
                
                for resource in resources:
                    resource_format = resource.get('format', '').lower()
                    if resource_format in [f.lower() for f in self.formatos_permitidos]:
                        
                        # Get all views for this resource
                        formatted_item, total_views = self.format_dataset_item(
                            resource, package_id, notes, org_info, 0
                        )
                        datasets_by_title[dataset_title].append(formatted_item)
                        
                        # Add additional views if they exist
                        if total_views > 1:
                            for view_index in range(1, total_views):
                                additional_item, _ = self.format_dataset_item(
                                    resource, package_id, notes, org_info, view_index
                                )
                                datasets_by_title[dataset_title].append(additional_item)
            
            # Build catalog structure
            tag_members = []
            for dataset_title, items in datasets_by_title.items():
                if len(items) == 1:
                    # Single item, add directly
                    tag_members.extend(items)
                else:
                    # Multiple items, group them
                    dataset_group = {
                        "name": dataset_title,
                        "type": "group",
                        "members": items
                    }
                    tag_members.append(dataset_group)
            
            # Create final configuration
            config = {
                "catalog": [{
                    "name": tag_name,
                    "type": "group",
                    "members": tag_members
                }]
            }
            
            # Cache the result
            self.cache_manager.cache_config('tag', tag_name, config)
            
            return config
            
        except Exception as e:
            self._debug_print(f"Error generating tag JSON for {tag_name}: {e}")
            raise
    
    def generate_full_catalog_json(self) -> Dict:
        """
        Generate full catalog Terria JSON.
        
        Returns:
            Terria JSON configuration
        """
        # Check cache first
        cached_config = self.cache_manager.get_cached_config('full', 'catalog')
        if cached_config:
            self._debug_print("Returning cached full catalog config")
            return cached_config
        
        try:
            # Get all organizations
            orgs_search = toolkit.get_action('organization_list')({}, {
                'all_fields': True,
                'include_extras': True,
                'include_dataset_count': True
            })
            
            catalog_members = []
            
            for org in orgs_search:
                if org.get('package_count', 0) > 0:  # Only include orgs with datasets
                    org_name = org['name']
                    
                    # Generate organization JSON (this will use cache if available)
                    try:
                        org_config = self.generate_organization_json(org_name)
                        if org_config and org_config.get('catalog'):
                            catalog_members.extend(org_config['catalog'])
                    except Exception as e:
                        self._debug_print(f"Error generating config for organization {org_name}: {e}")
                        continue
            
            # Create final configuration
            config = {
                "catalog": catalog_members,
                "name": "IHP-WINS"
            }
            
            # Cache the result
            self.cache_manager.cache_config('full', 'catalog', config)
            
            return config
            
        except Exception as e:
            self._debug_print(f"Error generating full catalog JSON: {e}")
            raise
    
    def convert_sets_to_lists(self, obj: Any) -> Any:
        """Convert any sets in the object to lists for JSON serialization."""
        if isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, dict):
            return {k: self.convert_sets_to_lists(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.convert_sets_to_lists(v) for v in obj]
        return obj