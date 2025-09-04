#!/usr/bin/env python
"""
Quick test script to verify the permission and compatibility fixes work correctly.
"""
import requests
import json
import time

BASE_URL = "https://data.dev-wins.com"

def test_endpoint(endpoint, description):
    """Test a single endpoint and return result."""
    url = f"{BASE_URL}{endpoint}"
    print(f"\n🧪 Testing {description}")
    print(f"   URL: {url}")
    
    try:
        start_time = time.time()
        response = requests.get(url, timeout=30)
        end_time = time.time()
        
        print(f"   Status: {response.status_code}")
        print(f"   Time: {end_time - start_time:.2f}s")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if 'error' in data:
                    print(f"   ⚠️  API returned error: {data.get('message', 'Unknown error')}")
                    return False
                else:
                    print(f"   ✅ Success - Response size: {len(response.content)} bytes")
                    return True
            except json.JSONDecodeError:
                print(f"   ✅ Success - Non-JSON response size: {len(response.content)} bytes")
                return True
        else:
            print(f"   ❌ Failed with status {response.status_code}")
            try:
                error_data = response.json()
                if 'message' in error_data:
                    print(f"   Error: {error_data['message']}")
            except:
                print(f"   Raw error: {response.text[:200]}...")
            return False
            
    except requests.exceptions.Timeout:
        print(f"   ⏰ Timeout after 30 seconds")
        return False
    except Exception as e:
        print(f"   💥 Exception: {e}")
        return False

def main():
    """Run basic endpoint tests."""
    print("🔧 Testing Terria API Endpoints After Fixes")
    print("=" * 60)
    
    tests = [
        ("/api/terria/cache/stats", "Cache statistics"),
        ("/api/terria/cache/cleanup", "Cache cleanup (POST as GET for testing)"),
        ("/api/terria/modular", "Modular catalog"),
        ("/api/terria/full", "Full catalog (JSON)"),
        ("/api/terria/file/full", "Full catalog (file)")
    ]
    
    results = []
    for endpoint, description in tests:
        result = test_endpoint(endpoint, description)
        results.append((description, result))
    
    print("\n" + "=" * 60)
    print("📊 Test Results Summary:")
    
    passed = 0
    for description, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"   {description}: {status}")
        if result:
            passed += 1
    
    print(f"\n🏆 Overall: {passed}/{len(results)} tests passed")
    
    if passed == len(results):
        print("🎉 All tests passed! The fixes appear to be working.")
    elif passed > 0:
        print("⚠️  Some tests passed. The system is partially working.")
    else:
        print("❌ All tests failed. Please check the logs for more details.")

if __name__ == "__main__":
    main()