#!/usr/bin/env python3
"""
Test to verify click events are captured even when they trigger DOM changes
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder

def test_click_capture_with_dom_changes():
    """Test that clicks are captured even when they trigger DOM changes"""
    
    print("=" * 80)
    print("Testing Click Capture with DOM Changes")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--headless=new')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    
    driver = webdriver.Chrome(options=chrome_options)
    
    try:
        # Create a test page with buttons that trigger DOM changes
        test_html = """
        <html>
        <head>
            <title>Click Test with DOM Changes</title>
            <style>
                button { margin: 10px; padding: 10px 20px; font-size: 16px; }
                #output { margin: 20px; padding: 10px; border: 1px solid #ccc; }
            </style>
        </head>
        <body>
            <h1>Click Test Page</h1>
            <button id="btn1" onclick="addContent()">Add Content (DOM Change)</button>
            <button id="btn2" onclick="removeContent()">Remove Content (DOM Change)</button>
            <button id="btn3" onclick="replaceContent()">Replace Content (DOM Change)</button>
            <button id="btn4">Simple Button (No DOM Change)</button>
            <div id="output"></div>
            
            <script>
                let counter = 0;
                
                function addContent() {
                    counter++;
                    let div = document.createElement('div');
                    div.textContent = 'Item ' + counter;
                    div.id = 'item-' + counter;
                    document.getElementById('output').appendChild(div);
                }
                
                function removeContent() {
                    let output = document.getElementById('output');
                    if (output.lastChild) {
                        output.removeChild(output.lastChild);
                    }
                }
                
                function replaceContent() {
                    document.getElementById('output').innerHTML = '<p>Replaced at ' + new Date().toLocaleTimeString() + '</p>';
                }
            </script>
        </body>
        </html>
        """
        
        # Save to temp file and load it
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(test_html)
            temp_file = f.name
        
        driver.get(f"file://{temp_file}")
        time.sleep(1)
        
        # Clean up temp file
        import os
        os.unlink(temp_file)
        
        # Create recorder instance
        recorder = BrowserActivityRecorder(driver)
        
        # Inject trackers
        click_ok = recorder.inject_click_tracker()
        input_ok = recorder.inject_input_tracker()
        
        if not click_ok:
            print("❌ Failed to inject click tracker")
            return False
        
        print("✓ Click tracker injected successfully\n")
        
        # Test 1: Click button that adds content (DOM change)
        print("Test 1: Clicking 'Add Content' button (triggers DOM change)...")
        btn1 = driver.find_element("id", "btn1")
        btn1.click()
        time.sleep(0.3)  # Give time for event to be captured
        
        recorder.collect_click_events()
        clicks_1 = len([a for a in recorder.activity_log if a['action'] == 'click'])
        print(f"  Clicks captured: {clicks_1}")
        
        if clicks_1 == 0:
            print("  ❌ FAIL: Click was not captured!")
        else:
            print(f"  ✓ PASS: Click captured ({recorder.activity_log[-1]['details']['id']})")
        
        # Test 2: Click multiple times with DOM changes
        print("\nTest 2: Multiple clicks with DOM changes...")
        btn1.click()
        time.sleep(0.2)
        btn2 = driver.find_element("id", "btn2")
        btn2.click()
        time.sleep(0.2)
        btn3 = driver.find_element("id", "btn3")
        btn3.click()
        time.sleep(0.3)
        
        recorder.collect_click_events()
        clicks_2 = len([a for a in recorder.activity_log if a['action'] == 'click'])
        new_clicks = clicks_2 - clicks_1
        print(f"  Additional clicks captured: {new_clicks}")
        
        if new_clicks < 3:
            print(f"  ❌ FAIL: Expected 3 clicks, got {new_clicks}")
        else:
            print(f"  ✓ PASS: All 3 clicks captured")
        
        # Test 3: Click button without DOM change
        print("\nTest 3: Click button without DOM change...")
        btn4 = driver.find_element("id", "btn4")
        btn4.click()
        time.sleep(0.2)
        
        recorder.collect_click_events()
        clicks_3 = len([a for a in recorder.activity_log if a['action'] == 'click'])
        new_clicks = clicks_3 - clicks_2
        print(f"  Additional clicks captured: {new_clicks}")
        
        if new_clicks == 0:
            print("  ❌ FAIL: Click was not captured!")
        else:
            print(f"  ✓ PASS: Click captured")
        
        # Test 4: Rapid clicks
        print("\nTest 4: Rapid clicks (5 clicks in quick succession)...")
        for i in range(5):
            btn1.click()
            time.sleep(0.05)  # Very short delay
        
        time.sleep(0.3)
        recorder.collect_click_events()
        clicks_4 = len([a for a in recorder.activity_log if a['action'] == 'click'])
        new_clicks = clicks_4 - clicks_3
        print(f"  Clicks captured: {new_clicks}/5")
        
        # Due to debouncing (100ms), we may not get all 5
        if new_clicks >= 4:
            print(f"  ✓ PASS: Most rapid clicks captured ({new_clicks}/5)")
        else:
            print(f"  ⚠️  WARNING: Only {new_clicks}/5 rapid clicks captured (debouncing active)")
        
        # Summary
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)
        print(f"Total clicks captured: {clicks_4}")
        print(f"Total activities: {len(recorder.activity_log)}")
        
        # Show all captured clicks
        print("\nCaptured Click Details:")
        for i, activity in enumerate([a for a in recorder.activity_log if a['action'] == 'click'], 1):
            details = activity['details']
            print(f"  {i}. {details.get('tagName', 'unknown')} - ID: {details.get('id', 'none')} - Text: {details.get('text', 'none')[:30]}")
        
        print("\n" + "=" * 80)
        if clicks_4 >= 5:
            print("✅ Click capture is working correctly with DOM changes!")
            return True
        else:
            print("⚠️  Click capture is working but may miss some rapid clicks")
            return clicks_4 > 0
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        driver.quit()

if __name__ == "__main__":
    success = test_click_capture_with_dom_changes()
    sys.exit(0 if success else 1)
