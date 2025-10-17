#!/usr/bin/env python3
"""
Quick test to verify the enhanced logging in activity_executor
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from activity_executor import ActivityExecutor
import time

def test_loading_detection_logging():
    """Test the enhanced loading detection with detailed logging"""
    
    print("=" * 80)
    print("Testing Enhanced Loading Detection with Detailed Logging")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Create executor instance
        executor = ActivityExecutor(driver, "test_screenshots")
        
        print("\n1. Testing with a simple static page (example.com)...")
        print("-" * 80)
        driver.get("https://example.com")
        time.sleep(1)  # Let page settle
        result = executor._wait_for_page_ready(timeout=10)
        print(f"Result: {'✓ Ready' if result else '✗ Timeout'}\n")
        
        print("\n2. Testing with a page that has resources (httpbin.org)...")
        print("-" * 80)
        driver.get("https://httpbin.org/delay/2")  # Page with 2-second delay
        result = executor._wait_for_page_ready(timeout=10)
        print(f"Result: {'✓ Ready' if result else '✗ Timeout'}\n")
        
        print("\n3. Getting detailed loading status...")
        print("-" * 80)
        driver.get("https://example.com")
        time.sleep(0.5)
        is_loading, reason = executor._quick_loading_check()
        print(f"Is Loading: {is_loading}")
        print(f"Reason: {reason}\n")
        
        print("=" * 80)
        print("✓ All tests completed successfully!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    test_loading_detection_logging()
