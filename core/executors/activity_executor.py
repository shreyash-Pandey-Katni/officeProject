"""
Activity Executor - Executes browser actions from recorded activities
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from typing import Dict, Any, Optional, List, Tuple
from core.locators.element_finder import VisualElementFinder
from llm_helpers import OllamaVLM
from core.locators.element_locator import ElementLocator
from core.analyzers.assertions import Assertion
from logging_config import setup_logger, log_exception
import time
import os

# Setup logger
logger = setup_logger('executor', 'executor.log')

# Phase 2: VLM imports (optional - graceful degradation if Ollama not available)
try:
    from core.locators.vlm_element_finder import VLMElementFinder
    from core.analyzers.intelligent_failure_analyzer import IntelligentFailureAnalyzer
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False
    print("[INFO] VLM modules not available - will use traditional methods only")


class ActivityExecutor:
    """Execute recorded browser activities with screenshot capture"""
    
    def __init__(self, driver: webdriver.Chrome, screenshots_dir: str = "replay_screenshots"):
        self.driver = driver
        self.finder = VisualElementFinder(driver)
        self.vlm = OllamaVLM(model="granite3.2-vision")  # For loading detection
        self.screenshots_dir = screenshots_dir
        self.step_counter = 0
        self.use_enhanced_locators = True  # Enable multi-strategy locators
        self.assertions: List[Assertion] = []  # Assertions to check after step
        # Basic locator + iframe context placeholders used by some helper methods
        self.element_locator = ElementLocator("generic")
        self.current_iframe_context = None
        
        # Create screenshots directory
        os.makedirs(screenshots_dir, exist_ok=True)
        
        # Track iframe context
        self.current_iframe = None
        
        # Phase 2: Initialize VLM components (optional - graceful degradation)
        self.vlm_finder = None
        self.failure_analyzer = None
        self.vlm_enabled = False
        
        if VLM_AVAILABLE:
            try:
                # Test Ollama connection before initializing
                import requests
                response = requests.get("http://localhost:11434/api/tags", timeout=2)
                if response.status_code == 200:
                    self.vlm_finder = VLMElementFinder()
                    self.failure_analyzer = IntelligentFailureAnalyzer()
                    self.vlm_enabled = True
                    print("[INFO] ✓ VLM features enabled (Ollama + Granite)")
                else:
                    print("[INFO] Ollama not responding - VLM features disabled")
            except Exception as e:
                print(f"[INFO] VLM features disabled: {e}")
        
        # Track failure analysis results
        self.last_failure_analysis = None

    def _ensure_window_context(self, activity: Dict[str, Any]):
        """Switch to the window/tab recorded for this activity if metadata present."""
        try:
            target_handle = activity.get('window_handle')
            target_index = activity.get('tab_index')
            handles = self.driver.window_handles
            # Prefer handle match
            if target_handle and target_handle in handles:
                if self.driver.current_window_handle != target_handle:
                    self.driver.switch_to.window(target_handle)
                return
            # Fallback to index
            if target_index is not None and isinstance(target_index, int):
                if 0 <= target_index < len(handles):
                    if self.driver.current_window_handle != handles[target_index]:
                        self.driver.switch_to.window(handles[target_index])
        except Exception:
            pass
    
    def _create_locator_from_details(self, details: Dict[str, Any]) -> ElementLocator:
        """Create ElementLocator from activity details with locators field"""
        locators_data = details.get('locators', {})
        
        # Create description
        tag_name = details.get('tagName', 'element')
        text = details.get('text', '')
        description = f"{tag_name}"
        if text:
            description += f" with text '{text[:30]}'"
        
        locator = ElementLocator(description)
        
        # Add strategies from locators data
        if locators_data.get('id'):
            locator.add_id(locators_data['id'])
        
        if locators_data.get('name'):
            locator.add_name(locators_data['name'])
        
        if locators_data.get('class'):
            locator.add_class(locators_data['class'])
        
        if locators_data.get('css_selector'):
            locator.add_css(locators_data['css_selector'])
        
        if locators_data.get('xpath'):
            locator.add_xpath(locators_data['xpath'])
        
        if locators_data.get('text'):
            locator.add_text(locators_data['text'])
        
        if locators_data.get('placeholder'):
            locator.add_strategy('css', f'[placeholder="{locators_data["placeholder"]}"]')
        
        if locators_data.get('aria_label'):
            locator.add_strategy('css', f'[aria-label="{locators_data["aria_label"]}"]')
        
        if locators_data.get('label'):
            # Try to find input by associated label
            locator.add_xpath(f"//label[contains(text(), '{locators_data['label']}')]/following-sibling::input")
        
        if locators_data.get('coordinates'):
            coords = locators_data['coordinates']
            if coords.get('x') is not None and coords.get('y') is not None:
                locator.add_coordinates(int(coords['x']), int(coords['y']))
        
        # Add visual context
        locator.set_visual_context({
            'in_shadow_root': locators_data.get('in_shadow_root', False),
            'in_iframe': locators_data.get('in_iframe', False),
            'tag_name': tag_name
        })
        
        return locator
    
    def _traverse_dom_path(self, dom_path: List[Dict[str, Any]]) -> Optional[Any]:
        """
        Traverse the DOM path array to find the target element.
        DOM path format: [
            {"type": "iframe", "selector": "...", "index": 0},
            {"type": "shadow", "host": "...", "hostSelector": "..."},
            {"type": "element", "selector": "...", "xpath": "..."}
        ]
        """
        if not dom_path:
            return None
            
        print(f"[EXECUTOR] Traversing DOM path with {len(dom_path)} steps...")
        
        # Reset to top-level context
        try:
            self.driver.switch_to.default_content()
        except Exception:
            pass
        
        current_root = self.driver
        
        for i, path_step in enumerate(dom_path):
            step_type = path_step.get('type')
            
            if step_type == 'iframe':
                # Switch to iframe
                try:
                    selector = path_step.get('selector')
                    index = path_step.get('index', 0)
                    iframe_id = path_step.get('id')
                    iframe_name = path_step.get('name')
                    
                    print(f"[EXECUTOR] Step {i+1}: Switching to iframe (selector: {selector}, index: {index})")
                    
                    # Try multiple methods to find iframe
                    iframe_element = None
                    if iframe_id:
                        try:
                            iframe_element = self.driver.find_element(By.ID, iframe_id)
                        except Exception:
                            pass
                    
                    if not iframe_element and iframe_name:
                        try:
                            iframe_element = self.driver.find_element(By.NAME, iframe_name)
                        except Exception:
                            pass
                    
                    if not iframe_element and selector:
                        try:
                            iframe_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        except Exception:
                            pass
                    
                    if not iframe_element and isinstance(index, int):
                        try:
                            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
                            if 0 <= index < len(iframes):
                                iframe_element = iframes[index]
                        except Exception:
                            pass
                    
                    if iframe_element:
                        self.driver.switch_to.frame(iframe_element)
                        print(f"[EXECUTOR] ✓ Switched to iframe")
                    else:
                        print(f"[EXECUTOR] ✗ Failed to find iframe")
                        return None
                        
                except Exception as e:
                    print(f"[EXECUTOR] ✗ Failed to switch to iframe: {e}")
                    return None
                    
            elif step_type == 'shadow':
                # Access shadow DOM
                try:
                    host_selector = path_step.get('hostSelector')
                    print(f"[EXECUTOR] Step {i+1}: Accessing shadow DOM (host: {host_selector})")
                    
                    # Find the shadow host element
                    shadow_host = self.driver.find_element(By.CSS_SELECTOR, host_selector)
                    
                    # Access shadow root via JavaScript
                    shadow_root = self.driver.execute_script("return arguments[0].shadowRoot", shadow_host)
                    
                    if shadow_root:
                        # Store shadow root reference for next steps
                        current_root = shadow_root
                        print(f"[EXECUTOR] ✓ Accessed shadow DOM")
                    else:
                        print(f"[EXECUTOR] ✗ Shadow root not found")
                        return None
                        
                except Exception as e:
                    print(f"[EXECUTOR] ✗ Failed to access shadow DOM: {e}")
                    return None
                    
            elif step_type == 'element':
                # Find the target element
                try:
                    selector = path_step.get('selector')
                    xpath = path_step.get('xpath')
                    element_id = path_step.get('id')
                    
                    print(f"[EXECUTOR] Step {i+1}: Finding target element (selector: {selector})")
                    
                    element = None
                    
                    # If we're in a shadow root, use JavaScript to query
                    if current_root != self.driver:
                        if selector:
                            element = self.driver.execute_script(
                                "return arguments[0].querySelector(arguments[1])", 
                                current_root, 
                                selector
                            )
                    else:
                        # Standard document queries
                        if element_id:
                            try:
                                element = self.driver.find_element(By.ID, element_id)
                            except Exception:
                                pass
                        
                        if not element and selector:
                            try:
                                element = self.driver.find_element(By.CSS_SELECTOR, selector)
                            except Exception:
                                pass
                        
                        if not element and xpath:
                            try:
                                element = self.driver.find_element(By.XPATH, xpath)
                            except Exception:
                                pass
                    
                    if element:
                        print(f"[EXECUTOR] ✓ Found target element")
                        return element
                    else:
                        print(f"[EXECUTOR] ✗ Target element not found")
                        return None
                        
                except Exception as e:
                    print(f"[EXECUTOR] ✗ Failed to find element: {e}")
                    return None
        
        return None
    
    def _find_element_in_shadow_dom(self, details: Dict[str, Any], max_retries: int = 3) -> Optional[Any]:
        """Find element inside shadow DOM using JavaScript with retry logic"""
        try:
            # Get element properties for matching
            tag_name = details.get('tagName', '').upper()
            elem_id = details.get('id', '')
            elem_name = details.get('name', '')
            placeholder = details.get('placeholder', '')
            elem_type = details.get('type', '')
            
            print(f"[EXECUTOR] Searching for {tag_name} in shadow DOM (name='{elem_name}', placeholder='{placeholder}')")
            
            # JavaScript to recursively search shadow DOMs with debug logging
            script = """
            function findInShadowRoots(root, criteria, debug) {
                // Search current root
                let elements = root.querySelectorAll('*');
                
                if (debug) {
                    console.log('Searching in root, found', elements.length, 'elements');
                }
                
                for (let elem of elements) {
                    // Check if element matches criteria
                    if (elem.tagName === criteria.tagName) {
                        if (debug) {
                            console.log('Found matching tag:', elem.tagName, 
                                'id:', elem.id, 
                                'name:', elem.name, 
                                'placeholder:', elem.placeholder,
                                'type:', elem.type);
                        }
                        
                        let matches = true;
                        
                        if (criteria.id && elem.id !== criteria.id) matches = false;
                        if (criteria.name && elem.name !== criteria.name) matches = false;
                        if (criteria.placeholder && elem.placeholder !== criteria.placeholder) matches = false;
                        if (criteria.type && elem.type !== criteria.type) matches = false;
                        
                        if (matches) {
                            if (debug) console.log('✓ Element matches all criteria!');
                            return elem;
                        }
                    }
                    
                    // Recursively search nested shadow roots
                    if (elem.shadowRoot) {
                        if (debug) {
                            console.log('Found shadow root in:', elem.tagName);
                        }
                        let found = findInShadowRoots(elem.shadowRoot, criteria, debug);
                        if (found) return found;
                    }
                }
                return null;
            }
            
            return findInShadowRoots(document, arguments[0], arguments[1]);
            """
            
            criteria = {
                'tagName': tag_name,
                'id': elem_id,
                'name': elem_name,
                'placeholder': placeholder,
                'type': elem_type
            }
            
            # Retry logic with waits for dynamically loaded shadow DOM content
            element = None
            for attempt in range(max_retries):
                # Enable debug logging on last attempt
                debug = (attempt == max_retries - 1)
                element = self.driver.execute_script(script, criteria, debug)
                
                if element:
                    print(f"[EXECUTOR] ✓ Found {tag_name} in shadow DOM")
                    return element
                
                if attempt < max_retries - 1:
                    wait_time = 0.5 * (attempt + 1)  # Progressive wait: 0.5s, 1s, 1.5s
                    print(f"[EXECUTOR] Element not found, waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
            
            print(f"[EXECUTOR] ✗ Element not found in any shadow root after {max_retries} attempts")
            
            # Debug: Show what INPUT elements exist in shadow DOM
            try:
                debug_script = """
                function getAllInputs(root, depth=0, results=[]) {
                    let elements = root.querySelectorAll('input');
                    for (let elem of elements) {
                        results.push({
                            depth: depth,
                            name: elem.name || '',
                            placeholder: elem.placeholder || '',
                            type: elem.type || '',
                            id: elem.id || '',
                            visible: elem.offsetParent !== null
                        });
                    }
                    
                    // Search nested shadow roots
                    let allElements = root.querySelectorAll('*');
                    for (let elem of allElements) {
                        if (elem.shadowRoot) {
                            getAllInputs(elem.shadowRoot, depth + 1, results);
                        }
                    }
                    return results;
                }
                return getAllInputs(document);
                """
                all_inputs = self.driver.execute_script(debug_script)
                if all_inputs:
                    print(f"[EXECUTOR] DEBUG: Found {len(all_inputs)} INPUT elements in shadow DOM:")
                    for inp in all_inputs[:5]:  # Show first 5
                        print(f"[EXECUTOR]   - name='{inp['name']}', placeholder='{inp['placeholder']}', type='{inp['type']}', visible={inp['visible']}")
                else:
                    print(f"[EXECUTOR] DEBUG: No INPUT elements found in any shadow root")
            except Exception as debug_e:
                print(f"[EXECUTOR] DEBUG: Could not list inputs: {debug_e}")
            
            return None
                
        except Exception as e:
            print(f"[EXECUTOR] Shadow DOM search error: {e}")
            return None
    
    def _find_element_in_iframe(self, details: Dict[str, Any]) -> Optional[Any]:
        """Find element inside iframe"""
        try:
            iframe_index = details.get('iframeIndex', 0)
            
            print(f"[EXECUTOR] Searching in iframe #{iframe_index}")
            
            # Get all iframes
            iframes = self.driver.find_elements(By.TAG_NAME, 'iframe')
            
            if iframe_index >= len(iframes):
                print(f"[EXECUTOR] ✗ iframe index {iframe_index} out of range (found {len(iframes)} iframes)")
                return None
            
            # Switch to iframe
            self.driver.switch_to.frame(iframes[iframe_index])
            self.current_iframe = iframe_index
            
            # Try to find element in iframe using standard methods
            tag_name = details.get('tagName', '').lower()
            elem_id = details.get('id', '')
            elem_name = details.get('name', '')
            
            element = None
            
            # Try by ID
            if elem_id:
                try:
                    element = self.driver.find_element(By.ID, elem_id)
                    if element:
                        print(f"[EXECUTOR] ✓ Found {tag_name} in iframe by ID")
                        return element
                except Exception:
                    pass
            
            # Try by name
            if elem_name:
                try:
                    element = self.driver.find_element(By.NAME, elem_name)
                    if element:
                        print(f"[EXECUTOR] ✓ Found {tag_name} in iframe by name")
                        return element
                except Exception:
                    pass
            
            # Try by tag name
            try:
                elements = self.driver.find_elements(By.TAG_NAME, tag_name)
                if elements:
                    # Find the best match
                    for elem in elements:
                        if elem_id and elem.get_attribute('id') == elem_id:
                            element = elem
                            break
                        if elem_name and elem.get_attribute('name') == elem_name:
                            element = elem
                            break
                    
                    if not element and elements:
                        element = elements[0]  # Use first match
                    
                    if element:
                        print(f"[EXECUTOR] ✓ Found {tag_name} in iframe by tag name")
                        return element
            except Exception:
                pass
            
            print(f"[EXECUTOR] ✗ Element not found in iframe")
            return None
            
        except Exception as e:
            print(f"[EXECUTOR] iframe search error: {e}")
            # Try to switch back to default content
            try:
                self.driver.switch_to.default_content()
                self.current_iframe = None
            except Exception:
                pass
            return None
    
    def _switch_back_from_iframe(self):
        """Switch back to main content from iframe"""
        try:
            if self.current_iframe is not None:
                self.driver.switch_to.default_content()
                self.current_iframe = None
        except Exception:
            pass
    
    def _wait_for_page_ready(self, timeout: int = 15) -> bool:
        """
        Wait for page to finish loading using fast JavaScript checks
        Only uses VLM as last resort if uncertain
        Returns True if page is ready, False if timeout
        """
        print("[EXECUTOR] Checking if page is loading...")
        start_time = time.time()
        stable_count = 0
        required_stable = 2  # Need 2 consecutive stable checks
        
        while (time.time() - start_time) < timeout:
            try:
                # Fast multi-layer check (same as recorder)
                is_loading, reason = self._quick_loading_check()
                
                if not is_loading:
                    stable_count += 1
                    if stable_count >= required_stable:
                        print("[EXECUTOR] ✓ Page is fully loaded and ready")
                        return True
                else:
                    stable_count = 0  # Reset if loading detected
                    print(f"[EXECUTOR] Page still loading... ({reason})")
                
                time.sleep(0.5)  # Check every 500ms
                    
            except Exception as e:
                print(f"[EXECUTOR] Warning: Loading check failed: {e}")
                # Assume ready on error (better than blocking)
                return True
        
        # Timeout - assume page is ready (better than blocking indefinitely)
        print(f"[EXECUTOR] Timeout reached, assuming page ready")
        return True
    
    def _quick_loading_check(self):
        """
        Fast combined loading check (under 100ms)
        Uses same logic as recorder's enhanced detection
        Returns: (is_loading: bool, reason: str)
        """
        try:
            # Check 1: Document ready state (1ms)
            doc_state = self.driver.execute_script("return document.readyState;")
            if doc_state != "complete":
                return True, f"document.readyState = '{doc_state}'"
            
            # Check 2: Network activity (5ms)
            network_info = self.driver.execute_script("""
                let reasons = [];
                
                // Check for active fetch/XHR requests
                if (window._networkTracker && window._networkTracker.pendingRequests > 0) {
                    reasons.push('Active fetch/XHR: ' + window._networkTracker.pendingRequests);
                }
                
                // Check Performance API
                let inProgress = window.performance.getEntriesByType('resource')
                    .filter(r => r.duration === 0 || (performance.now() - r.startTime) < 50);
                
                if (inProgress.length > 0) {
                    reasons.push('Resources loading: ' + inProgress.length);
                }
                
                // Check jQuery if present
                if (window.jQuery && jQuery.active > 0) {
                    reasons.push('jQuery.active: ' + jQuery.active);
                }
                
                return reasons.length > 0 ? reasons.join(', ') : null;
            """)
            
            if network_info:
                return True, f"Network activity - {network_info}"
            
            # Check 3: DOM mutations (10ms)
            mutation_info = self.driver.execute_script("""
                if (!window._loadingObserver) return null;
                
                let now = Date.now();
                let timeSinceLastMutation = now - (window._lastMutationTime || 0);
                
                // If mutations happened in last 200ms, consider loading
                if (timeSinceLastMutation < 200) {
                    return 'DOM mutations ' + timeSinceLastMutation + 'ms ago';
                }
                return null;
            """)
            
            if mutation_info:
                return True, mutation_info
            
            # Check 4: Visible loaders (20ms - faster version)
            loader_info = self.driver.execute_script("""
                // Helper function to check if element is truly visible
                function isElementVisible(el) {
                    // Must have dimensions
                    if (el.offsetWidth <= 0 || el.offsetHeight <= 0) {
                        return false;
                    }
                    
                    // Must be in document and have offsetParent (not display:none)
                    if (!el.offsetParent && el.tagName !== 'BODY' && el.tagName !== 'HTML') {
                        return false;
                    }
                    
                    // Check computed style
                    let style = window.getComputedStyle(el);
                    
                    // Display check
                    if (style.display === 'none') {
                        return false;
                    }
                    
                    // Visibility check
                    if (style.visibility === 'hidden' || style.visibility === 'collapse') {
                        return false;
                    }
                    
                    // Opacity check - consider < 0.1 as invisible
                    let opacity = parseFloat(style.opacity);
                    if (opacity < 0.1) {
                        return false;
                    }
                    
                    // Check if element is in viewport or at least rendered
                    let rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) {
                        return false;
                    }
                    
                    // Check if element is off-screen (negative positioning)
                    if (rect.right < 0 || rect.bottom < 0) {
                        return false;
                    }
                    
                    // Check for clip-path or clip that hides the element
                    if (style.clip && style.clip !== 'auto' && style.clip.includes('rect(0')) {
                        return false;
                    }
                    
                    // Check ALL parent elements up to body/html for hidden properties
                    let parent = el.parentElement;
                    while (parent && parent.tagName !== 'BODY' && parent.tagName !== 'HTML') {
                        let parentStyle = window.getComputedStyle(parent);
                        
                        // Check if parent is hidden in any way
                        if (parentStyle.display === 'none') {
                            return false;
                        }
                        
                        if (parentStyle.visibility === 'hidden' || parentStyle.visibility === 'collapse') {
                            return false;
                        }
                        
                        let parentOpacity = parseFloat(parentStyle.opacity);
                        if (parentOpacity < 0.1) {
                            return false;
                        }
                        
                        // Check if parent has zero dimensions (collapsed)
                        if (parent.offsetWidth === 0 || parent.offsetHeight === 0) {
                            return false;
                        }
                        
                        parent = parent.parentElement;
                    }
                    
                    return true;
                }
                
                // Quick check for most common loading indicators
                const loadingSelectors = [
                    '[class*="loading"]',
                    '[class*="spinner"]', 
                    '[class*="loader"]',
                    'progress',
                    '[role="progressbar"]'
                ];
                
                let found = [];
                for (let sel of loadingSelectors) {
                    let els = document.querySelectorAll(sel);
                    for (let el of els) {
                        if (isElementVisible(el)) {
                            found.push(sel);
                            break;
                        }
                    }
                }
                
                return found.length > 0 ? found.join(', ') : null;
            """)
            
            if loader_info:
                return True, f"Visible loaders: {loader_info}"
            
            # All checks passed - page is ready
            return False, "All checks passed"
            
        except Exception as e:
            # On error, assume not loading
            return False, f"Check error (assuming ready): {str(e)}"
    
    def _wait_for_element_ready(self, element_details: Dict[str, Any], 
                                screenshot_path: str, timeout: int = 15) -> bool:
        """
        Wait for specific element to be ready for interaction using VLM
        Returns True if element is ready, False if timeout
        """
        coords = element_details.get('coordinates', {})
        if not coords:
            return True  # Can't check without coordinates
        
        print("[EXECUTOR] Checking if element is ready for interaction...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout:
            # Capture current screenshot
            temp_screenshot = os.path.join(self.screenshots_dir, "temp_element_check.png")
            try:
                self.driver.save_screenshot(temp_screenshot)
                
                # Use VLM to check element state
                element_state = self.vlm.is_element_visible_and_ready(
                    temp_screenshot, element_details, coords
                )
                
                if element_state['ready']:
                    print(f"[EXECUTOR] ✓ Element is ready: {element_state['reason']}")
                    if os.path.exists(temp_screenshot):
                        os.remove(temp_screenshot)
                    return True
                
                print(f"[EXECUTOR] Element not ready: {element_state['reason']}")
                time.sleep(1)  # Wait before checking again
                
            except Exception as e:
                print(f"[EXECUTOR] Warning: Element check failed: {e}")
                break
        
        print(f"[EXECUTOR] Warning: Timeout waiting for element to be ready")
        return False
    
    def execute_activity(self, activity: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single activity and return result
        Returns: {success, method, screenshot, error, timestamp}
        """
        self.step_counter += 1
        action = activity.get('action', '')
        details = activity.get('details', {})
        original_screenshot = activity.get('screenshot', {}).get('path', '')
        
        # Extract VLM description and element HTML from activity (if available)
        vlm_description = activity.get('vlm_description', '')
        element_html = activity.get('element_html', '')
        
        # Add VLM data to details for element finder
        enhanced_details = details.copy()
        if vlm_description:
            enhanced_details['vlm_description'] = vlm_description
            print(f"[EXECUTOR] Using VLM description for element detection")
        if element_html:
            enhanced_details['element_html'] = element_html
        
        print(f"\n{'='*80}")
        print(f"[EXECUTOR] Step {self.step_counter}: {action}")
        if vlm_description:
            preview = vlm_description[:100] + "..." if len(vlm_description) > 100 else vlm_description
            print(f"[EXECUTOR] VLM Description: {preview}")
        print(f"{'='*80}")
        
        result = {
            'step': self.step_counter,
            'action': action,
            'success': False,
            'method': '',
            'screenshot_before': '',
            'screenshot_after': '',
            'error': '',
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'used_vlm_description': bool(vlm_description)
        }
        
        try:
            # Capture screenshot before action
            print(f"[EXECUTOR] Capturing 'before' screenshot for step {self.step_counter}...")
            result['screenshot_before'] = self._capture_screenshot('before')
            print(f"[EXECUTOR] Before screenshot path: {result['screenshot_before']}")
            
            # Ensure correct tab/window context before executing (if metadata present)
            self._ensure_window_context(activity)

            # Execute based on action type (pass enhanced_details with VLM data)
            if action == 'navigation':
                success, method, error = self._execute_navigation(enhanced_details)
            elif action == 'click':
                success, method, error = self._execute_click(enhanced_details, original_screenshot)
            elif action == 'text_input':
                success, method, error = self._execute_input(enhanced_details, original_screenshot)
            elif action == 'popup_handled':
                success, method, error = self._execute_popup(enhanced_details)
            elif action == 'modal_button_click':
                success, method, error = self._execute_modal_button_click(enhanced_details, original_screenshot)
            elif action == 'modal_detected':
                success, method, error = True, 'modal_noted', ''  # Just log modal detection
                print(f"[EXECUTOR] Modal detected: {details.get('text', '')[:100]}")
            elif action in ('switch_tab', 'tab_switch'):
                success, method, error = self._execute_switch_tab(enhanced_details)
            elif action == 'switch_window':
                success, method, error = self._execute_switch_window(enhanced_details)
            elif action == 'hover':
                # Pass original screenshot (may be empty) so hover fallback can capture context for VLM
                success, method, error = self._execute_hover(enhanced_details, original_screenshot)
            elif action == 'new_tab':
                # No direct action required – context should already reflect this
                success, method, error = True, 'new_tab_noted', ''
            elif action == 'tab_closed':
                success, method, error = True, 'tab_closed_noted', ''
            elif action == 'scroll_to_element':
                success, method, error = self._execute_scroll_to_element(enhanced_details, original_screenshot)
            elif action == 'verification':
                success, method, error = self._execute_verification(enhanced_details)
            else:
                success, method, error = False, 'unknown_action', f'Unknown action type: {action}'
            
            result['success'] = success
            result['method'] = method
            result['error'] = error
            
            # Wait a bit for page to settle
            time.sleep(0.5)
            
            # Capture screenshot after action
            print(f"[EXECUTOR] Capturing 'after' screenshot for step {self.step_counter}...")
            result['screenshot_after'] = self._capture_screenshot('after')
            print(f"[EXECUTOR] After screenshot path: {result['screenshot_after']}")
            
            # Execute assertions if any
            assertion_results = []
            if self.assertions:
                print(f"[EXECUTOR] Running {len(self.assertions)} assertions...")
                for assertion in self.assertions:
                    assertion_result = assertion.execute(self.driver)
                    assertion_results.append(assertion_result)
                    
                    if assertion_result.passed:
                        print(f"[EXECUTOR] ✓ Assertion passed: {assertion.description}")
                    else:
                        print(f"[EXECUTOR] ✗ Assertion failed: {assertion.description}")
                        if assertion.required:
                            success = False
                            error = f"Assertion failed: {assertion_result.message}"
                
                result['assertions'] = [a.to_dict() for a in assertion_results]
                
                # Clear assertions after execution
                self.assertions.clear()
            
            if success:
                print(f"[EXECUTOR] ✓ Step {self.step_counter} completed successfully using {method}")
            else:
                print(f"[EXECUTOR] ✗ Step {self.step_counter} failed: {error}")
        
        except Exception as e:
            result['error'] = str(e)
            print(f"[EXECUTOR] ✗ Step {self.step_counter} exception: {e}")
        
        return result
    
    def add_assertion(self, assertion: Assertion) -> 'ActivityExecutor':
        """
        Add an assertion to check after the next step
        
        Args:
            assertion: Assertion to check
        
        Returns:
            Self for method chaining
        """
        self.assertions.append(assertion)
        return self
    
    def analyze_failure(
        self,
        activity: Dict[str, Any],
        error_message: str,
        before_screenshot: Optional[str] = None,
        after_screenshot: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze test failure using intelligent VLM-based failure analyzer
        
        Args:
            activity: Failed activity
            error_message: Error message from execution
            before_screenshot: Path to screenshot before action
            after_screenshot: Path to screenshot after action
        
        Returns:
            Failure analysis result or None if VLM not available
        """
        if not self.vlm_enabled or not self.failure_analyzer or not hasattr(self.failure_analyzer, 'analyze_failure'):
            return None
        
        try:
            print("[EXECUTOR] Analyzing failure with VLM...")
            
            # Build step description from activity
            action = activity.get('action', 'unknown')
            details = activity.get('details', {})
            step_desc = f"{action}"
            if details.get('tagName'):
                step_desc += f" {details['tagName']}"
            if details.get('text'):
                step_desc += f" with text '{details['text'][:50]}'"
            
            # Load screenshots if provided
            before_bytes = None
            after_bytes = None
            if before_screenshot:
                try:
                    with open(before_screenshot, 'rb') as f:
                        before_bytes = f.read()
                except Exception:
                    pass
            if after_screenshot:
                try:
                    with open(after_screenshot, 'rb') as f:
                        after_bytes = f.read()
                except Exception:
                    pass
            
            # Analyze the failure
            analysis = self.failure_analyzer.analyze_failure(
                step_description=step_desc,
                error_message=error_message,
                before_screenshot=before_bytes,
                after_screenshot=after_bytes,
                page_url=self.driver.current_url
            )
            
            # Store for later reference
            self.last_failure_analysis = analysis
            
            # Print summary
            print(f"[EXECUTOR] Failure Analysis:")
            print(f"  Root Cause: {analysis.root_cause.value}")
            print(f"  Confidence: {analysis.confidence:.2f}")
            print(f"  Suggested Fixes ({len(analysis.suggested_fixes)}):")
            for i, fix in enumerate(analysis.suggested_fixes[:3], 1):  # Show top 3
                print(f"    {i}. {fix.description} (confidence: {fix.confidence:.2f})")
            
            return {
                'root_cause': analysis.root_cause.value,
                'diagnosis': analysis.diagnosis,
                'confidence': analysis.confidence,
                'fixes': [
                    {
                        'description': fix.description,
                        'code_change': fix.code_change,
                        'priority': fix.priority,
                        'confidence': fix.confidence
                    }
                    for fix in analysis.suggested_fixes
                ],
                'what_changed': analysis.what_changed
            }
        except Exception as e:
            print(f"[EXECUTOR] Failure analysis error: {e}")
            return None
    
    def _execute_navigation(self, details: Dict[str, Any]) -> tuple:
        """Execute navigation action"""
        try:
            url = details.get('url', '')
            if not url:
                return False, 'navigation', 'No URL provided'
            
            print(f"[EXECUTOR] Navigating to: {url}")
            self.driver.get(url)
            
            # Wait for page load
            time.sleep(2)
            
            return True, 'navigation', ''
        except Exception as e:
            return False, 'navigation', str(e)
    
    def _execute_popup(self, details: Dict[str, Any]) -> tuple:
        """Execute popup handling action"""
        try:
            popup_type = details.get('type', 'confirm')
            popup_text = details.get('text', '')
            popup_action = details.get('action', 'accept')
            input_value = details.get('input_value')
            
            print(f"[EXECUTOR] Waiting for {popup_type} popup...")
            
            # Wait for alert to appear (with timeout)
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            try:
                WebDriverWait(self.driver, 5).until(EC.alert_is_present())
            except Exception:
                return False, 'popup_timeout', 'Popup did not appear within timeout'
            
            # Get the alert
            alert = self.driver.switch_to.alert
            
            # Verify the text matches (if provided)
            if popup_text:
                alert_text = alert.text
                if popup_text not in alert_text and alert_text not in popup_text:
                    print(f"[EXECUTOR] Warning: Popup text mismatch")
                    print(f"[EXECUTOR] Expected: {popup_text[:100]}")
                    print(f"[EXECUTOR] Got: {alert_text[:100]}")
            
            # Handle based on recorded action
            if popup_action == 'accept':
                # For prompts, send input value first
                if popup_type == 'prompt' and input_value is not None:
                    alert.send_keys(input_value)
                alert.accept()
                print(f"[EXECUTOR] Accepted {popup_type} popup")
            elif popup_action == 'dismiss':
                alert.dismiss()
                print(f"[EXECUTOR] Dismissed {popup_type} popup")
            else:
                # Default to accept
                alert.accept()
                print(f"[EXECUTOR] Accepted {popup_type} popup (default)")
            
            return True, f'popup_{popup_action}', ''
            
        except Exception as e:
            error_str = str(e).lower()
            if "no such alert" in error_str or "no alert is present" in error_str:
                return False, 'no_popup', 'No popup found'
            return False, 'popup_error', str(e)
    
    def _execute_modal_button_click(self, details: Dict[str, Any], 
                                     original_screenshot: str) -> tuple:
        """Execute modal dialog button click"""
        try:
            modal_selector = details.get('modal_selector', '')
            button_text = details.get('button_text', '')
            button_id = details.get('button_id', '')
            button_class = details.get('button_class', '')
            button_xpath = details.get('xpath', '')
            coordinates = details.get('coordinates', {})
            matched_text = details.get('matched_text', '')
            
            print(f"[EXECUTOR] Looking for modal button: '{button_text or matched_text}'")
            
            # Wait for modal to appear
            time.sleep(1)
            
            # Strategy 1: Try XPath
            if button_xpath:
                try:
                    button = self.driver.find_element(By.XPATH, button_xpath)
                    if button.is_displayed():
                        print(f"[EXECUTOR] Found button by XPath")
                        button.click()
                        return True, 'modal_button_xpath', ''
                except Exception:
                    pass
            
            # Strategy 2: Try by ID
            if button_id:
                try:
                    button = self.driver.find_element(By.ID, button_id)
                    if button.is_displayed():
                        print(f"[EXECUTOR] Found button by ID: {button_id}")
                        button.click()
                        return True, 'modal_button_id', ''
                except Exception:
                    pass
            
            # Strategy 3: Try by text content
            if button_text or matched_text:
                search_text = button_text or matched_text
                try:
                    # Find all buttons
                    all_buttons = self.driver.find_elements(By.TAG_NAME, 'button')
                    all_buttons += self.driver.find_elements(By.CSS_SELECTOR, '[role="button"]')
                    
                    for btn in all_buttons:
                        try:
                            if btn.is_displayed():
                                btn_text = btn.text.strip()
                                btn_value = btn.get_attribute('value') or ''
                                btn_aria = btn.get_attribute('aria-label') or ''
                                
                                if (search_text.lower() in btn_text.lower() or
                                    search_text.lower() in btn_value.lower() or
                                    search_text.lower() in btn_aria.lower()):
                                    print(f"[EXECUTOR] Found button by text: '{btn_text or btn_value}'")
                                    btn.click()
                                    return True, 'modal_button_text', ''
                        except Exception:
                            continue
                except Exception:
                    pass
            
            # Strategy 4: Try by modal selector + button class
            if modal_selector and button_class:
                try:
                    modal = self.driver.find_element(By.CSS_SELECTOR, modal_selector)
                    buttons = modal.find_elements(By.CLASS_NAME, button_class.split()[0])
                    if buttons:
                        for btn in buttons:
                            if btn.is_displayed():
                                print(f"[EXECUTOR] Found button by class in modal")
                                btn.click()
                                return True, 'modal_button_class', ''
                except Exception:
                    pass
            
            # Strategy 5: Try by coordinates (fallback)
            if coordinates and coordinates.get('x') and coordinates.get('y'):
                try:
                    x = coordinates['x']
                    y = coordinates['y']
                    print(f"[EXECUTOR] Trying to click at coordinates: ({x}, {y})")
                    
                    # Reuse globally imported ActionChains (removed local reimport)
                    actions = ActionChains(self.driver)
                    actions.move_by_offset(x, y).click().perform()
                    
                    # Reset
                    actions = ActionChains(self.driver)
                    actions.move_by_offset(-x, -y).perform()
                    
                    return True, 'modal_button_coordinates', ''
                except Exception as e:
                    print(f"[EXECUTOR] Coordinate click failed: {e}")
            
            return False, 'modal_button_not_found', 'Could not find modal button with any method'
            
        except Exception as e:
            return False, 'modal_button_error', str(e)
    
    def _execute_click(self, details: Dict[str, Any], 
                       original_screenshot: str) -> tuple:
        """Execute click action with multi-strategy locator and VLM fallback"""
        try:
            # Wait for page to finish loading first
            self._wait_for_page_ready(timeout=15)
            
            # Check if element is in shadow DOM or iframe
            in_shadow_root = details.get('inShadowRoot', False)
            in_iframe = details.get('inIframe', False)
            
            element = None
            method = 'not_found'
            
            # Phase 0: Try DOM path traversal if available (most reliable for iframe/shadow DOM)
            locators_data = details.get('locators', {})
            dom_path = locators_data.get('dom_path')
            if dom_path and isinstance(dom_path, list) and len(dom_path) > 0:
                print("[EXECUTOR] Attempting DOM path traversal...")
                try:
                    element = self._traverse_dom_path(dom_path)
                    if element:
                        method = 'dom_path'
                        print(f"[EXECUTOR] ✓ Found element using DOM path traversal")
                except Exception as e:
                    print(f"[EXECUTOR] DOM path traversal failed: {e}")
                    element = None
            
            # Phase 1: Try multi-strategy ElementLocator if locators available
            if not element and self.use_enhanced_locators and 'locators' in details:
                print("[EXECUTOR] Attempting multi-strategy element location...")
                try:
                    locator = self._create_locator_from_details(details)
                    element, method_used, _unused_error = locator.find_element(self.driver, timeout=5.0)
                    
                    if element:
                        method = method_used
                        print(f"[EXECUTOR] ✓ Found element using: {method_used}")
                except Exception as e:
                    print(f"[EXECUTOR] Multi-strategy locator failed: {e}")
                    element = None
            
            # Fallback to legacy methods if enhanced locator failed
            if not element:
                if in_shadow_root:
                    # Find element in shadow DOM
                    element = self._find_element_in_shadow_dom(details)
                    method = 'shadow_dom' if element else 'not_found'
                elif in_iframe:
                    # Find element in iframe
                    element = self._find_element_in_iframe(details)
                    method = 'iframe' if element else 'not_found'
                else:
                    # Find element using standard visual detection
                    try:
                        element, method = self.finder.find_element(details, original_screenshot)
                    except Exception as e:
                        print(f"[EXECUTOR] Visual finder failed: {e}")
                        element = None
                        method = 'not_found'
            
            # Phase 2: VLM fallback if traditional methods failed
            # Capture screenshot if not provided (for VLM to use)
            screenshot_for_vlm = original_screenshot
            if not element and self.vlm_enabled and self.vlm_finder:
                if not screenshot_for_vlm:
                    print("[EXECUTOR] Capturing screenshot for VLM fallback...")
                    try:
                        screenshot_for_vlm = self._capture_screenshot('vlm_fallback')
                    except Exception as e:
                        print(f"[EXECUTOR] Failed to capture screenshot for VLM: {e}")
                
                if screenshot_for_vlm:
                    print("[EXECUTOR] Traditional methods failed - trying VLM element finder...")
                    try:
                        # Generate natural language description from details
                        desc_parts = []
                        if details.get('text'):
                            desc_parts.append(f"text '{details['text'][:50]}'")
                        if details.get('tagName'):
                            desc_parts.append(f"{details['tagName']} element")
                        if details.get('placeholder'):
                            desc_parts.append(f"placeholder '{details['placeholder']}'")
                        if details.get('ariaLabel'):
                            desc_parts.append(f"aria-label '{details['ariaLabel']}'")
                        if details.get('id'):
                            desc_parts.append(f"id '{details['id']}'")
                        if details.get('name'):
                            desc_parts.append(f"name '{details['name']}'")
                        description = " with ".join(desc_parts) if desc_parts else "clickable element"
                        
                        print(f"[EXECUTOR] VLM looking for: {description}")

                        # Prefer direct click helper if provided by concrete implementation
                        if hasattr(self.vlm_finder, 'click_element_by_description'):
                            success, message = self.vlm_finder.click_element_by_description(  # type: ignore
                                self.driver,
                                description,
                                screenshot_path=screenshot_for_vlm
                            )
                            if success:
                                method = 'vlm_finder'
                                print(f"[EXECUTOR] ✓ VLM clicked element: {message}")
                                return True, method, ''
                            else:
                                print(f"[EXECUTOR] VLM click failed: {message}")
                        elif hasattr(self.vlm_finder, 'find_element_by_description'):
                            # Generic coordinate-based fallback
                            vlm_result = self.vlm_finder.find_element_by_description(  # type: ignore
                                self.driver,
                                description,
                                screenshot_path=screenshot_for_vlm
                            )
                            if getattr(vlm_result, 'found', False) and getattr(vlm_result, 'coordinates', None):
                                x, y = vlm_result.coordinates  # type: ignore
                                print(f"[EXECUTOR] ✓ VLM located element at ({x},{y}) - performing coordinate click")
                                actions = ActionChains(self.driver)
                                actions.move_by_offset(x, y).click().perform()
                                # Reset pointer to avoid offset accumulation
                                actions = ActionChains(self.driver)
                                actions.move_by_offset(-x, -y).perform()
                                method = 'vlm_coordinates'
                                return True, method, ''
                            else:
                                print("[EXECUTOR] VLM did not locate element coordinates")
                    except Exception as vlm_error:
                        print(f"[EXECUTOR] VLM fallback failed: {vlm_error}")
                        from logging_config import log_exception
                        log_exception(logger, f"VLM fallback error in click: {vlm_error}")

            
            if not element:
                # Try to switch back from iframe if we were in one
                self._switch_back_from_iframe()
                return False, 'not_found', 'Element not found with any method'
            
            # Note: Element readiness is now checked by VLM during visual detection
            # No need for separate _wait_for_element_ready() call
            
            # Handle coordinate-based clicking
            if isinstance(element, dict) and 'click_at_coords' in element:
                coords = element['click_at_coords']
                print(f"[EXECUTOR] Clicking at coordinates: {coords}")
                
                actions = ActionChains(self.driver)
                actions.move_by_offset(coords[0], coords[1]).click().perform()
                
                # Reset mouse position
                actions = ActionChains(self.driver)
                actions.move_by_offset(-coords[0], -coords[1]).perform()
                
                return True, method, ''
            
            # Normal element click
            if hasattr(element, 'tag_name') and not isinstance(element, dict):
                try:
                    print(f"[EXECUTOR] Clicking element: {element.tag_name}")
                except Exception:
                    print("[EXECUTOR] Clicking element (tag unavailable)")
            else:
                print(f"[EXECUTOR] Clicking element")
            
            # Scroll element into view and wait
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            time.sleep(0.5)
            
            # Additional Selenium wait for clickability (backup check)
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable(element)  # type: ignore
                )
            except Exception:
                print("[EXECUTOR] Warning: Selenium wait timeout, but VLM approved - trying anyway...")
            
            # Highlight element briefly
            self._highlight_element(element)
            
            # Try normal click first
            try:
                element.click()  # type: ignore
            except Exception as e:
                print(f"[EXECUTOR] Normal click failed ({e}), trying JavaScript click")
                # Fallback to JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
            
            # For search elements or shadow DOM elements, try clicking at coordinates
            tag_name = details.get('tagName', '').upper()
            coordinates = details.get('coordinates', {})
            
            if 'SEARCH' in tag_name or 'C4D-' in tag_name:
                print(f"[EXECUTOR] Custom web component detected, trying coordinate-based click...")
                
                # Try clicking at the recorded coordinates
                click_x = coordinates.get('clickX')
                click_y = coordinates.get('clickY')
                
                if click_x is not None and click_y is not None:
                    try:
                        print(f"[EXECUTOR] Clicking at coordinates: ({click_x}, {click_y})")
                        
                        # Use ActionChains to click at specific coordinates
                        actions = ActionChains(self.driver)
                        
                        # Move to the coordinates and click
                        # Need to move from current position (0,0) to target
                        actions.move_by_offset(int(click_x), int(click_y)).click().perform()
                        
                        # Reset mouse position
                        actions = ActionChains(self.driver)
                        actions.move_by_offset(-int(click_x), -int(click_y)).perform()
                        
                        print(f"[EXECUTOR] ✓ Clicked at coordinates successfully")
                        time.sleep(1.5)  # Give extra time for UI to respond
                        
                    except Exception as coord_e:
                        print(f"[EXECUTOR] Coordinate click failed: {coord_e}")
                        time.sleep(1.5)
                else:
                    print(f"[EXECUTOR] No coordinates available for click")
                    time.sleep(1.5)
            
            # Switch back from iframe if we were in one
            self._switch_back_from_iframe()
            
            return True, method, ''
        
        except Exception as e:
            # Make sure to switch back from iframe on error
            self._switch_back_from_iframe()
            return False, 'click_error', str(e)
    
    def _execute_input(self, details: Dict[str, Any], 
                       original_screenshot: str) -> tuple:
        """Execute text input action with multi-strategy locator and VLM fallback"""
        try:
            # Wait for page to finish loading first
            self._wait_for_page_ready(timeout=15)
            
            # Check if element is in shadow DOM or iframe
            in_shadow_root = details.get('inShadowRoot', False)
            in_iframe = details.get('inIframe', False)
            
            element = None
            method = 'not_found'
            
            # Phase 0: Try DOM path traversal if available (most reliable for iframe/shadow DOM)
            locators_data = details.get('locators', {})
            dom_path = locators_data.get('dom_path')
            if dom_path and isinstance(dom_path, list) and len(dom_path) > 0:
                print("[EXECUTOR] Attempting DOM path traversal...")
                try:
                    element = self._traverse_dom_path(dom_path)
                    if element:
                        method = 'dom_path'
                        print(f"[EXECUTOR] ✓ Found input element using DOM path traversal")
                except Exception as e:
                    print(f"[EXECUTOR] DOM path traversal failed: {e}")
                    element = None
            
            # Phase 1: Try multi-strategy ElementLocator if locators available
            if not element and self.use_enhanced_locators and 'locators' in details:
                print("[EXECUTOR] Attempting multi-strategy element location...")
                locator = self._create_locator_from_details(details)
                element, method_used, _unused_error = locator.find_element(self.driver, timeout=5.0)
                
                if element:
                    method = method_used
                    print(f"[EXECUTOR] ✓ Found input element using: {method_used}")
            
            # Fallback to legacy methods if enhanced locator failed
            if not element:
                if in_shadow_root:
                    # Find element in shadow DOM
                    element = self._find_element_in_shadow_dom(details)
                    method = 'shadow_dom' if element else 'not_found'
                elif in_iframe:
                    # Find element in iframe
                    element = self._find_element_in_iframe(details)
                    method = 'iframe' if element else 'not_found'
                else:
                    # Find element using standard visual detection
                    element, method = self.finder.find_element(details, original_screenshot)
            
            # Phase 2: VLM fallback if traditional methods failed
            if not element and self.vlm_enabled and self.vlm_finder and original_screenshot:
                print("[EXECUTOR] Traditional methods failed - trying VLM element finder...")
                try:
                    # Generate natural language description for input field
                    desc_parts = []
                    if details.get('placeholder'):
                        desc_parts.append(f"input with placeholder '{details['placeholder']}'")
                    elif details.get('label'):
                        desc_parts.append(f"input field labeled '{details['label']}'")
                    elif details.get('name'):
                        desc_parts.append(f"input with name '{details['name']}'")
                    elif details.get('type'):
                        desc_parts.append(f"{details['type']} input field")
                    else:
                        desc_parts.append("input field")
                    
                    description = " ".join(desc_parts)
                    
                    # Use VLM to find the element
                    vlm_result = self.vlm_finder.find_element_by_description(
                        self.driver,
                        description,
                        screenshot_path=original_screenshot
                    )
                    
                    if vlm_result.found and vlm_result.coordinates:
                        # Click at coordinates found by VLM
                        x, y = vlm_result.coordinates
                        self.driver.execute_script(f"""
                            var element = document.elementFromPoint({x}, {y});
                            if (element) {{
                                element.focus();
                                element.click();
                            }}
                        """)
                        method = 'vlm_finder'
                        print(f"[EXECUTOR] ✓ VLM found input field at ({x}, {y}): {description}")
                        
                        # Create a dummy element dict to proceed with typing
                        element = {'found_by_vlm': True, 'coordinates': (x, y)}
                except Exception as vlm_error:
                    print(f"[EXECUTOR] VLM fallback failed: {vlm_error}")
            
            if not element:
                # Try to switch back from iframe if we were in one
                self._switch_back_from_iframe()
                return False, 'not_found', 'Element not found with any method'
            
            # Note: Element readiness is now checked by VLM during visual detection
            # No need for separate _wait_for_element_ready() call
            
            # Handle coordinate-based clicking for input fields
            if isinstance(element, dict) and 'click_at_coords' in element:
                coords = element['click_at_coords']
                print(f"[EXECUTOR] Clicking input field at coordinates: {coords}")
                
                actions = ActionChains(self.driver)
                actions.move_by_offset(coords[0], coords[1]).click().perform()
                actions.move_by_offset(-coords[0], -coords[1]).perform()
                
                # Wait for focus
                time.sleep(0.3)
                
                # Type text
                text = details.get('value', '')
                actions = ActionChains(self.driver)
                actions.send_keys(text).perform()
                
                return True, method, ''
            
            # Normal input
            text = details.get('value', '')
            if hasattr(element, 'tag_name') and not isinstance(element, dict):
                try:
                    print(f"[EXECUTOR] Typing into {element.tag_name}: '{text}'")
                except Exception:
                    print(f"[EXECUTOR] Typing text: '{text}' (tag unavailable)")
            else:
                print(f"[EXECUTOR] Typing text: '{text}'")
            
            # Scroll into view and wait
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
            time.sleep(0.7)  # Increased wait for smooth scroll
            
            # Additional Selenium wait for clickability (backup check)
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            try:
                WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable(element)  # type: ignore
                )
            except Exception:
                print("[EXECUTOR] Warning: Selenium wait timeout, but VLM approved - trying anyway...")
            
            # Highlight element for input action
            self._highlight_element(element, action_type="input")
            
            # Click to focus
            try:
                element.click()  # type: ignore
            except Exception:
                self.driver.execute_script("arguments[0].click();", element)
            
            time.sleep(0.3)
            
            # Clear existing text
            try:
                element.clear()  # type: ignore
            except Exception:
                # If clear fails, try selecting all and deleting
                try:
                    element.send_keys(Keys.CONTROL + "a")  # type: ignore
                    element.send_keys(Keys.DELETE)  # type: ignore
                except Exception:
                    pass  # If all fails, just type
            
            # Type text
            element.send_keys(text)  # type: ignore
            
            # Switch back from iframe if we were in one
            self._switch_back_from_iframe()
            
            return True, method, ''
        
        except Exception as e:
            # Make sure to switch back from iframe on error
            self._switch_back_from_iframe()
            return False, 'input_error', str(e)
    
    def _highlight_element(self, element, action_type="click"):
        """Temporarily highlight element with prominent border and background"""
        try:
            original_style = element.get_attribute('style') or ''
            
            # Different colors for different actions
            if action_type == "input" or action_type == "text_input":
                highlight_style = "border: 5px solid #00FF00 !important; background-color: rgba(144, 238, 144, 0.3) !important; box-shadow: 0 0 20px rgba(0, 255, 0, 0.8) !important;"
            else:  # click
                highlight_style = "border: 5px solid #FF0000 !important; background-color: rgba(255, 255, 0, 0.3) !important; box-shadow: 0 0 20px rgba(255, 0, 0, 0.8) !important;"
            
            # Apply highlight
            self.driver.execute_script(
                "arguments[0].setAttribute('style', arguments[1]);",
                element,
                original_style + highlight_style
            )
            
            # Keep highlight visible longer
            time.sleep(1.0)
            
            # Restore original style
            self.driver.execute_script(
                "arguments[0].setAttribute('style', arguments[1]);",
                element,
                original_style
            )
        except Exception:
            pass
    
    def _execute_switch_tab(self, details: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Switch to a browser tab by title or URL pattern (regex supported)"""
        try:
            pattern = details.get('pattern', '')
            match_type = details.get('match_type', 'title')  # 'title' or 'url'
            use_regex = details.get('use_regex', True)
            
            if not pattern:
                return False, 'switch_tab_error', 'No pattern provided for tab switching'
            
            print(f"[EXECUTOR] Switching tab by {match_type}: {pattern} (regex: {use_regex})")
            
            # Get current window handle
            current_handle = self.driver.current_window_handle
            all_handles = self.driver.window_handles
            
            if len(all_handles) <= 1:
                return False, 'switch_tab_error', 'Only one tab/window open, cannot switch'
            
            # Try to find matching tab
            import re
            for handle in all_handles:
                if handle == current_handle:
                    continue
                    
                self.driver.switch_to.window(handle)
                
                # Get title or URL to match
                match_value = self.driver.title if match_type == 'title' else self.driver.current_url
                
                # Check if it matches
                if use_regex:
                    if re.search(pattern, match_value, re.IGNORECASE):
                        print(f"[EXECUTOR] Switched to tab: {self.driver.title}")
                        return True, 'switch_tab_success', ''
                else:
                    if pattern.lower() in match_value.lower():
                        print(f"[EXECUTOR] Switched to tab: {self.driver.title}")
                        return True, 'switch_tab_success', ''
            
            # No match found, switch back to original
            self.driver.switch_to.window(current_handle)
            return False, 'switch_tab_error', f'No tab found matching {match_type} pattern: {pattern}'
            
        except Exception as e:
            return False, 'switch_tab_error', str(e)
    
    def _execute_switch_window(self, details: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Switch to a browser window by title pattern"""
        try:
            pattern = details.get('pattern', '')
            use_regex = details.get('use_regex', True)
            
            if not pattern:
                return False, 'switch_window_error', 'No pattern provided for window switching'
            
            print(f"[EXECUTOR] Switching window by title: {pattern} (regex: {use_regex})")
            
            # Get current window handle
            current_handle = self.driver.current_window_handle
            all_handles = self.driver.window_handles
            
            if len(all_handles) <= 1:
                return False, 'switch_window_error', 'Only one window open, cannot switch'
            
            # Try to find matching window
            import re
            for handle in all_handles:
                if handle == current_handle:
                    continue
                    
                self.driver.switch_to.window(handle)
                
                # Check if title matches
                if use_regex:
                    if re.search(pattern, self.driver.title, re.IGNORECASE):
                        print(f"[EXECUTOR] Switched to window: {self.driver.title}")
                        return True, 'switch_window_success', ''
                else:
                    if pattern.lower() in self.driver.title.lower():
                        print(f"[EXECUTOR] Switched to window: {self.driver.title}")
                        return True, 'switch_window_success', ''
            
            # No match found, switch back to original
            self.driver.switch_to.window(current_handle)
            return False, 'switch_window_error', f'No window found matching title pattern: {pattern}'
            
        except Exception as e:
            return False, 'switch_window_error', str(e)
    
    def _execute_scroll_to_element(self, details: Dict[str, Any], screenshot: Optional[str] = None) -> Tuple[bool, str, str]:
        """Scroll to make an element visible on the page"""
        try:
            locators = details.get('locators', {})
            visual_description = details.get('visual_description', '')
            
            if not locators and not visual_description:
                return False, 'scroll_error', 'No locators or visual description provided'
            
            print(f"[EXECUTOR] Scrolling to element with locators: {locators}")
            
            # Find the element
            element = None
            method = 'unknown'
            
            # Try to find element using locators
            if locators:
                try:
                    result = self.element_locator.find_element(self.driver, locators)
                    if isinstance(result, dict) and result.get('success'):
                        element = result.get('element')
                        method = result.get('method', 'unknown')
                except Exception:
                    pass
            
            # Fallback to VLM if available and no element found
            if not element and self.vlm_finder and visual_description and screenshot:
                print(f"[EXECUTOR] Trying VLM to find element: {visual_description}")
                vlm_result = self.vlm_finder.find_element_by_description(
                    self.driver,
                    visual_description,
                    screenshot_path=screenshot
                )
                # stub result object has attributes, not dict
                if getattr(vlm_result, 'found', False) and getattr(vlm_result, 'coordinates', None):
                    # We'll treat coordinates click later, no locator resolution
                    element = {'click_at_coords': vlm_result.coordinates}
                    method = 'vlm_coordinates'
            
            if not element:
                return False, 'scroll_error', 'Could not find element to scroll to'
            
            # Scroll element into view
            self.driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", element)
            time.sleep(0.5)  # Wait for smooth scroll
            
            print(f"[EXECUTOR] Scrolled to element using {method}")
            return True, f'scroll_success_{method}', ''
            
        except Exception as e:
            return False, 'scroll_error', str(e)

    def _execute_verification(self, details: Dict[str, Any]) -> Tuple[bool, str, str]:
        """Verify presence of element or text based on criteria/locators.

        Strategies:
        1. Direct DOM text exact/contains search
        2. Locator-based lookup (text, placeholder)
        3. VLM fallback (if enabled) using screenshot + description
        """
        criteria = details.get('criteria') or details.get('value') or details.get('description') or ''
        if not criteria:
            return False, 'verification_skipped', 'No verification criteria provided'
        print(f"[EXECUTOR] Verifying presence of: {criteria}")

        # Strategy 1: DOM text search
        try:
            script = """
            const needle = arguments[0].trim().toLowerCase();
            const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null);
            while (walker.nextNode()) {
                const t = walker.currentNode.nodeValue.trim().toLowerCase();
                if (t && t === needle) { return {found:true, method:'text_node'}; }
            }
            const allElems = document.querySelectorAll('*');
            for (const el of allElems) {
                const txt = (el.innerText || '').trim().toLowerCase();
                if (txt && txt.includes(needle)) { return {found:true, method:'contains_text'}; }
            }
            return {found:false};
            """
            dom_result = self.driver.execute_script(script, criteria)
            if dom_result and dom_result.get('found'):
                return True, f"verification_{dom_result.get('method','text')}", ''
        except Exception as e:
            print(f"[EXECUTOR] DOM verification failed: {e}")

        # Strategy 2: Locator-based
        locators = details.get('locators') or {}
        try:
            if locators.get('text'):
                elems = self.driver.find_elements(By.XPATH, f"//*[contains(normalize-space(text()), '{locators['text']}')]")
                if elems:
                    return True, 'verification_locator_text', ''
            if locators.get('placeholder'):
                elems = self.driver.find_elements(By.CSS_SELECTOR, f"[placeholder='{locators['placeholder']}']")
                if elems:
                    return True, 'verification_locator_placeholder', ''
        except Exception as e:
            print(f"[EXECUTOR] Locator verification failed: {e}")

        # Strategy 3: VLM fallback
        if getattr(self, 'vlm_enabled', False) and getattr(self, 'vlm_finder', None):
            try:
                screenshot_path = self._capture_screenshot('verification')
                vlm_result = self.vlm_finder.find_element_by_description(
                    self.driver,
                    criteria,
                    screenshot_path=screenshot_path
                )
                if getattr(vlm_result, 'found', False):
                    # Conditional follow-up actions
                    self._execute_conditional_followups(True, details)
                    return True, 'verification_vlm', ''
            except Exception as e:
                print(f"[EXECUTOR] VLM verification failed: {e}")

        # Failure path conditional follow-ups
        self._execute_conditional_followups(False, details)
        return False, 'verification_failed', f"Criteria not found: {criteria[:80]}"

    def _execute_conditional_followups(self, passed: bool, details: Dict[str, Any]):
        """Execute on_pass or on_fail sub-activities embedded in a verification step."""
        key = 'on_pass' if passed else 'on_fail'
        followups = details.get(key)
        if not followups:
            return
        if not isinstance(followups, list):
            print(f"[EXECUTOR] Conditional follow-ups must be a list, got {type(followups)}")
            return
        print(f"[EXECUTOR] Executing {len(followups)} conditional follow-up action(s) for {key}")
        for idx, sub_activity in enumerate(followups, 1):
            if not isinstance(sub_activity, dict):
                print(f"[EXECUTOR] Skipping invalid sub-activity #{idx}: not a dict")
                continue
            try:
                sub_result = self.execute_activity(sub_activity)
                status = '✓' if sub_result.get('success') else '✗'
                print(f"[EXECUTOR] {status} Conditional sub-activity #{idx}: {sub_activity.get('action')} method={sub_result.get('method')}")
            except Exception as e:
                print(f"[EXECUTOR] ✗ Error executing sub-activity #{idx}: {e}")

    def _execute_hover(self, details: Dict[str, Any], original_screenshot: Optional[str] = None) -> Tuple[bool, str, str]:
        """Hover over an element.

        Resolution order:
        0. DOM path traversal (if available - most reliable for iframe/shadow DOM)
        1. Multi-strategy locators (if provided)
        2. Recorded coordinates (elementCenterX/Y)
        3. VLM fallback (description -> coordinates)
        4. Failure
        """
        try:
            locators = details.get('locators', {})
            element = None
            method = 'unknown'

            # 0. Try DOM path traversal if available
            dom_path = locators.get('dom_path')
            if dom_path and isinstance(dom_path, list) and len(dom_path) > 0:
                print("[EXECUTOR] Attempting DOM path traversal for hover...")
                try:
                    element = self._traverse_dom_path(dom_path)
                    if element:
                        method = 'dom_path'
                        print(f"[EXECUTOR] ✓ Found hover element using DOM path traversal")
                except Exception as e:
                    print(f"[EXECUTOR] DOM path traversal failed: {e}")
                    element = None

            # 1. Try locator-based resolution (ElementLocator style interface)
            if not element and locators:
                try:
                    result = self.element_locator.find_element(self.driver, locators)
                    if isinstance(result, dict) and result.get('success'):
                        element = result.get('element')
                        method = result.get('method', 'locators')
                except Exception:
                    pass

            # 2. Coordinate fallback from recorded metadata
            if not element and isinstance(details.get('coordinates'), dict):
                coords = details['coordinates']
                x = int(coords.get('elementCenterX', 0))
                y = int(coords.get('elementCenterY', 0))
                if x or y:  # Only attempt if non-zero
                    try:
                        actions = ActionChains(self.driver)
                        actions.move_by_offset(x, y).perform()
                        # Small pause to allow hover-driven menus to appear
                        time.sleep(0.3)
                        actions.move_by_offset(-x, -y).perform()
                        return True, 'hover_coordinates', ''
                    except Exception as coord_err:
                        print(f"[EXECUTOR] Coordinate hover failed: {coord_err}")

            # 3. VLM fallback if enabled
            if not element and self.vlm_enabled and self.vlm_finder:
                # Build description
                tag_part = f"{details.get('tagName')} element" if details.get('tagName') else None
                description = details.get('vlm_description') or details.get('text') or tag_part or 'target element'
                # Ensure we have a screenshot for the model
                context_shot = original_screenshot
                if not context_shot:
                    context_shot = self._capture_screenshot('hover_context')
                try:
                    if hasattr(self.vlm_finder, 'find_element_by_description'):
                        vlm_result = self.vlm_finder.find_element_by_description(  # type: ignore
                            self.driver,
                            description,
                            screenshot_path=context_shot
                        )
                        if getattr(vlm_result, 'found', False) and getattr(vlm_result, 'coordinates', None):
                            x, y = vlm_result.coordinates  # type: ignore
                            print(f"[EXECUTOR] ✓ VLM provided hover coordinates ({x},{y}) for '{description[:60]}'")
                            # Dispatch synthetic hover via JS to avoid offset drift
                            try:
                                js = """
                                    const x = arguments[0];
                                    const y = arguments[1];
                                    const el = document.elementFromPoint(x, y);
                                    if (el) {
                                        const evOpts = {bubbles:true,cancelable:true,clientX:x,clientY:y};
                                        el.dispatchEvent(new MouseEvent('mousemove', evOpts));
                                        el.dispatchEvent(new MouseEvent('mouseover', evOpts));
                                        el.dispatchEvent(new MouseEvent('mouseenter', evOpts));
                                        return true;
                                    }
                                    return false;
                                """
                                dispatched = self.driver.execute_script(js, x, y)
                                if dispatched:
                                    time.sleep(0.3)
                                    return True, 'hover_vlm_coordinates', ''
                            except Exception as js_err:
                                print(f"[EXECUTOR] JS hover dispatch failed: {js_err}")
                            # Fallback: move pointer physically
                            try:
                                actions = ActionChains(self.driver)
                                actions.move_by_offset(x, y).perform()
                                time.sleep(0.3)
                                actions.move_by_offset(-x, -y).perform()
                                return True, 'hover_vlm_coordinates', ''
                            except Exception as act_err:
                                print(f"[EXECUTOR] ActionChains hover failed after VLM coords: {act_err}")
                except Exception as vlm_err:
                    print(f"[EXECUTOR] VLM hover fallback error: {vlm_err}")

            if not element:
                return False, 'hover_not_found', 'No element/coordinates/VLM result for hover'

            # 4. Element-based hover
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            except Exception:
                pass
            try:
                ActionChains(self.driver).move_to_element(element).perform()
                time.sleep(0.3)
                return True, f'hover_{method}', ''
            except Exception as move_err:
                return False, 'hover_error', f'Move to element failed: {move_err}'
        except Exception as e:
            return False, 'hover_error', str(e)
    
    def _capture_screenshot(self, suffix: str) -> str:
        """Capture screenshot and return path"""
        try:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"step_{self.step_counter}_{suffix}_{timestamp}.png"
            
            # Use ABSOLUTE path to ensure files are saved in the correct location
            abs_screenshots_dir = os.path.abspath(self.screenshots_dir)
            filepath = os.path.join(abs_screenshots_dir, filename)
            
            print(f"[EXECUTOR] Attempting to save screenshot: {filepath}")
            print(f"[EXECUTOR] Current working directory: {os.getcwd()}")
            
            # Ensure directory exists
            os.makedirs(abs_screenshots_dir, exist_ok=True)
            print(f"[EXECUTOR] Directory exists: {os.path.exists(abs_screenshots_dir)}")
            
            # Capture screenshot and check return value
            result = self.driver.save_screenshot(filepath)
            print(f"[EXECUTOR] driver.save_screenshot() returned: {result}")
            
            # Small delay to ensure file is written
            time.sleep(0.2)
            
            # Force filesystem sync
            try:
                import subprocess
                subprocess.run(['sync'], check=False, timeout=1)
            except:
                pass
            
            # Verify file was created
            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                print(f"[EXECUTOR] ✓ Screenshot saved: {filename} ({file_size} bytes)")
                
                # Double-check after another small delay
                time.sleep(0.1)
                if os.path.exists(filepath):
                    print(f"[EXECUTOR] ✓ File still exists after 0.3s delay")
                else:
                    print(f"[EXECUTOR] ✗ WARNING: File disappeared after 0.3s!")
                
                # Return relative path for HTML compatibility
                return os.path.relpath(filepath)
            else:
                print(f"[EXECUTOR] ✗ Screenshot file not created: {filename}")
                print(f"[EXECUTOR] ✗ Checked path: {filepath}")
                # List directory contents
                if os.path.exists(abs_screenshots_dir):
                    files = os.listdir(abs_screenshots_dir)
                    print(f"[EXECUTOR] Directory contents ({len(files)} files): {files[:5]}")
                return ''
            
        except Exception as e:
            print(f"[EXECUTOR] ✗ Screenshot capture error: {e}")
            import traceback
            traceback.print_exc()
            return ''
