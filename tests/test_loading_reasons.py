#!/usr/bin/env python3
"""
Test to demonstrate detailed loading detection reasons
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from activity_executor import ActivityExecutor
import time

def test_loading_reasons():
    """Test showing different loading detection reasons"""
    
    print("=" * 80)
    print("Testing Loading Detection Reasons")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        executor = ActivityExecutor(driver, "test_screenshots")
        
        # Test 1: Check during page load (before complete)
        print("\n1. Checking DURING page load...")
        print("-" * 80)
        driver.get("https://httpbin.org/delay/5")
        
        # Check immediately (should show document state or network activity)
        for i in range(3):
            is_loading, reason = executor._quick_loading_check()
            print(f"  Check {i+1}: Loading={is_loading}, Reason: {reason}")
            time.sleep(1)
        
        # Test 2: Inject a fake loader element
        print("\n2. Testing with injected loading spinner...")
        print("-" * 80)
        driver.get("https://example.com")
        time.sleep(1)
        
        # Inject a visible spinner
        driver.execute_script("""
            let spinner = document.createElement('div');
            spinner.className = 'loading-spinner';
            spinner.style.width = '50px';
            spinner.style.height = '50px';
            spinner.style.display = 'block';
            document.body.appendChild(spinner);
        """)
        
        is_loading, reason = executor._quick_loading_check()
        print(f"  Loading={is_loading}, Reason: {reason}")
        
        # Remove spinner
        driver.execute_script("""
            let spinner = document.querySelector('.loading-spinner');
            if (spinner) spinner.remove();
        """)
        
        is_loading, reason = executor._quick_loading_check()
        print(f"  After removal: Loading={is_loading}, Reason: {reason}")
        
        # Test 3: Test with document not complete
        print("\n3. Testing document.readyState check...")
        print("-" * 80)
        
        # Navigate to a new page and check immediately
        driver.execute_script("window.location.href = 'https://example.com';")
        time.sleep(0.1)  # Very brief pause
        
        is_loading, reason = executor._quick_loading_check()
        print(f"  Loading={is_loading}, Reason: {reason}")
        
        # Wait for complete
        time.sleep(2)
        is_loading, reason = executor._quick_loading_check()
        print(f"  After load: Loading={is_loading}, Reason: {reason}")
        
        # Test 4: Full wait with logging
        print("\n4. Testing full _wait_for_page_ready with logging...")
        print("-" * 80)
        driver.get("https://httpbin.org/delay/2")
        result = executor._wait_for_page_ready(timeout=10)
        print(f"  Final result: {'✓ Ready' if result else '✗ Timeout'}")
        
        print("\n" + "=" * 80)
        print("✓ Tests completed!")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    test_loading_reasons()
