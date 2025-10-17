#!/usr/bin/env python3
"""
Test replay with shadow DOM and iframe support
This verifies that the executor can now replay actions from shadow DOM and iframes
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from main import BrowserActivityRecorder
from activity_executor import ActivityExecutor
import time
import json

def test_replay_shadow_dom():
    """Test that executor can replay shadow DOM actions"""
    
    print("=" * 80)
    print("Testing Replay with Shadow DOM and iframe Support")
    print("=" * 80)
    
    # Setup Chrome
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Create test HTML with shadow DOM
    test_html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Shadow DOM Replay Test</title>
        <style>
            button { margin: 10px; padding: 10px 20px; }
            input { margin: 10px; padding: 5px; }
            #result { margin: 20px; padding: 10px; border: 1px solid green; }
        </style>
    </head>
    <body>
        <h1>Shadow DOM Replay Test</h1>
        
        <h2>Regular DOM</h2>
        <button id="regular-btn" onclick="showResult('Regular button clicked')">Regular Button</button>
        
        <h2>Shadow DOM</h2>
        <div id="shadow-host"></div>
        
        <div id="result"></div>
        
        <script>
            function showResult(msg) {
                document.getElementById('result').innerHTML = '<p>' + msg + '</p>';
            }
            
            // Create shadow DOM
            const shadowHost = document.getElementById('shadow-host');
            const shadowRoot = shadowHost.attachShadow({mode: 'open'});
            
            shadowRoot.innerHTML = `
                <style>
                    button { background: purple; color: white; margin: 10px; padding: 10px; }
                    input { margin: 10px; padding: 5px; }
                </style>
                <button id="shadow-btn">Shadow DOM Button</button>
                <input type="text" id="shadow-input" name="shadow-field" placeholder="Shadow DOM input">
            `;
            
            shadowRoot.getElementById('shadow-btn').onclick = function() {
                document.getElementById('result').innerHTML = '<p>Shadow DOM button clicked!</p>';
            };
            
            shadowRoot.getElementById('shadow-input').oninput = function(e) {
                document.getElementById('result').innerHTML = '<p>Shadow input: ' + e.target.value + '</p>';
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
    
    url = f"file://{temp_file}"
    
    print("\n=== PHASE 1: RECORDING ===")
    
    # Record activities
    driver1 = webdriver.Chrome(options=chrome_options)
    recorder = BrowserActivityRecorder(driver1)
    
    try:
        print("\n1. Loading test page...")
        driver1.get(url)
        time.sleep(2)
        
        print("\n2. Injecting trackers...")
        recorder.inject_click_tracker()
        recorder.inject_input_tracker()
        time.sleep(1)
        
        print("\n3. Recording: Click regular button...")
        regular_btn = driver1.find_element("css selector", "#regular-btn")
        regular_btn.click()
        time.sleep(0.5)
        recorder.collect_click_events()
        
        print("\n4. Recording: Click shadow DOM button...")
        shadow_btn = driver1.execute_script("""
            return document.getElementById('shadow-host').shadowRoot.getElementById('shadow-btn');
        """)
        driver1.execute_script("arguments[0].click();", shadow_btn)
        time.sleep(0.5)
        recorder.collect_click_events()
        
        print("\n5. Recording: Type in shadow DOM input...")
        shadow_input = driver1.execute_script("""
            return document.getElementById('shadow-host').shadowRoot.getElementById('shadow-input');
        """)
        driver1.execute_script("arguments[0].value = 'Test from shadow';", shadow_input)
        driver1.execute_script("""
            var event = new Event('input', { bubbles: true });
            arguments[0].dispatchEvent(event);
        """, shadow_input)
        time.sleep(0.5)
        recorder.collect_input_events()
        
        # Save activity log
        print("\n6. Saving activity log...")
        log_file = "tests/test_shadow_replay_log.json"
        with open(log_file, "w") as f:
            json.dump(recorder.activity_log, f, indent=2)
        
        print(f"\n✓ Recorded {len(recorder.activity_log)} activities")
        
        # Show what was recorded
        for i, activity in enumerate(recorder.activity_log, 1):
            action = activity.get('action')
            details = activity.get('details', {})
            in_shadow = details.get('inShadowRoot', False)
            tag = details.get('tagName', 'N/A')
            print(f"   {i}. {action} - {tag} - inShadow: {in_shadow}")
        
    finally:
        driver1.quit()
    
    print("\n=== PHASE 2: REPLAY ===")
    
    # Replay activities
    driver2 = webdriver.Chrome(options=chrome_options)
    executor = ActivityExecutor(driver2)
    
    try:
        # Load activities
        with open(log_file, "r") as f:
            activities = json.load(f)
        
        # Navigate to page first (simulate navigation)
        print("\n1. Navigating to test page...")
        driver2.get(url)
        time.sleep(2)
        
        # Replay activities
        results = []
        for i, activity in enumerate(activities, 1):
            action = activity.get('action')
            details = activity.get('details', {})
            in_shadow = details.get('inShadowRoot', False)
            
            print(f"\n{i}. Replaying: {action} (inShadow: {in_shadow})...")
            
            result = executor.execute_activity(activity)
            results.append(result)
            
            if result['success']:
                print(f"   ✓ Success (method: {result['method']})")
            else:
                print(f"   ✗ Failed: {result['error']}")
        
        # Analyze results
        print("\n=== RESULTS ===")
        total = len(results)
        success = sum(1 for r in results if r['success'])
        failed = total - success
        
        print(f"\nTotal actions: {total}")
        print(f"Successful: {success} ({success/max(total, 1)*100:.1f}%)")
        print(f"Failed: {failed} ({failed/max(total, 1)*100:.1f}%)")
        
        # Check shadow DOM actions specifically
        shadow_actions = [a for a in activities if a.get('details', {}).get('inShadowRoot')]
        shadow_results = [r for i, r in enumerate(results) if activities[i].get('details', {}).get('inShadowRoot')]
        shadow_success = sum(1 for r in shadow_results if r['success'])
        
        print(f"\nShadow DOM actions: {len(shadow_actions)}")
        print(f"Shadow DOM successful: {shadow_success} ({shadow_success/max(len(shadow_actions), 1)*100:.1f}%)")
        
        print("\n" + "=" * 80)
        if success == total and shadow_success == len(shadow_actions):
            print("✅ SUCCESS: All actions replayed successfully!")
            print("✅ Shadow DOM support is working!")
        elif shadow_success > 0:
            print("⚠️  PARTIAL: Some shadow DOM actions succeeded")
        else:
            print("❌ FAILED: Shadow DOM actions not working")
        print("=" * 80)
        
        # Cleanup
        os.unlink(temp_file)
        
    finally:
        driver2.quit()

if __name__ == "__main__":
    test_replay_shadow_dom()
