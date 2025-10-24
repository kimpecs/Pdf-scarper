# test_api.py
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_api():
    # First, test if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ Server is running")
        else:
            print("✗ Server responded with error")
            return
    except requests.exceptions.ConnectionError:
        print("✗ Server is not running. Please start it with: python app_toc.py")
        return
    except Exception as e:
        print(f"✗ Error connecting to server: {e}")
        return

    # Test categories endpoint
    try:
        response = requests.get(f"{BASE_URL}/categories")
        if response.status_code == 200:
            data = response.json()
            print("✓ Categories endpoint working")
            print(f"  Found {len(data.get('categories', []))} categories")
        else:
            print("✗ Categories endpoint failed")
    except Exception as e:
        print(f"✗ Categories test failed: {e}")

    # Test search endpoint
    try:
        response = requests.get(f"{BASE_URL}/search?q=600-216")
        if response.status_code == 200:
            results = response.json()
            print(f"✓ Search endpoint working - found {results['count']} results for '600-216'")
            if results['count'] > 0:
                first_result = results['results'][0]
                print(f"  First result: {first_result['part_number']} on page {first_result['page']}")
        else:
            print("✗ Search endpoint failed")
    except Exception as e:
        print(f"✗ Search test failed: {e}")

    # Test part details endpoint
    try:
        response = requests.get(f"{BASE_URL}/part/1")
        if response.status_code == 200:
            part_data = response.json()
            print(f"✓ Part details endpoint working - Part {part_data['part_number']}")
        else:
            print("✗ Part details endpoint failed")
    except Exception as e:
        print(f"✗ Part details test failed: {e}")

if __name__ == "__main__":
    print("Testing API endpoints...")
    test_api()