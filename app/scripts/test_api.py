#!/usr/bin/env python3
"""
Simple API test - uses the correct endpoints
"""
import requests

def test_simple():
    """Test the actual API endpoints"""
    base = "http://localhost:8000"
    
    endpoints = [
        "/api/debug/status",
        "/catalogs", 
        "/categories",
        "/part_types",
        "/search?q=test&limit=5"
    ]
    
    print("Testing API Endpoints:\n")
    
    for endpoint in endpoints:
        try:
            url = base + endpoint
            print(f"Testing: {url}")
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if "catalogs" in data:
                    print(f"✅ {endpoint}: {len(data['catalogs'])} catalogs")
                elif "categories" in data:
                    print(f"✅ {endpoint}: {len(data['categories'])} categories") 
                elif "results" in data:
                    print(f"✅ {endpoint}: {len(data['results'])} results")
                elif "status" in data:
                    print(f"✅ {endpoint}: {data['status']} - {data['parts_count']} parts")
                else:
                    print(f"✅ {endpoint}: Success")
            else:
                print(f"❌ {endpoint}: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"❌ {endpoint}: {e}")
        
        print()

if __name__ == "__main__":
    test_simple()