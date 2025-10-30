"""
Quick test to debug screenshot issue with a single activity
"""
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from core.executors.activity_executor import ActivityExecutor
import json
import os

def test_single_activity_screenshot():
    """Test screenshot capture with a single navigation activity"""
    
    print("="*80)
    print("Testing Single Activity Screenshot Capture")
    print("="*80)
    
    # Setup Chrome (same as replayer)
    chrome_options = Options()
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=chrome_options)
    driver.maximize_window()
    
    try:
        # Create executor (same as replayer - no explicit screenshots_dir)
        executor = ActivityExecutor(driver)
        
        print(f"\n[TEST] Executor screenshots_dir: {executor.screenshots_dir}")
        print(f"[TEST] Current working directory: {os.getcwd()}")
        
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
        for key in ['screenshot_before', 'screenshot_after']:
            path = result[key]
            if path:
                abs_path = os.path.abspath(path)
                exists = os.path.exists(path)
                print(f"\n[TEST] {key}:")
                print(f"  Path: {path}")
                print(f"  Absolute: {abs_path}")
                print(f"  Exists: {exists}")
                if exists:
                    size = os.path.getsize(path)
                    print(f"  Size: {size} bytes")
            else:
                print(f"\n[TEST] {key}: EMPTY PATH!")
        
        print("\n" + "="*80)
        
    finally:
        driver.quit()
        print("\n[TEST] Browser closed")

if __name__ == "__main__":
    test_single_activity_screenshot()
