#!/usr/bin/env python3
"""
Test to verify recorder (main.py) also has detailed loading detection logging
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
import time

def test_recorder_loading_detection():
    """Test the recorder's enhanced loading detection with detailed logging"""
    
    print("=" * 80)
    print("Testing Recorder Loading Detection with Detailed Logging")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Create recorder instance
        recorder = BrowserActivityRecorder(driver)
        
        # Test 1: Simple page
        print("\n1. Testing with example.com...")
        print("-" * 80)
        driver.get("https://example.com")
        time.sleep(1)
        
        is_loading, reason = recorder.is_page_loading()
        print(f"  Is Loading: {is_loading}")
        print(f"  Reason: {reason}")
        
        # Test 2: Inject a spinner
        print("\n2. Testing with injected loading spinner...")
        print("-" * 80)
        driver.execute_script("""
            let spinner = document.createElement('div');
            spinner.className = 'loading-spinner';
            spinner.style.width = '50px';
            spinner.style.height = '50px';
            spinner.style.display = 'block';
            document.body.appendChild(spinner);
        """)
        
        is_loading, reason = recorder.is_page_loading()
        print(f"  Is Loading: {is_loading}")
        print(f"  Reason: {reason}")
        
        # Remove spinner
        driver.execute_script("""
            let spinner = document.querySelector('.loading-spinner');
            if (spinner) spinner.remove();
        """)
        
        is_loading, reason = recorder.is_page_loading()
        print(f"  After removal - Is Loading: {is_loading}")
        print(f"  Reason: {reason}")
        
        # Test 3: Test network activity check
        print("\n3. Testing individual check methods...")
        print("-" * 80)
        
        network_reason = recorder._check_network_activity()
        print(f"  Network Activity: {network_reason if network_reason else 'None'}")
        
        mutation_reason = recorder._check_dom_mutations()
        print(f"  DOM Mutations: {mutation_reason if mutation_reason else 'None'}")
        
        loader_reason = recorder._check_visual_loaders()
        print(f"  Visual Loaders: {loader_reason if loader_reason else 'None'}")
        
        framework_reason = recorder._check_framework_loading()
        print(f"  Framework Loading: {framework_reason if framework_reason else 'None'}")
        
        print("\n" + "=" * 80)
        print("✓ All recorder tests completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    test_recorder_loading_detection()
