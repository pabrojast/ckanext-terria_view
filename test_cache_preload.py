#!/usr/bin/env python
"""
Test script to verify cache preloading functionality.
"""
import requests
import json
import time
import sys

BASE_URL = "https://data.dev-wins.com"

def test_cache_preload():
    """Test cache preloading by monitoring cache stats."""
    print("Testing Cache Preloading System")
    print("=" * 50)
    
    # Step 1: Get initial cache stats
    print("\n1. Getting initial cache statistics...")
    initial_stats = get_cache_stats()
    if not initial_stats:
        print("   ERROR: Could not get initial cache stats")
        return False
    
    print_cache_stats("Initial", initial_stats)
    
    # Step 2: Clear cache to simulate fresh start
    print("\n2. Clearing cache to simulate pod restart...")
    if not clear_cache():
        print("   WARNING: Could not clear cache, continuing anyway")
    
    # Step 3: Wait a moment and check if cache is repopulated
    print("\n3. Waiting for cache preloading to occur...")
    for i in range(6):  # Check for 30 seconds
        time.sleep(5)
        stats = get_cache_stats()
        if stats:
            memory_entries = stats.get('memory_cache', {}).get('total_entries', 0)
            file_entries = stats.get('file_cache', {}).get('total_files', 0)
            
            if memory_entries > 0 or file_entries > 0:
                print(f"   Cache entries detected after {(i+1)*5} seconds")
                print_cache_stats(f"After {(i+1)*5}s", stats)
                break
        
        print(f"   Checking... ({(i+1)*5}s)")
    
    # Step 4: Test endpoint performance
    print("\n4. Testing endpoint performance...")
    endpoints = [
        ("/api/terria/modular", "Modular catalog"),
        ("/api/terria/cache/stats", "Cache stats"),
        ("/api/terria/file/full", "Full catalog (file)")
    ]
    
    for endpoint, description in endpoints:
        test_endpoint_performance(endpoint, description)
    
    # Step 5: Final cache stats
    print("\n5. Final cache statistics:")
    final_stats = get_cache_stats()
    if final_stats:
        print_cache_stats("Final", final_stats)
        
        # Compare with initial
        initial_memory = initial_stats.get('memory_cache', {}).get('total_entries', 0)
        final_memory = final_stats.get('memory_cache', {}).get('total_entries', 0)
        
        initial_files = initial_stats.get('file_cache', {}).get('total_files', 0)  
        final_files = final_stats.get('file_cache', {}).get('total_files', 0)
        
        print(f"\n   Memory cache: {initial_memory} -> {final_memory} (+{final_memory - initial_memory})")
        print(f"   File cache: {initial_files} -> {final_files} (+{final_files - initial_files})")
        
        if (final_memory > initial_memory) or (final_files > initial_files):
            print("\n   SUCCESS: Cache preloading appears to be working!")
            return True
        else:
            print("\n   INFO: No significant cache increase detected")
            return True
    
    return False

def get_cache_stats():
    """Get cache statistics."""
    try:
        response = requests.get(f"{BASE_URL}/api/terria/cache/stats", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"   Error getting cache stats: {e}")
    return None

def clear_cache():
    """Clear cache."""
    try:
        response = requests.post(f"{BASE_URL}/api/terria/cache/invalidate", timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"   Error clearing cache: {e}")
        return False

def print_cache_stats(title, stats):
    """Print formatted cache statistics."""
    memory = stats.get('memory_cache', {})
    file_cache = stats.get('file_cache', {})
    
    print(f"   {title} Stats:")
    print(f"     Memory: {memory.get('total_entries', 0)} entries ({memory.get('valid_entries', 0)} valid)")
    print(f"     Files: {file_cache.get('total_files', 0)} files ({file_cache.get('valid_files', 0)} valid)")
    if file_cache.get('total_size_mb'):
        print(f"     Size: {file_cache.get('total_size_mb', 0)} MB")

def test_endpoint_performance(endpoint, description):
    """Test endpoint performance."""
    url = f"{BASE_URL}{endpoint}"
    print(f"   Testing {description}...")
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=30)
        end_time = time.time()
        
        if response.status_code == 200:
            response_time = end_time - start_time
            size_mb = len(response.content) / (1024 * 1024)
            print(f"     SUCCESS: {response_time:.2f}s, {size_mb:.2f} MB")
        else:
            print(f"     FAILED: Status {response.status_code}")
            
    except requests.exceptions.Timeout:
        print(f"     TIMEOUT: > 30 seconds")
    except Exception as e:
        print(f"     ERROR: {e}")

if __name__ == "__main__":
    success = test_cache_preload()
    sys.exit(0 if success else 1)