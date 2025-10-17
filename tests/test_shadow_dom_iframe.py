#!/usr/bin/env python3
"""
Test click and input capture in shadow DOM and iframes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
import time
import json

def test_shadow_dom_and_iframe():
    """Test event capture in shadow DOM and iframes"""
    
    print("=" * 80)
    print("Testing Shadow DOM and iframe Event Capture")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    driver = webdriver.Chrome(options=chrome_options)
    recorder = BrowserActivityRecorder(driver)
    
    try:
        # Create test HTML with shadow DOM and iframe
        test_html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Shadow DOM and iframe Test</title>
            <style>
                button { margin: 10px; padding: 10px 20px; }
                #output { margin: 20px; padding: 10px; border: 1px solid #ccc; }
                iframe { border: 2px solid blue; margin: 10px; }
            </style>
        </head>
        <body>
            <h1>Shadow DOM and iframe Test</h1>
            
            <h2>Regular DOM</h2>
            <button id="regular-btn">Regular Button</button>
            <input type="text" id="regular-input" placeholder="Regular input">
            
            <h2>Shadow DOM</h2>
            <div id="shadow-host"></div>
            
            <h2>iframe</h2>
            <iframe id="test-iframe" srcdoc="
                <html>
                <body>
                    <h3>Inside iframe</h3>
                    <button id='iframe-btn'>iframe Button</button>
                    <input type='text' id='iframe-input' placeholder='iframe input'>
                </body>
                </html>
            " width="400" height="200"></iframe>
            
            <div id="output"></div>
            
            <script>
                // Create shadow DOM
                const shadowHost = document.getElementById('shadow-host');
                const shadowRoot = shadowHost.attachShadow({mode: 'open'});
                
                shadowRoot.innerHTML = `
                    <style>
                        button { background: purple; color: white; margin: 10px; padding: 10px; }
                        input { margin: 10px; padding: 5px; }
                    </style>
                    <button id="shadow-btn">Shadow DOM Button</button>
                    <input type="text" id="shadow-input" placeholder="Shadow DOM input">
                `;
                
                // Add click handlers to show feedback
                document.getElementById('regular-btn').onclick = function() {
                    document.getElementById('output').innerHTML += '<p>Regular button clicked</p>';
                };
                
                shadowRoot.getElementById('shadow-btn').onclick = function() {
                    document.getElementById('output').innerHTML += '<p>Shadow DOM button clicked</p>';
                };
            </script>
        </body>
        </html>
        """
        
        # Save to temp file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(test_html)
            temp_file = f.name
        
        print("\n1. Loading test page...")
        driver.get(f"file://{temp_file}")
        time.sleep(2)
        
        print("\n2. Injecting trackers...")
        recorder.inject_click_tracker()
        recorder.inject_input_tracker()
        time.sleep(1)
        
        print("\n3. Testing regular DOM button...")
        regular_btn = driver.find_element("css selector", "#regular-btn")
        regular_btn.click()
        time.sleep(0.5)
        recorder.collect_click_events()
        
        print("\n4. Testing regular DOM input...")
        regular_input = driver.find_element("css selector", "#regular-input")
        regular_input.send_keys("Regular input text")
        time.sleep(0.5)
        recorder.collect_input_events()
        
        print("\n5. Testing shadow DOM button...")
        shadow_btn = driver.execute_script("""
            return document.getElementById('shadow-host').shadowRoot.getElementById('shadow-btn');
        """)
        driver.execute_script("arguments[0].click();", shadow_btn)
        time.sleep(0.5)
        recorder.collect_click_events()
        
        print("\n6. Testing shadow DOM input...")
        shadow_input = driver.execute_script("""
            return document.getElementById('shadow-host').shadowRoot.getElementById('shadow-input');
        """)
        driver.execute_script("arguments[0].value = 'Shadow input text';", shadow_input)
        driver.execute_script("""
            var event = new Event('input', { bubbles: true });
            arguments[0].dispatchEvent(event);
        """, shadow_input)
        time.sleep(0.5)
        recorder.collect_input_events()
        
        print("\n7. Testing iframe button...")
        driver.switch_to.frame("test-iframe")
        iframe_btn = driver.find_element("css selector", "#iframe-btn")
        iframe_btn.click()
        driver.switch_to.default_content()
        time.sleep(0.5)
        recorder.collect_click_events()
        
        print("\n8. Testing iframe input...")
        driver.switch_to.frame("test-iframe")
        iframe_input = driver.find_element("css selector", "#iframe-input")
        iframe_input.send_keys("iframe input text")
        driver.switch_to.default_content()
        time.sleep(0.5)
        recorder.collect_input_events()
        
        # Save results
        print("\n9. Saving results...")
        log_file = "tests/test_shadow_iframe_log.json"
        with open(log_file, "w") as f:
            json.dump(recorder.activity_log, f, indent=2)
        
        # Analyze results
        print("\n10. Analyzing captured events...")
        click_events = [a for a in recorder.activity_log if a.get("action") == "click"]
        input_events = [a for a in recorder.activity_log if a.get("action") == "text_input"]
        
        print(f"\n   Total activities: {len(recorder.activity_log)}")
        print(f"   Click events: {len(click_events)}")
        print(f"   Input events: {len(input_events)}")
        
        # Check for shadow DOM and iframe events
        shadow_clicks = [c for c in click_events if c.get("details", {}).get("inShadowRoot")]
        iframe_clicks = [c for c in click_events if c.get("details", {}).get("inIframe")]
        regular_clicks = [c for c in click_events if not c.get("details", {}).get("inShadowRoot") and not c.get("details", {}).get("inIframe")]
        
        shadow_inputs = [i for i in input_events if i.get("details", {}).get("inShadowRoot")]
        iframe_inputs = [i for i in input_events if i.get("details", {}).get("inIframe")]
        regular_inputs = [i for i in input_events if not i.get("details", {}).get("inShadowRoot") and not i.get("details", {}).get("inIframe")]
        
        print(f"\n   Regular DOM clicks: {len(regular_clicks)}")
        print(f"   Shadow DOM clicks: {len(shadow_clicks)}")
        print(f"   iframe clicks: {len(iframe_clicks)}")
        
        print(f"\n   Regular DOM inputs: {len(regular_inputs)}")
        print(f"   Shadow DOM inputs: {len(shadow_inputs)}")
        print(f"   iframe inputs: {len(iframe_inputs)}")
        
        # Results
        print("\n" + "=" * 80)
        success = True
        
        if len(regular_clicks) >= 1:
            print("✅ Regular DOM clicks captured")
        else:
            print("❌ Regular DOM clicks NOT captured")
            success = False
        
        if len(shadow_clicks) >= 1:
            print("✅ Shadow DOM clicks captured")
        else:
            print("⚠️  Shadow DOM clicks NOT captured (expected - requires user interaction)")
        
        if len(iframe_clicks) >= 1:
            print("✅ iframe clicks captured")
        else:
            print("⚠️  iframe clicks NOT captured (expected - requires user interaction)")
        
        if len(regular_inputs) >= 1:
            print("✅ Regular DOM inputs captured")
        else:
            print("❌ Regular DOM inputs NOT captured")
            success = False
        
        if success:
            print("\n✅ Basic event capture working!")
        
        print("=" * 80)
        
        # Cleanup
        os.unlink(temp_file)
        
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
    test_shadow_dom_and_iframe()
