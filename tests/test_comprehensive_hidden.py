#!/usr/bin/env python3
"""
Comprehensive test for all possible ways an element can be hidden
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
from activity_executor import ActivityExecutor
import time

def test_all_hidden_scenarios():
    """Test all possible ways an element can be hidden"""
    
    print("=" * 80)
    print("Comprehensive Hidden Element Test")
    print("=" * 80)
    
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    test_cases = []
    
    try:
        recorder = BrowserActivityRecorder(driver)
        executor = ActivityExecutor(driver, "test_screenshots")
        
        driver.get("https://ibm.com")
        time.sleep(1)
        
        # Test 1: display: none
        print("\n1. Testing display:none...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'loading-test';
            el.style.display = 'none';
            el.style.width = '100px';
            el.style.height = '100px';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("display:none", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.loading-test').remove();")
        
        # Test 2: visibility: hidden
        print("2. Testing visibility:hidden...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'spinner-test';
            el.style.visibility = 'hidden';
            el.style.width = '100px';
            el.style.height = '100px';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("visibility:hidden", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.spinner-test').remove();")
        
        # Test 3: opacity: 0
        print("3. Testing opacity:0...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'loader-test';
            el.style.opacity = '0';
            el.style.width = '100px';
            el.style.height = '100px';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("opacity:0", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.loader-test').remove();")
        
        # Test 4: opacity: 0.05 (below 0.1 threshold)
        print("4. Testing opacity:0.05...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'loading-test';
            el.style.opacity = '0.05';
            el.style.width = '100px';
            el.style.height = '100px';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("opacity:0.05", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.loading-test').remove();")
        
        # Test 5: width/height = 0
        print("5. Testing width:0, height:0...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'spinner-test';
            el.style.width = '0';
            el.style.height = '0';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("width:0, height:0", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.spinner-test').remove();")
        
        # Test 6: Hidden parent container
        print("6. Testing hidden parent (parent has display:none)...")
        driver.execute_script("""
            let parent = document.createElement('div');
            parent.style.display = 'none';
            let el = document.createElement('div');
            el.className = 'loader-test';
            el.style.width = '100px';
            el.style.height = '100px';
            parent.appendChild(el);
            document.body.appendChild(parent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("parent display:none", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 7: Off-screen positioning (negative coords)
        print("7. Testing off-screen positioning...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'loading-test';
            el.style.position = 'absolute';
            el.style.left = '-9999px';
            el.style.top = '-9999px';
            el.style.width = '100px';
            el.style.height = '100px';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("off-screen position", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.loading-test').remove();")
        
        # Test 8: visibility: collapse
        print("8. Testing visibility:collapse...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'spinner-test';
            el.style.visibility = 'collapse';
            el.style.width = '100px';
            el.style.height = '100px';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("visibility:collapse", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.spinner-test').remove();")
        
        # Test 9: VISIBLE element (should be detected!)
        print("9. Testing VISIBLE element (should detect!)...")
        driver.execute_script("""
            let el = document.createElement('div');
            el.className = 'loading-spinner';
            el.style.width = '100px';
            el.style.height = '100px';
            el.style.display = 'block';
            el.style.visibility = 'visible';
            el.style.opacity = '1';
            document.body.appendChild(el);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("VISIBLE (should detect)", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.querySelector('.loading-spinner').remove();")
        
        # Print results
        print("\n" + "=" * 80)
        print("TEST RESULTS:")
        print("=" * 80)
        
        passed = 0
        failed = 0
        
        for i, (test_name, r_loading, e_loading, r_reason, e_reason) in enumerate(test_cases, 1):
            should_detect = "VISIBLE" in test_name
            
            r_correct = r_loading == should_detect
            e_correct = e_loading == should_detect
            
            if r_correct and e_correct:
                status = "✓ PASS"
                passed += 1
            else:
                status = "✗ FAIL"
                failed += 1
            
            print(f"\n{i}. {test_name}: {status}")
            print(f"   Expected: {'DETECT' if should_detect else 'IGNORE'}")
            print(f"   Recorder: {'DETECT' if r_loading else 'IGNORE'} - {r_reason}")
            print(f"   Executor: {'DETECT' if e_loading else 'IGNORE'} - {e_reason}")
        
        print("\n" + "=" * 80)
        print(f"Total: {passed} passed, {failed} failed out of {len(test_cases)} tests")
        print("=" * 80)
        
        if failed > 0:
            print("\n❌ Some tests failed!")
            return False
        else:
            print("\n✅ All tests passed!")
            return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_all_hidden_scenarios()
    sys.exit(0 if success else 1)
