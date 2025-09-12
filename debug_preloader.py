#!/usr/bin/env python
"""
Debug script to test preloader functionality locally.
"""
import sys
import os
sys.path.append('ckanext/terria_view')

try:
    from terria_json_generator import TerriaJSONGenerator
    from cache_preloader import CachePreloader
    
    print("Testing cache preloader locally...")
    
    # Create generator
    generator = TerriaJSONGenerator()
    print(f"Generator created. Cache manager: {type(generator.cache_manager)}")
    print(f"Memory cache entries: {generator.cache_manager.get_cache_stats()['total_entries']}")
    
    # Test cache functionality
    print("\nTesting cache storage...")
    test_data = {"test": "data", "timestamp": "2025-01-01"}
    generator.cache_manager.cache_json("test", "test_key", test_data)
    
    cached = generator.cache_manager.get_cached_json("test", "test_key")
    if cached:
        print("✅ Cache storage/retrieval working")
    else:
        print("❌ Cache storage/retrieval failed")
    
    print(f"Memory cache entries after test: {generator.cache_manager.get_cache_stats()['total_entries']}")
    
    # Test preloader
    print("\nTesting preloader initialization...")
    preloader = CachePreloader(generator)
    print(f"Preload enabled: {preloader.preload_enabled}")
    print(f"Startup delay: {preloader.startup_delay}")
    
    if preloader.preload_enabled:
        print("✅ Preloader configuration looks good")
    else:
        print("⚠️ Preloader is disabled")
        
except ImportError as e:
    print(f"Import error: {e}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()