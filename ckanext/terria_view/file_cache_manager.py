# encoding: utf-8
"""
File-based cache manager for pre-generated Terria JSON files.
"""
import os
import json
import tempfile
import hashlib
import time
from typing import Dict, Optional, Any
import ckan.plugins.toolkit as toolkit
from ckan.common import config


class FileCacheManager:
    """Manages file-based cache for pre-generated Terria JSON files."""
    
    def __init__(self):
        """Initialize the file cache manager."""
        # Try different cache directory options with fallbacks
        cache_locations = [
            # First try CKAN's storage path
            config.get('ckan.storage_path'),
            # Then try common writable directories
            '/tmp',
            '/var/tmp', 
            # Finally use system temp directory
            tempfile.gettempdir()
        ]
        
        self.cache_subdir = None
        
        for cache_dir in cache_locations:
            if cache_dir:
                try:
                    cache_subdir = os.path.join(cache_dir, 'terria_json_cache')
                    # Test if we can create the directory
                    os.makedirs(cache_subdir, exist_ok=True)
                    # Test if we can write to it
                    test_file = os.path.join(cache_subdir, '.write_test')
                    with open(test_file, 'w') as f:
                        f.write('test')
                    os.remove(test_file)
                    
                    self.cache_subdir = cache_subdir
                    self._debug_print(f"File cache initialized at: {self.cache_subdir}")
                    break
                    
                except (OSError, PermissionError) as e:
                    self._debug_print(f"Cannot use cache directory {cache_dir}: {e}")
                    continue
        
        if self.cache_subdir is None:
            # If all fails, disable file caching
            self._debug_print("WARNING: File caching disabled due to permission issues")
            self.cache_subdir = None
        
        # Default cache timeout (1 hour)
        self.cache_timeout = 3600
    
    def _debug_print(self, message: str):
        """Print debug messages when TERRIA_DEBUG is enabled."""
        import os
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(f"FileCacheManager: {message}")
    
    def _get_cache_filename(self, cache_type: str, identifier: str) -> str:
        """
        Generate a cache filename.
        
        Args:
            cache_type: Type of cache (dataset, organization, tag, full)
            identifier: Identifier (dataset_id, org_name, tag_name, etc.)
            
        Returns:
            Cache filename
        """
        # Create a safe filename using hash
        safe_id = hashlib.md5(identifier.encode()).hexdigest()
        return f"terria_{cache_type}_{safe_id}.json"
    
    def _get_cache_path(self, cache_type: str, identifier: str) -> str:
        """
        Get full path to cache file.
        
        Args:
            cache_type: Type of cache
            identifier: Identifier
            
        Returns:
            Full path to cache file
        """
        filename = self._get_cache_filename(cache_type, identifier)
        return os.path.join(self.cache_subdir, filename)
    
    def _is_cache_valid(self, filepath: str) -> bool:
        """
        Check if cache file is still valid based on modification time.
        
        Args:
            filepath: Path to cache file
            
        Returns:
            True if cache is valid, False otherwise
        """
        try:
            if not os.path.exists(filepath):
                return False
            
            # Check if file is recent enough
            file_age = time.time() - os.path.getmtime(filepath)
            return file_age < self.cache_timeout
            
        except Exception as e:
            self._debug_print(f"Error checking cache validity: {e}")
            return False
    
    def get_cached_file(self, cache_type: str, identifier: str) -> Optional[str]:
        """
        Get path to cached file if valid.
        
        Args:
            cache_type: Type of cache (dataset, organization, tag, full)
            identifier: Identifier
            
        Returns:
            Path to cached file or None if not found/invalid
        """
        if self.cache_subdir is None:
            return None  # File caching disabled
            
        filepath = self._get_cache_path(cache_type, identifier)
        
        if self._is_cache_valid(filepath):
            self._debug_print(f"Cache hit for {cache_type}:{identifier}")
            return filepath
        
        # Clean up invalid cache file
        if os.path.exists(filepath):
            try:
                os.remove(filepath)
                self._debug_print(f"Removed expired cache file: {filepath}")
            except Exception as e:
                self._debug_print(f"Error removing cache file: {e}")
        
        return None
    
    def get_cached_json(self, cache_type: str, identifier: str) -> Optional[Dict]:
        """
        Get cached JSON data if valid.
        
        Args:
            cache_type: Type of cache
            identifier: Identifier
            
        Returns:
            Cached JSON data or None if not found/invalid
        """
        if self.cache_subdir is None:
            return None  # File caching disabled
            
        filepath = self.get_cached_file(cache_type, identifier)
        
        if filepath:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self._debug_print(f"Error reading cached JSON: {e}")
                # Remove corrupted cache file
                try:
                    os.remove(filepath)
                except:
                    pass
        
        return None
    
    def cache_json(self, cache_type: str, identifier: str, data: Dict) -> Optional[str]:
        """
        Cache JSON data to file.
        
        Args:
            cache_type: Type of cache
            identifier: Identifier
            data: JSON data to cache
            
        Returns:
            Path to cached file or None if caching failed/disabled
        """
        if self.cache_subdir is None:
            self._debug_print(f"File caching disabled, skipping cache for {cache_type}:{identifier}")
            return None  # File caching disabled
            
        filepath = self._get_cache_path(cache_type, identifier)
        
        try:
            # Write to temporary file first, then move to avoid corruption
            temp_path = filepath + '.tmp'
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Atomic move
            os.rename(temp_path, filepath)
            
            self._debug_print(f"Cached {cache_type}:{identifier} to {filepath}")
            return filepath
            
        except Exception as e:
            self._debug_print(f"Error caching JSON: {e}")
            # Clean up temp file if it exists
            temp_path = filepath + '.tmp'
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return None  # Return None instead of raising exception
    
    def invalidate_cache(self, cache_type: str = None, identifier: str = None) -> None:
        """
        Invalidate cache files.
        
        Args:
            cache_type: Type of cache to invalidate (None for all)
            identifier: Specific identifier to invalidate (None for all of type)
        """
        if self.cache_subdir is None:
            return  # File caching disabled
            
        if cache_type and identifier:
            # Invalidate specific cache file
            filepath = self._get_cache_path(cache_type, identifier)
            if os.path.exists(filepath):
                try:
                    os.remove(filepath)
                    self._debug_print(f"Invalidated {cache_type}:{identifier}")
                except Exception as e:
                    self._debug_print(f"Error invalidating cache: {e}")
        
        elif cache_type:
            # Invalidate all files of specific type
            pattern = f"terria_{cache_type}_"
            try:
                for filename in os.listdir(self.cache_subdir):
                    if filename.startswith(pattern):
                        filepath = os.path.join(self.cache_subdir, filename)
                        try:
                            os.remove(filepath)
                            self._debug_print(f"Invalidated cache file: {filename}")
                        except Exception as e:
                            self._debug_print(f"Error removing cache file: {e}")
            except Exception as e:
                self._debug_print(f"Error listing cache directory: {e}")
        
        else:
            # Invalidate all cache
            try:
                for filename in os.listdir(self.cache_subdir):
                    if filename.startswith('terria_') and filename.endswith('.json'):
                        filepath = os.path.join(self.cache_subdir, filename)
                        try:
                            os.remove(filepath)
                            self._debug_print(f"Invalidated cache file: {filename}")
                        except Exception as e:
                            self._debug_print(f"Error removing cache file: {e}")
            except Exception as e:
                self._debug_print(f"Error listing cache directory: {e}")
    
    def invalidate_by_resource_id(self, resource_id: str) -> None:
        """
        Invalidate cache files related to a specific resource.
        
        Args:
            resource_id: Resource ID that was updated
        """
        try:
            # Get the dataset that contains this resource
            resource = toolkit.get_action('resource_show')({}, {'id': resource_id})
            dataset_id = resource.get('package_id')
            
            if dataset_id:
                dataset = toolkit.get_action('package_show')({}, {'id': dataset_id})
                
                # Invalidate dataset cache (all view variants)
                self.invalidate_cache('dataset', dataset_id)
                
                # Also invalidate with view indices
                for i in range(10):  # Assume max 10 views per resource
                    cache_key = f"{dataset_id}_{i}"
                    self.invalidate_cache('dataset', cache_key)
                
                cache_key = f"{dataset_id}_all"
                self.invalidate_cache('dataset', cache_key)
                
                # Invalidate organization cache
                org = dataset.get('organization')
                if org:
                    org_name = org.get('name')
                    if org_name:
                        self.invalidate_cache('organization', org_name)
                
                # Invalidate full catalog cache
                self.invalidate_cache('full', 'catalog')
                
                # Invalidate tag caches
                tags = dataset.get('tags', [])
                for tag in tags:
                    tag_name = tag.get('name')
                    if tag_name:
                        self.invalidate_cache('tag', tag_name)
                        
                self._debug_print(f"Invalidated all caches related to resource {resource_id}")
                        
        except Exception as e:
            # If we can't determine relationships, just invalidate everything
            self._debug_print(f"Error in targeted invalidation, clearing all cache: {e}")
            self.invalidate_cache()
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get file cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        if self.cache_subdir is None:
            return {
                'file_caching_enabled': False,
                'message': 'File caching disabled due to permission issues',
                'cache_directory': None
            }
            
        try:
            files = [f for f in os.listdir(self.cache_subdir) 
                    if f.startswith('terria_') and f.endswith('.json')]
            
            total_files = len(files)
            total_size = 0
            valid_files = 0
            expired_files = 0
            
            current_time = time.time()
            
            for filename in files:
                filepath = os.path.join(self.cache_subdir, filename)
                try:
                    stat = os.stat(filepath)
                    total_size += stat.st_size
                    
                    file_age = current_time - stat.st_mtime
                    if file_age < self.cache_timeout:
                        valid_files += 1
                    else:
                        expired_files += 1
                        
                except Exception as e:
                    self._debug_print(f"Error getting stats for {filename}: {e}")
            
            return {
                'file_caching_enabled': True,
                'cache_directory': self.cache_subdir,
                'total_files': total_files,
                'valid_files': valid_files,
                'expired_files': expired_files,
                'total_size_bytes': total_size,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'cache_timeout': self.cache_timeout
            }
            
        except Exception as e:
            self._debug_print(f"Error getting cache stats: {e}")
            return {
                'file_caching_enabled': True,
                'error': str(e),
                'cache_directory': self.cache_subdir
            }
    
    def cleanup_expired_files(self) -> int:
        """
        Clean up expired cache files.
        
        Returns:
            Number of files cleaned up
        """
        if self.cache_subdir is None:
            return 0  # File caching disabled
            
        cleaned_files = 0
        
        try:
            files = [f for f in os.listdir(self.cache_subdir) 
                    if f.startswith('terria_') and f.endswith('.json')]
            
            for filename in files:
                filepath = os.path.join(self.cache_subdir, filename)
                
                if not self._is_cache_valid(filepath):
                    try:
                        os.remove(filepath)
                        cleaned_files += 1
                        self._debug_print(f"Cleaned up expired file: {filename}")
                    except Exception as e:
                        self._debug_print(f"Error cleaning up {filename}: {e}")
            
            self._debug_print(f"Cleaned up {cleaned_files} expired files")
            
        except Exception as e:
            self._debug_print(f"Error during cleanup: {e}")
        
        return cleaned_files