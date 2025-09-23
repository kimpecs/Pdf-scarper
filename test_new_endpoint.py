# test_new_endpoint.py
import requests
import json

def test_new_endpoint():
    BASE_URL = "http://localhost:8000"
    
    print("=== Testing New Endpoint ===\n")
    
    try:
        # Test the new endpoint
        response = requests.get(f"{BASE_URL}/test")
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Test endpoint is working!")
            print(f"Server Status: {data.get('server_status', 'unknown')}")
            print(f"Database Connection: {data.get('database_connection', 'unknown')}")
            print(f"Tables Exist: {data.get('tables_exist', 'unknown')}")
            print(f"Total Parts in DB: {data.get('parts_count', 0)}")
            print(f"Categories Count: {data.get('categories_count', 0)}")
            
            print("\n📋 Sample Parts:")
            for part in data.get('sample_parts', []):
                print(f"  - {part['type']}: {part['number']} (Page {part['page']}, {part['category']})")
            
            print("\n🔗 API Endpoints Status:")
            for endpoint, status in data.get('api_endpoints', {}).items():
                print(f"  - {endpoint}: {status}")
                
        else:
            print(f"❌ Test endpoint failed with status {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure it's running:")
        print("   python app_toc.py")
    except Exception as e:
        print(f"❌ Error: {e}")

def test_all_endpoints():
    BASE_URL = "http://localhost:8000"
    endpoints = [
        "/health",
        "/categories", 
        "/part_types",
        "/search?q=CH5004",
        "/part/1",
        "/test"
    ]
    
    print("\n=== Testing All Endpoints ===\n")
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{BASE_URL}{endpoint}", timeout=5)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {endpoint} - Status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"   Response: {response.text[:100]}...")
                
        except Exception as e:
            print(f"❌ {endpoint} - Error: {e}")

if __name__ == "__main__":
    test_new_endpoint()
    test_all_endpoints()