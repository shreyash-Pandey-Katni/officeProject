#!/usr/bin/env python3
"""
Test to verify that hidden elements with loading classes are properly ignored
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
from activity_executor import ActivityExecutor
import time

def test_hidden_loading_elements():
    """Test that hidden elements with 'loading' classes are properly ignored"""
    
    print("=" * 80)
    print("Testing Hidden Loading Element Detection")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        recorder = BrowserActivityRecorder(driver)
        executor = ActivityExecutor(driver, "test_screenshots")
        
        # Test 1: Hidden element with display:none
        print("\n1. Testing hidden element with display:none and class='loading'...")
        print("-" * 80)
        driver.get("https://example.com")
        time.sleep(1)
        
        driver.execute_script("""
            let hiddenLoader = document.createElement('div');
            hiddenLoader.className = 'loading-spinner';
            hiddenLoader.style.display = 'none';
            hiddenLoader.style.width = '50px';
            hiddenLoader.style.height = '50px';
            document.body.appendChild(hiddenLoader);
        """)
        
        is_loading_recorder, reason_recorder = recorder.is_page_loading()
        is_loading_executor, reason_executor = executor._quick_loading_check()
        
        print(f"  Recorder - Is Loading: {is_loading_recorder}, Reason: {reason_recorder}")
        print(f"  Executor - Is Loading: {is_loading_executor}, Reason: {reason_executor}")
        assert not is_loading_recorder, "❌ Recorder should NOT detect hidden (display:none) loader!"
        assert not is_loading_executor, "❌ Executor should NOT detect hidden (display:none) loader!"
        print("  ✓ Correctly ignored hidden element with display:none")
        
        # Test 2: Hidden element with visibility:hidden
        print("\n2. Testing hidden element with visibility:hidden and class='spinner'...")
        print("-" * 80)
        driver.execute_script("""
            document.querySelectorAll('.loading-spinner').forEach(el => el.remove());
            
            let hiddenSpinner = document.createElement('div');
            hiddenSpinner.className = 'spinner';
            hiddenSpinner.style.visibility = 'hidden';
            hiddenSpinner.style.width = '50px';
            hiddenSpinner.style.height = '50px';
            document.body.appendChild(hiddenSpinner);
        """)
        
        is_loading_recorder, reason_recorder = recorder.is_page_loading()
        is_loading_executor, reason_executor = executor._quick_loading_check()
        
        print(f"  Recorder - Is Loading: {is_loading_recorder}, Reason: {reason_recorder}")
        print(f"  Executor - Is Loading: {is_loading_executor}, Reason: {reason_executor}")
        assert not is_loading_recorder, "❌ Recorder should NOT detect hidden (visibility:hidden) loader!"
        assert not is_loading_executor, "❌ Executor should NOT detect hidden (visibility:hidden) loader!"
        print("  ✓ Correctly ignored hidden element with visibility:hidden")
        
        # Test 3: Hidden element with opacity:0
        print("\n3. Testing hidden element with opacity:0 and class='loader'...")
        print("-" * 80)
        driver.execute_script("""
            document.querySelectorAll('.spinner').forEach(el => el.remove());
            
            let transparentLoader = document.createElement('div');
            transparentLoader.className = 'loader';
            transparentLoader.style.opacity = '0';
            transparentLoader.style.width = '50px';
            transparentLoader.style.height = '50px';
            document.body.appendChild(transparentLoader);
        """)
        
        is_loading_recorder, reason_recorder = recorder.is_page_loading()
        is_loading_executor, reason_executor = executor._quick_loading_check()
        
        print(f"  Recorder - Is Loading: {is_loading_recorder}, Reason: {reason_recorder}")
        print(f"  Executor - Is Loading: {is_loading_executor}, Reason: {reason_executor}")
        assert not is_loading_recorder, "❌ Recorder should NOT detect transparent (opacity:0) loader!"
        assert not is_loading_executor, "❌ Executor should NOT detect transparent (opacity:0) loader!"
        print("  ✓ Correctly ignored transparent element with opacity:0")
        
        # Test 4: Hidden element with zero dimensions
        print("\n4. Testing element with width=0 and class='loading'...")
        print("-" * 80)
        driver.execute_script("""
            document.querySelectorAll('.loader').forEach(el => el.remove());
            
            let zeroDimLoader = document.createElement('div');
            zeroDimLoader.className = 'loading';
            zeroDimLoader.style.width = '0px';
            zeroDimLoader.style.height = '0px';
            document.body.appendChild(zeroDimLoader);
        """)
        
        is_loading_recorder, reason_recorder = recorder.is_page_loading()
        is_loading_executor, reason_executor = executor._quick_loading_check()
        
        print(f"  Recorder - Is Loading: {is_loading_recorder}, Reason: {reason_recorder}")
        print(f"  Executor - Is Loading: {is_loading_executor}, Reason: {reason_executor}")
        assert not is_loading_recorder, "❌ Recorder should NOT detect zero-dimension loader!"
        assert not is_loading_executor, "❌ Executor should NOT detect zero-dimension loader!"
        print("  ✓ Correctly ignored element with zero dimensions")
        
        # Test 5: VISIBLE element with loading class (should be detected)
        print("\n5. Testing VISIBLE element with class='loading-spinner'...")
        print("-" * 80)
        driver.execute_script("""
            document.querySelectorAll('.loading').forEach(el => el.remove());
            
            let visibleLoader = document.createElement('div');
            visibleLoader.className = 'loading-spinner';
            visibleLoader.style.width = '50px';
            visibleLoader.style.height = '50px';
            visibleLoader.style.display = 'block';
            visibleLoader.style.visibility = 'visible';
            visibleLoader.style.opacity = '1';
            document.body.appendChild(visibleLoader);
        """)
        
        is_loading_recorder, reason_recorder = recorder.is_page_loading()
        is_loading_executor, reason_executor = executor._quick_loading_check()
        
        print(f"  Recorder - Is Loading: {is_loading_recorder}, Reason: {reason_recorder}")
        print(f"  Executor - Is Loading: {is_loading_executor}, Reason: {reason_executor}")
        assert is_loading_recorder, "❌ Recorder SHOULD detect visible loader!"
        assert is_loading_executor, "❌ Executor SHOULD detect visible loader!"
        print("  ✓ Correctly detected visible loading element")
        
        # Clean up
        driver.execute_script("""
            document.querySelectorAll('.loading-spinner').forEach(el => el.remove());
        """)
        
        # Test 6: Verify page is ready after cleanup
        print("\n6. Verifying page is ready after removing loaders...")
        print("-" * 80)
        is_loading_recorder, reason_recorder = recorder.is_page_loading()
        is_loading_executor, reason_executor = executor._quick_loading_check()
        
        print(f"  Recorder - Is Loading: {is_loading_recorder}, Reason: {reason_recorder}")
        print(f"  Executor - Is Loading: {is_loading_executor}, Reason: {reason_executor}")
        assert not is_loading_recorder, "❌ Recorder should report page as ready!"
        assert not is_loading_executor, "❌ Executor should report page as ready!"
        print("  ✓ Page correctly reported as ready")
        
        print("\n" + "=" * 80)
        print("✓ All hidden element detection tests passed!")
        print("=" * 80)
        
    except AssertionError as e:
        print(f"\n✗ Test assertion failed: {e}")
        import traceback
        traceback.print_exc()
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    test_hidden_loading_elements()
