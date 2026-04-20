# encoding: utf-8
"""
Cache manager for Terria JSON configurations.

IMPORTANT: This cache stores ONLY public dataset configurations.
Private datasets are loaded on-demand per-request in the plugin's
_get_private_datasets_catalog() method and are never stored here.
"""
import json
import hashlib
import time
from typing import Dict, Optional, Any
import ckan.plugins.toolkit as toolkit
from datetime import datetime, timedelta


class CacheManager:
    """Manages caching for Terria JSON configurations."""
    
    def __init__(self):
        """Initialize the cache manager."""
        self.cache = {}  # In-memory cache
        self.cache_timeout = 3600  # 1 hour default
        
    def _get_cache_key(self, cache_type: str, identifier: str) -> str:
        """
        Generate a cache key.
        
        Args:
            cache_type: Type of cache (dataset, organization, tag, full)
            identifier: Identifier (dataset_id, org_name, tag_name, etc.)
            
        Returns:
            Cache key string
        """
        return f"terria_{cache_type}_{hashlib.md5(identifier.encode()).hexdigest()}"
    
    def _get_dataset_hash(self, dataset_id: str) -> str:
        """
        Get hash of dataset based on last modification time, resource info, and Terria views.
        
        Args:
            dataset_id: Dataset ID
            
        Returns:
            Hash string representing current dataset state
        """
        try:
            # Get dataset info
            dataset = toolkit.get_action('package_show')({}, {'id': dataset_id})
            
            # Create hash based on dataset metadata and resource info
            hash_data = {
                'metadata_modified': dataset.get('metadata_modified', ''),
                'resources': []
            }
            
            for resource in dataset.get('resources', []):
                resource_hash = {
                    'id': resource.get('id'),
                    'last_modified': resource.get('last_modified', ''),
                    'url': resource.get('url', ''),
                    'format': resource.get('format', ''),
                    'terria_views': []
                }
                
                # Get Terria views for this resource and include them in hash
                try:
                    views_data = toolkit.get_action('resource_view_list')({}, {'id': resource.get('id')})
                    terria_views = [view for view in views_data if view.get('view_type') == 'terria_view']
                    
                    for view in terria_views:
                        resource_hash['terria_views'].append({
                            'id': view.get('id'),
                            'title': view.get('title', ''),
                            'custom_config': view.get('custom_config', ''),
                            'style': view.get('style', ''),
                            'terria_instance_url': view.get('terria_instance_url', ''),
                            'modified': view.get('modified', '')  # Include view modification time
                        })
                except Exception as view_error:
                    # If we can't get views, continue without them
                    pass
                
                hash_data['resources'].append(resource_hash)
            
            hash_string = json.dumps(hash_data, sort_keys=True)
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception as e:
            # If we can't get dataset info, return current timestamp as hash
            return str(int(time.time()))
    
    def _get_organization_hash(self, org_name: str) -> str:
        """
        Get hash of organization based on its datasets.
        
        Args:
            org_name: Organization name
            
        Returns:
            Hash string representing current organization state
        """
        try:
            # Get organization datasets
            datasets = toolkit.get_action('package_search')({}, {
                'fq': f'organization:{org_name}',
                'rows': 1000,  # Adjust as needed
                'sort': 'metadata_modified desc'
            })
            
            # Create hash based on dataset modifications
            hash_data = []
            for dataset in datasets.get('results', []):
                hash_data.append({
                    'id': dataset.get('id'),
                    'metadata_modified': dataset.get('metadata_modified', '')
                })
            
            hash_string = json.dumps(hash_data, sort_keys=True)
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception as e:
            return str(int(time.time()))
    
    def _get_tag_hash(self, tag_name: str) -> str:
        """
        Get hash of tag based on its datasets.
        
        Args:
            tag_name: Tag name
            
        Returns:
            Hash string representing current tag state
        """
        try:
            # Get tag datasets
            datasets = toolkit.get_action('package_search')({}, {
                'fq': f'tags:{tag_name}',
                'rows': 1000,  # Adjust as needed
                'sort': 'metadata_modified desc'
            })
            
            # Create hash based on dataset modifications
            hash_data = []
            for dataset in datasets.get('results', []):
                hash_data.append({
                    'id': dataset.get('id'),
                    'metadata_modified': dataset.get('metadata_modified', '')
                })
            
            hash_string = json.dumps(hash_data, sort_keys=True)
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception as e:
            return str(int(time.time()))
    
    def _get_full_catalog_hash(self) -> str:
        """
        Get hash of full catalog based on all datasets.
        
        Returns:
            Hash string representing current full catalog state
        """
        try:
            # Get all datasets
            datasets = toolkit.get_action('package_search')({}, {
                'rows': 10000,  # Adjust as needed
                'sort': 'metadata_modified desc'
            })
            
            # Create hash based on dataset modifications
            hash_data = []
            for dataset in datasets.get('results', []):
                hash_data.append({
                    'id': dataset.get('id'),
                    'metadata_modified': dataset.get('metadata_modified', '')
                })
            
            hash_string = json.dumps(hash_data, sort_keys=True)
            return hashlib.md5(hash_string.encode()).hexdigest()
            
        except Exception as e:
            return str(int(time.time()))
    
    def get_cached_config(self, cache_type: str, identifier: str) -> Optional[Dict]:
        """
        Get cached configuration if valid.
        
        Args:
            cache_type: Type of cache (dataset, organization, tag, full)
            identifier: Identifier (dataset_id, org_name, tag_name, etc.)
            
        Returns:
            Cached configuration dict or None if not found/invalid
        """
        cache_key = self._get_cache_key(cache_type, identifier)
        
        if cache_key not in self.cache:
            return None
            
        cached_item = self.cache[cache_key]
        current_time = time.time()
        
        # Check if cache has expired
        if current_time - cached_item['timestamp'] > self.cache_timeout:
            del self.cache[cache_key]
            return None
        
        # Check if content has changed by comparing hashes
        if cache_type == 'dataset':
            current_hash = self._get_dataset_hash(identifier)
        elif cache_type == 'organization':
            current_hash = self._get_organization_hash(identifier)
        elif cache_type == 'tag':
            current_hash = self._get_tag_hash(identifier)
        elif cache_type == 'full':
            current_hash = self._get_full_catalog_hash()
        else:
            return None
        
        if current_hash != cached_item['content_hash']:
            # Content has changed, invalidate cache
            del self.cache[cache_key]
            return None
        
        return cached_item['config']
    
    def cache_config(self, cache_type: str, identifier: str, config: Dict) -> None:
        """
        Cache a configuration.
        
        Args:
            cache_type: Type of cache (dataset, organization, tag, full)
            identifier: Identifier (dataset_id, org_name, tag_name, etc.)
            config: Configuration dict to cache
        """
        cache_key = self._get_cache_key(cache_type, identifier)
        
        # Get current content hash
        if cache_type == 'dataset':
            content_hash = self._get_dataset_hash(identifier)
        elif cache_type == 'organization':
            content_hash = self._get_organization_hash(identifier)
        elif cache_type == 'tag':
            content_hash = self._get_tag_hash(identifier)
        elif cache_type == 'full':
            content_hash = self._get_full_catalog_hash()
        else:
            return
        
        self.cache[cache_key] = {
            'config': config,
            'timestamp': time.time(),
            'content_hash': content_hash
        }
    
    def invalidate_cache(self, cache_type: str = None, identifier: str = None) -> None:
        """
        Invalidate cache entries.
        
        Args:
            cache_type: Type of cache to invalidate (None for all)
            identifier: Specific identifier to invalidate (None for all of type)
        """
        if cache_type and identifier:
            # Invalidate specific cache entry
            cache_key = self._get_cache_key(cache_type, identifier)
            self.cache.pop(cache_key, None)
        elif cache_type:
            # Invalidate all entries of specific type
            keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"terria_{cache_type}_")]
            for key in keys_to_remove:
                self.cache.pop(key, None)
        else:
            # Invalidate all cache
            self.cache.clear()
    
    def invalidate_by_resource_id(self, resource_id: str) -> None:
        """
        Invalidate cache entries related to a specific resource.
        This should be called when a resource or its views are updated.
        
        Args:
            resource_id: Resource ID that was updated
        """
        try:
            # Get the dataset that contains this resource
            resource = toolkit.get_action('resource_show')({}, {'id': resource_id})
            dataset_id = resource.get('package_id')
            
            if dataset_id:
                # Get dataset info to find organization
                dataset = toolkit.get_action('package_show')({}, {'id': dataset_id})
                
                # Invalidate dataset cache (all view variants)
                keys_to_remove = [k for k in self.cache.keys() if k.startswith(f"terria_dataset_{hashlib.md5(dataset_id.encode()).hexdigest()}")]
                for key in keys_to_remove:
                    self.cache.pop(key, None)
                
                # Also check for cache keys that include view index
                keys_to_remove = [k for k in self.cache.keys() if dataset_id in k]
                for key in keys_to_remove:
                    self.cache.pop(key, None)
                
                # Invalidate organization cache if organization exists
                org = dataset.get('organization')
                if org:
                    org_name = org.get('name')
                    if org_name:
                        self.invalidate_cache('organization', org_name)
                
                # Invalidate full catalog cache
                self.invalidate_cache('full', 'catalog')
                
                # Invalidate tag caches - we need to check all tags for this dataset
                tags = dataset.get('tags', [])
                for tag in tags:
                    tag_name = tag.get('name')
                    if tag_name:
                        self.invalidate_cache('tag', tag_name)
                        
        except Exception as e:
            # If we can't determine relationships, just invalidate everything to be safe
            self.cache.clear()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        current_time = time.time()
        valid_entries = 0
        expired_entries = 0
        
        for cache_key, cached_item in self.cache.items():
            if current_time - cached_item['timestamp'] > self.cache_timeout:
                expired_entries += 1
            else:
                valid_entries += 1
        
        return {
            'total_entries': len(self.cache),
            'valid_entries': valid_entries,
            'expired_entries': expired_entries,
            'cache_timeout': self.cache_timeout
        }