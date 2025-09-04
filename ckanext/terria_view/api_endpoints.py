# encoding: utf-8
"""
API endpoints for Terria JSON generation.
"""
import json
import os
from flask import Blueprint, jsonify, request, Response, send_file
import ckan.plugins.toolkit as toolkit
from ckan.common import config

from .terria_json_generator import TerriaJSONGenerator


# Create Blueprint for our API endpoints
terria_api = Blueprint('terria_api', __name__)


class TerriaAPIController:
    """Controller for Terria API endpoints."""
    
    def __init__(self):
        """Initialize the controller."""
        self.generator = TerriaJSONGenerator()
    
    def _create_json_response(self, data: dict, status_code: int = 200) -> Response:
        """
        Create a JSON response with appropriate headers.
        
        Args:
            data: Data to return as JSON
            status_code: HTTP status code
            
        Returns:
            Flask Response object
        """
        response = Response(
            json.dumps(data, ensure_ascii=False, indent=2),
            status=status_code,
            content_type='application/json; charset=utf-8'
        )
        
        # Add CORS headers if needed
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        
        return response
    
    def _create_error_response(self, message: str, status_code: int = 500) -> Response:
        """
        Create an error response.
        
        Args:
            message: Error message
            status_code: HTTP status code
            
        Returns:
            Flask Response object
        """
        return self._create_json_response({
            'error': True,
            'message': message
        }, status_code)
    
    def dataset_json(self, dataset_id: str):
        """
        Generate Terria JSON for a specific dataset.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            JSON response with Terria configuration
        """
        try:
            # Get view_index from query parameters
            view_index = request.args.get('view_index', type=int)
            
            # Generate configuration
            config = self.generator.generate_dataset_json(dataset_id, view_index)
            
            # Convert sets to lists for JSON serialization
            config = self.generator.convert_sets_to_lists(config)
            
            return self._create_json_response(config)
            
        except toolkit.ObjectNotFound:
            return self._create_error_response(f'Dataset not found: {dataset_id}', 404)
        except Exception as e:
            return self._create_error_response(f'Error generating dataset JSON: {str(e)}')
    
    def organization_json(self, org_name: str):
        """
        Generate Terria JSON for an organization.
        
        Args:
            org_name: Organization name
            
        Returns:
            JSON response with Terria configuration
        """
        try:
            # Generate configuration
            config = self.generator.generate_organization_json(org_name)
            
            # Convert sets to lists for JSON serialization
            config = self.generator.convert_sets_to_lists(config)
            
            return self._create_json_response(config)
            
        except toolkit.ObjectNotFound:
            return self._create_error_response(f'Organization not found: {org_name}', 404)
        except Exception as e:
            return self._create_error_response(f'Error generating organization JSON: {str(e)}')
    
    def tag_json(self, tag_name: str):
        """
        Generate Terria JSON for a tag.
        
        Args:
            tag_name: Tag name
            
        Returns:
            JSON response with Terria configuration
        """
        try:
            # Generate configuration
            config = self.generator.generate_tag_json(tag_name)
            
            # Convert sets to lists for JSON serialization
            config = self.generator.convert_sets_to_lists(config)
            
            return self._create_json_response(config)
            
        except Exception as e:
            return self._create_error_response(f'Error generating tag JSON: {str(e)}')
    
    def full_catalog_json(self):
        """
        Generate full catalog Terria JSON.
        
        Returns:
            JSON response with full Terria configuration
        """
        try:
            # Generate configuration
            config = self.generator.generate_full_catalog_json()
            
            # Convert sets to lists for JSON serialization
            config = self.generator.convert_sets_to_lists(config)
            
            return self._create_json_response(config)
            
        except Exception as e:
            return self._create_error_response(f'Error generating full catalog JSON: {str(e)}')
    
    def resource_views(self, resource_id: str):
        """
        Get Terria views for a specific resource.
        
        Args:
            resource_id: Resource ID
            
        Returns:
            JSON response with resource views information
        """
        try:
            # Get resource views
            views_data = toolkit.get_action('resource_view_list')({}, {'id': resource_id})
            terria_views = [view for view in views_data if view.get('view_type') == 'terria_view']
            
            # Get resource info
            resource = toolkit.get_action('resource_show')({}, {'id': resource_id})
            
            # Format response
            response_data = {
                'resource_id': resource_id,
                'resource_name': resource.get('name', ''),
                'resource_format': resource.get('format', ''),
                'total_views': len(terria_views),
                'views': []
            }
            
            for i, view in enumerate(terria_views):
                view_info = {
                    'view_index': i,
                    'view_id': view.get('id'),
                    'title': view.get('title', ''),
                    'description': view.get('description', ''),
                    'custom_config': view.get('custom_config', ''),
                    'style': view.get('style', ''),
                    'terria_instance_url': view.get('terria_instance_url', ''),
                    'created': view.get('created', ''),
                    'modified': view.get('modified', ''),
                    'json_url': f"/api/terria/dataset/{resource.get('package_id')}?view_index={i}"
                }
                response_data['views'].append(view_info)
            
            return self._create_json_response(response_data)
            
        except toolkit.ObjectNotFound:
            return self._create_error_response(f'Resource not found: {resource_id}', 404)
        except Exception as e:
            return self._create_error_response(f'Error getting resource views: {str(e)}')
    
    def cache_stats(self):
        """
        Get cache statistics.
        
        Returns:
            JSON response with cache statistics
        """
        try:
            stats = self.generator.cache_manager.get_cache_stats()
            return self._create_json_response(stats)
        except Exception as e:
            return self._create_error_response(f'Error getting cache stats: {str(e)}')
    
    def modular_catalog_json(self):
        """
        Generate modular catalog Terria JSON (reference-based for performance).
        
        Returns:
            JSON response with modular Terria configuration
        """
        try:
            # Generate configuration
            config = self.generator.generate_modular_catalog()
            
            # Convert sets to lists for JSON serialization
            config = self.generator.convert_sets_to_lists(config)
            
            return self._create_json_response(config)
            
        except Exception as e:
            return self._create_error_response(f'Error generating modular catalog JSON: {str(e)}')
    
    def dataset_json_file(self, dataset_id: str):
        """
        Generate and serve dataset JSON as file for better performance.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            File response with JSON
        """
        try:
            view_index = request.args.get('view_index', type=int)
            cache_key = f"{dataset_id}_{view_index if view_index is not None else 'all'}"
            
            # Get or generate cached file
            file_path = self.generator.get_or_generate_file(
                'dataset', cache_key, 
                self.generator.generate_dataset_json, 
                dataset_id, view_index
            )
            
            # Serve file
            return send_file(
                file_path,
                mimetype='application/json',
                as_attachment=False,
                download_name=f'dataset_{dataset_id}.json'
            )
            
        except toolkit.ObjectNotFound:
            return self._create_error_response(f'Dataset not found: {dataset_id}', 404)
        except Exception as e:
            return self._create_error_response(f'Error generating dataset file: {str(e)}')
    
    def organization_json_file(self, org_name: str):
        """
        Generate and serve organization JSON as file.
        
        Args:
            org_name: Organization name
            
        Returns:
            File response with JSON
        """
        try:
            # Get or generate cached file
            file_path = self.generator.get_or_generate_file(
                'organization', org_name,
                self.generator.generate_organization_json,
                org_name
            )
            
            # Serve file
            return send_file(
                file_path,
                mimetype='application/json',
                as_attachment=False,
                download_name=f'organization_{org_name}.json'
            )
            
        except toolkit.ObjectNotFound:
            return self._create_error_response(f'Organization not found: {org_name}', 404)
        except Exception as e:
            return self._create_error_response(f'Error generating organization file: {str(e)}')
    
    def full_catalog_json_file(self):
        """
        Generate and serve full catalog JSON as file.
        
        Returns:
            File response with JSON
        """
        try:
            # Get or generate cached file
            file_path = self.generator.get_or_generate_file(
                'full', 'catalog',
                self.generator.generate_full_catalog_json
            )
            
            # Serve file
            return send_file(
                file_path,
                mimetype='application/json',
                as_attachment=False,
                download_name='ihp-wins.json'
            )
            
        except Exception as e:
            return self._create_error_response(f'Error generating full catalog file: {str(e)}')
    
    def invalidate_cache(self):
        """
        Invalidate cache entries.
        
        Returns:
            JSON response confirming cache invalidation
        """
        try:
            # Get parameters
            cache_type = request.args.get('type')
            identifier = request.args.get('id')
            
            # Invalidate both memory and file cache
            self.generator.cache_manager.invalidate_cache(cache_type, identifier)
            self.generator.file_cache_manager.invalidate_cache(cache_type, identifier)
            
            return self._create_json_response({
                'success': True,
                'message': 'Cache invalidated successfully'
            })
        except Exception as e:
            return self._create_error_response(f'Error invalidating cache: {str(e)}')
    
    def cleanup_cache(self):
        """
        Clean up expired cache files.
        
        Returns:
            JSON response with cleanup results
        """
        try:
            cleaned_files = self.generator.file_cache_manager.cleanup_expired_files()
            
            return self._create_json_response({
                'success': True,
                'cleaned_files': cleaned_files,
                'message': f'Cleaned up {cleaned_files} expired cache files'
            })
        except Exception as e:
            return self._create_error_response(f'Error cleaning up cache: {str(e)}')


# Initialize controller lazily to avoid import-time errors
controller = None

def get_controller():
    global controller
    if controller is None:
        try:
            controller = TerriaAPIController()
        except Exception as e:
            # Log the error and create a minimal error response
            print(f"Error initializing TerriaAPIController: {e}")
            # Return a minimal controller that can handle errors
            from flask import jsonify
            class ErrorController:
                def __getattr__(self, name):
                    def error_response(*args, **kwargs):
                        return jsonify({
                            'error': True,
                            'message': f'Service temporarily unavailable: {e}'
                        }), 503
                    return error_response
            controller = ErrorController()
    return controller


# Define routes
@terria_api.route('/api/terria/dataset/<dataset_id>', methods=['GET'])
def dataset_json_endpoint(dataset_id):
    """Dataset JSON endpoint."""
    return get_controller().dataset_json(dataset_id)


@terria_api.route('/api/terria/organization/<org_name>', methods=['GET'])
def organization_json_endpoint(org_name):
    """Organization JSON endpoint."""
    return get_controller().organization_json(org_name)


@terria_api.route('/api/terria/tag/<tag_name>', methods=['GET'])
def tag_json_endpoint(tag_name):
    """Tag JSON endpoint."""
    return get_controller().tag_json(tag_name)


@terria_api.route('/api/terria/full', methods=['GET'])
def full_catalog_json_endpoint():
    """Full catalog JSON endpoint."""
    return get_controller().full_catalog_json()


@terria_api.route('/api/terria/resource/<resource_id>/views', methods=['GET'])
def resource_views_endpoint(resource_id):
    """Resource views endpoint."""
    return get_controller().resource_views(resource_id)


@terria_api.route('/api/terria/modular', methods=['GET'])
def modular_catalog_endpoint():
    """Modular catalog JSON endpoint."""
    return get_controller().modular_catalog_json()


# File serving endpoints for better performance
@terria_api.route('/api/terria/file/dataset/<dataset_id>', methods=['GET'])
def dataset_json_file_endpoint(dataset_id):
    """Dataset JSON file endpoint."""
    return get_controller().dataset_json_file(dataset_id)


@terria_api.route('/api/terria/file/organization/<org_name>', methods=['GET'])
def organization_json_file_endpoint(org_name):
    """Organization JSON file endpoint."""
    return get_controller().organization_json_file(org_name)


@terria_api.route('/api/terria/file/full', methods=['GET'])
def full_catalog_json_file_endpoint():
    """Full catalog JSON file endpoint."""
    return get_controller().full_catalog_json_file()


# Serve the main IHP-WINS.json file at the root for compatibility
@terria_api.route('/ihp-wins.json', methods=['GET'])
def ihp_wins_json_endpoint():
    """Main IHP-WINS JSON file endpoint (compatibility)."""
    return get_controller().full_catalog_json_file()


@terria_api.route('/api/terria/cache/stats', methods=['GET'])
def cache_stats_endpoint():
    """Cache statistics endpoint."""
    return get_controller().cache_stats()


@terria_api.route('/api/terria/cache/invalidate', methods=['POST'])
def invalidate_cache_endpoint():
    """Cache invalidation endpoint."""
    return get_controller().invalidate_cache()


@terria_api.route('/api/terria/cache/cleanup', methods=['POST'])
def cleanup_cache_endpoint():
    """Cache cleanup endpoint."""
    return get_controller().cleanup_cache()


# Support for OPTIONS requests (CORS preflight)
@terria_api.route('/api/terria/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle OPTIONS requests for CORS."""
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response