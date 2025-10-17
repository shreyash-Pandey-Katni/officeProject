#!/usr/bin/env python3
"""
Test complete parent chain checking for hidden elements
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
from activity_executor import ActivityExecutor
import time

def test_parent_chain_hiding():
    """Test that ALL parent levels are checked for hidden properties"""
    
    print("=" * 80)
    print("Testing Complete Parent Chain Visibility Checking")
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
        
        # Test 1: Parent with display:none (1 level up)
        print("\n1. Testing parent with display:none (1 level)...")
        driver.execute_script("""
            let parent = document.createElement('div');
            parent.style.display = 'none';
            let child = document.createElement('div');
            child.className = 'loading-spinner';
            child.style.width = '100px';
            child.style.height = '100px';
            parent.appendChild(child);
            document.body.appendChild(parent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Parent display:none (1 level)", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 2: Grandparent with display:none (2 levels up)
        print("2. Testing grandparent with display:none (2 levels)...")
        driver.execute_script("""
            let grandparent = document.createElement('div');
            grandparent.style.display = 'none';
            let parent = document.createElement('div');
            let child = document.createElement('div');
            child.className = 'loading-spinner';
            child.style.width = '100px';
            child.style.height = '100px';
            parent.appendChild(child);
            grandparent.appendChild(parent);
            document.body.appendChild(grandparent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Grandparent display:none (2 levels)", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 3: Deep nesting (10 levels up) with hidden ancestor
        print("3. Testing deeply nested (10 levels) with hidden ancestor...")
        driver.execute_script("""
            let root = document.createElement('div');
            root.style.visibility = 'hidden';  // Hidden at top level
            
            let current = root;
            for (let i = 0; i < 10; i++) {
                let div = document.createElement('div');
                current.appendChild(div);
                current = div;
            }
            
            let loader = document.createElement('div');
            loader.className = 'spinner-loader';
            loader.style.width = '100px';
            loader.style.height = '100px';
            current.appendChild(loader);
            
            document.body.appendChild(root);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Deep nesting (10 levels) hidden ancestor", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 4: Parent with opacity:0
        print("4. Testing parent with opacity:0...")
        driver.execute_script("""
            let parent = document.createElement('div');
            parent.style.opacity = '0';
            let child = document.createElement('div');
            child.className = 'loading-test';
            child.style.width = '100px';
            child.style.height = '100px';
            parent.appendChild(child);
            document.body.appendChild(parent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Parent opacity:0", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 5: Parent with visibility:hidden
        print("5. Testing parent with visibility:hidden...")
        driver.execute_script("""
            let parent = document.createElement('div');
            parent.style.visibility = 'hidden';
            let child = document.createElement('div');
            child.className = 'spinner-test';
            child.style.width = '100px';
            child.style.height = '100px';
            parent.appendChild(child);
            document.body.appendChild(parent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Parent visibility:hidden", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 6: Parent with zero width
        print("6. Testing parent with width:0...")
        driver.execute_script("""
            let parent = document.createElement('div');
            parent.style.width = '0';
            parent.style.height = '100px';
            let child = document.createElement('div');
            child.className = 'loader-test';
            child.style.width = '100px';
            child.style.height = '100px';
            parent.appendChild(child);
            document.body.appendChild(parent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Parent width:0", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 7: Parent with zero height
        print("7. Testing parent with height:0...")
        driver.execute_script("""
            let parent = document.createElement('div');
            parent.style.width = '100px';
            parent.style.height = '0';
            let child = document.createElement('div');
            child.className = 'loading-test';
            child.style.width = '100px';
            child.style.height = '100px';
            parent.appendChild(child);
            document.body.appendChild(parent);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Parent height:0", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 8: Middle parent hidden (5 levels deep)
        print("8. Testing middle parent hidden (5 levels deep)...")
        driver.execute_script("""
            let level1 = document.createElement('div');
            let level2 = document.createElement('div');
            let level3 = document.createElement('div');
            level3.style.display = 'none';  // Hidden at middle level
            let level4 = document.createElement('div');
            let level5 = document.createElement('div');
            
            let loader = document.createElement('div');
            loader.className = 'spinner-loader';
            loader.style.width = '100px';
            loader.style.height = '100px';
            
            level5.appendChild(loader);
            level4.appendChild(level5);
            level3.appendChild(level4);
            level2.appendChild(level3);
            level1.appendChild(level2);
            document.body.appendChild(level1);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("Middle parent hidden (5 levels)", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Test 9: ALL parents visible - should detect!
        print("9. Testing ALL parents visible (should DETECT!)...")
        driver.execute_script("""
            let level1 = document.createElement('div');
            level1.style.width = '200px';
            level1.style.height = '200px';
            let level2 = document.createElement('div');
            level2.style.width = '150px';
            level2.style.height = '150px';
            let level3 = document.createElement('div');
            level3.style.width = '120px';
            level3.style.height = '120px';
            
            let loader = document.createElement('div');
            loader.className = 'loading-spinner';
            loader.style.width = '100px';
            loader.style.height = '100px';
            loader.style.display = 'block';
            
            level3.appendChild(loader);
            level2.appendChild(level3);
            level1.appendChild(level2);
            document.body.appendChild(level1);
        """)
        r_loading, r_reason = recorder.is_page_loading()
        e_loading, e_reason = executor._quick_loading_check()
        test_cases.append(("ALL parents visible (should DETECT)", r_loading, e_loading, r_reason, e_reason))
        driver.execute_script("document.body.removeChild(document.body.lastChild);")
        
        # Print results
        print("\n" + "=" * 80)
        print("TEST RESULTS:")
        print("=" * 80)
        
        passed = 0
        failed = 0
        
        for i, (test_name, r_loading, e_loading, r_reason, e_reason) in enumerate(test_cases, 1):
            should_detect = "should DETECT" in test_name
            
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
            print("\n✅ All parent chain tests passed!")
            return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_parent_chain_hiding()
    sys.exit(0 if success else 1)
