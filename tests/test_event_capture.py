"""
Advanced test to verify actual event capture on IBM website
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

def test_event_capture():
    print("Testing actual event capture on IBM website...")
    
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
        time.sleep(5)  # Wait for page to fully load
        
        # Inject our tracking script
        print("\n1. Injecting click tracker...")
        script = """
        if (!window.clickTrackerInjected) {
            window.clickEvents = [];
            window.lastClickTime = 0;
            document.addEventListener('click', function(e) {
                var element = e.target;
                var now = Date.now();
                if (now - window.lastClickTime < 100) return;
                window.lastClickTime = now;
                
                var clickData = {
                    tagName: element.tagName,
                    id: element.id || '',
                    className: element.className || '',
                    text: element.innerText ? element.innerText.substring(0, 50) : '',
                    href: element.href || '',
                    timestamp: new Date().toISOString()
                };
                window.clickEvents.push(clickData);
                console.log('Click captured:', clickData);
            }, true);
            window.clickTrackerInjected = true;
        }
        return window.clickTrackerInjected;
        """
        result = driver.execute_script(script)
        print(f"   Tracker injected: {result}")
        
        # Wait a bit
        time.sleep(2)
        
        # Try to find and click something
        print("\n2. Looking for clickable elements...")
        try:
            # Try to find links
            links = driver.find_elements(By.TAG_NAME, "a")
            print(f"   Found {len(links)} links")
            
            if len(links) > 0:
                # Try to click the first visible link
                for link in links[:10]:
                    try:
                        if link.is_displayed() and link.is_enabled():
                            print(f"\n3. Clicking on element: {link.text[:50]}")
                            link.click()
                            time.sleep(2)
                            break
                    except:
                        continue
        except Exception as e:
            print(f"   Could not click: {e}")
        
        # Check if clicks were captured
        print("\n4. Checking captured events...")
        time.sleep(1)
        
        try:
            clicks = driver.execute_script("return window.clickEvents || [];")
            print(f"   Total clicks captured: {len(clicks)}")
            
            if clicks:
                print("\n   Captured events:")
                for i, click in enumerate(clicks[:5]):  # Show first 5
                    print(f"   [{i+1}] {click['tagName']} - {click['text'][:30]}")
            else:
                print("   ⚠️  NO CLICKS CAPTURED!")
                
                # Debug: Check if tracker is still there
                still_injected = driver.execute_script("return window.clickTrackerInjected;")
                print(f"   Tracker still injected: {still_injected}")
                
                # Debug: Check current URL (might have navigated)
                print(f"   Current URL: {driver.current_url}")
                
                # Debug: Try manual click detection
                print("\n5. Attempting manual click simulation...")
                driver.execute_script("""
                    var event = new MouseEvent('click', {
                        view: window,
                        bubbles: true,
                        cancelable: true
                    });
                    document.body.dispatchEvent(event);
                """)
                time.sleep(1)
                
                clicks = driver.execute_script("return window.clickEvents || [];")
                print(f"   After manual simulation: {len(clicks)} clicks")
                
        except Exception as e:
            print(f"   Error checking events: {e}")
        
        print("\n" + "="*60)
        print("Test completed! Analysis:")
        print("="*60)
        
        # Final analysis
        if clicks and len(clicks) > 0:
            print("✅ Event capture is WORKING")
        else:
            print("❌ Event capture is NOT WORKING")
            print("\nPossible reasons:")
            print("1. Page navigation removed our tracker (SPA behavior)")
            print("2. Click happened on iframe or shadow DOM")
            print("3. Event bubbling was stopped by website's code")
            print("4. Page uses custom click handlers that prevent default")
        
        print("\nPress Ctrl+C to close browser...")
        time.sleep(30)
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
    finally:
        driver.quit()

if __name__ == "__main__":
    test_event_capture()
