#!/usr/bin/env python3
"""
Performance testing for the parts catalog system
"""
import requests
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed

def test_single_request(query="engine", endpoint="/api/parts/search"):
    """Test performance of a single request"""
    start_time = time.time()
    try:
        response = requests.get(f"http://localhost:8000{endpoint}?q={query}", timeout=30)
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        
        if response.status_code == 200:
            data = response.json()
            return {
                "success": True,
                "response_time": response_time,
                "results": data.get("count", 0),
                "query": query
            }
        else:
            return {
                "success": False,
                "response_time": response_time,
                "error": f"HTTP {response.status_code}",
                "query": query
            }
            
    except Exception as e:
        end_time = time.time()
        return {
            "success": False,
            "response_time": (end_time - start_time) * 1000,
            "error": str(e),
            "query": query
        }

def test_concurrent_requests(queries, max_workers=5):
    """Test performance under concurrent load"""
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(test_single_request, query) for query in queries]
        
        results = []
        for future in as_completed(futures):
            results.append(future.result())
        
        return results

def run_performance_test():
    """Run comprehensive performance tests"""
    print("[PERF] Running Performance Tests...")
    print("=" * 50)
    
    # Test queries
    test_queries = [
        "engine",
        "brake", 
        "sensor",
        "hydraulic",
        "electrical",
        "caterpillar",
        "detroit",
        "cummins"
    ]
    
    # Single request performance
    print("Single request performance:")
    print("-" * 30)
    
    single_results = []
    for query in test_queries:
        result = test_single_request(query)
        single_results.append(result)
        
        status = "[OK]" if result["success"] else "[FAIL]"
        if result["success"]:
            print(f"   {status} '{query}': {result['response_time']:.1f}ms, {result.get('results', 0)} results")
        else:
            print(f"   {status} '{query}': {result['response_time']:.1f}ms, Error: {result.get('error', 'Unknown')}")
    
    # Calculate statistics for successful requests
    successful_times = [r["response_time"] for r in single_results if r["success"]]
    if successful_times:
        avg_time = statistics.mean(successful_times)
        max_time = max(successful_times)
        min_time = min(successful_times)
        
        print(f"\nPerformance Summary:")
        print(f"  Average response time: {avg_time:.1f}ms")
        print(f"  Minimum response time: {min_time:.1f}ms") 
        print(f"  Maximum response time: {max_time:.1f}ms")
        print(f"  Successful requests: {len(successful_times)}/{len(single_results)}")
    else:
        print("\n[FAIL] No successful requests to analyze")
        return False
    
    # Concurrent load test
    print(f"\nConcurrent load test (5 simultaneous requests):")
    print("-" * 50)
    
    concurrent_queries = ["engine", "brake", "sensor", "hydraulic", "electrical"]
    concurrent_results = test_concurrent_requests(concurrent_queries, max_workers=5)
    
    concurrent_times = [r["response_time"] for r in concurrent_results if r["success"]]
    if concurrent_times:
        avg_concurrent = statistics.mean(concurrent_times)
        max_concurrent = max(concurrent_times)
        
        print(f"  Average concurrent response: {avg_concurrent:.1f}ms")
        print(f"  Maximum concurrent response: {max_concurrent:.1f}ms")
        print(f"  Concurrent success rate: {len(concurrent_times)}/{len(concurrent_results)}")
        
        # Performance thresholds
        print(f"\nPerformance Thresholds:")
        if avg_time < 100:
            print("  [OK] Single request performance: Excellent (< 100ms)")
        elif avg_time < 500:
            print("  [OK] Single request performance: Good (< 500ms)")
        else:
            print("  [WARN] Single request performance: Slow (> 500ms)")
            
        if avg_concurrent < 1000:
            print("  [OK] Concurrent performance: Good (< 1000ms)")
        else:
            print("  [WARN] Concurrent performance: Slow (> 1000ms)")
            
        return len(concurrent_times) > 0
    else:
        print("  [FAIL] No successful concurrent requests")
        return False

def main():
    """Main performance test runner"""
    try:
        success = run_performance_test()
        if success:
            print("\n[SUCCESS] Performance tests completed")
        else:
            print("\n[FAIL] Performance tests failed")
        exit(0 if success else 1)
    except Exception as e:
        print(f"[ERROR] Performance test failed: {e}")
        exit(1)

if __name__ == "__main__":
    main()