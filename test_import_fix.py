#!/usr/bin/env python
"""
Test script to verify import compatibility fixes.
"""
import sys

def test_urllib3_compatibility():
    """Test urllib3 Retry import compatibility."""
    try:
        from urllib3.util.retry import Retry
        print("✓ urllib3.util.retry.Retry import successful")
        
        # Test newer parameter
        try:
            retry = Retry(
                total=2,
                backoff_factor=1,
                status_forcelist=[500, 502, 503, 504],
                allowed_methods=["GET", "POST"]
            )
            print("✓ Retry with allowed_methods parameter works")
            return True
        except TypeError as e:
            print(f"✗ Retry with allowed_methods failed: {e}")
            
            # Test older parameter
            try:
                retry = Retry(
                    total=2,
                    backoff_factor=1,
                    status_forcelist=[500, 502, 503, 504],
                    method_whitelist=["GET", "POST"]
                )
                print("✓ Retry with method_whitelist parameter works (fallback)")
                return True
            except Exception as e2:
                print(f"✗ Retry with method_whitelist also failed: {e2}")
                return False
                
    except ImportError as e:
        print(f"✗ urllib3 import failed: {e}")
        return False

def test_api_import():
    """Test API endpoints import."""
    try:
        # Set up minimal CKAN environment simulation
        import os
        os.environ.setdefault('CKAN_INI', '/dev/null')
        
        from ckanext.terria_view.api_endpoints import terria_api
        print("✓ API endpoints import successful")
        return True
    except Exception as e:
        print(f"✗ API endpoints import failed: {e}")
        return False

def test_generator_import():
    """Test JSON generator import.""" 
    try:
        from ckanext.terria_view.terria_json_generator import TerriaJSONGenerator
        print("✓ TerriaJSONGenerator import successful")
        
        # Test initialization
        generator = TerriaJSONGenerator()
        print("✓ TerriaJSONGenerator initialization successful")
        return True
    except Exception as e:
        print(f"✗ TerriaJSONGenerator import/init failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Testing import compatibility fixes...")
    print("=" * 50)
    
    tests = [
        ("urllib3 compatibility", test_urllib3_compatibility),
        ("API endpoints import", test_api_import),
        ("JSON generator import", test_generator_import),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\nTesting {test_name}:")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"✗ Test {test_name} crashed: {e}")
            results.append(False)
    
    print("\n" + "=" * 50)
    print("Test Summary:")
    
    for i, (test_name, _) in enumerate(tests):
        status = "✓ PASS" if results[i] else "✗ FAIL"
        print(f"  {test_name}: {status}")
    
    all_passed = all(results)
    print(f"\nOverall: {'✓ ALL TESTS PASSED' if all_passed else '✗ SOME TESTS FAILED'}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())