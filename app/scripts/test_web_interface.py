#!/usr/bin/env python3
"""
Test web interface functionality
"""
import requests
import time
from pathlib import Path

def test_main_page():
    """Test if main page loads"""
    try:
        response = requests.get("http://localhost:8000", timeout=10)
        if response.status_code == 200:
            print("[OK] Main page: Loaded successfully")
            return True
        else:
            print(f"[FAIL] Main page: Failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Main page: {e}")
        return False

def test_search_page():
    """Test if search page loads"""
    try:
        response = requests.get("http://localhost:8000/search", timeout=10)
        if response.status_code == 200:
            print("[OK] Search page: Loaded successfully")
            return True
        else:
            print(f"[FAIL] Search page: Failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Search page: {e}")
        return False

def test_static_files():
    """Test if static files are accessible"""
    try:
        response = requests.get("http://localhost:8000/static/css/style.css", timeout=10)
        if response.status_code == 200:
            print("[OK] Static files: CSS loaded successfully")
            return True
        else:
            print(f"[FAIL] Static files: CSS failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Static files: {e}")
        return False

def test_search_functionality():
    """Test search functionality"""
    try:
        # Test basic search
        response = requests.get("http://localhost:8000/api/parts/search?q=engine", timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"[OK] Search functionality: Found {data.get('count', 0)} results")
            return True
        else:
            print(f"[FAIL] Search functionality: Failed with status {response.status_code}")
            return False
    except Exception as e:
        print(f"[FAIL] Search functionality: {e}")
        return False

def test():
    """Run all web interface tests"""
    print("[WEB] Testing Web Interface...")
    print("=" * 40)
    
    tests = [
        test_main_page,
        test_search_page, 
        test_static_files,
        test_search_functionality
    ]
    
    results = []
    for test_func in tests:
        result = test_func()
        results.append(result)
        time.sleep(0.5)  # Small delay between tests
    
    passed = sum(results)
    total = len(results)
    
    print("=" * 40)
    print(f"Web Interface Tests: {passed}/{total} passed")
    
    return passed == total

def main():
    """Main test runner"""
    try:
        success = test()
        exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] Web interface test failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()