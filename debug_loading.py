#!/usr/bin/env python3
"""
Debug test to see exactly what elements are being detected
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
import time

def debug_loading_detection():
    """Debug what elements are being detected"""
    
    print("=" * 80)
    print("DEBUG: Finding what elements are being detected")
    print("=" * 80)
    
    # Setup Chrome (visible so we can see)
    chrome_options = Options()
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        recorder = BrowserActivityRecorder(driver)
        
        # Go to a simple page
        driver.get("https://example.com")
        time.sleep(1)
        
        print("\n1. Checking current page for any loading elements...")
        print("-" * 80)
        
        # Get detailed info about what's on the page
        result = driver.execute_script("""
            let details = {
                loadingElements: [],
                hiddenLoadingElements: []
            };
            
            // Find all elements with loading-related classes
            let selectors = [
                '[class*="loading"]',
                '[class*="spinner"]',
                '[class*="loader"]',
                '[class*="skeleton"]',
                '[class*="shimmer"]'
            ];
            
            for (let sel of selectors) {
                let elements = document.querySelectorAll(sel);
                for (let el of elements) {
                    let style = window.getComputedStyle(el);
                    let rect = el.getBoundingClientRect();
                    
                    let info = {
                        selector: sel,
                        className: el.className,
                        tagName: el.tagName,
                        offsetWidth: el.offsetWidth,
                        offsetHeight: el.offsetHeight,
                        offsetParent: el.offsetParent !== null,
                        display: style.display,
                        visibility: style.visibility,
                        opacity: style.opacity,
                        rectWidth: rect.width,
                        rectHeight: rect.height,
                        innerHTML: el.innerHTML.substring(0, 50)
                    };
                    
                    if (el.offsetWidth > 0 && el.offsetHeight > 0 && el.offsetParent !== null) {
                        details.loadingElements.push(info);
                    } else {
                        details.hiddenLoadingElements.push(info);
                    }
                }
            }
            
            return details;
        """)
        
        print(f"\nFound {len(result['loadingElements'])} VISIBLE loading elements:")
        for i, el in enumerate(result['loadingElements'], 1):
            print(f"\n  Element {i}:")
            print(f"    Selector: {el['selector']}")
            print(f"    Tag: {el['tagName']}")
            print(f"    Class: {el['className']}")
            print(f"    Size: {el['offsetWidth']}x{el['offsetHeight']}")
            print(f"    Display: {el['display']}")
            print(f"    Visibility: {el['visibility']}")
            print(f"    Opacity: {el['opacity']}")
            print(f"    Has offsetParent: {el['offsetParent']}")
        
        print(f"\nFound {len(result['hiddenLoadingElements'])} HIDDEN loading elements:")
        for i, el in enumerate(result['hiddenLoadingElements'], 1):
            print(f"\n  Hidden Element {i}:")
            print(f"    Selector: {el['selector']}")
            print(f"    Tag: {el['tagName']}")
            print(f"    Class: {el['className']}")
            print(f"    Size: {el['offsetWidth']}x{el['offsetHeight']}")
            print(f"    Display: {el['display']}")
            print(f"    Visibility: {el['visibility']}")
            print(f"    Opacity: {el['opacity']}")
            print(f"    Has offsetParent: {el['offsetParent']}")
        
        # Now check what our detection says
        print("\n" + "=" * 80)
        is_loading, reason = recorder.is_page_loading()
        print(f"Our detection says: Loading={is_loading}, Reason={reason}")
        
        # Test visual loaders specifically
        print("\n" + "=" * 80)
        print("Testing _check_visual_loaders specifically...")
        loader_reason = recorder._check_visual_loaders()
        print(f"Visual loaders check result: {loader_reason}")
        
        print("\nPress Enter to close browser and continue...")
        input()
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    debug_loading_detection()
