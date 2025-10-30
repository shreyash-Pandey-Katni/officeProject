"""
Test script to verify screenshot capture in ActivityExecutor
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from core.executors.activity_executor import ActivityExecutor
import json

def test_screenshot_capture():
    """Test that screenshots are being captured properly"""
    
    print("="*80)
    print("Testing Screenshot Capture")
    print("="*80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Create executor
        executor = ActivityExecutor(driver, screenshots_dir="test_screenshots")
        
        # Test simple navigation
        activity = {
            'action': 'navigation',
            'details': {
                'url': 'https://www.google.com',
                'description': 'Navigate to Google'
            }
        }
        
        print("\n[TEST] Executing navigation activity...")
        result = executor.execute_activity(activity)
        
        print("\n[TEST] Result:")
        print(f"  Success: {result['success']}")
        print(f"  Before screenshot: {result['screenshot_before']}")
        print(f"  After screenshot: {result['screenshot_after']}")
        
        # Verify screenshots exist
        import os
        if result['screenshot_before'] and os.path.exists(result['screenshot_before']):
            size = os.path.getsize(result['screenshot_before'])
            print(f"  ✓ Before screenshot exists ({size} bytes)")
        else:
            print(f"  ✗ Before screenshot missing!")
        
        if result['screenshot_after'] and os.path.exists(result['screenshot_after']):
            size = os.path.getsize(result['screenshot_after'])
            print(f"  ✓ After screenshot exists ({size} bytes)")
        else:
            print(f"  ✗ After screenshot missing!")
        
        print("\n" + "="*80)
        
    finally:
        driver.quit()
        print("\n[TEST] Browser closed")

if __name__ == "__main__":
    test_screenshot_capture()
