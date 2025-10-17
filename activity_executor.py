"""
Activity Executor - Executes browser actions from recorded activities
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from typing import Dict, Any, Optional, List, Tuple
from element_finder import VisualElementFinder
from llm_helpers import OllamaVLM
from element_locator import ElementLocator, create_locator_from_activity, LocatorStrategy
from assertions import Assertion, AssertionResult, AssertionBuilder
from PIL import Image
import time
import os
import traceback

# Phase 2: VLM imports (optional - graceful degradation if Ollama not available)
try:
    from vlm_element_finder import VLMElementFinder
    from intelligent_failure_analyzer import IntelligentFailureAnalyzer
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
                except:
                    pass
            
            # Try by name
            if elem_name:
                try:
                    element = self.driver.find_element(By.NAME, elem_name)
                    if element:
                        print(f"[EXECUTOR] ✓ Found {tag_name} in iframe by name")
                        return element
                except:
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
            except:
                pass
            
            print(f"[EXECUTOR] ✗ Element not found in iframe")
            return None
            
        except Exception as e:
            print(f"[EXECUTOR] iframe search error: {e}")
            # Try to switch back to default content
            try:
                self.driver.switch_to.default_content()
                self.current_iframe = None
            except:
                pass
            return None
    
    def _switch_back_from_iframe(self):
        """Switch back to main content from iframe"""
        try:
            if self.current_iframe is not None:
                self.driver.switch_to.default_content()
                self.current_iframe = None
        except:
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
            result['screenshot_before'] = self._capture_screenshot('before')
            
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
            else:
                success, method, error = False, 'unknown_action', f'Unknown action type: {action}'
            
            result['success'] = success
            result['method'] = method
            result['error'] = error
            
            # Wait a bit for page to settle
            time.sleep(0.5)
            
            # Capture screenshot after action
            result['screenshot_after'] = self._capture_screenshot('after')
            
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
        if not self.vlm_enabled or not self.failure_analyzer:
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
                except:
                    pass
            if after_screenshot:
                try:
                    with open(after_screenshot, 'rb') as f:
                        after_bytes = f.read()
                except:
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
            print(f"  Suggested Fixes ({len(analysis.fixes)}):")
            for i, fix in enumerate(analysis.fixes[:3], 1):  # Show top 3
                print(f"    {i}. {fix.description} (confidence: {fix.confidence:.2f})")
            
            return {
                'root_cause': analysis.root_cause.value,
                'description': analysis.description,
                'confidence': analysis.confidence,
                'fixes': [
                    {
                        'description': fix.description,
                        'code_change': fix.code_change,
                        'priority': fix.priority.value,
                        'confidence': fix.confidence
                    }
                    for fix in analysis.fixes
                ],
                'visual_analysis': analysis.visual_analysis
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
            except:
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
                except:
                    pass
            
            # Strategy 2: Try by ID
            if button_id:
                try:
                    button = self.driver.find_element(By.ID, button_id)
                    if button.is_displayed():
                        print(f"[EXECUTOR] Found button by ID: {button_id}")
                        button.click()
                        return True, 'modal_button_id', ''
                except:
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
                        except:
                            continue
                except:
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
                except:
                    pass
            
            # Strategy 5: Try by coordinates (fallback)
            if coordinates and coordinates.get('x') and coordinates.get('y'):
                try:
                    x = coordinates['x']
                    y = coordinates['y']
                    print(f"[EXECUTOR] Trying to click at coordinates: ({x}, {y})")
                    
                    from selenium.webdriver.common.action_chains import ActionChains
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
            
            # Phase 1: Try multi-strategy ElementLocator if locators available
            if self.use_enhanced_locators and 'locators' in details:
                print("[EXECUTOR] Attempting multi-strategy element location...")
                locator = self._create_locator_from_details(details)
                element, method_used, error_msg = locator.find_element(self.driver, timeout=5.0)
                
                if element:
                    method = method_used
                    print(f"[EXECUTOR] ✓ Found element using: {method_used}")
            
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
                    
                    description = " with ".join(desc_parts) if desc_parts else "clickable element"
                    
                    # Try VLM-based element finding
                    success, message = self.vlm_finder.click_element_by_description(
                        self.driver,
                        description,
                        screenshot_path=original_screenshot
                    )
                    
                    if success:
                        method = 'vlm_finder'
                        print(f"[EXECUTOR] ✓ VLM clicked element: {message}")
                        # VLM already clicked, so return success
                        return True, method, ''
                    else:
                        print(f"[EXECUTOR] VLM click failed: {message}")
                except Exception as vlm_error:
                    print(f"[EXECUTOR] VLM fallback failed: {vlm_error}")
            
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
            if hasattr(element, 'tag_name'):
                print(f"[EXECUTOR] Clicking element: {element.tag_name}")
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
            except:
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
            
            # Phase 1: Try multi-strategy ElementLocator if locators available
            if self.use_enhanced_locators and 'locators' in details:
                print("[EXECUTOR] Attempting multi-strategy element location...")
                locator = self._create_locator_from_details(details)
                element, method_used, error_msg = locator.find_element(self.driver, timeout=5.0)
                
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
            if hasattr(element, 'tag_name'):
                print(f"[EXECUTOR] Typing into {element.tag_name}: '{text}'")
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
            except:
                print("[EXECUTOR] Warning: Selenium wait timeout, but VLM approved - trying anyway...")
            
            # Highlight element for input action
            self._highlight_element(element, action_type="input")
            
            # Click to focus
            try:
                element.click()  # type: ignore
            except:
                self.driver.execute_script("arguments[0].click();", element)
            
            time.sleep(0.3)
            
            # Clear existing text
            try:
                element.clear()  # type: ignore
            except:
                # If clear fails, try selecting all and deleting
                try:
                    element.send_keys(Keys.CONTROL + "a")  # type: ignore
                    element.send_keys(Keys.DELETE)  # type: ignore
                except:
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
        except:
            pass
    
    def _capture_screenshot(self, suffix: str) -> str:
        """Capture screenshot and return path"""
        try:
            timestamp = time.strftime('%Y%m%d_%H%M%S')
            filename = f"step_{self.step_counter}_{suffix}_{timestamp}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            self.driver.save_screenshot(filepath)
            print(f"[EXECUTOR] Screenshot saved: {filename}")
            
            return filepath
        except Exception as e:
            print(f"[EXECUTOR] Screenshot capture error: {e}")
            return ''
