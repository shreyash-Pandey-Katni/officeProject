#!/usr/bin/env python3
"""
Final comprehensive test combining all scenarios
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
from activity_executor import ActivityExecutor

def run_all_tests():
    """Run all visibility detection tests"""
    
    print("=" * 80)
    print("FINAL COMPREHENSIVE VISIBILITY DETECTION TEST SUITE")
    print("=" * 80)
    
    import test_comprehensive_hidden
    import test_parent_chain
    
    results = {
        'Basic Hidden Elements': False,
        'Parent Chain Hiding': False
    }
    
    print("\n" + "=" * 80)
    print("RUNNING: Basic Hidden Elements Test")
    print("=" * 80)
    results['Basic Hidden Elements'] = test_comprehensive_hidden.test_all_hidden_scenarios()
    
    print("\n" + "=" * 80)
    print("RUNNING: Parent Chain Hiding Test")
    print("=" * 80)
    results['Parent Chain Hiding'] = test_parent_chain.test_parent_chain_hiding()
    
    print("\n" + "=" * 80)
    print("FINAL SUMMARY")
    print("=" * 80)
    
    all_passed = all(results.values())
    
    for test_name, passed in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print("\n" + "=" * 80)
    if all_passed:
        print("🎉 ALL TEST SUITES PASSED! 🎉")
        print("\nVisibility Detection Summary:")
        print("  ✓ Checks element's own visibility (display, visibility, opacity, dimensions)")
        print("  ✓ Checks ALL parent elements up to <body> for hiding properties")
        print("  ✓ Handles deeply nested structures (unlimited depth)")
        print("  ✓ Detects off-screen positioning")
        print("  ✓ Validates loading text visibility")
        print("  ✓ Works in both recorder and executor")
    else:
        print("❌ SOME TESTS FAILED")
    print("=" * 80)
    
    return all_passed

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
