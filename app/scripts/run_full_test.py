#!/usr/bin/env python3
"""
Run complete system test sequence
"""
import os
import subprocess
import sys
from pathlib import Path
from fastapi import File, UploadFile

def run_script(script_name):
    """Run a test script and return success status"""
    print(f"\n{'='*60}")
    print(f"Running: {script_name}")
    print('='*60)
    
    try:
        result = subprocess.run([sys.executable, script_name], 
                              capture_output=True, text=True, timeout=120)
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print(f"[ERROR] {script_name} timed out")
        return False
    except Exception as e:
        print(f"[ERROR] {script_name} failed: {e}")
        return False

def main():
    """Run all tests in sequence"""
    scripts_dir = Path(__file__).parent
    test_scripts = [
        scripts_dir / "check_completion.py",
        scripts_dir / "test_api.py", 
        scripts_dir / "test_web_interface.py",
        scripts_dir / "test_performance.py",
    ]
    
    print("🔬 Starting Complete System Test Suite")
    print("Make sure the server is running: python run_server.py")
    input("Press Enter to continue...")
    
    results = []
    for script in test_scripts:
        if script.exists():
            success = run_script(str(script))
            results.append(success)
        else:
            print(f"[ERROR] Script not found: {script}")
            results.append(False)
    
    print("\n" + "="*60)
    print("🎯 FINAL TEST RESULTS")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    for i, (script, success) in enumerate(zip(test_scripts, results)):
        status = "[OK] PASS" if success else "[ERROR] FAIL"
        print(f"{i+1}. {script.name}: {status}")
    
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 ALL TESTS PASSED! System is ready for production.")
        print("\nNext steps:")
        print("1. Add more PDF catalogs to app/data/pdfs/")
        print("2. Add technical guides to app/data/guides/")
        print("3. Customize the web interface in app/static/")
        print("4. Set up production deployment")
    else:
        print(" [WARNING]  Some tests failed. Review the output above.")
    
    sys.exit(0 if passed == total else 1)

if __name__ == "__main__":
    main()