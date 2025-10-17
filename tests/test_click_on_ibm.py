#!/usr/bin/env python3
"""
Test click capture on IBM.com
This test verifies that clicks are captured even when they trigger DOM changes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
import time
import json

def test_ibm_click_capture():
    """Test click capture on IBM.com with real DOM interactions"""
    
    print("=" * 80)
    print("Testing Click Capture on IBM.com")
    print("=" * 80)
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    # Not headless so we can see what's happening
    
    # Create driver
    driver = webdriver.Chrome(options=chrome_options)
    
    # Create recorder
    recorder = BrowserActivityRecorder(driver)
    
    try:
        print("\n1. Navigating to IBM.com...")
        driver.get("https://www.ibm.com")
        
        # Wait for page to load
        print("   Waiting for page to load...")
        time.sleep(5)
        
        print("\n2. Injecting click tracker...")
        recorder.inject_click_tracker()
        recorder.inject_input_tracker()
        time.sleep(1)
        
        print("\n3. Looking for clickable elements on IBM.com...")
        
        # Try to find and click interactive elements
        # IBM.com often has navigation menus, buttons, etc.
        clickable_selectors = [
            "button",
            "a[href]",
            "[role='button']",
            ".cta",
            "[class*='button']"
        ]
        
        clicks_performed = 0
        for selector in clickable_selectors:
            try:
                elements = recorder.driver.find_elements("css selector", selector)
                visible_elements = []
                
                for elem in elements[:10]:  # Check first 10 of each type
                    try:
                        if elem.is_displayed() and elem.is_enabled():
                            # Get element details
                            tag = elem.tag_name
                            text = elem.text[:50] if elem.text else ""
                            elem_id = elem.get_attribute("id") or ""
                            
                            # Skip if no visible text and no meaningful id
                            if not text and not elem_id:
                                continue
                                
                            visible_elements.append({
                                'element': elem,
                                'tag': tag,
                                'text': text,
                                'id': elem_id
                            })
                    except:
                        continue
                
                # Click first 2 visible elements of this type
                for elem_info in visible_elements[:2]:
                    try:
                        elem = elem_info['element']
                        print(f"\n   Clicking: {elem_info['tag']} - ID: '{elem_info['id']}' - Text: '{elem_info['text']}'")
                        
                        # Scroll element into view
                        recorder.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elem)
                        time.sleep(0.5)
                        
                        # For links, prevent default navigation and collect click immediately
                        is_link = elem.tag_name.lower() == 'a' and elem.get_attribute('href')
                        
                        if is_link:
                            # Prevent navigation for testing
                            recorder.driver.execute_script("""
                                arguments[0].addEventListener('click', function(e) {
                                    e.preventDefault();
                                }, {once: true, capture: true});
                            """, elem)
                        
                        # Click the element
                        elem.click()
                        clicks_performed += 1
                        print(f"   ✓ Click performed ({clicks_performed} total)")
                        
                        # Collect the click event IMMEDIATELY (within 50ms window)
                        time.sleep(0.1)  # Wait for click tracker's 50ms timeout
                        recorder.collect_click_events()
                        
                        # Wait to see if DOM changes occur
                        time.sleep(2)
                        
                        if clicks_performed >= 5:
                            break
                    except Exception as e:
                        print(f"   ✗ Could not click: {str(e)[:100]}")
                        continue
                
                if clicks_performed >= 5:
                    break
                    
            except Exception as e:
                print(f"   Error with selector '{selector}': {str(e)[:100]}")
                continue
        
        print(f"\n4. Total clicks performed: {clicks_performed}")
        print("   Collecting final events...")
        recorder.collect_click_events()
        time.sleep(1)
        
        # Save activity log
        print("\n5. Saving activity log...")
        log_file = "tests/test_ibm_activity_log.json"
        with open(log_file, "w") as f:
            json.dump(recorder.activity_log, f, indent=2)
        
        # Check captured activities
        print("\n6. Checking captured activities...")
        activities = recorder.activity_log
            
        click_activities = [a for a in activities if a.get("action") == "click"]
        
        print(f"\n   Total activities captured: {len(activities)}")
        print(f"   Click activities captured: {len(click_activities)}")
        print(f"   Click capture rate: {len(click_activities)}/{clicks_performed} ({len(click_activities)/max(clicks_performed, 1)*100:.0f}%)")
        
        if click_activities:
            print("\n   Captured Click Details:")
            for i, click in enumerate(click_activities, 1):
                details = click.get("details", {})
                elem_tag = details.get("tagName", "N/A")  # Changed from element_tag to tagName
                elem_id = details.get("id", "N/A")  # Direct field, not in details
                text = details.get("text", "N/A")[:40]  # Direct field
                coords = details.get("coordinates", {})
                click_pos = f"({coords.get('clickX', 0):.0f}, {coords.get('clickY', 0):.0f})" if coords else "N/A"
                print(f"   {i}. {elem_tag} - ID: '{elem_id}' - Text: '{text}' - Position: {click_pos}")
        
        print("\n" + "=" * 80)
        if len(click_activities) >= clicks_performed * 0.8:  # 80% capture rate
            print("✅ SUCCESS: Click capture is working correctly!")
            print(f"   {len(click_activities)}/{clicks_performed} clicks captured on IBM.com")
        else:
            print("⚠️  WARNING: Low click capture rate")
            print(f"   Only {len(click_activities)}/{clicks_performed} clicks captured")
            print("   Expected at least 80% capture rate")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        try:
            driver.quit()
        except:
            pass

if __name__ == "__main__":
    test_ibm_click_capture()
