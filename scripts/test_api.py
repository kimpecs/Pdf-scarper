#!/usr/bin/env python3
"""
Test API endpoints
"""
import requests
import time

def test_api():
    """Test API endpoints"""
    print("Testing API endpoints...")
    
    base_url = "http://localhost:8000"
    endpoints = [
        "/api/parts/search?q=engine",
        "/api/parts/categories", 
        "/api/parts/catalogs",
        "/api/guides/search"
    ]
    
    all_success = True
    
    for endpoint in endpoints:
        try:
            url = base_url + endpoint
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] {endpoint}: Success ({len(data) if isinstance(data, list) else data.get('count', 'N/A')} items)")
            else:
                print(f"[FAIL] {endpoint}: HTTP {response.status_code} - {response.text}")
                all_success = False
                
        except requests.exceptions.ConnectionError:
            print(f"[FAIL] {endpoint}: Cannot connect to server")
            print("Make sure the server is running with: python run_server.py")
            all_success = False
        except Exception as e:
            print(f"[FAIL] {endpoint}: {e}")
            all_success = False
        
        time.sleep(0.2)  # Small delay between requests
    
    return all_success

if __name__ == "__main__":
    try:
        success = test_api()
        exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] API test failed: {e}")
        exit(1)