# encoding: utf-8
"""
Cache preloader to warm up cache on startup.
"""
import threading
import time
import os
import ckan.plugins.toolkit as toolkit
from ckan.common import config


class CachePreloader:
    """Preloads cache on application startup."""
    
    def __init__(self, generator):
        """
        Initialize cache preloader.
        
        Args:
            generator: TerriaJSONGenerator instance
        """
        self.generator = generator
        self.preload_enabled = self._is_preload_enabled()
        self.startup_delay = self._get_startup_delay()
        self.preload_started = False
    
    def _is_preload_enabled(self) -> bool:
        """Check if cache preloading is enabled."""
        # Check environment variable first
        env_enabled = os.getenv("TERRIA_PRELOAD_CACHE", "").lower()
        if env_enabled in ("true", "1", "yes", "on"):
            return True
        elif env_enabled in ("false", "0", "no", "off"):
            return False
        
        # Check CKAN config
        return toolkit.asbool(config.get('ckanext.terria_view.preload_cache', True))
    
    def _get_startup_delay(self) -> int:
        """Get startup delay in seconds."""
        # Check environment variable first
        env_delay = os.getenv("TERRIA_PRELOAD_DELAY", "")
        if env_delay.isdigit():
            return int(env_delay)
        
        # Check CKAN config
        return int(config.get('ckanext.terria_view.preload_delay', 10))
    
    def _debug_print(self, message: str):
        """Print debug messages when TERRIA_DEBUG is enabled."""
        if os.getenv("TERRIA_DEBUG", "false").lower() == "true":
            print(f"CachePreloader: {message}")
    
    def start_preload(self):
        """Start cache preloading in background thread."""
        if not self.preload_enabled:
            self._debug_print("Cache preloading disabled")
            return
        
        if self.preload_started:
            self._debug_print("Cache preloading already started")
            return
        
        self.preload_started = True
        self._debug_print(f"Starting cache preloading in {self.startup_delay} seconds")
        
        # Start preloading in background thread
        thread = threading.Thread(target=self._preload_worker, daemon=True)
        thread.start()
    
    def _preload_worker(self):
        """Background worker to preload cache."""
        try:
            # Wait for startup delay
            time.sleep(self.startup_delay)
            
            self._debug_print("Starting cache preloading...")
            start_time = time.time()
            
            # Preload in order of importance and size
            preload_tasks = [
                ("modular_catalog", self._preload_modular_catalog),
                ("organizations", self._preload_organizations),
                ("popular_datasets", self._preload_popular_datasets),
                ("tags", self._preload_tags),
                ("full_catalog", self._preload_full_catalog)  # This one last as it's largest
            ]
            
            completed_tasks = 0
            for task_name, task_func in preload_tasks:
                try:
                    self._debug_print(f"Preloading {task_name}...")
                    task_func()
                    completed_tasks += 1
                    self._debug_print(f"Completed {task_name} ({completed_tasks}/{len(preload_tasks)})")
                except Exception as e:
                    self._debug_print(f"Error preloading {task_name}: {e}")
                    # Continue with other tasks even if one fails
            
            elapsed_time = time.time() - start_time
            self._debug_print(f"Cache preloading completed in {elapsed_time:.2f} seconds ({completed_tasks}/{len(preload_tasks)} tasks)")
            
        except Exception as e:
            self._debug_print(f"Error in preload worker: {e}")
    
    def _preload_modular_catalog(self):
        """Preload modular catalog (lightweight)."""
        try:
            config = self.generator.generate_modular_catalog()
            self._debug_print(f"Preloaded modular catalog with {len(config.get('catalog', []))} entries")
        except Exception as e:
            self._debug_print(f"Failed to preload modular catalog: {e}")
    
    def _preload_organizations(self):
        """Preload organization catalogs."""
        try:
            # Get list of organizations with datasets
            orgs = toolkit.get_action('organization_list')({}, {
                'all_fields': True,
                'include_dataset_count': True
            })
            
            preloaded_count = 0
            for org in orgs[:5]:  # Limit to top 5 organizations
                if org.get('package_count', 0) > 0:
                    try:
                        org_name = org.get('name')
                        config = self.generator.generate_organization_json(org_name)
                        preloaded_count += 1
                        self._debug_print(f"Preloaded organization: {org_name}")
                    except Exception as e:
                        self._debug_print(f"Failed to preload org {org.get('name', 'unknown')}: {e}")
            
            self._debug_print(f"Preloaded {preloaded_count} organization catalogs")
            
        except Exception as e:
            self._debug_print(f"Failed to preload organizations: {e}")
    
    def _preload_popular_datasets(self):
        """Preload popular/recent datasets."""
        try:
            # Get recently modified datasets
            recent_datasets = toolkit.get_action('package_search')({}, {
                'q': 'state:active AND private:false',
                'sort': 'metadata_modified desc',
                'rows': 10,  # Top 10 recent datasets
                'fq': '+dataset_type:dataset'
            })
            
            preloaded_count = 0
            for dataset in recent_datasets.get('results', []):
                try:
                    dataset_id = dataset.get('id')
                    config = self.generator.generate_dataset_json(dataset_id)
                    preloaded_count += 1
                    self._debug_print(f"Preloaded dataset: {dataset.get('name', dataset_id)}")
                except Exception as e:
                    self._debug_print(f"Failed to preload dataset {dataset.get('name', 'unknown')}: {e}")
            
            self._debug_print(f"Preloaded {preloaded_count} popular datasets")
            
        except Exception as e:
            self._debug_print(f"Failed to preload popular datasets: {e}")
    
    def _preload_tags(self):
        """Preload tag catalogs for popular tags."""
        try:
            # Get popular tags
            tags = toolkit.get_action('tag_list')({}, {
                'vocabulary_id': None,
                'all_fields': True
            })
            
            # Sort by usage and take top 5
            popular_tags = sorted(tags, key=lambda x: x.get('packages', 0), reverse=True)[:5]
            
            preloaded_count = 0
            for tag in popular_tags:
                try:
                    tag_name = tag.get('name')
                    if tag.get('packages', 0) > 0:  # Only preload tags with packages
                        config = self.generator.generate_tag_json(tag_name)
                        preloaded_count += 1
                        self._debug_print(f"Preloaded tag: {tag_name}")
                except Exception as e:
                    self._debug_print(f"Failed to preload tag {tag.get('name', 'unknown')}: {e}")
            
            self._debug_print(f"Preloaded {preloaded_count} tag catalogs")
            
        except Exception as e:
            self._debug_print(f"Failed to preload tags: {e}")
    
    def _preload_full_catalog(self):
        """Preload full catalog (this is the largest and slowest)."""
        try:
            self._debug_print("Starting full catalog preload (this may take a while)...")
            config = self.generator.generate_full_catalog_json()
            
            # Also generate and cache the file version
            file_path = self.generator.get_or_generate_file(
                'full', 'catalog',
                self.generator.generate_full_catalog_json
            )
            
            catalog_size = len(config.get('catalog', []))
            file_status = "with file cache" if file_path else "memory only"
            self._debug_print(f"Preloaded full catalog with {catalog_size} entries ({file_status})")
            
        except Exception as e:
            self._debug_print(f"Failed to preload full catalog: {e}")