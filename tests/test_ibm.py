"""
Test script to verify browser activity recording on IBM website
"""
from selenium import webdriver
import time

def test_ibm_website():
    print("Testing browser activity recorder on IBM website...")
    
    # Configure Chrome options
    options = webdriver.ChromeOptions()
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    driver = webdriver.Chrome(options=options)
    
    try:
        # Navigate to IBM
        print("Navigating to IBM website...")
        driver.get("https://www.ibm.com")
        time.sleep(3)
        
        # Test JavaScript injection
        print("\nTesting JavaScript injection capabilities...")
        
        # Test 1: Basic script execution
        try:
            result = driver.execute_script("return document.readyState;")
            print(f"✓ Basic script execution works: {result}")
        except Exception as e:
            print(f"✗ Basic script execution failed: {e}")
        
        # Test 2: Event listener injection
        try:
            script = """
            if (!window.testInjection) {
                window.testEvents = [];
                document.addEventListener('click', function(e) {
                    window.testEvents.push({clicked: true});
                }, true);
                window.testInjection = true;
            }
            return window.testInjection;
            """
            result = driver.execute_script(script)
            print(f"✓ Event listener injection: {'Success' if result else 'Failed'}")
        except Exception as e:
            print(f"✗ Event listener injection failed: {e}")
        
        # Test 3: Check for CSP headers
        try:
            csp = driver.execute_script("""
                var meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
                return meta ? meta.content : 'No CSP meta tag';
            """)
            print(f"Content Security Policy: {csp[:100] if csp else 'None'}")
        except Exception as e:
            print(f"Could not check CSP: {e}")
        
        # Test 4: Check if we can access active element
        try:
            active = driver.execute_script("return document.activeElement.tagName;")
            print(f"✓ Can access active element: {active}")
        except Exception as e:
            print(f"✗ Cannot access active element: {e}")
        
        print("\nTest completed! Press Ctrl+C to close browser...")
        time.sleep(30)
        
    except Exception as e:
        print(f"Error during testing: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    test_ibm_website()
