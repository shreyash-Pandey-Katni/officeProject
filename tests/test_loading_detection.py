#!/usr/bin/env python3
"""
Test script for enhanced loading detection
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import BrowserActivityRecorder

def test_loading_detection():
    print("=" * 60)
    print("Testing Enhanced Loading Detection")
    print("=" * 60)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Initialize recorder
        print("\n1. Initializing recorder with network monitoring...")
        recorder = BrowserActivityRecorder(driver)
        print("   ✓ Recorder initialized")
        
        # Test 1: Simple static page
        print("\n2. Testing with simple static page...")
        driver.get("https://example.com")
        
        import time
        time.sleep(2)  # Wait for page to fully load
        
        loading_details = recorder.get_loading_details()
        print(f"   Document Ready: {loading_details['document_ready']}")
        print(f"   Network Activity: {loading_details['network_activity']}")
        print(f"   DOM Mutations: {loading_details['dom_mutations']}")
        print(f"   Visual Loaders: {loading_details['visual_loaders']}")
        print(f"   Framework Loading: {loading_details['framework_loading']}")
        print(f"   Overall Loading: {loading_details['overall_loading']}")
        
        if not loading_details['overall_loading']:
            print("   ✓ Correctly detected page is ready")
        else:
            print("   ⚠ Page detected as loading (might be network activity)")
        
        # Test 2: Page with AJAX (if available)
        print("\n3. Testing with dynamic content page...")
        driver.get("https://httpbin.org/delay/2")
        
        time.sleep(0.5)
        loading_details = recorder.get_loading_details()
        print(f"   Network Activity (during load): {loading_details['network_activity']}")
        print(f"   Overall Loading: {loading_details['overall_loading']}")
        
        time.sleep(3)
        loading_details = recorder.get_loading_details()
        print(f"   Network Activity (after load): {loading_details['network_activity']}")
        print(f"   Overall Loading: {loading_details['overall_loading']}")
        
        # Test 3: Check is_page_loading method
        print("\n4. Testing is_page_loading() method...")
        driver.get("https://example.com")
        time.sleep(1)
        
        is_loading = recorder.is_page_loading()
        print(f"   is_page_loading() returned: {is_loading}")
        
        if not is_loading:
            print("   ✓ Enhanced loading detection working!")
        else:
            print("   ⚠ Still detecting loading state")
        
        print("\n" + "=" * 60)
        print("Test Complete!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("\nClosing browser...")
        driver.quit()

if __name__ == "__main__":
    test_loading_detection()
