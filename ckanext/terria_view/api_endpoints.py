# encoding: utf-8
"""
API endpoints for Terria JSON generation.
"""
import json
import mimetypes
import os
import threading
import urllib.parse

import requests
from flask import Blueprint, jsonify, request, Response, send_file


# Supplement mimetypes for formats TerriaJS cares about. Many CKAN resources
# have no ``mimetype`` set, and Azure Blob Storage defaults uploads to
# ``application/octet-stream``; TerriaJS then refuses to parse them (e.g. a CSV
# item silently stays out of the workbench).
_TERRIA_CONTENT_TYPES = {
    '.csv': 'text/csv',
    '.tsv': 'text/tab-separated-values',
    '.geojson': 'application/geo+json',
    '.json': 'application/json',
    '.czml': 'application/json',
    '.kml': 'application/vnd.google-earth.kml+xml',
    '.kmz': 'application/vnd.google-earth.kmz',
    '.zip': 'application/zip',
    '.tif': 'image/tiff',
    '.tiff': 'image/tiff',
    '.cog': 'image/tiff',
}


def _terria_friendly_content_type(filename, fallback):
    """
    Return a mimetype TerriaJS recognises, preferring the filename extension.

    Azure Blob responses commonly default to ``application/octet-stream`` even
    for CSV/GeoJSON, which causes TerriaJS to silently ignore the resource.
    We prefer an extension-based hint over such generic upstream values.
    """
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        if ext in _TERRIA_CONTENT_TYPES:
            return _TERRIA_CONTENT_TYPES[ext]
        guessed, _ = mimetypes.guess_type(filename)
        if guessed:
            return guessed
    if fallback and fallback.lower() != 'application/octet-stream':
        return fallback
    return fallback or 'application/octet-stream'
import ckan.plugins.toolkit as toolkit
from ckan.common import config

from .terria_json_generator import TerriaJSONGenerator


# Create Blueprint for our API endpoints
terria_api = Blueprint('terria_api', __name__)

# Lock to prevent concurrent regeneration of the full catalog
_catalog_regen_lock = threading.Lock()


class TerriaAPIController:
    """Controller for Terria API endpoints."""
    
    def __init__(self):
        """Initialize the controller."""
        self.generator = TerriaJSONGenerator()

    @staticmethod
    def _get_user_context() -> dict:
        """Build a CKAN context dict for the current user (CKAN 2.10+ compatible)."""
        try:
            user = toolkit.current_user
            return {
                'user': user.name if hasattr(user, 'name') else str(user),
                'auth_user_obj': user
            }
        except (AttributeError, RuntimeError):
            return {
                'user': getattr(toolkit.g, 'user', ''),
                'auth_user_obj': getattr(toolkit.g, 'userobj', None)
            }
    
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
        Uses stale-while-revalidate: returns cached data (even if stale) while
        regenerating in background.
        
        Returns:
            JSON response with full Terria configuration
        """
        try:
            # Try file cache (allow stale, validates JSON integrity)
            filepath, is_fresh = self.generator.file_cache_manager.get_cached_file_allow_stale(
                'full', 'catalog'
            )

            if filepath:
                if not is_fresh:
                    self._trigger_background_regeneration()
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    return self._create_json_response(data)
                except (json.JSONDecodeError, IOError) as e:
                    # File corrupted between validation and read (unlikely but possible)
                    try:
                        os.remove(filepath)
                    except OSError:
                        pass

            # No cache or corrupted — trigger background regen and return 202
            self._trigger_background_regeneration()
            return self._create_json_response({
                'status': 'generating',
                'message': 'Full catalog is being generated. Please retry in a few minutes.'
            }, 202)

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
            # Get memory cache stats
            memory_stats = self.generator.cache_manager.get_cache_stats()
            
            # Get file cache stats
            file_stats = self.generator.file_cache_manager.get_cache_stats()
            
            # Combine stats
            combined_stats = {
                'memory_cache': memory_stats,
                'file_cache': file_stats
            }
            
            return self._create_json_response(combined_stats)
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
            File response with JSON or JSON response if file caching disabled
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
            
            if file_path and os.path.exists(file_path):
                # Serve file with Flask version compatibility
                try:
                    return send_file(
                        file_path,
                        mimetype='application/json',
                        as_attachment=False,
                        download_name=f'dataset_{dataset_id}.json'
                    )
                except TypeError:
                    # Fallback for older Flask versions without download_name
                    return send_file(
                        file_path,
                        mimetype='application/json',
                        as_attachment=False
                    )
            else:
                # Fallback to JSON response if file caching failed/disabled
                config = self.generator.generate_dataset_json(dataset_id, view_index)
                config = self.generator.convert_sets_to_lists(config)
                return self._create_json_response(config)
            
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
            File response with JSON or JSON response if file caching disabled
        """
        try:
            # Get or generate cached file
            file_path = self.generator.get_or_generate_file(
                'organization', org_name,
                self.generator.generate_organization_json,
                org_name
            )
            
            if file_path and os.path.exists(file_path):
                # Serve file with Flask version compatibility
                try:
                    return send_file(
                        file_path,
                        mimetype='application/json',
                        as_attachment=False,
                        download_name=f'organization_{org_name}.json'
                    )
                except TypeError:
                    # Fallback for older Flask versions without download_name
                    return send_file(
                        file_path,
                        mimetype='application/json',
                        as_attachment=False
                    )
            else:
                # Fallback to JSON response if file caching failed/disabled
                config = self.generator.generate_organization_json(org_name)
                config = self.generator.convert_sets_to_lists(config)
                return self._create_json_response(config)
            
        except toolkit.ObjectNotFound:
            return self._create_error_response(f'Organization not found: {org_name}', 404)
        except Exception as e:
            return self._create_error_response(f'Error generating organization file: {str(e)}')
    
    def full_catalog_json_file(self):
        """
        Generate and serve full catalog JSON as file.
        Uses stale-while-revalidate: serves stale cache immediately
        while triggering background regeneration.
        
        Returns:
            File response with JSON, or 202 if catalog is still being generated
        """
        try:
            # Use stale-while-revalidate (validates JSON integrity)
            filepath, is_fresh = self.generator.file_cache_manager.get_cached_file_allow_stale(
                'full', 'catalog'
            )

            if filepath and is_fresh:
                # Cache is fresh — serve directly
                return self._send_json_file(filepath, 'ihp-wins.json')

            if filepath and not is_fresh:
                # Cache is stale — serve it now but trigger background regeneration
                self._trigger_background_regeneration()
                return self._send_json_file(filepath, 'ihp-wins.json')

            # No cache at all (or was corrupted and removed) — trigger regeneration
            self._trigger_background_regeneration()
            return self._create_json_response({
                'status': 'generating',
                'message': 'Full catalog is being generated. Please retry in a few minutes.'
            }, 202)

        except Exception as e:
            return self._create_error_response(f'Error generating full catalog file: {str(e)}')

    def _send_json_file(self, file_path: str, download_name: str) -> Response:
        """Send a JSON file as response with Flask version compatibility."""
        try:
            return send_file(
                file_path,
                mimetype='application/json',
                as_attachment=False,
                download_name=download_name
            )
        except TypeError:
            return send_file(
                file_path,
                mimetype='application/json',
                as_attachment=False
            )

    def _trigger_background_regeneration(self):
        """Trigger full catalog regeneration in a background thread (non-blocking)."""
        if not _catalog_regen_lock.acquire(blocking=False):
            # Another regeneration is already in progress
            return

        def _regenerate():
            try:
                self.generator.get_or_generate_file(
                    'full', 'catalog',
                    self.generator.generate_full_catalog_json
                )
            except Exception as e:
                print(f"[terria_view] Background catalog regeneration failed: {e}")
            finally:
                _catalog_regen_lock.release()

        thread = threading.Thread(target=_regenerate, daemon=True)
        thread.start()
    
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
            
            result = {
                'success': True,
                'cleaned_files': cleaned_files,
                'message': f'Cleaned up {cleaned_files} expired cache files'
            }
            
            if cleaned_files == 0:
                file_cache_enabled = self.generator.file_cache_manager.cache_subdir is not None
                if not file_cache_enabled:
                    result['message'] = 'File caching is disabled - no cleanup needed'
                else:
                    result['message'] = 'No expired cache files found'
            
            return self._create_json_response(result)
        except Exception as e:
            return self._create_error_response(f'Error cleaning up cache: {str(e)}')
    
    def save_view_config(self, view_id: str):
        """
        Save custom configuration URL to a resource view.
        
        Args:
            view_id: Resource view ID
            
        Returns:
            JSON response confirming the save operation
        """
        try:
            # Get JSON data from request
            data = request.get_json()
            if not data:
                return self._create_error_response('No data provided', 400)
            
            custom_config_url = data.get('custom_config_url')
            if not custom_config_url:
                return self._create_error_response('custom_config_url is required', 400)

            # Validate URL scheme to prevent stored XSS / javascript: URIs
            if not isinstance(custom_config_url, str) or not custom_config_url.strip().startswith(('http://', 'https://')):
                return self._create_error_response('custom_config_url must be an HTTP(S) URL', 400)
            custom_config_url = custom_config_url.strip()
            
            # Get current user context
            context = self._get_user_context()
            
            # Get current view data
            try:
                current_view = toolkit.get_action('resource_view_show')(context, {'id': view_id})
            except toolkit.ObjectNotFound:
                return self._create_error_response(f'View not found: {view_id}', 404)
            except toolkit.NotAuthorized:
                return self._create_error_response('Not authorized to access this view', 403)
            
            # Update view with new custom_config
            update_data = {
                'id': view_id,
                'resource_id': current_view.get('resource_id'),
                'view_type': current_view.get('view_type'),
                'title': current_view.get('title'),
                'description': current_view.get('description', ''),
                'terria_instance_url': current_view.get('terria_instance_url', ''),
                'style': current_view.get('style', 'NA'),
                'custom_config': custom_config_url
            }
            
            try:
                updated_view = toolkit.get_action('resource_view_update')(context, update_data)
            except toolkit.NotAuthorized:
                return self._create_error_response('Not authorized to update this view', 403)
            except Exception as e:
                return self._create_error_response(f'Failed to update view: {str(e)}', 500)
            
            return self._create_json_response({
                'success': True,
                'message': 'Configuration saved successfully',
                'view_id': view_id,
                'custom_config': custom_config_url
            })
            
        except Exception as e:
            return self._create_error_response(f'Error saving view configuration: {str(e)}')
    
    def resource_content(self, resource_id: str):
        """
        Stream a private resource's content through CKAN with open CORS.

        The caller must supply a signed ``token`` query param generated by
        ``ResourceUtils.generate_resource_token``. We keep authorization in the
        token itself (not cookies) because the Terria iframe requesting this
        URL lives on a different origin and cannot forward the CKAN session.
        """
        debug = os.getenv("TERRIA_DEBUG", "false").lower() == "true"

        def _debug(msg):
            if debug:
                print(f"[terria_view.proxy] {msg}")

        try:
            token = request.args.get('token', '')
            resource_utils = self.generator.resource_utils
            if not resource_utils.verify_resource_token(resource_id, token):
                _debug(f"reject: invalid/expired token for {resource_id}")
                return self._create_cors_error_response('Invalid or expired token', 401)

            source = resource_utils.resolve_private_resource_source(resource_id)
            if not source:
                _debug(f"reject: could not resolve upstream for {resource_id}")
                return self._create_cors_error_response(
                    'Resource not resolvable (missing url/filename or not accessible)',
                    404
                )

            upstream_url, content_type, filename = source
            _debug(
                f"resolved upstream for {resource_id}: "
                f"filename={filename!r} content_type={content_type!r} "
                f"upstream_host={urllib.parse.urlparse(upstream_url).netloc}"
            )

            # Azure/S3 only accept GET/HEAD for blob SAS; don't forward cookies or auth.
            upstream_method = 'HEAD' if request.method == 'HEAD' else 'GET'
            try:
                upstream = requests.request(
                    upstream_method,
                    upstream_url,
                    stream=True,
                    timeout=60,
                    allow_redirects=True,
                )
            except requests.RequestException as exc:
                _debug(f"upstream request failed: {exc}")
                return self._create_cors_error_response(
                    f'Error fetching resource from storage: {exc}', 502
                )

            if upstream.status_code >= 400:
                body = ''
                try:
                    body = upstream.text[:500]
                except Exception:
                    pass
                _debug(
                    f"upstream returned {upstream.status_code} for {resource_id}: {body!r}"
                )
                return self._create_cors_error_response(
                    f'Storage backend returned {upstream.status_code}: {body}',
                    502
                )

            # Prefer filename extension over upstream Content-Type: Azure Blob
            # frequently returns ``application/octet-stream`` for uploaded CSVs,
            # which causes TerriaJS to drop the item silently (no CSV parser).
            upstream_ct = upstream.headers.get('Content-Type')
            resolved_type = _terria_friendly_content_type(
                filename, content_type or upstream_ct
            )
            _debug(f"content-type resolved to {resolved_type!r} (upstream={upstream_ct!r})")

            def _stream():
                try:
                    for chunk in upstream.iter_content(chunk_size=8192):
                        if chunk:
                            yield chunk
                finally:
                    upstream.close()

            response = Response(_stream(), mimetype=resolved_type)

            # Preserve headers that matter for range/streaming/caching.
            for header in ('Content-Length', 'ETag', 'Last-Modified', 'Accept-Ranges'):
                value = upstream.headers.get(header)
                if value:
                    response.headers[header] = value

            # Always expose a friendly filename when available.
            if filename:
                response.headers['Content-Disposition'] = f'inline; filename="{filename}"'

            # CORS: token-gated, so we can safely allow any origin to read.
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, OPTIONS'
            response.headers['Access-Control-Expose-Headers'] = (
                'Content-Length, ETag, Last-Modified, Accept-Ranges, Content-Disposition'
            )
            # Short private cache so repeated TerriaJS loads within a session don't re-hit Azure.
            response.headers['Cache-Control'] = 'private, max-age=300'
            response.headers['X-Accel-Buffering'] = 'no'

            return response

        except Exception as exc:
            _debug(f"unexpected error: {exc}")
            return self._create_cors_error_response(
                f'Error streaming resource content: {exc}'
            )

    def _create_cors_error_response(self, message: str, status_code: int = 500) -> Response:
        """
        Build an error response with CORS headers so the Terria iframe can read the body.

        Without CORS, ``fetch`` from a cross-origin iframe hides the status and body
        of error responses from client code — making proxy failures opaque in the
        user's browser console.
        """
        response = self._create_error_response(message, status_code)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Expose-Headers'] = 'Content-Type'
        return response

    def user_private_datasets(self):
        """
        Get private datasets accessible to the current logged-in user in Terria JSON format.
        
        Returns:
            JSON response with Terria catalog configuration for private datasets
        """
        try:
            # Check if user is logged in
            context = self._get_user_context()
            user = context.get('user')
            if not user:
                return self._create_error_response('Authentication required. Please log in.', 401)
            
            # Search for private datasets the user can access
            try:
                # Use package_search with include_private=True to get private datasets
                search_result = toolkit.get_action('package_search')(context, {
                    'include_private': True,
                    'rows': 1000,
                    'q': '*:*'
                })
                
                # Filter only private datasets and generate Terria catalog
                catalog_members = []
                
                for dataset in search_result.get('results', []):
                    if not dataset.get('private', False):
                        continue
                    
                    dataset_id = dataset.get('id')
                    dataset_title = dataset.get('title', dataset.get('name', 'Unknown'))
                    notes = dataset.get('notes', '')
                    resources = dataset.get('resources', [])
                    
                    # Get organization info
                    org = dataset.get('organization', {})
                    if org:
                        org_info = {
                            'display_name': org.get('title', 'Unknown Organization'),
                            'description': org.get('description', ''),
                            'image_display_url': org.get('image_display_url', '')
                        }
                    else:
                        org_info = {
                            'display_name': 'Unknown Organization',
                            'description': '',
                            'image_display_url': ''
                        }
                    
                    # Build dataset group with resources
                    dataset_members = []
                    
                    for resource in resources:
                        resource_format = resource.get('format', '').lower()
                        if resource_format not in [f.lower() for f in self.generator.formatos_permitidos]:
                            continue
                        
                        # Format resource as Terria item with styles
                        try:
                            formatted_item, total_views = self.generator.format_dataset_item(
                                resource, dataset_id, notes, org_info, 0,
                                package=dataset, user_context=context
                            )
                            dataset_members.append(formatted_item)
                            
                            # Add additional views if they exist
                            if total_views > 1:
                                for vi in range(1, total_views):
                                    additional_item, _ = self.generator.format_dataset_item(
                                        resource, dataset_id, notes, org_info, vi,
                                        package=dataset, user_context=context
                                    )
                                    dataset_members.append(additional_item)
                        except Exception as e:
                            # If formatting fails, skip this resource
                            continue
                    
                    # Only add dataset if it has Terria-compatible resources
                    if dataset_members:
                        catalog_members.append({
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
                        })
                
                # Create final Terria catalog configuration
                config = {
                    "catalog": [{
                        "name": f"Private Datasets ({user})",
                        "type": "group",
                        "members": catalog_members,
                        "description": f"Private datasets accessible to {user}",
                        "isOpen": True
                    }]
                }
                
                # Convert sets to lists for JSON serialization
                config = self.generator.convert_sets_to_lists(config)
                
                return self._create_json_response(config)
                
            except toolkit.NotAuthorized:
                return self._create_error_response('Not authorized to access private datasets', 403)
                
        except Exception as e:
            return self._create_error_response(f'Error retrieving private datasets: {str(e)}')


# Initialize controller lazily to avoid import-time errors
controller = None

def get_controller():
    global controller
    if controller is None:
        try:
            controller = TerriaAPIController()
        except Exception as init_error:
            # Log the error and create a minimal error response
            print(f"Error initializing TerriaAPIController: {init_error}")
            # Return a minimal controller that can handle errors
            from flask import jsonify
            
            error_message = str(init_error)
            
            class ErrorController:
                def __getattr__(self, name):
                    def error_response(*args, **kwargs):
                        return jsonify({
                            'error': True,
                            'message': f'Service temporarily unavailable: {error_message}'
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


@terria_api.route('/api/terria/view/<view_id>/save-config', methods=['POST'])
def save_view_config_endpoint(view_id):
    """Save view configuration endpoint."""
    return get_controller().save_view_config(view_id)


@terria_api.route('/api/terria/user/private-datasets', methods=['GET'])
def user_private_datasets_endpoint():
    """Get private datasets accessible to the current user."""
    return get_controller().user_private_datasets()


@terria_api.route('/api/terria/resource/<resource_id>/content', methods=['GET', 'HEAD'])
@terria_api.route('/api/terria/resource/<resource_id>/content/<path:filename>', methods=['GET', 'HEAD'])
def resource_content_endpoint(resource_id, filename=None):
    """Stream a private resource through CKAN with open CORS (token-gated).

    ``filename`` is purely cosmetic — TerriaJS validates URL extensions
    client-side before fetching (e.g. shapefiles must end in ``.zip``), so we
    let callers embed the filename in the path. Authorization stays on the
    signed ``token`` query parameter.
    """
    return get_controller().resource_content(resource_id)


# Support for OPTIONS requests (CORS preflight)
@terria_api.route('/api/terria/<path:path>', methods=['OPTIONS'])
def handle_options(path):
    """Handle OPTIONS requests for CORS."""
    response = Response()
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, HEAD, POST, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Range, If-None-Match, If-Modified-Since'
    response.headers['Access-Control-Max-Age'] = '600'
    return response