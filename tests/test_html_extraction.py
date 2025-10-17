#!/usr/bin/env python3
"""
Test HTML extraction for shadow DOM and iframe elements
"""

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
import sys

def create_test_page_with_shadow_dom():
    """Create an HTML page with shadow DOM elements"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Shadow DOM HTML Extraction Test</title>
        <style>
            body { font-family: Arial, sans-serif; padding: 20px; }
            .container { margin: 20px 0; padding: 20px; border: 2px solid #ccc; }
            h2 { color: #333; }
        </style>
    </head>
    <body>
        <h1>Shadow DOM HTML Extraction Test</h1>
        
        <!-- Regular DOM element -->
        <div class="container">
            <h2>Regular DOM Element</h2>
            <button id="regular-button" class="test-button">Regular Button</button>
        </div>
        
        <!-- Shadow DOM host -->
        <div class="container">
            <h2>Shadow DOM Element</h2>
            <div id="shadow-host"></div>
        </div>
        
        <!-- Iframe -->
        <div class="container">
            <h2>Iframe Element</h2>
            <iframe id="test-iframe" style="width: 100%; height: 150px; border: 1px solid #999;"></iframe>
        </div>
        
        <script>
            // Create shadow DOM
            const shadowHost = document.getElementById('shadow-host');
            const shadowRoot = shadowHost.attachShadow({mode: 'open'});
            
            shadowRoot.innerHTML = `
                <style>
                    .shadow-container {
                        padding: 10px;
                        background: #f0f0f0;
                        border: 1px solid #999;
                    }
                    .shadow-button {
                        padding: 10px 20px;
                        background: #4CAF50;
                        color: white;
                        border: none;
                        cursor: pointer;
                        font-size: 16px;
                    }
                </style>
                <div class="shadow-container">
                    <p>This content is inside a shadow DOM</p>
                    <button class="shadow-button" id="shadow-button">Shadow DOM Button</button>
                </div>
            `;
            
            // Create iframe content using srcdoc
            const iframe = document.getElementById('test-iframe');
            iframe.srcdoc = `
                <!DOCTYPE html>
                <html>
                <head>
                    <style>
                        body { font-family: Arial, sans-serif; padding: 20px; }
                        .iframe-button {
                            padding: 10px 20px;
                            background: #2196F3;
                            color: white;
                            border: none;
                            cursor: pointer;
                            font-size: 16px;
                        }
                    </style>
                </head>
                <body>
                    <p>This content is inside an iframe</p>
                    <button class="iframe-button" id="iframe-button">Iframe Button</button>
                </body>
                </html>
            `;
        </script>
    </body>
    </html>
    """
    return html_content


def test_html_extraction():
    """Test HTML extraction with shadow DOM and iframe support"""
    print("\n" + "="*80)
    print("SHADOW DOM & IFRAME HTML EXTRACTION TEST")
    print("="*80 + "\n")
    
    # Set up Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--headless')
    
    driver = None
    import tempfile
    import os
    
    try:
        # Initialize driver
        print("[TEST] Initializing Chrome WebDriver...")
        driver = webdriver.Chrome(options=chrome_options)
        
        # Create temporary HTML file
        html_content = create_test_page_with_shadow_dom()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            temp_file = f.name
        
        print(f"[TEST] Created temporary file: {temp_file}")
        
        # Load the file
        driver.get(f"file://{temp_file}")
        time.sleep(3)  # Wait for page to load and scripts to execute
        
        # Verify page is loaded
        page_ready = driver.execute_script("""
            return document.readyState === 'complete' && 
                   document.getElementById('regular-button') !== null;
        """)
        print(f"[TEST] Page ready: {page_ready}")
        
        if not page_ready:
            print("[TEST] ⚠️  Waiting for page to fully load...")
            time.sleep(2)
        
        print("[TEST] ✓ Test page loaded\n")
        
        # Test 1: Regular DOM element
        print("[TEST 1] Testing Regular DOM HTML extraction...")
        regular_html = driver.execute_script("""
            var element = document.querySelector("#regular-button");
            console.log('Regular button element:', element);
            return element ? element.outerHTML : null;
        """)
        
        if regular_html and 'Regular Button' in regular_html:
            print(f"[TEST 1] ✓ Regular DOM HTML extracted successfully")
            print(f"         HTML: {regular_html[:100]}...")
        else:
            print(f"[TEST 1] ✗ Failed to extract regular DOM HTML")
            print(f"         Got: {regular_html}")
        
        # Test 2: Shadow DOM element
        print("\n[TEST 2] Testing Shadow DOM HTML extraction...")
        shadow_html = driver.execute_script("""
            // Recursive shadow DOM search for CSS selector
            function findInShadowDOM(root, selector) {
                // Try to find in current root
                let element = root.querySelector(selector);
                if (element) return element;
                
                // Search in all shadow roots
                let allElements = root.querySelectorAll('*');
                for (let el of allElements) {
                    if (el.shadowRoot) {
                        element = findInShadowDOM(el.shadowRoot, selector);
                        if (element) return element;
                    }
                }
                return null;
            }
            
            let element = findInShadowDOM(document, ".shadow-button");
            return element ? element.outerHTML : null;
        """)
        
        if shadow_html and 'Shadow DOM Button' in shadow_html:
            print(f"[TEST 2] ✓ Shadow DOM HTML extracted successfully")
            print(f"         HTML: {shadow_html[:100]}...")
        else:
            print(f"[TEST 2] ✗ Failed to extract shadow DOM HTML")
            print(f"         Got: {shadow_html}")
        
        # Test 3: Iframe element
        print("\n[TEST 3] Testing Iframe HTML extraction...")
        
        # Wait for iframe to be fully loaded
        time.sleep(2)
        
        # Debug iframe loading
        iframe_info = driver.execute_script("""
            let iframe = document.getElementById('test-iframe');
            if (!iframe) return {error: 'Iframe not found'};
            
            try {
                let iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                let button = iframeDoc.querySelector('.iframe-button');
                return {
                    iframeFound: true,
                    iframeLoaded: iframeDoc.readyState === 'complete',
                    buttonFound: button !== null,
                    buttonHTML: button ? button.outerHTML : null
                };
            } catch (e) {
                return {error: e.toString()};
            }
        """)
        print(f"[TEST 3] Iframe debug info: {iframe_info}")
        
        iframe_html = driver.execute_script("""
            // Search in all iframes for CSS selector
            function findInIframes(selector) {
                // Try main document first
                let element = document.querySelector(selector);
                if (element) return element.outerHTML;
                
                // Search in all iframes
                let iframes = document.querySelectorAll('iframe');
                console.log('Found iframes:', iframes.length);
                
                for (let iframe of iframes) {
                    try {
                        let iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                        console.log('Iframe doc:', iframeDoc);
                        element = iframeDoc.querySelector(selector);
                        console.log('Found element in iframe:', element);
                        if (element) return element.outerHTML;
                    } catch (e) {
                        // Cross-origin iframe, skip
                        console.log('Error accessing iframe:', e);
                    }
                }
                return null;
            }
            
            return findInIframes(".iframe-button");
        """)
        
        if iframe_html and 'Iframe Button' in iframe_html:
            print(f"[TEST 3] ✓ Iframe HTML extracted successfully")
            print(f"         HTML: {iframe_html[:100]}...")
        else:
            print(f"[TEST 3] ✗ Failed to extract iframe HTML")
            print(f"         Got: {iframe_html}")
        
        # Summary
        print("\n" + "="*80)
        tests_passed = 0
        if regular_html and 'Regular Button' in regular_html:
            tests_passed += 1
        if shadow_html and 'Shadow DOM Button' in shadow_html:
            tests_passed += 1
        if iframe_html and 'Iframe Button' in iframe_html:
            tests_passed += 1
        
        print(f"RESULTS: {tests_passed}/3 tests passed")
        
        if tests_passed == 3:
            print("✅ SUCCESS: All HTML extraction methods working!")
            print("="*80 + "\n")
            return True
        else:
            print("⚠️  PARTIAL: Some HTML extraction methods failed")
            print("="*80 + "\n")
            return False
            
    except Exception as e:
        print(f"\n[ERROR] Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        if driver:
            driver.quit()
            print("[TEST] WebDriver closed")
        
        # Clean up temp file
        try:
            if 'temp_file' in locals():
                os.unlink(temp_file)
                print(f"[TEST] Cleaned up temporary file")
        except:
            pass


if __name__ == "__main__":
    success = test_html_extraction()
    sys.exit(0 if success else 1)
